# Describe Data Diagnostic

The same data-quality checks, run on any NGO survey export: KoboToolbox,
Google Forms or a hand-kept Excel sheet. One command produces what the paid
**Data Diagnostic** delivers:

- `findings.html`: a one-page findings report with a data health score, the
  three things to fix first, every finding in plain language, whether each
  indicator can actually be counted (overall and by sex, location, etc.) and a
  table per data collector. Open it in a browser and print to PDF to send.
- `findings.md`: the same findings as text, to paste into an email or doc.
- `issues-log.xlsx`: every flagged cell with its spreadsheet row, so the
  client's team can fix their file directly.

It runs free on any laptop, in Google Colab or in Google Cloud Shell. BigQuery
is optional (see below), so nothing stops working when the Cloud trial ends.

## Run it

```bash
pip install -r requirements.txt
python -m diagnostic run client_export.xlsx --out reports/client-name
```

Add a settings file when you know the survey (agreed answer options, number
ranges, fieldwork dates, indicators, contradiction rules):

```bash
python -m diagnostic run client_export.xlsx --config configs/client-name.yaml --out reports/client-name
```

Copy `configs/example-kobo-household.yaml` to start one. Every key is optional;
use the short Kobo column names (the part after the last `/`).

Try it on the made-up samples:

```bash
python samples/make_samples.py
python -m diagnostic run samples/kobo_household_survey.xlsx \
  --config configs/example-kobo-household.yaml --out reports/sample
```

**Kobo:** export as XLS, "XML values and headers", and tick "Include groups in
headers". Repeat groups land on extra sheets; check one with `--sheet 2`.
**Google Forms:** Responses → Download responses (.csv). **Excel:** the first
sheet is read unless you pass `--sheet`.

## What it checks

| Check | Catches |
|---|---|
| Duplicates | Forms sent twice; one ID used by two people (ID columns found by name, or set `id_columns`) |
| Blanks | Blank required fields; questions with many blanks. Blanks that follow a skip rule (blank exactly when another answer is "no") are recognised and not reported |
| Spellings | One answer written several ways: `Female` / `female ` / `F` / `أنثى`, `خانيونس` / `خان يونس`. With `codes`, anything outside the agreed list |
| Numbers | Text in number columns (`500 NIS`, `unknown`), Arabic-Indic digits (`٣٥`) that Excel and Sheets read as text |
| Ranges | Impossible values (age, household size, a `(1-5)` scale in the question, or your `ranges`); extreme outliers |
| Dates | Unreadable dates, future dates, records outside the fieldwork window (test submissions) |
| Interview length | Kobo interviews faster than `min_interview_minutes`, or ending before they start |
| Rules | Your own contradictions, e.g. `received_cash == 'no' and cash_amount > 0` |
| Indicator coverage | Share of records that can be counted in each indicator, overall and per group |
| Data collectors | Collectors with far more blanks or very short interviews |

The score starts at 100 and each finding takes off up to 10 points (fix before
reporting), 4 (fix soon) or 1 (worth a look), scaled by the share of records it
touches. 85+ reads "Ready to report", 65-84 "Usable after targeted fixes".

## BigQuery (optional)

For the Google Cloud trial project `describe-ngo-lab-2026`, and the free BigQuery
sandbox afterwards. Run these in **Google Cloud Shell** (free, `bq` is already
installed): open shell.cloud.google.com, `git clone` this repo, then:

```bash
pip install -r requirements.txt
bq mk --dataset describe-ngo-lab-2026:client_name            # once per client
python -m diagnostic bq-upload export.xlsx describe-ngo-lab-2026.client_name.survey
python -m diagnostic run --from-bigquery describe-ngo-lab-2026.client_name.survey \
  --config configs/client-name.yaml --out reports/client-name
python -m diagnostic bq-sql export.xlsx describe-ngo-lab-2026.client_name.survey > checks.sql
```

- `bq-upload` loads every column as text, with the original question as the
  column description, so nothing is converted or lost on the way in.
- `run --from-bigquery` reads the table back and runs the exact same checks,
  so a report from BigQuery matches one from the file.
- `bq-sql` writes the core checks (blanks, duplicates, IDs, spellings, Arabic
  digits, interview length) as BigQuery SQL. Save the queries as views, or as a
  scheduled query, and point a Looker Studio report at them for a client who
  keeps collecting data. All queries return `check_name, column_name, records, detail`.

Keep client data small (well under BigQuery's 10 GB free storage) and delete a
client's dataset when the engagement ends.

## Tests

```bash
python -m unittest discover tests
```

The tests include the sample files, whose planted problems are listed in
`samples/README.md`.
