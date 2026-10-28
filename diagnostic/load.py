"""Read a Kobo, Google Forms or Excel/CSV export into one clean table.

Every export lands in the same shape: a pandas DataFrame with readable column
names, plus a `Dataset` record that remembers where it came from, which
columns are system columns (ids, timestamps) and the original column names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Columns Kobo adds to every export. They are not survey questions.
KOBO_SYSTEM = {
    "_id", "_uuid", "_submission_time", "_validation_status", "_notes",
    "_status", "_submitted_by", "__version__", "_tags", "_index",
    "_parent_index", "_parent_table_name", "_version_", "meta/instanceid",
    "meta/rootuuid", "meta/deprecatedid", "formhub/uuid", "_attachments",
    "_geolocation", "_xform_id_string",
}
KOBO_META = {"start", "end", "today", "deviceid", "username", "simserial",
             "subscriberid", "phonenumber", "audit"}
FORMS_TIMESTAMP = {"timestamp", "الطابع الزمني", "horodateur", "marca temporal"}


@dataclass
class Dataset:
    df: pd.DataFrame
    source: str                       # "kobo", "google_forms" or "excel"
    path: str
    sheet: str | None = None
    original_names: dict[str, str] = field(default_factory=dict)
    system_columns: list[str] = field(default_factory=list)

    @property
    def question_columns(self) -> list[str]:
        return [c for c in self.df.columns if c not in self.system_columns]


def _short_names(columns: list[str]) -> dict[str, str]:
    """Kobo group paths like `hh_info/hh_size` become `hh_size` when unique."""
    cleaned = {}
    for c in columns:
        base = re.sub(r"\s+", " ", str(c)).strip()
        cleaned[c] = base or "unnamed"
    last = {c: n.split("/")[-1] for c, n in cleaned.items()}
    counts = pd.Series(list(last.values())).value_counts()
    out, used = {}, set()
    for c in columns:
        name = last[c] if counts[last[c]] == 1 else cleaned[c].replace("/", "__")
        candidate, i = name, 2
        while candidate in used:          # duplicated headers in Excel
            candidate, i = f"{name}_{i}", i + 1
        used.add(candidate)
        out[c] = candidate
    return out


def detect_source(columns: list[str]) -> str:
    lower = {str(c).strip().lower() for c in columns}
    if lower & {"_uuid", "_submission_time", "meta/instanceid", "_index"}:
        return "kobo"
    if columns and str(columns[0]).strip().lower() in FORMS_TIMESTAMP:
        return "google_forms"
    return "excel"


def _read(path: Path, sheet: str | int | None) -> tuple[pd.DataFrame, str | None]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        # Kobo CSVs use ';' by default, Forms and Excel use ','.
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            head = f.readline()
        sep = ";" if head.count(";") > head.count(",") else ","
        return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False,
                           encoding="utf-8-sig"), None
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        book = pd.ExcelFile(path)
        name = sheet if sheet is not None else book.sheet_names[0]
        if isinstance(name, int):
            name = book.sheet_names[name]
        df = pd.read_excel(book, sheet_name=name, dtype=object)
        return df, str(name)
    raise ValueError(f"Unsupported file type: {path.suffix} (use .csv or .xlsx)")


def load(path: str | Path, sheet: str | int | None = None) -> Dataset:
    path = Path(path)
    df, sheet_name = _read(path, sheet)
    df = df.dropna(axis=0, how="all")
    # Drop trailing columns Excel leaves behind ("Unnamed: 12") when empty.
    df = df[[c for c in df.columns
             if not (str(c).startswith("Unnamed:") and df[c].isna().all())]]
    source = detect_source(list(df.columns))

    names = _short_names(list(df.columns))
    original = {new: str(old) for old, new in names.items()}
    df = df.rename(columns=names).reset_index(drop=True)

    system = []
    for new, old in original.items():
        o = old.strip().lower()
        if source == "kobo" and (o in KOBO_SYSTEM or o in KOBO_META or o.startswith("_")):
            system.append(new)
        elif source == "google_forms" and o in FORMS_TIMESTAMP:
            system.append(new)
    return Dataset(df=df, source=source, path=str(path), sheet=sheet_name,
                   original_names=original, system_columns=system)
