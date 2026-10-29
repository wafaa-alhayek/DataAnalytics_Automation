-- Views for Looker Studio on top of the tagged survey tables.
-- Load the CSVs first (see README), then run this file in the BigQuery console
-- or with:  bq query --use_legacy_sql=false < bigquery/views.sql

-- How often each theme comes up, by question, site and gender.
CREATE OR REPLACE VIEW `describe-ngo-lab.survey_demo.theme_counts` AS
SELECT
  l.question_id,
  l.site,
  l.gender,
  l.theme_code,
  l.theme_ar,
  l.theme_en,
  COUNT(DISTINCT l.response_id) AS answers,
  COUNTIF(l.theme_rank = 1) AS answers_as_primary,
  ROUND(100 * COUNT(DISTINCT l.response_id) / ANY_VALUE(t.total_answers), 1) AS pct_of_answers
FROM `describe-ngo-lab.survey_demo.tagged_long` AS l
JOIN (
  SELECT question_id, COUNT(*) AS total_answers
  FROM `describe-ngo-lab.survey_demo.tagged`
  GROUP BY question_id
) AS t USING (question_id)
GROUP BY 1, 2, 3, 4, 5, 6;

-- Sentiment split per question and site.
CREATE OR REPLACE VIEW `describe-ngo-lab.survey_demo.sentiment_by_site` AS
SELECT question_id, site, sentiment, COUNT(*) AS answers
FROM `describe-ngo-lab.survey_demo.tagged`
GROUP BY 1, 2, 3;

-- Answers that a trained staff member must read. Keep this view out of any
-- dashboard shared with donors or partners.
CREATE OR REPLACE VIEW `describe-ngo-lab.survey_demo.followup_queue` AS
SELECT response_id, question_id, site, answer, followup_reason, summary_en, tagged_at
FROM `describe-ngo-lab.survey_demo.tagged`
WHERE needs_followup = 1;
