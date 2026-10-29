# Arabic open-ended survey coding with Gemini

A demo for the NGO Data Diagnostic and the "Survey to Report" package. Gemini
on Vertex AI reads open-ended Arabic survey answers (dialect included) and tags
each one with themes from a codebook, a sentiment, a one-line English summary,
and a follow-up flag for answers a trained staff member must read. Results load
into BigQuery for a Looker Studio page.

**Data honesty.** The 70 answers in `data/sample_responses.csv` were written
for this demo. They are not from real people or a real organisation. Never put
real beneficiary answers through this without the client's written agreement
and without removing names, phone numbers and ID numbers first.

## What's in here

| File | What it does |
|---|---|
| `codebook.json` | 16 themes with Arabic and English labels and a description each, the sentiment scale, and the follow-up rule. Copy and edit per client. |
| `make_sample_data.py` | Writes `data/sample_responses.csv` (the answers) and `data/gold_labels.csv` (how a human coder tagged them). |
| `tag_responses.py` | Sends answers to Gemini in batches of 20 and writes `data/tagged_<model>.csv` plus a long `_long.csv` (one row per theme). Resumes where it stopped. `--mock` runs an offline keyword baseline instead. |
| `evaluate.py` | Scores a tagged file against the gold labels: agreement, per-theme precision and recall, follow-up cases caught, worst disagreements. |
| `bigquery/views.sql` | Views for Looker Studio: theme counts by question, site and gender; sentiment by site; and a follow-up queue that stays out of shared dashboards. |

## Run it in Cloud Shell (about 10 minutes)

1. Open <https://console.cloud.google.com/>, select project **describe-ngo-lab**,
   and click the Cloud Shell icon (top right).
2. Turn on Vertex AI for the project (once):

   ```bash
   gcloud config set project describe-ngo-lab
   gcloud services enable aiplatform.googleapis.com
   ```

3. Get the code and install the one library:

   ```bash
   git clone https://github.com/wafaa-alhayek/DataAnalytics_Automation.git
   cd DataAnalytics_Automation/arabic-survey-coding
   pip install --user -r requirements.txt
   ```

4. Test on 5 answers, then run the rest (the second run skips the first 5):

   ```bash
   python tag_responses.py --project describe-ngo-lab --limit 5
   python tag_responses.py --project describe-ngo-lab
   ```

   If it says a model is not found, Google has renamed or retired it. Try
   `--model gemini-3.5-flash-lite`, or pick a current Flash model in
   Vertex AI → Model Garden. If it asks for credentials, run
   `gcloud auth application-default login` once.

5. Check quality against the human coding:

   ```bash
   python evaluate.py data/tagged_gemini-3.8-flash.csv
   python tag_responses.py --mock && python evaluate.py data/tagged_keyword-baseline.csv
   ```

   The keyword baseline scores 79% theme overlap, 23% sentiment and catches
   0 of 3 follow-up cases. Gemini should beat it clearly, above all on
   sentiment and follow-up cases; those two numbers are the demo's selling point.

6. Load into BigQuery and build the views:

   ```bash
   bq --location=US mk --dataset describe-ngo-lab:survey_demo
   bq load --replace --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines \
     survey_demo.tagged data/tagged_gemini-3.8-flash.csv \
     response_id:STRING,question_id:STRING,site:STRING,gender:STRING,answer:STRING,themes:STRING,primary_theme:STRING,sentiment:STRING,needs_followup:INT64,followup_reason:STRING,summary_en:STRING,model:STRING,tagged_at:TIMESTAMP
   bq load --replace --source_format=CSV --skip_leading_rows=1 \
     survey_demo.tagged_long data/tagged_gemini-3.8-flash_long.csv \
     response_id:STRING,question_id:STRING,site:STRING,gender:STRING,theme_code:STRING,theme_ar:STRING,theme_en:STRING,theme_rank:INT64,sentiment:STRING,needs_followup:INT64
   bq query --use_legacy_sql=false < bigquery/views.sql
   ```

7. In Looker Studio, add `survey_demo.theme_counts` as a data source and chart
   `answers` by `theme_ar` (or `theme_en`), with filters for question and site.
   Label the page "Sample data".

## Cost

Gemini 3.8 Flash costs $0.75 per million input tokens and $3.75 per million
output tokens (standard tier, global endpoint, price to 31 Dec 2026). A batch of
20 answers uses about 2,000 input and 1,500 output tokens, so the 70 sample
answers cost about 3 cents and 10,000 real answers about $5. The script prints
the token count and estimate at the end of each run. BigQuery storage and
queries here stay inside the free tier.

## Using it for a client

1. Agree the codebook with the client first: start from `codebook.json`, rename
   and merge themes to match their programme and indicators.
2. Hand-code 50 to 100 of their answers (or have their M&E officer do it) into a
   gold file with the same columns as `data/gold_labels.csv`.
3. Run the tagger and `evaluate.py`. Tighten theme descriptions where precision
   or recall is low and rerun on a fresh output file.
4. Every answer flagged for follow-up goes to the client's trained protection or
   safeguarding focal point the same day. The model flags; a person decides.
