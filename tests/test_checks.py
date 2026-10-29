"""Run with: python -m unittest discover tests"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diagnostic import bigquery, load, load_config, run  # noqa: E402
from diagnostic.report import write_all  # noqa: E402
from diagnostic.text import normalize_label, to_number  # noqa: E402

TODAY = datetime(2026, 10, 28)


def write_csv(df: pd.DataFrame) -> Path:
    path = Path(tempfile.mkdtemp()) / "data.csv"
    df.to_csv(path, index=False)
    return path


def titles(result):
    return [f.title for f in result.findings]


class TextTests(unittest.TestCase):
    def test_arabic_spellings_fold(self):
        self.assertEqual(normalize_label("خان يونس"), normalize_label("خانيونس"))
        self.assertEqual(normalize_label("أنثى"), normalize_label("انثى"))
        self.assertEqual(normalize_label(" Female "), normalize_label("female"))

    def test_numbers_with_arabic_digits(self):
        self.assertEqual(list(to_number(pd.Series(["٣٥", "1,200", "500 NIS", "x"])).fillna(-1)),
                         [35, 1200, 500, -1])


class CheckTests(unittest.TestCase):
    def base(self, n=40):
        return pd.DataFrame({
            "household_id": [f"H{i}" for i in range(n)],
            "gender": ["female", "male"] * (n // 2),
            "age": [str(20 + i % 40) for i in range(n)],
            "visit_date": [f"2026-10-{1 + i % 20:02d}" for i in range(n)],
        })

    def test_clean_file_scores_high(self):
        r = run(load(write_csv(self.base())), today=TODAY)
        self.assertEqual(r.findings, [])
        self.assertEqual(r.score, 100)

    def test_duplicates_and_ids(self):
        df = self.base()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)    # exact copy
        df.loc[5, "household_id"] = "H6"                          # shared ID
        r = run(load(write_csv(df)), today=TODAY)
        checks = {f.check for f in r.findings}
        self.assertIn("duplicates", checks)
        self.assertTrue(any("exact copies" in t for t in titles(r)))
        self.assertTrue(any("used more than once" in t for t in titles(r)))
        # The exact copy is not counted again as a shared ID.
        id_finding = next(f for f in r.findings if "used more than once" in f.title)
        self.assertEqual(id_finding.rows_affected, 2)

    def test_mixed_spellings_and_languages(self):
        df = self.base()
        df.loc[[1, 3], "gender"] = ["Male", "ذكر"]
        r = run(load(write_csv(df)), today=TODAY)
        self.assertTrue(any("'gender' records the same answer" in t for t in titles(r)))

    def test_arabic_digits_ranges_and_future_dates(self):
        df = self.base()
        df.loc[2, "age"] = "٣٥"
        df.loc[4, "age"] = "250"
        df.loc[6, "visit_date"] = "2027-01-01"
        r = run(load(write_csv(df)), today=TODAY)
        t = " | ".join(titles(r))
        self.assertIn("Arabic-Indic digits", t)
        self.assertIn("outside 0-110", t)
        self.assertIn("in the future", t)

    def test_skip_logic_blanks_are_not_reported(self):
        df = self.base()
        df["received"] = ["yes", "no"] * 20
        df["amount"] = ["500" if v == "yes" else "" for v in df.received]
        r = run(load(write_csv(df)), today=TODAY)
        self.assertFalse(any("'amount' is blank" in t for t in titles(r)))

    def test_config_codes_rules_and_coverage(self):
        df = self.base()
        df["received"] = ["yes", "no"] * 20
        df["amount"] = ["500" if v == "yes" else "" for v in df.received]
        df.loc[1, "amount"] = "300"
        df.loc[0, "gender"] = "other"
        cfg_path = Path(tempfile.mkdtemp()) / "c.yaml"
        cfg_path.write_text(
            "codes:\n  gender: [female, male]\n"
            "rules:\n  - name: Amount without cash\n    when: received == 'no' and amount > 0\n"
            "indicators:\n  - name: Age known\n    columns: [age]\n    disaggregate_by: [gender]\n",
            encoding="utf-8")
        r = run(load(write_csv(df)), load_config(cfg_path), today=TODAY)
        t = " | ".join(titles(r))
        self.assertIn("outside the agreed options", t)
        self.assertIn("Amount without cash: 1 records", t)
        self.assertEqual(r.coverage.iloc[0]["coverage"], 1.0)


class SampleTests(unittest.TestCase):
    """The sample files have known, planted problems."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "samples"))
        import make_samples
        make_samples.main()

    def test_kobo_sample(self):
        ds = load(ROOT / "samples" / "kobo_household_survey.xlsx")
        self.assertEqual(ds.source, "kobo")
        self.assertIn("_uuid", ds.system_columns)
        r = run(ds, load_config(ROOT / "configs" / "example-kobo-household.yaml"), today=TODAY)
        t = " | ".join(titles(r))
        for expected in ("6 submission(s) are exact copies", "interviews took under 5 minutes",
                         "No cash received, but a cash amount is recorded: 6 records",
                         "data collector(s) stand out", "'today' has 3 dates in the future"):
            self.assertIn(expected, t)
        out = Path(tempfile.mkdtemp())
        paths = write_all(r, out)
        self.assertTrue(all(p.exists() for p in paths.values()))

    def test_forms_and_excel_samples(self):
        forms = load(ROOT / "samples" / "google_forms_feedback.csv")
        self.assertEqual(forms.source, "google_forms")
        self.assertTrue(any("outside 1-5" in t for t in titles(run(forms, today=TODAY))))
        excel = run(load(ROOT / "samples" / "excel_beneficiary_register.xlsx"), today=TODAY)
        self.assertEqual(excel.dataset.source, "excel")
        self.assertTrue(any("'رقم الهوية'" in t for t in titles(excel)))

    def test_bigquery_sql_quotes_columns(self):
        ds = load(ROOT / "samples" / "kobo_household_survey.xlsx")
        sql = bigquery.check_sql(ds, "p.d.t")
        self.assertIn("`end`", sql)
        self.assertEqual(bigquery.bq_name("الجنس"), "col")
        self.assertEqual(bigquery.bq_name("_uuid"), "_uuid")
        # Spelling check folds Arabic and English the way the Python check does,
        # and the ID check ignores exact copies (both verified on BigQuery).
        self.assertIn("'انثي') THEN 'female'", sql)
        self.assertIn("ANY_VALUE(`beneficiary_id`)", sql)


if __name__ == "__main__":
    unittest.main()
