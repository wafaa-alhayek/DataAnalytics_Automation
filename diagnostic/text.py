"""Text helpers for Arabic and English survey answers."""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
_HAS_EASTERN_DIGIT = re.compile(r"[٠-٩۰-۹]")
_DIACRITICS = re.compile("[\u064B-\u065F\u0670\u0640]")   # harakat + tatweel
_SPACES = re.compile(r"\s+")

# Answers people type when they mean "no answer". Kept short on purpose:
# "none" and "لا يوجد" (there is none) are real answers, so they are not in it.
MISSING_TOKENS = {
    "", "na", "n/a", "n.a.", "nan", "null", "-", "--", "---", "?",
    "#n/a", "not applicable", "missing", "غير متوفر", "لا ينطبق",
}


def has_eastern_digits(value) -> bool:
    return isinstance(value, str) and bool(_HAS_EASTERN_DIGIT.search(value))


def to_western_digits(value: str) -> str:
    return value.translate(ARABIC_DIGITS)


def normalize_label(value) -> str:
    """Fold the spelling differences that make one answer look like several.

    'Female ', 'female' and 'FEMALE' fold together; so do 'خانيونس' and
    'خان يونس', and 'أنثى' with 'انثى'.
    """
    s = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    s = _DIACRITICS.sub("", s)
    s = s.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
                                   "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}))
    s = to_western_digits(s)
    s = re.sub(r"[\s\-_.,'\"()]+", "", s)
    return s


def is_missing(series: pd.Series) -> pd.Series:
    def one(v):
        if v is None:
            return True
        try:
            if pd.isna(v):
                return True
        except (TypeError, ValueError):
            pass
        if isinstance(v, str):
            return _SPACES.sub(" ", v).strip().casefold() in MISSING_TOKENS
        return False
    return series.map(one).astype(bool)


def to_number(series: pd.Series) -> pd.Series:
    """Numbers typed as text, with Arabic digits or thousands separators."""
    def one(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = to_western_digits(v).strip().replace(",", "")
            s = re.sub(r"^(?:usd|ils|nis|jod|\$|₪)\s*|\s*(?:usd|ils|nis|jod|\$|₪)$", "", s,
                       flags=re.I)
            try:
                return float(s)
            except ValueError:
                return None
        return None
    return pd.to_numeric(series.map(one), errors="coerce")
