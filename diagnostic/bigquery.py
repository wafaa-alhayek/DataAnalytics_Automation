"""Optional BigQuery mode, for the Google Cloud trial and the free sandbox after it.

Uses the `bq` command line tool (built into Google Cloud Shell, which is free),
so there is nothing extra to install or pay for.

  upload    clean the export and load it into a BigQuery table (all text columns)
  sql       write the same checks as BigQuery SQL, to save as views or scheduled queries
  download  read a BigQuery table back so the Python checks run on it unchanged
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from .checks import NAME_PATTERNS
from .load import Dataset


def bq_name(column: str) -> str:
    """BigQuery column names: letters, digits and underscores, not starting with a digit."""
    s = re.sub(r"[^0-9A-Za-z_]+", "_", column).rstrip("_") or "col"
    if s[0].isdigit():
        s = "c_" + s
    return s[:300]


def bq_columns(ds: Dataset) -> dict[str, str]:
    out, used = {}, set()
    for i, col in enumerate(ds.df.columns):
        name = bq_name(col)
        if name == "col" or name in used:           # Arabic-only headers, repeats
            name = f"{name}_{i + 1}"
        used.add(name)
        out[col] = name
    return out


def _bq(*args: str, stdin: str | None = None) -> str:
    try:
        done = subprocess.run(["bq", *args], input=stdin, capture_output=True, text=True,
                              check=False)
    except FileNotFoundError:
        raise SystemExit("The `bq` tool is not installed. Run this in Google Cloud Shell, or "
                         "install the Google Cloud CLI.") from None
    if done.returncode != 0:
        raise SystemExit(f"bq {' '.join(args[:2])} failed:\n{done.stderr or done.stdout}")
    return done.stdout


def upload(ds: Dataset, table: str, replace: bool = True) -> dict[str, str]:
    """Load the export into `project.dataset.table`. Every column is loaded as text,
    so nothing is silently dropped or converted on the way in."""
    names = bq_columns(ds)
    frame = ds.df.rename(columns=names).astype("string")
    schema = [{"name": n, "type": "STRING", "mode": "NULLABLE",
               "description": ds.original_names.get(c, c)[:1024]} for c, n in names.items()]
    with tempfile.TemporaryDirectory() as tmp:
        csv_path, schema_path = Path(tmp, "data.csv"), Path(tmp, "schema.json")
        frame.to_csv(csv_path, index=False)
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        args = ["load", "--source_format=CSV", "--skip_leading_rows=1",
                "--allow_quoted_newlines", "--encoding=UTF-8"]
        if replace:
            args.append("--replace")
        _bq(*args, _bq_ref(table), str(csv_path), str(schema_path))
    return names


def download(table: str, limit: int = 1_000_000) -> pd.DataFrame:
    out = _bq("query", "--use_legacy_sql=false", "--format=csv", f"--max_rows={limit}",
              f"SELECT * FROM `{table}`")
    return pd.read_csv(io.StringIO(out), dtype=str, keep_default_na=False)


def _bq_ref(table: str) -> str:
    """`project.dataset.table` -> `project:dataset.table`, the form `bq load` expects."""
    parts = table.split(".")
    return f"{parts[0]}:{'.'.join(parts[1:])}" if len(parts) == 3 else table


def check_sql(ds: Dataset, table: str) -> str:
    """The core checks as one BigQuery script. Every query returns the same shape
    (check_name, column_name, records, detail), so they can feed one Looker Studio table."""
    plain = bq_columns(ds)
    names = {c: f"`{n}`" for c, n in plain.items()}   # quoted: `end` is a keyword
    questions = list(ds.question_columns)
    t = f"`{table}`"
    blocks = [f"-- Data Diagnostic checks for {t}\n-- Generated from {Path(ds.path).name}. "
              "Columns are loaded as STRING by `python -m diagnostic bq-upload`.\n"]

    def blank(col: str) -> str:
        return (f"(NULLIF(LOWER(TRIM({col})), '') IS NULL OR LOWER(TRIM({col})) IN "
                "('na','n/a','nan','null','-','--','?','#n/a','missing','غير متوفر'))")

    missing = [f"SELECT 'missing' AS check_name, '{plain[c]}' AS column_name, "
               f"COUNTIF({blank(names[c])}) AS records, "
               f"FORMAT('%.1f%% blank', 100 * COUNTIF({blank(names[c])}) / COUNT(*)) AS detail "
               f"FROM {t}" for c in questions]
    blocks.append("-- 1. Blank answers per question\n" + "\nUNION ALL\n".join(missing) + ";\n")

    q_cols = ", ".join(f"LOWER(TRIM(IFNULL({names[c]}, '')))" for c in questions)
    blocks.append(f"""-- 2. Exact duplicate submissions (system columns ignored)
SELECT 'duplicate_row' AS check_name, '' AS column_name, SUM(n - 1) AS records,
       FORMAT('%d groups of copies', COUNT(*)) AS detail
FROM (SELECT TO_JSON_STRING([{q_cols}]) AS k, COUNT(*) AS n FROM {t} GROUP BY k HAVING n > 1);
""")

    id_pat = re.compile(NAME_PATTERNS["id"], re.I)
    ids = [c for c in questions if id_pat.search(c)]
    for c in ids:
        n = names[c]
        blocks.append(f"""-- 3. IDs used more than once: {c}
SELECT 'duplicate_id' AS check_name, '{plain[c]}' AS column_name, SUM(n) AS records,
       STRING_AGG(k, ', ' LIMIT 10) AS detail
FROM (SELECT LOWER(TRIM({n})) AS k, COUNT(*) AS n FROM {t}
      WHERE NOT {blank(n)} GROUP BY k HAVING n > 1);
""")

    spell = []
    for c in questions:
        n = names[c]
        spell.append(f"""SELECT 'inconsistent_code' AS check_name, '{plain[c]}' AS column_name,
       SUM(variants) AS records, STRING_AGG(spellings, ' | ' LIMIT 5) AS detail
FROM (SELECT REGEXP_REPLACE(LOWER(TRIM({n})), r'[\\s\\-_.]+', '') AS k,
             COUNT(DISTINCT {n}) AS variants,
             STRING_AGG(DISTINCT {n}, ' / ' LIMIT 4) AS spellings
      FROM {t} WHERE NOT {blank(n)} GROUP BY k HAVING variants > 1)
HAVING COUNT(*) > 0""")
    blocks.append("-- 4. One answer written several ways ('Female ' vs 'female')\n"
                  + "\nUNION ALL\n".join(spell) + ";\n")

    digits = [f"SELECT 'arabic_digits' AS check_name, '{plain[c]}' AS column_name, "
              f"COUNTIF(REGEXP_CONTAINS({names[c]}, r'[٠-٩۰-۹]')) AS records, "
              f"'Arabic-Indic digits; Sheets reads these as text' AS detail FROM {t} "
              f"HAVING records > 0" for c in questions]
    blocks.append("-- 5. Numbers typed with Arabic-Indic digits\n"
                  + "\nUNION ALL\n".join(digits) + ";\n")

    if {"start", "end"} <= set(ds.df.columns):
        blocks.append(f"""-- 6. Interview length (Kobo start/end)
SELECT 'too_fast' AS check_name, 'end' AS column_name,
       COUNTIF(m BETWEEN 0 AND 5) AS records, FORMAT('median %.0f min', APPROX_QUANTILES(m, 2)[OFFSET(1)]) AS detail
FROM (SELECT TIMESTAMP_DIFF(SAFE_CAST({names['end']} AS TIMESTAMP),
                            SAFE_CAST({names['start']} AS TIMESTAMP), SECOND) / 60 AS m FROM {t});
""")
    return "\n".join(blocks)
