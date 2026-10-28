"""Turn a diagnostic result into the files the client receives.

  findings.html   the one-page findings report (prints to PDF from a browser)
  findings.md     the same findings as plain text, for email or a doc
  issues-log.xlsx every flagged cell, so the client's team can fix them
"""
from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd

from .checks import Result

SEVERITY_LABEL = {"high": "Fix before reporting", "medium": "Fix soon", "low": "Worth a look"}


def _pct(x: float) -> str:
    return f"{x:.0%}" if x >= 0.01 or x == 0 else "<1%"


def _top_actions(r: Result, n: int = 3) -> list[str]:
    seen, out = set(), []
    for f in r.findings:
        if f.check in seen:
            continue
        seen.add(f.check)
        out.append(f.fix)
        if len(out) == n:
            break
    return out


def summary_numbers(r: Result) -> dict:
    # Blank optional answers and outliers are worth a look, but don't make a record wrong.
    real = r.flags[~r.flags["check"].isin(["missing", "outlier"])] if len(r.flags) else r.flags
    flagged_rows = real["row"].nunique() if len(real) else 0
    n = len(r.dataset.df)
    return {
        "records": n,
        "questions": len(r.dataset.question_columns),
        "flagged_rows": flagged_rows,
        "clean_share": 1 - flagged_rows / n if n else 1.0,
        "high": sum(f.severity == "high" for f in r.findings),
        "medium": sum(f.severity == "medium" for f in r.findings),
        "low": sum(f.severity == "low" for f in r.findings),
    }


def write_markdown(r: Result, path: Path) -> None:
    s = summary_numbers(r)
    title = r.config.project or Path(r.dataset.path).stem
    lines = [
        f"# Data Diagnostic: {title}",
        "",
        f"{r.config.client + ' · ' if r.config.client else ''}{date.today():%d %B %Y} · "
        f"source: {r.dataset.source.replace('_', ' ')} export",
        "",
        f"**Data health score: {r.score}/100 ({r.verdict}).** "
        f"{s['records']} records and {s['questions']} questions checked; "
        f"{_pct(s['clean_share'])} of records have no problems found.",
        "",
        "## What to do first",
        "",
        *[f"{i}. {a}" for i, a in enumerate(_top_actions(r), 1)],
        "",
        "## Findings",
        "",
        "| Priority | Finding | Records | What it breaks |",
        "|---|---|---|---|",
    ]
    for f in r.findings:
        lines.append(f"| {SEVERITY_LABEL[f.severity]} | {f.title} | {f.rows_affected} "
                     f"({_pct(f.share)}) | {f.why} |")
    if len(r.coverage):
        lines += ["", "## Can the indicators be counted?", "",
                  "| Indicator | Group | Usable records | Coverage |", "|---|---|---|---|"]
        for _, row in r.coverage.iterrows():
            lines.append(f"| {row.indicator} | {row.group} | {row.usable} of {row.records} "
                         f"| {_pct(row.coverage)} |")
    lines += ["", "Every flagged cell is listed in the issues log (issues-log.xlsx).", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_excel(r: Result, path: Path) -> None:
    findings = pd.DataFrame([{
        "priority": SEVERITY_LABEL[f.severity], "finding": f.title,
        "columns": ", ".join(f.columns), "records": f.rows_affected,
        "share": f.share, "what it breaks": f.why, "what to do": f.fix,
        "examples": " | ".join(f.examples)} for f in r.findings])
    s = summary_numbers(r)
    summary = pd.DataFrame([
        ("Project", r.config.project or Path(r.dataset.path).stem),
        ("File", Path(r.dataset.path).name),
        ("Source", r.dataset.source),
        ("Records", s["records"]),
        ("Questions", s["questions"]),
        ("Data health score", f"{r.score}/100"),
        ("Verdict", r.verdict),
        ("Records with no problems found", _pct(s["clean_share"])),
        ("Findings: fix before reporting", s["high"]),
        ("Findings: fix soon", s["medium"]),
        ("Findings: worth a look", s["low"]),
    ], columns=["item", "value"])
    sheets = {"Summary": summary, "Findings": findings,
              "Issues log": r.flags.rename(columns={"row": "spreadsheet row"}),
              "Indicator coverage": r.coverage, "Columns": r.profile}
    if len(r.enumerators):
        sheets["Data collectors"] = r.enumerators
    with pd.ExcelWriter(path, engine="xlsxwriter") as xl:
        book = xl.book
        head = book.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#092052",
                                "text_wrap": True, "valign": "top"})
        wrap = book.add_format({"text_wrap": True, "valign": "top"})
        pct = book.add_format({"num_format": "0%", "valign": "top"})
        for name, frame in sheets.items():
            frame.to_excel(xl, sheet_name=name, index=False)
            ws = xl.sheets[name]
            for i, col in enumerate(frame.columns):
                ws.write(0, i, col, head)
                width = min(60, max(10, int(frame[col].astype(str).str.len().quantile(0.9)
                                            if len(frame) else 10), len(str(col)) + 2))
                fmt = pct if col in {"share", "coverage", "filled", "blank_share"} else wrap
                ws.set_column(i, i, width, fmt)
            ws.freeze_panes(1, 0)
            if len(frame):
                ws.autofilter(0, 0, len(frame), len(frame.columns) - 1)


CSS = """
:root{--ink:#092052;--body:#5A6B85;--dim:#63738D;--rule:#D8E1EF;--ground:#F6F8FC;
--panel:#FFFFFF;--active:#0F58E5;--neg:#8C1D1D;--pos:#0F7B3D;--faint:#CBD5E1}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
font:15px/1.55 'Readex Pro',Vazirmatn,system-ui,-apple-system,sans-serif}
main{max-width:880px;margin:0 auto;padding:40px 24px 64px}
h1{font:300 34px/1.15 Fraunces,Georgia,serif;margin:0 0 6px}
h2{font:400 21px/1.3 Fraunces,Georgia,serif;margin:36px 0 12px}
.meta{color:var(--dim);font-size:13px}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0 8px}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:14px 16px}
.tile b{display:block;font:500 28px/1.1 'IBM Plex Mono',ui-monospace,monospace}
.tile span{color:var(--body);font-size:13px}
.verdict{background:var(--ink);color:#F6F8FC;border-radius:8px;padding:18px 20px;margin-top:20px}
.verdict b{font:300 22px/1.3 Fraunces,Georgia,serif}
ol li{margin:6px 0}
.f{background:var(--panel);border:1px solid var(--rule);border-left:4px solid var(--faint);
border-radius:6px;padding:14px 16px;margin:10px 0;break-inside:avoid}
.f.high{border-left-color:var(--neg)}.f.medium{border-left-color:var(--active)}
.f h3{font-size:15px;margin:0 0 4px}
.tag{font:500 11px/1 'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:.04em;
color:var(--dim);margin-bottom:6px;display:block}
.f.high .tag{color:var(--neg)}.f.medium .tag{color:var(--active)}
.f p{margin:4px 0;color:var(--body)}
.f p strong{color:var(--ink);font-weight:500}
.ex{font-size:13px;color:var(--dim)}
.ex code{background:var(--ground);border:1px solid var(--rule);border-radius:4px;padding:0 4px;
unicode-bidi:plaintext}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;background:var(--panel);font-size:14px}
th,td{text-align:start;padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
td.num{font-family:'IBM Plex Mono',monospace;text-align:end;white-space:nowrap}
.bar{height:6px;background:var(--rule);border-radius:3px;min-width:80px}
.bar i{display:block;height:6px;border-radius:3px;background:var(--active)}
.bar.low i{background:var(--neg)}
footer{margin-top:40px;color:var(--dim);font-size:12px;border-top:1px solid var(--rule);padding-top:12px}
@media (max-width:640px){.tiles{grid-template-columns:repeat(2,1fr)}h1{font-size:28px}}
@media print{body{background:#fff}main{padding:0}.f,.tile{border-color:#ccc}}
"""


def _e(x) -> str:
    return html.escape(str(x))


def write_html(r: Result, path: Path) -> None:
    s = summary_numbers(r)
    title = r.config.project or Path(r.dataset.path).stem
    by = f"{_e(r.config.client)} · " if r.config.client else ""
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Diagnostic: {_e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400&family=IBM+Plex+Mono:wght@400;500&family=Readex+Pro:wght@300;400;500&family=Vazirmatn:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<p class="meta mono">DATA DIAGNOSTIC · DESCRIBE</p>
<h1>{_e(title)}</h1>
<p class="meta">{by}{date.today():%d %B %Y} · {_e(Path(r.dataset.path).name)}
 ({_e(r.dataset.source.replace('_', ' '))} export)</p>
<div class="tiles">
 <div class="tile"><b>{r.score}</b><span>Data health score / 100</span></div>
 <div class="tile"><b>{s['records']:,}</b><span>Records checked</span></div>
 <div class="tile"><b>{_pct(s['clean_share'])}</b><span>Records with no problems found</span></div>
 <div class="tile"><b>{s['high']}</b><span>Findings to fix before reporting</span></div>
</div>
<div class="verdict"><b>{_e(r.verdict)}.</b><br>
{s['questions']} questions checked for blanks, duplicates, mixed spellings, numbers stored as
text, impossible values, dates and interview length.</div>
<h2>What to do first</h2><ol>"""]
    parts += [f"<li>{_e(a)}</li>" for a in _top_actions(r)]
    parts.append("</ol><h2>Findings</h2>")
    if not r.findings:
        parts.append("<p>No issues found by the standard checks.</p>")
    for f in r.findings:
        ex = ""
        if f.examples:
            ex = '<p class="ex">Examples: ' + " ".join(f"<code>{_e(x)}</code>"
                                                        for x in f.examples) + "</p>"
        affected = (f"<p><strong>{f.rows_affected:,} records ({_pct(f.share)})</strong></p>"
                    if f.rows_affected else "")
        parts.append(f"""<div class="f {f.severity}"><span class="tag">{SEVERITY_LABEL[f.severity]}</span>
<h3>{_e(f.title)}</h3>{affected}<p>{_e(f.why)}</p><p><strong>Fix:</strong> {_e(f.fix)}</p>{ex}</div>""")
    if len(r.coverage):
        parts.append("<h2>Can the indicators be counted?</h2><div class='scroll'><table><thead><tr><th>Indicator"
                     "</th><th>Group</th><th>Usable</th><th>Coverage</th><th></th></tr></thead><tbody>")
        for _, row in r.coverage.iterrows():
            cls = " low" if row.coverage < 0.9 else ""
            parts.append(f"<tr><td>{_e(row.indicator)}</td><td>{_e(row.group)}</td>"
                         f"<td class='num'>{row.usable:,} / {row.records:,}</td>"
                         f"<td class='num'>{_pct(row.coverage)}</td><td><div class='bar{cls}'>"
                         f"<i style='width:{row.coverage * 100:.0f}%'></i></div></td></tr>")
        parts.append("</tbody></table></div>")
    if len(r.enumerators):
        parts.append("<h2>By data collector</h2><div class='scroll'><table><thead><tr><th>Data collector</th>"
                     "<th>Records</th><th>Blank answers</th><th>Issues per record</th>"
                     + ("<th>Median minutes</th>" if "median_minutes" in r.enumerators else "")
                     + "</tr></thead><tbody>")
        for _, row in r.enumerators.head(15).iterrows():
            mins = (f"<td class='num'>{row.median_minutes:.0f}</td>"
                    if "median_minutes" in r.enumerators else "")
            parts.append(f"<tr><td>{_e(row.enumerator)}</td><td class='num'>{row.records}</td>"
                         f"<td class='num'>{_pct(row.blank_share)}</td>"
                         f"<td class='num'>{row.issues_per_record:.1f}</td>{mins}</tr>")
        parts.append("</tbody></table></div>")
    parts.append(f"""<footer>Every flagged cell is listed in the issues log
(issues-log.xlsx) with its spreadsheet row, so the team can fix the file directly.
The score starts at 100. Each finding takes off up to 10 points (fix before reporting),
4 (fix soon) or 1 (worth a look), in proportion to the records it touches, full weight from 10%. Prepared by Describe · describe.team</footer>
</main></body></html>""")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_all(r: Result, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"html": out / "findings.html", "markdown": out / "findings.md",
             "excel": out / "issues-log.xlsx"}
    write_html(r, paths["html"])
    write_markdown(r, paths["markdown"])
    write_excel(r, paths["excel"])
    return paths
