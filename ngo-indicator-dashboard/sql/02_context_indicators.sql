-- 02_context_indicators.sql
-- Country context for the dashboard: a few humanitarian indicators for
-- Palestine and neighbouring countries, from the World Bank's public WDI
-- dataset in BigQuery (free to query; this reads well under 1 GB).

CREATE OR REPLACE TABLE `describe-ngo-lab.ngo_demo.context_indicators` AS
WITH countries AS (
  SELECT * FROM UNNEST([
    STRUCT('PSE' AS country_code, 'Palestine (West Bank and Gaza)' AS country_en, 'فلسطين (الضفة الغربية وغزة)' AS country_ar),
    ('JOR', 'Jordan', 'الأردن'),
    ('LBN', 'Lebanon', 'لبنان'),
    ('SYR', 'Syria', 'سوريا'),
    ('YEM', 'Yemen', 'اليمن'),
    ('SDN', 'Sudan', 'السودان'),
    ('IRQ', 'Iraq', 'العراق'),
    ('EGY', 'Egypt', 'مصر')
  ])
),
indicators AS (
  -- higher_is_better drives the colour of "change since previous year".
  SELECT * FROM UNNEST([
    STRUCT('SP.POP.TOTL' AS indicator_code, 'Population' AS sector_en, 'السكان' AS sector_ar,
           'Total population' AS indicator_en, 'إجمالي السكان' AS indicator_ar, 'people' AS unit_en, CAST(NULL AS BOOL) AS higher_is_better),
    ('SH.DYN.MORT', 'Health', 'الصحة', 'Under-5 mortality (per 1,000 live births)', 'وفيات الأطفال دون الخامسة (لكل 1,000 ولادة حية)', 'per 1,000', FALSE),
    ('SH.STA.MMRT', 'Health', 'الصحة', 'Maternal mortality (per 100,000 live births)', 'وفيات الأمهات (لكل 100,000 ولادة حية)', 'per 100,000', FALSE),
    ('SH.IMM.MEAS', 'Health', 'الصحة', 'Measles immunisation (% of children 12-23 months)', 'التطعيم ضد الحصبة (% من الأطفال 12-23 شهراً)', '%', TRUE),
    ('SH.STA.STNT.ZS', 'Nutrition', 'التغذية', 'Stunting (% of children under 5)', 'التقزم (% من الأطفال دون الخامسة)', '%', FALSE),
    ('SH.H2O.BASW.ZS', 'Water, sanitation and hygiene', 'المياه والصرف الصحي والنظافة', 'Basic drinking water services (% of people)', 'خدمات مياه الشرب الأساسية (% من السكان)', '%', TRUE),
    ('SH.STA.BASS.ZS', 'Water, sanitation and hygiene', 'المياه والصرف الصحي والنظافة', 'Basic sanitation services (% of people)', 'خدمات الصرف الصحي الأساسية (% من السكان)', '%', TRUE),
    ('SE.PRM.NENR', 'Education', 'التعليم', 'Primary school net enrolment (%)', 'صافي الالتحاق بالتعليم الابتدائي (%)', '%', TRUE),
    ('SL.UEM.1524.ZS', 'Livelihoods', 'سبل العيش', 'Youth unemployment (% of labour force 15-24)', 'بطالة الشباب (% من القوى العاملة 15-24)', '%', FALSE),
    ('EG.ELC.ACCS.ZS', 'Infrastructure', 'البنية التحتية', 'Access to electricity (% of people)', 'الحصول على الكهرباء (% من السكان)', '%', TRUE),
    ('SM.POP.REFG.OR', 'Displacement', 'النزوح واللجوء', 'Refugees by country of origin', 'اللاجئون حسب بلد المنشأ', 'people', FALSE)
  ])
)
SELECT
  d.country_code,
  c.country_en,
  c.country_ar,
  i.indicator_code,
  i.sector_en,
  i.sector_ar,
  i.indicator_en,
  i.indicator_ar,
  i.unit_en,
  i.higher_is_better,
  d.year,
  DATE(d.year, 1, 1) AS year_date,  -- Looker Studio time series need a date
  d.value,
  'World Bank, World Development Indicators (BigQuery public dataset)' AS source
FROM `bigquery-public-data.world_bank_wdi.indicators_data` AS d
JOIN countries AS c USING (country_code)
JOIN indicators AS i USING (indicator_code)
WHERE d.year >= 2000
  AND d.value IS NOT NULL;

-- Latest available value per country and indicator, with the change since the
-- previous reported year. Feeds the scorecards and the comparison table.
CREATE OR REPLACE VIEW `describe-ngo-lab.ngo_demo.v_context_latest` AS
WITH ranked AS (
  SELECT
    *,
    LAG(value) OVER (PARTITION BY country_code, indicator_code ORDER BY year) AS previous_value,
    LAG(year) OVER (PARTITION BY country_code, indicator_code ORDER BY year) AS previous_year,
    ROW_NUMBER() OVER (PARTITION BY country_code, indicator_code ORDER BY year DESC) AS rn
  FROM `describe-ngo-lab.ngo_demo.context_indicators`
)
SELECT
  * EXCEPT (rn),
  value - previous_value AS change,
  CASE
    WHEN higher_is_better IS NULL OR previous_value IS NULL OR value = previous_value THEN 'No change / n.a.'
    WHEN (value > previous_value) = higher_is_better THEN 'Improved'
    ELSE 'Worsened'
  END AS direction_en,
  CASE
    WHEN higher_is_better IS NULL OR previous_value IS NULL OR value = previous_value THEN 'لا تغيير / غير متاح'
    WHEN (value > previous_value) = higher_is_better THEN 'تحسّن'
    ELSE 'تراجع'
  END AS direction_ar
FROM ranked
WHERE rn = 1;
