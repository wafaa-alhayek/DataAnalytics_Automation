# Sample NGO indicator dashboard

A demo of what Describe builds for NGOs: programme indicators tracked against
targets by month, governorate, sex and age, next to country context from public
data. It runs in BigQuery (Google Cloud project `describe-ngo-lab-2026`) with a
Looker Studio dashboard on top, in English and Arabic.

**Data honesty.** The programme figures (targets and people reached) are
**made-up sample data** from a fictional "Sample Emergency Response Programme
2026" in the five Gaza governorates. Every view carries `data_note = 'SAMPLE DATA'`
and the dashboard must show a "Sample data" label. The country context comes from
the World Bank's World Development Indicators, read from the BigQuery public
dataset `bigquery-public-data.world_bank_wdi`.

## What's in here

| File | What it does |
|---|---|
| `sql/01_setup_and_check.sql` | Creates the `ngo_demo` dataset (US region) and checks the World Bank table. |
| `sql/02_context_indicators.sql` | Builds `context_indicators` (11 indicators, 8 countries, 2000 onward) and the view `v_context_latest`. |
| `sql/03_load_programme_data.sql` | Creates and fills the sample programme tables (`dim_*`, `fact_target`, `fact_monthly_reach`). Generated, don't edit by hand. |
| `sql/04_dashboard_views.sql` | Views Looker Studio reads: `v_reach_detail`, `v_progress_by_governorate`, `v_progress_by_indicator`. |
| `scripts/generate_programme_data.py` | Regenerates the sample data (CSV + `03_*.sql`). Change indicators, targets or governorates here. |
| `data/*.csv` | The same sample data as CSV, for upload elsewhere (Sheets, Power BI). |
| `looker-studio-guide.md` | Step-by-step dashboard build. |

## Run it (about 10 minutes)

1. Open <https://console.cloud.google.com/bigquery>, select project **describe-ngo-lab-2026**.
2. Open each file in `sql/` in order (01 → 04), paste into a new query tab, and run.
   In 01, run the statements one at a time and read the results of the two checks.
3. The last query in 04 should return 7 indicators; WASH-1 and PSS-1 are on track, FS-2 is behind.
4. Build the dashboard with `looker-studio-guide.md`.

Cost: all of this scans well under 1 GB, inside BigQuery's free monthly 1 TB of
queries, and stores under 10 MB, so it stays free after the trial ends.

## If the World Bank data is out of date

The public copy in BigQuery is refreshed by Google, not by the World Bank, and
can lag. If the check in `01` shows a latest year that is too old for a demo:

- try `bigquery-public-data.world_bank_health_population.health_nutrition_population`
  (same column names) by swapping the table name in `02`, or
- download the CSVs from <https://data.worldbank.org> or HDX
  (<https://data.humdata.org>) and upload them as a table in `ngo_demo`, then
  point `02` at that table.

## Regenerating the sample data

```bash
cd ngo-indicator-dashboard
python scripts/generate_programme_data.py
```

The seed is fixed, so the same numbers come out each time unless you change the script.

## Using it with a client

Swap the sample tables for the client's real indicator matrix (indicator list,
targets per area, monthly reach by sex and age). The views and the dashboard
stay the same, which is the point of the Data Diagnostic: get the client's data
into this shape once, then reporting is automatic.
