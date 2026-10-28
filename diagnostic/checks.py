"""The data-quality checks behind the Data Diagnostic.

Each check reads the dataset and returns findings (what is wrong, how bad it
is, what to do) and flags (the exact rows and cells, for the issues log).
The same checks run on every client file, so every diagnostic is comparable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .config import Config
from .load import Dataset
from .text import has_eastern_digits, is_missing, normalize_label, to_number, to_western_digits

# Same answer in two languages or two spellings. Applied after normalize_label.
SYNONYMS = {
    "f": "female", "female": "female", "انثي": "female", "انثى": "female",
    "woman": "female", "girl": "female", "امراه": "female",
    "m": "male", "male": "male", "ذكر": "male", "man": "male", "boy": "male",
    "رجل": "male",
    "y": "yes", "yes": "yes", "نعم": "yes", "true": "yes", "1": "yes",
    "n": "no", "no": "no", "لا": "no", "false": "no", "0": "no",
}

NAME_PATTERNS = {
    "id": r"(^|_)(beneficiary_?id|hh_?id|household_?id|national_?id|case_?id|"
          r"respondent_?id|id_?number|رقم_?الهويه|رقم_?الهوية|الهويه|الهوية)$",
    "phone": r"(phone|mobile|tel|جوال|هاتف)",
    "sex": r"(^|_)(sex|gender|الجنس|النوع)($|_)",
    "age": r"(^|_)(age|العمر|عمر)($|_)",
    "location": r"(governorate|region|district|location|area|camp|city|"
                r"المحافظه|المحافظة|المنطقه|المنطقة|المدينه|المدينة)",
    "disability": r"(disab|اعاقه|إعاقة|اعاقة)",
    "enumerator": r"(enumerator|interviewer|surveyor|data_collector|الباحث|جامع)",
    "hh_size": r"(hh_?size|household_?size|family_?size|members|عدد_?افراد|عدد_?الافراد)",
    "date": r"(date|تاريخ|dob|birth)",
    "free_text": r"(comment|note|remark|specify|other_|feedback|anything_else|ملاحظ|تعليق|"
                 r"اخرى|أخرى)",
    "collection_date": r"(interview|survey|visit|submission|collection)_?date|^today$|"
                       r"^_submission_time$|^timestamp$|الطابع الزمني",
}

AUTO_RANGES = {"age": (0, 110), "hh_size": (1, 40)}


@dataclass
class Finding:
    check: str
    title: str
    severity: str                  # high | medium | low
    columns: list[str]
    rows_affected: int
    share: float                   # of all rows
    why: str                       # what it breaks, in plain words
    fix: str
    examples: list[str] = field(default_factory=list)


@dataclass
class Result:
    dataset: Dataset
    config: Config
    findings: list[Finding]
    flags: pd.DataFrame
    profile: pd.DataFrame
    coverage: pd.DataFrame
    enumerators: pd.DataFrame
    score: int
    verdict: str


class _Ctx:
    """Shared state for one run: the data, the guesses and the flag list."""

    def __init__(self, ds: Dataset, cfg: Config, today: datetime):
        self.ds, self.cfg, self.today = ds, cfg, today
        self.df = ds.df
        self.n = len(ds.df)
        self.questions = [c for c in ds.question_columns if c not in cfg.ignore]
        self.missing = {c: is_missing(self.df[c]) for c in self.df.columns}
        self.numbers = {c: to_number(self.df[c]) for c in self.df.columns}
        self.flags: list[dict] = []
        self.skipped: dict[str, str] = {}        # column -> skip rule that explains blanks
        self.copies = pd.Series(False, index=self.df.index)
        self.findings: list[Finding] = []
        self.id_col = self._id_label_column()

    # -- column guesses -------------------------------------------------
    def match(self, kind: str, columns=None) -> list[str]:
        pat = re.compile(NAME_PATTERNS[kind], re.I)
        cols = self.df.columns if columns is None else columns
        def names(col):
            for n in (col, self.ds.original_names.get(col, col)):
                yield n
                yield re.sub(r"\s+", "_", n.strip())
        return [col for col in cols if any(pat.search(n) for n in names(col))]

    def is_numeric(self, col: str) -> bool:
        filled = (~self.missing[col]).sum()
        return filled > 0 and self.numbers[col].notna().sum() / filled >= 0.8

    def is_categorical(self, col: str) -> bool:
        vals = self.df[col][~self.missing[col]]
        if len(vals) < 5 or self.is_numeric(col):
            return False
        uniq = vals.astype(str).str.strip().nunique()
        return 2 <= uniq <= 60 and uniq / len(vals) <= 0.5

    def _id_label_column(self) -> str | None:
        for c in self.cfg.id_columns + ["_uuid", "_index", "_id"]:
            if c in self.df.columns:
                return c
        return None

    # -- recording ------------------------------------------------------
    def flag(self, idx, column, check, note):
        for i in ([idx] if not hasattr(idx, "__iter__") else idx):
            self.flags.append({
                "row": int(i) + 2,          # spreadsheet row; header is row 1
                "record": "" if self.id_col is None else str(self.df.at[i, self.id_col]),
                "column": self.ds.original_names.get(column, column),
                "value": "" if column not in self.df.columns else str(self.df.at[i, column]),
                "check": check,
                "note": note,
            })

    def add(self, check, title, severity, columns, rows, why, fix, examples=()):
        rows = int(rows)
        self.findings.append(Finding(
            check=check, title=title, severity=severity,
            columns=[self.ds.original_names.get(c, c) for c in columns],
            rows_affected=rows, share=rows / self.n if self.n else 0.0,
            why=why, fix=fix, examples=[str(e) for e in list(examples)[:5]]))


def _pct(x: float) -> str:
    return f"{x:.0%}" if x >= 0.01 or x == 0 else "<1%"


# ---------------------------------------------------------------------------
def check_structure(c: _Ctx):
    empty = [col for col in c.questions if c.missing[col].all()]
    if empty:
        c.add("structure", f"{len(empty)} column(s) are completely empty", "low", empty, 0,
              "Empty columns make the file harder to read and often mean a question "
              "was removed from the form, or never shown because of a broken skip rule.",
              "Confirm the question was meant to be skipped; otherwise fix the form logic "
              "and drop the column from the analysis file.", empty)
    constant = [col for col in c.questions if col not in empty
                and c.df[col][~c.missing[col]].astype(str).str.strip().nunique() == 1
                and (~c.missing[col]).sum() >= 10]
    if constant:
        c.add("structure", f"{len(constant)} column(s) hold the same answer in every row", "low",
              constant, 0,
              "A question everyone answers the same way tells you nothing, and can mean "
              "a default value was never changed by the data collector.",
              "Check whether the form pre-fills this answer.",
              [f"{col} = {c.df[col][~c.missing[col]].iloc[0]}" for col in constant])
    dup_headers = [col for col in c.df.columns if re.search(r"_\d+$", col)
                   and re.sub(r"_\d+$", "", col) in c.df.columns
                   and c.ds.original_names[col] == c.ds.original_names.get(re.sub(r"_\d+$", "", col))]
    if dup_headers:
        c.add("structure", "Some column headers appear twice", "medium", dup_headers, 0,
              "Two columns with the same name get mixed up in formulas, pivots and imports.",
              "Rename one of each pair so every header is unique.", dup_headers)


def _skip_logic(c: _Ctx, col: str) -> str | None:
    """Blank exactly when another question has a given answer: a skip rule, not a gap.
    Returns that question's name, or None."""
    miss = c.missing[col]
    for other in c.questions:
        if other == col or not c.is_categorical(other):
            continue
        keys = c.df[other].map(lambda v: _code_key(v) if not pd.isna(v) else "")
        if keys.nunique() > 10:
            continue
        for value in keys.unique():
            if value and ((keys == value) == miss).mean() >= 0.97:
                c.skipped[col] = f"{c.ds.original_names.get(other, other)} = {value}"
                return other
    return None


def check_missing(c: _Ctx):
    required = [col for col in c.cfg.required if col in c.df.columns]
    for col in required:
        miss = c.missing[col]
        if miss.any():
            c.flag(c.df.index[miss], col, "missing_required", "Required answer is blank")
            c.add("missing", f"Required field '{c.ds.original_names.get(col, col)}' is blank "
                  f"in {miss.sum()} rows", "high", [col], miss.sum(),
                  "These records cannot be counted in any indicator that needs this field.",
                  "Make the question required in the form, and follow up these records "
                  "with the field team.")
    for col in c.questions:
        if col in required:
            continue
        miss = c.missing[col]
        share = miss.mean() if c.n else 0
        if share < c.cfg.missing_warn or miss.all():
            continue
        if _skip_logic(c, col):
            continue
        c.flag(c.df.index[miss], col, "missing", "Blank answer")
        sev = "medium" if share >= c.cfg.missing_high else "low"
        if c.match("free_text", [col]) or not (c.is_numeric(col) or c.is_categorical(col)):
            sev = "low"                     # optional free-text comments
        c.add("missing", f"'{c.ds.original_names.get(col, col)}' is blank in {_pct(share)} of rows",
              sev, [col], miss.sum(),
              "Totals and percentages built on this question only describe the people "
              "who answered it. If the blanks come from skip logic this is expected.",
              "Confirm which blanks are skip logic and which are real gaps; record "
              "'not applicable' explicitly for skipped questions.")


def check_duplicates(c: _Ctx):
    qs = [col for col in c.questions if not c.missing[col].all()]
    if qs:
        norm = c.df[qs].astype(str).apply(lambda s: s.str.strip().str.casefold())
        dup = norm.duplicated(keep=False)
        extra = norm.duplicated(keep="first")
        c.copies = extra
        if extra.any():
            c.flag(c.df.index[dup], qs[0], "duplicate_row", "Same answers as another row")
            c.add("duplicates", f"{extra.sum()} submission(s) are exact copies of another row",
                  "high", [], extra.sum(),
                  "Copies inflate every count: beneficiaries reached, households surveyed "
                  "and each indicator built on them.",
                  "Keep one copy of each. If the device sent the same form twice, check the "
                  "app's sending settings.",
                  [f"row {i + 2}" for i in c.df.index[extra][:5]])

    ids = [col for col in c.cfg.id_columns if col in c.df.columns]
    if not c.cfg.id_columns:
        for col in c.match("id", c.questions):
            filled = c.df[col][~c.missing[col]].astype(str).str.strip()
            if len(filled) >= 5 and filled.nunique() / len(filled) >= 0.9:
                ids.append(col)
    for col in ids:
        filled = ~c.missing[col] & ~c.copies     # exact copies are reported above
        key = c.df[col].astype(str).map(normalize_label)
        dup = key[filled].duplicated(keep=False).reindex(key.index, fill_value=False)
        extra = key[filled].duplicated(keep="first").reindex(key.index, fill_value=False)
        if extra.any():
            c.flag(c.df.index[dup], col, "duplicate_id", "ID used by more than one row")
            c.add("duplicates", f"{extra.sum()} ID(s) in '{c.ds.original_names.get(col, col)}' "
                  "are used more than once", "high", [col], dup.sum(),
                  "The same person or household is counted twice, or two people share one "
                  "ID, so follow-ups and distributions cannot be matched to the right record.",
                  "Look at each pair: merge true repeats, and correct the ID where two "
                  "different people got the same one.",
                  c.df.loc[dup, col].astype(str).drop_duplicates().head(5))


def _code_key(value) -> str:
    k = normalize_label(value)
    return SYNONYMS.get(k, k)


def check_codes(c: _Ctx):
    allowed = {col: {_code_key(v) for v in vals} for col, vals in c.cfg.codes.items()
               if col in c.df.columns}
    for col, ok in allowed.items():
        vals = c.df[col][~c.missing[col]]
        bad = vals[~vals.map(_code_key).isin(ok)]
        if len(bad):
            c.flag(bad.index, col, "invalid_code", "Not one of the agreed answer options")
            c.add("codes", f"'{c.ds.original_names.get(col, col)}' has {len(bad)} answers outside "
                  "the agreed options", "high", [col], len(bad),
                  "Answers outside the list drop out of every breakdown by this question.",
                  "Map each one to an agreed option, and switch the question to a "
                  "drop-down list so it cannot happen again.",
                  bad.astype(str).value_counts().index[:5])

    for col in c.questions:
        if not c.is_categorical(col):
            continue
        vals = c.df[col][~c.missing[col]].astype(str)
        keys = vals.map(_code_key)
        groups = vals.groupby(keys).agg(lambda s: sorted(set(s)))
        messy = groups[groups.map(len) > 1]
        if messy.empty:
            continue
        rows = keys.isin(messy.index)
        # The most common spelling of each group is the one to keep.
        main = vals.groupby(keys).agg(lambda s: s.value_counts().index[0])
        off = rows & (vals != keys.map(main))
        c.flag(vals.index[off], col, "inconsistent_code",
               "Spelling differs from the most common form")
        examples = [" / ".join(f"'{v}'" for v in spellings[:4]) for spellings in messy]
        c.add("codes", f"'{c.ds.original_names.get(col, col)}' records the same answer in "
              f"{sum(map(len, messy))} different ways", "medium", [col], off.sum(),
              "A pivot table or chart treats each spelling as a separate category, so "
              "breakdowns by this question come out split and wrong.",
              "Pick one spelling per answer, recode the rest, and use a choice list in the form.",
              examples)


def check_numbers(c: _Ctx):
    for col in c.questions:
        filled = ~c.missing[col]
        if filled.sum() < 5:
            continue
        parsed = c.numbers[col]
        share = parsed[filled].notna().mean()
        if share < 0.8:
            continue
        bad = filled & parsed.isna()
        if bad.any():
            c.flag(c.df.index[bad], col, "text_in_number", "Not a number")
            c.add("numbers", f"'{c.ds.original_names.get(col, col)}' has text where a number "
                  "should be", "medium", [col], bad.sum(),
                  "Sums and averages skip these cells without warning, so totals come out low.",
                  "Replace each with the number it means, or leave it blank; set the form "
                  "question type to integer or decimal.",
                  c.df.loc[bad, col].astype(str).head(5))
        eastern = c.df[col].map(has_eastern_digits) & filled
        if eastern.any() and eastern.sum() < filled.sum():
            c.flag(c.df.index[eastern], col, "arabic_digits", "Written with Arabic-Indic digits")
            c.add("numbers", f"'{c.ds.original_names.get(col, col)}' mixes Arabic-Indic digits "
                  "(١٢٣) with 123", "medium", [col], eastern.sum(),
                  "Excel and Google Sheets read '٥' as text, not 5, so these rows drop out of "
                  "every total and average.",
                  "Convert to 0-9 digits (the diagnostic issues log lists every cell), and use "
                  "a number field in the form so the phone keyboard can't send text.",
                  c.df.loc[eastern, col].astype(str).head(5))


def check_ranges(c: _Ctx):
    ranges = {col: tuple(v) for col, v in c.cfg.ranges.items() if col in c.df.columns}
    for col in c.questions:          # "How satisfied are you? (1-5)"
        m = re.search(r"\(\s*(\d+)\s*[-–to]+\s*(\d+)\s*\)\s*$", c.ds.original_names.get(col, col))
        if m and col not in ranges and c.is_numeric(col):
            ranges[col] = (int(m.group(1)), int(m.group(2)))
    for kind, rng in AUTO_RANGES.items():
        for col in c.match(kind, c.questions):
            if col not in ranges and c.is_numeric(col):
                ranges[col] = rng
    for col, (lo, hi) in ranges.items():
        x = c.numbers[col]
        out = x.notna() & ((x < lo) | (x > hi))
        if out.any():
            c.flag(c.df.index[out], col, "out_of_range", f"Outside {lo}-{hi}")
            c.add("ranges", f"'{c.ds.original_names.get(col, col)}' has {out.sum()} values "
                  f"outside {lo}-{hi}", "high" if out.mean() >= 0.02 else "medium", [col],
                  out.sum(),
                  "Impossible values pull averages up or down and usually point to a typing "
                  "slip (an extra zero, a year typed as an age).",
                  "Correct from the paper form or call back; add min/max limits to the form.",
                  x[out].astype(str).head(5))

    # Robust outliers in any other numeric question: far from the median.
    for col in c.questions:
        if col in ranges or not c.is_numeric(col) or c.match("id", [col]) or c.match("phone", [col]):
            continue
        x = c.numbers[col].dropna()
        if len(x) < 30 or x.nunique() < 8:
            continue
        med = x.median()
        mad = (x - med).abs().median()
        if mad == 0:
            continue
        z = (c.numbers[col] - med).abs() / (1.4826 * mad)
        out = z > 6
        if out.any():
            c.flag(c.df.index[out], col, "outlier", "Far from the typical value")
            c.add("outliers", f"'{c.ds.original_names.get(col, col)}' has {out.sum()} unusually "
                  "large or small values", "low", [col], out.sum(),
                  "A few extreme values can move the average a lot. Some are real; some are typos.",
                  "Check these against the source. Report the median next to the average.",
                  c.numbers[col][out].head(5).map(lambda v: f"{v:g}"))


def _dayfirst(texts: pd.Series) -> bool:
    """Decide once per column whether 03/04/2026 means 3 April or March 4."""
    parts = texts.str.extract(r"^(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}").dropna().astype(int)
    if parts.empty:
        return False
    return bool((parts[0] > 12).any() or not (parts[1] > 12).any())


def _parse_dates(s: pd.Series) -> pd.Series:
    texts = s.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v))
                  else to_western_digits(str(v)).strip())
    dayfirst = _dayfirst(texts)

    def one(v, text):
        if isinstance(v, (datetime, pd.Timestamp)):
            return pd.Timestamp(v).tz_localize(None) if pd.Timestamp(v).tzinfo else pd.Timestamp(v)
        if not text:
            return pd.NaT
        try:
            ts = pd.to_datetime(text, dayfirst=dayfirst, utc=True)
        except (ValueError, OverflowError, TypeError):
            return pd.NaT
        return ts.tz_convert(None)
    return pd.Series([one(v, t) for v, t in zip(s, texts)], index=s.index, dtype="datetime64[ns]")


def check_dates(c: _Ctx):
    today = pd.Timestamp(c.today)
    start = pd.Timestamp(c.cfg.collection_start) if c.cfg.collection_start else None
    end = pd.Timestamp(c.cfg.collection_end) + pd.Timedelta(days=1) if c.cfg.collection_end else None
    cols = set(c.match("date")) | set(c.match("collection_date"))
    cols |= {col for col in c.df.columns
             if pd.api.types.is_datetime64_any_dtype(c.df[col])}
    for kobo in ("start", "end", "today"):
        if kobo in c.df.columns:
            cols.add(kobo)
    collection = set(c.match("collection_date")) | ({"start", "end", "today"} & set(c.df.columns))
    for col in sorted(cols):
        filled = ~c.missing[col]
        if filled.sum() == 0:
            continue
        d = _parse_dates(c.df[col])
        bad = filled & d.isna()
        if bad.any() and bad.sum() < filled.sum():
            c.flag(c.df.index[bad], col, "bad_date", "Not a readable date")
            c.add("dates", f"'{c.ds.original_names.get(col, col)}' has {bad.sum()} values that "
                  "are not readable dates", "medium", [col], bad.sum(),
                  "Unreadable dates fall out of any monthly or weekly count.",
                  "Re-enter as YYYY-MM-DD and use a date field in the form.",
                  c.df.loc[bad, col].astype(str).head(5))
        future = d.notna() & (d > today + pd.Timedelta(days=1))
        if future.any():
            c.flag(c.df.index[future], col, "future_date", "Date is in the future")
            c.add("dates", f"'{c.ds.original_names.get(col, col)}' has {future.sum()} dates in "
                  "the future", "high", [col], future.sum(),
                  "Future dates usually mean a wrong phone clock or a typing slip; they put "
                  "records in the wrong reporting period.",
                  "Correct from the source, and check the date settings on the collection phones.",
                  d[future].dt.strftime("%Y-%m-%d").head(5))
        if col in collection and (start is not None or end is not None):
            outside = d.notna() & ~future
            if start is not None:
                early = outside & (d < start)
            else:
                early = pd.Series(False, index=d.index)
            late = outside & (d >= end) if end is not None else pd.Series(False, index=d.index)
            win = early | late
            if win.any():
                c.flag(c.df.index[win], col, "outside_window", "Outside the data collection dates")
                c.add("dates", f"{win.sum()} records in '{c.ds.original_names.get(col, col)}' "
                      "fall outside the collection period", "medium", [col], win.sum(),
                      "Records from before or after fieldwork are often test submissions "
                      "or belong to another round.",
                      "Confirm with the field team, then remove test records from the analysis file.",
                      d[win].dt.strftime("%Y-%m-%d").head(5))


def interview_minutes(c: _Ctx) -> pd.Series | None:
    if not {"start", "end"} <= set(c.df.columns):
        return None
    s, e = _parse_dates(c.df["start"]), _parse_dates(c.df["end"])
    return (e - s).dt.total_seconds() / 60


def check_duration(c: _Ctx):
    mins = interview_minutes(c)
    if mins is None:
        return
    neg = mins < 0
    if neg.any():
        c.flag(c.df.index[neg], "end", "negative_duration", "Ended before it started")
        c.add("duration", f"{neg.sum()} interviews end before they start", "high",
              ["start", "end"], neg.sum(),
              "The phone clock was wrong or changed during the interview, so dates on "
              "these records can't be trusted.",
              "Check the clock settings on the devices used for these records.")
    fast = (mins >= 0) & (mins < c.cfg.min_interview_minutes)
    if fast.any():
        c.flag(c.df.index[fast], "end", "too_fast",
               f"Interview under {c.cfg.min_interview_minutes:g} minutes")
        c.add("duration", f"{fast.sum()} interviews took under "
              f"{c.cfg.min_interview_minutes:g} minutes", "high" if fast.mean() >= 0.05 else "medium",
              ["start", "end"], fast.sum(),
              "The questionnaire can't be read out that fast. These are often filled in "
              "without the respondent, and quietly bias the results.",
              "Review them by data collector and back-check a sample by phone.",
              mins[fast].round(1).astype(str).head(5) + " min")


def _rule_frame(c: _Ctx) -> pd.DataFrame:
    out = {}
    for col in c.df.columns:
        if c.is_numeric(col):
            out[col] = c.numbers[col]
        else:
            out[col] = c.df[col].map(lambda v: _code_key(v) if not pd.isna(v) else None)
    return pd.DataFrame(out, index=c.df.index)


def check_rules(c: _Ctx):
    if not c.cfg.rules:
        return
    frame = _rule_frame(c)
    for rule in c.cfg.rules:
        name, when = rule.get("name", rule.get("when")), rule["when"]
        try:
            hit = frame.eval(when, engine="python").fillna(False).astype(bool)
        except Exception as exc:                      # a typo in the client config
            c.add("rules", f"Rule could not run: {name}", "low", [], 0,
                  f"The rule `{when}` failed: {exc}.", "Fix the rule in the config file.")
            continue
        if hit.any():
            cols = [col for col in c.df.columns if re.search(rf"\b{re.escape(col)}\b", when)]
            c.flag(c.df.index[hit], cols[0] if cols else "", "rule", name)
            c.add("rules", f"{name}: {hit.sum()} records", rule.get("severity", "medium"),
                  cols, hit.sum(),
                  rule.get("why", "These answers contradict each other, so at least one of "
                               "them is wrong."),
                  rule.get("fix", "Check each record against the source and correct it."))


def _disaggregations(c: _Ctx) -> list[str]:
    if c.cfg.disaggregations:
        return [col for col in c.cfg.disaggregations if col in c.df.columns]
    found = []
    for kind in ("sex", "age", "location", "disability"):
        found += [col for col in c.match(kind, c.questions) if col not in found][:1]
    return found


def coverage(c: _Ctx) -> pd.DataFrame:
    """How many records can actually be counted in each indicator."""
    rows = []
    auto = not c.cfg.indicators
    indicators = c.cfg.indicators or [
        {"name": f"Breakdown by {c.ds.original_names.get(col, col)}", "columns": [col]}
        for col in _disaggregations(c)]
    for ind in indicators:
        cols = [col for col in ind.get("columns", []) if col in c.df.columns]
        if not cols:
            continue
        ok = pd.Series(True, index=c.df.index)
        for col in cols:
            ok &= ~c.missing[col]
            if col in c.cfg.ranges:
                lo, hi = c.cfg.ranges[col]
                ok &= c.numbers[col].between(lo, hi)
        rows.append({"indicator": ind["name"], "group": "All records", "records": c.n,
                     "usable": int(ok.sum()), "coverage": ok.mean() if c.n else 0.0})
        for by in ind.get("disaggregate_by", []):
            if by not in c.df.columns:
                continue
            labels = c.df[by].map(lambda v: "(blank)" if is_missing(pd.Series([v]))[0]
                                  else str(v).strip())
            main = labels.groupby(labels.map(_code_key)).agg(lambda s: s.value_counts().index[0])
            labels = labels.map(_code_key).map(main)
            for g, idx in labels.groupby(labels).groups.items():
                rows.append({"indicator": ind["name"],
                             "group": f"{c.ds.original_names.get(by, by)}: {g}",
                             "records": len(idx), "usable": int(ok[idx].sum()),
                             "coverage": ok[idx].mean()})
        share = ok.mean() if c.n else 1
        if share < 0.9 and auto:
            label = c.ds.original_names.get(cols[0], cols[0])
            c.findings = [f for f in c.findings if not (f.check == "missing" and f.columns == [label])]
            c.add("coverage", f"Only {_pct(share)} of records can be broken down by '{label}'",
                  "high" if share < 0.7 else "medium", cols, (~ok).sum(),
                  "Donor reports ask for results by sex, age and location. Records without "
                  "this answer can't go into those tables.",
                  "Make the question required in the form, and fill the gaps from registration "
                  "lists where you can.")
        elif share < 0.9:
            c.add("coverage", f"Only {_pct(share)} of records can be counted in "
                  f"'{ind['name']}'", "high" if share < 0.7 else "medium", cols, (~ok).sum(),
                  "The indicator you report is based on fewer people than you surveyed, "
                  "which donors will ask about.",
                  "Fill the gaps listed in the issues log, or report the indicator with its "
                  "real base (n=...).")
    return pd.DataFrame(rows, columns=["indicator", "group", "records", "usable", "coverage"])


def enumerator_table(c: _Ctx) -> pd.DataFrame:
    col = c.cfg.enumerator_column
    if not col:
        guess = c.match("enumerator") or (["username"] if "username" in c.df.columns else [])
        col = guess[0] if guess else None
    if not col or col not in c.df.columns:
        return pd.DataFrame()
    flagged = pd.Series(0, index=c.df.index)
    if c.flags:
        f = pd.DataFrame(c.flags)
        counts = f.groupby("row").size()
        flagged = pd.Series(c.df.index + 2, index=c.df.index).map(counts).fillna(0)
    blanks = pd.DataFrame({q: c.missing[q] for q in c.questions}).mean(axis=1)
    table = pd.DataFrame({"enumerator": c.df[col].astype(str).str.strip(),
                          "blank_share": blanks, "issues": flagged})
    mins = interview_minutes(c)
    if mins is not None:
        table["minutes"] = mins
    agg = {"records": ("blank_share", "size"), "blank_share": ("blank_share", "mean"),
           "issues_per_record": ("issues", "mean")}
    if "minutes" in table:
        agg["median_minutes"] = ("minutes", "median")
    out = table.groupby("enumerator").agg(**agg).reset_index()
    overall = blanks.mean()
    odd = (out.records >= 10) & (out.blank_share > max(1.5 * overall, overall + 0.08))
    if "median_minutes" in out:
        odd |= (out.records >= 10) & (out.median_minutes < c.cfg.min_interview_minutes)
    odd = out[odd]
    if len(odd):
        c.add("enumerators", f"{len(odd)} data collector(s) stand out: many more blanks or "
              "very short interviews", "medium", [col], int(odd.records.sum()),
              "When one person's records are much emptier or much faster, the cause is in "
              "how they collect, not in the population, and it skews results for their area.",
              "Share the per-collector table with the field supervisor and plan a refresher.",
              odd.enumerator.head(5))
    return out.sort_values("issues_per_record", ascending=False)


def profile(c: _Ctx) -> pd.DataFrame:
    rows = []
    for col in c.df.columns:
        filled = ~c.missing[col]
        kind = ("system" if col in c.ds.system_columns else
                "number" if c.is_numeric(col) else
                "choice" if c.is_categorical(col) else "text")
        vals = c.df[col][filled].astype(str).str.strip()
        rows.append({"column": c.ds.original_names.get(col, col), "type": kind,
                     "filled": filled.mean() if c.n else 0.0,
                     "unique": vals.nunique(),
                     "examples": ", ".join(vals.value_counts().index[:3]),
                     "note": f"blank when {c.skipped[col]} (skip rule)" if col in c.skipped else ""})
    return pd.DataFrame(rows)


SEVERITY_CAP = {"high": 10, "medium": 4, "low": 1}


def score(findings: list[Finding]) -> tuple[int, str]:
    """100 minus a penalty per finding. A finding costs its full weight once it
    touches 10% of records, and proportionally less below that, so a handful of
    bad rows in a big survey doesn't sink the score."""
    lost = 0.0
    for f in findings:
        reach = 1.0 if f.rows_affected == 0 and f.check == "structure" else min(1.0, f.share / 0.10)
        lost += SEVERITY_CAP[f.severity] * max(reach, 0.1)
    s = max(0, round(100 - lost))
    verdict = ("Ready to report" if s >= 85 else
               "Usable after targeted fixes" if s >= 65 else
               "Needs clean-up before reporting")
    return s, verdict


def run(ds: Dataset, cfg: Config | None = None, today: datetime | None = None) -> Result:
    cfg = cfg or Config()
    c = _Ctx(ds, cfg, today or datetime.now())
    for check in (check_structure, check_missing, check_duplicates, check_codes,
                  check_numbers, check_ranges, check_dates, check_duration, check_rules):
        check(c)
    cov = coverage(c)
    enum = enumerator_table(c)
    order = {"high": 0, "medium": 1, "low": 2}
    findings = sorted(c.findings, key=lambda f: (order[f.severity], -f.rows_affected))
    s, verdict = score(findings)
    flags = pd.DataFrame(c.flags, columns=["row", "record", "column", "value", "check", "note"])
    flags = flags.drop_duplicates().sort_values(["row", "column"]).reset_index(drop=True)
    return Result(dataset=ds, config=cfg, findings=findings, flags=flags,
                  profile=profile(c), coverage=cov, enumerators=enum,
                  score=s, verdict=verdict)
