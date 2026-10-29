-- 01_setup_and_check.sql
-- Run in the BigQuery console with project describe-ngo-lab-2026 selected.
-- Run each statement on its own (select it, then Run), top to bottom.

-- 1) Create the dataset. It must be in the US multi-region, because the
--    World Bank public dataset we read from lives in the US and BigQuery
--    can't join tables across regions.
CREATE SCHEMA IF NOT EXISTS `describe-ngo-lab-2026.ngo_demo`
OPTIONS (
  location = 'US',
  description = 'Describe sample NGO indicator dashboard. Programme figures are SAMPLE data; context indicators are World Bank WDI (public).'
);

-- 2) Check the public World Bank table: column names and how recent it is.
--    Expect columns country_name, country_code, indicator_name,
--    indicator_code, value, year. If the latest year looks old, see the
--    README section "If the World Bank data is out of date".
SELECT column_name, data_type
FROM `bigquery-public-data.world_bank_wdi.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'indicators_data';

SELECT indicator_code, MAX(year) AS latest_year, COUNT(*) AS rows_found
FROM `bigquery-public-data.world_bank_wdi.indicators_data`
WHERE country_code IN ('PSE', 'JOR', 'LBN', 'SYR', 'YEM', 'SDN', 'IRQ', 'EGY')
  AND indicator_code IN ('SP.POP.TOTL', 'SH.DYN.MORT', 'SH.STA.STNT.ZS', 'SH.H2O.BASW.ZS',
                         'SH.STA.BASS.ZS', 'SH.IMM.MEAS', 'SE.PRM.NENR', 'SL.UEM.1524.ZS',
                         'EG.ELC.ACCS.ZS', 'SM.POP.REFG.OR', 'SH.STA.MMRT')
  AND value IS NOT NULL
GROUP BY indicator_code
ORDER BY indicator_code;
