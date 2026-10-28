"""Per-client settings. Every key is optional: with no file the checks guess."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    project: str = ""
    client: str = ""
    id_columns: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    enumerator_column: str | None = None
    codes: dict[str, list] = field(default_factory=dict)
    ranges: dict[str, list] = field(default_factory=dict)
    collection_start: str | None = None
    collection_end: str | None = None
    min_interview_minutes: float = 5
    rules: list[dict] = field(default_factory=list)
    indicators: list[dict] = field(default_factory=list)
    disaggregations: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    missing_warn: float = 0.20      # share of blanks that earns a finding
    missing_high: float = 0.50


def load_config(path: str | Path | None) -> Config:
    if not path:
        return Config()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    dates = data.pop("dates", {}) or {}
    data.setdefault("collection_start", dates.get("collection_start"))
    data.setdefault("collection_end", dates.get("collection_end"))
    known = set(Config.__dataclass_fields__)
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    for key in ("collection_start", "collection_end"):
        if data.get(key) is not None:
            data[key] = str(data[key])
    return Config(**data)
