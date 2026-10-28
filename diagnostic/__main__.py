"""Command line.

  python -m diagnostic run survey.xlsx --config client.yaml --out reports/client
  python -m diagnostic run --from-bigquery describe-ngo-lab.client.survey --out reports/client
  python -m diagnostic bq-upload survey.xlsx describe-ngo-lab.client.survey
  python -m diagnostic bq-sql survey.xlsx describe-ngo-lab.client.survey > checks.sql
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import bigquery
from .checks import run
from .config import load_config
from .load import load
from .report import write_all


def _sheet(value):
    return int(value) - 1 if value is not None and value.isdigit() else value   # 1 = first sheet


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m diagnostic", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run every check and write the findings report")
    r.add_argument("file", nargs="?", help="Kobo, Google Forms or Excel export (.xlsx or .csv)")
    r.add_argument("--from-bigquery", metavar="TABLE", help="read project.dataset.table instead")
    r.add_argument("--config", help="client settings (YAML); optional")
    r.add_argument("--sheet", help="sheet name or number (1 = first), for Excel files with several sheets")
    r.add_argument("--out", default="diagnostic-report", help="folder for the report files")

    u = sub.add_parser("bq-upload", help="load an export into BigQuery")
    u.add_argument("file")
    u.add_argument("table", help="project.dataset.table")
    u.add_argument("--sheet")

    q = sub.add_parser("bq-sql", help="print the checks as BigQuery SQL")
    q.add_argument("file")
    q.add_argument("table", help="project.dataset.table")
    q.add_argument("--sheet")

    a = p.parse_args(argv)
    if a.cmd == "run":
        if a.from_bigquery:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp, a.from_bigquery.split(".")[-1] + ".csv")
                bigquery.download(a.from_bigquery).to_csv(path, index=False)
                ds = load(path)
                ds.path = a.from_bigquery
        elif a.file:
            ds = load(a.file, _sheet(a.sheet))
        else:
            p.error("give a file, or --from-bigquery TABLE")
        result = run(ds, load_config(a.config))
        paths = write_all(result, a.out)
        print(f"{len(ds.df)} records · {ds.source} export · score {result.score}/100 "
              f"({result.verdict}) · {len(result.findings)} findings")
        for f in result.findings:
            print(f"  [{f.severity:6}] {f.title}")
        for kind, path in paths.items():
            print(f"{kind:9} {path}")
    elif a.cmd == "bq-upload":
        ds = load(a.file, _sheet(a.sheet))
        names = bigquery.upload(ds, a.table)
        print(f"Loaded {len(ds.df)} rows into {a.table} ({len(names)} columns)")
    elif a.cmd == "bq-sql":
        ds = load(a.file, _sheet(a.sheet))
        sys.stdout.write(bigquery.check_sql(ds, a.table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
