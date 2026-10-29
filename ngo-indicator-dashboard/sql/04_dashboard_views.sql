-- 04_dashboard_views.sql
-- Views that Looker Studio reads. Run after 03_load_programme_data.sql.
-- "Expected so far" assumes the annual target is spread evenly over 12 months,
-- so after 9 reported months a programme on pace has reached 75% of target.

-- One row per month, indicator, governorate, sex and age group, with labels
-- in English and Arabic. Use for trends and disaggregation charts.
CREATE OR REPLACE VIEW `describe-ngo-lab-2026.ngo_demo.v_reach_detail` AS
SELECT
  r.month,
  r.indicator_code,
  i.sector_en, i.sector_ar,
  i.indicator_en, i.indicator_ar,
  i.unit_en, i.unit_ar,
  r.governorate_code,
  g.governorate_en, g.governorate_ar, g.lat_long,
  IFNULL(s.sex_en, 'Not disaggregated') AS sex_en,
  IFNULL(s.sex_ar, 'غير مصنف') AS sex_ar,
  IFNULL(a.age_group_en, 'Not disaggregated') AS age_group_en,
  IFNULL(a.age_group_ar, 'غير مصنف') AS age_group_ar,
  r.value,
  'SAMPLE DATA' AS data_note
FROM `describe-ngo-lab-2026.ngo_demo.fact_monthly_reach` AS r
JOIN `describe-ngo-lab-2026.ngo_demo.dim_indicator` AS i USING (indicator_code)
JOIN `describe-ngo-lab-2026.ngo_demo.dim_governorate` AS g USING (governorate_code)
LEFT JOIN `describe-ngo-lab-2026.ngo_demo.dim_sex` AS s USING (sex)
LEFT JOIN `describe-ngo-lab-2026.ngo_demo.dim_age_group` AS a USING (age_group);

-- Progress against target per indicator and governorate.
CREATE OR REPLACE VIEW `describe-ngo-lab-2026.ngo_demo.v_progress_by_governorate` AS
WITH reached AS (
  SELECT indicator_code, governorate_code, SUM(value) AS reached
  FROM `describe-ngo-lab-2026.ngo_demo.fact_monthly_reach`
  GROUP BY indicator_code, governorate_code
),
months AS (
  SELECT COUNT(DISTINCT month) AS months_reported, MAX(month) AS last_month
  FROM `describe-ngo-lab-2026.ngo_demo.fact_monthly_reach`
),
base AS (
  SELECT
    t.indicator_code,
    t.governorate_code,
    t.target,
    IFNULL(r.reached, 0) AS reached,
    m.months_reported,
    m.last_month,
    t.target * m.months_reported / 12 AS expected_so_far
  FROM `describe-ngo-lab-2026.ngo_demo.fact_target` AS t
  CROSS JOIN months AS m
  LEFT JOIN reached AS r USING (indicator_code, governorate_code)
)
SELECT
  b.*,
  i.sector_en, i.sector_ar, i.indicator_en, i.indicator_ar, i.unit_en, i.unit_ar,
  g.governorate_en, g.governorate_ar, g.lat_long,
  SAFE_DIVIDE(b.reached, b.target) AS pct_of_target,
  SAFE_DIVIDE(b.reached, b.expected_so_far) AS pct_of_expected,
  CASE
    WHEN SAFE_DIVIDE(b.reached, b.expected_so_far) >= 0.95 THEN 'On track'
    WHEN SAFE_DIVIDE(b.reached, b.expected_so_far) >= 0.80 THEN 'Slightly behind'
    ELSE 'Behind'
  END AS status_en,
  CASE
    WHEN SAFE_DIVIDE(b.reached, b.expected_so_far) >= 0.95 THEN 'على المسار'
    WHEN SAFE_DIVIDE(b.reached, b.expected_so_far) >= 0.80 THEN 'متأخر قليلاً'
    ELSE 'متأخر'
  END AS status_ar,
  'SAMPLE DATA' AS data_note
FROM base AS b
JOIN `describe-ngo-lab-2026.ngo_demo.dim_indicator` AS i USING (indicator_code)
JOIN `describe-ngo-lab-2026.ngo_demo.dim_governorate` AS g USING (governorate_code);

-- Programme-level progress per indicator (all governorates together).
-- Feeds the headline indicator table with progress bars.
CREATE OR REPLACE VIEW `describe-ngo-lab-2026.ngo_demo.v_progress_by_indicator` AS
SELECT
  indicator_code,
  ANY_VALUE(sector_en) AS sector_en,
  ANY_VALUE(sector_ar) AS sector_ar,
  ANY_VALUE(indicator_en) AS indicator_en,
  ANY_VALUE(indicator_ar) AS indicator_ar,
  ANY_VALUE(unit_en) AS unit_en,
  ANY_VALUE(unit_ar) AS unit_ar,
  ANY_VALUE(last_month) AS last_month,
  SUM(target) AS target,
  SUM(reached) AS reached,
  SUM(expected_so_far) AS expected_so_far,
  SAFE_DIVIDE(SUM(reached), SUM(target)) AS pct_of_target,
  SAFE_DIVIDE(SUM(reached), SUM(expected_so_far)) AS pct_of_expected,
  CASE
    WHEN SAFE_DIVIDE(SUM(reached), SUM(expected_so_far)) >= 0.95 THEN 'On track'
    WHEN SAFE_DIVIDE(SUM(reached), SUM(expected_so_far)) >= 0.80 THEN 'Slightly behind'
    ELSE 'Behind'
  END AS status_en,
  CASE
    WHEN SAFE_DIVIDE(SUM(reached), SUM(expected_so_far)) >= 0.95 THEN 'على المسار'
    WHEN SAFE_DIVIDE(SUM(reached), SUM(expected_so_far)) >= 0.80 THEN 'متأخر قليلاً'
    ELSE 'متأخر'
  END AS status_ar,
  'SAMPLE DATA' AS data_note
FROM `describe-ngo-lab-2026.ngo_demo.v_progress_by_governorate`
GROUP BY indicator_code;

-- Quick check: should return 7 rows. WASH-1 and PSS-1 on track, FS-2 behind.
SELECT indicator_code, indicator_en, target, reached,
       ROUND(pct_of_target * 100) AS pct_of_target, status_en
FROM `describe-ngo-lab-2026.ngo_demo.v_progress_by_indicator`
ORDER BY indicator_code;
