# Build the dashboard in Looker Studio

Looker Studio is free and needs no trial. Build the English pages first, then
duplicate them for Arabic. Allow about an hour.

**Brand colours (Describe chart kit):** ink `#092052`, highlight blue `#0F58E5`,
context grey `#64748B`, rule `#D8E1EF`, good `#0F7B3D`, bad `#8C1D1D`,
alert `#E5484D`. Background white; fonts: Readex Pro if available, else Roboto.

## 1. Connect the data

1. Go to <https://lookerstudio.google.com> → **Create → Report**.
2. Choose **BigQuery** → **My projects** → `describe-ngo-lab` → `ngo_demo`.
3. Add these five sources (Resource → Manage added data sources → Add):
   `v_progress_by_indicator`, `v_progress_by_governorate`, `v_reach_detail`,
   `context_indicators`, `v_context_latest`.
4. In each source, set `pct_of_target` and `pct_of_expected` to type **Percent**,
   and `lat_long` to **Geo → Latitude, Longitude**.
5. Theme and layout → Customize → set the colours above. Canvas 1200 × 900.

## 2. Page "Programme overview"

- **Header band** (ink background, white text): "Sample Emergency Response
  Programme 2026 · Indicator tracker". Right side, a small rounded label in
  alert red: **"Sample data, for demonstration"**. Keep it on every page.
- **Scorecards** (from `v_progress_by_indicator`): count of indicators where
  `status_en = On track` (add a filter), the same for `Behind`, and
  `last_month` formatted as "Month YYYY" with the label "Data up to".
- **Indicator table** (`v_progress_by_indicator`): dimensions `sector_en`,
  `indicator_en`, `unit_en`; metrics `target`, `reached`, `pct_of_target`
  (show as **bar**, bar colour blue, max 100%), `status_en`.
  Conditional formatting on `status_en`: On track → green text,
  Slightly behind → `#B26B00`, Behind → red.
- **Controls** at the top: drop-down on `sector_en`.
- Footnote: "Expected so far = annual target × months reported ÷ 12. On track ≥ 95% of expected."

## 3. Page "By governorate"

- **Bubble map** (Google Maps, `v_progress_by_governorate`): location `lat_long`,
  tooltip `governorate_en`, size `reached`, colour by `status_en`.
  Add a drop-down control on `indicator_en` (default WASH-1) so the map shows one indicator at a time.
- **Pivot table / heatmap**: rows `governorate_en`, columns `indicator_code`,
  metric `pct_of_expected`, heatmap colouring (red → white → green, mid at 95%).
  This is the "where are we falling behind" view NGOs ask for.

## 4. Page "Trends and who we reach"

All from `v_reach_detail`, with a drop-down on `indicator_en` and one on `governorate_en`.

- **Time series**: dimension `month`, metric `SUM(value)`, one line, blue.
  Optional: a second series "cumulative" (Style → Cumulative).
- **Stacked bar by sex**: dimension `governorate_en`, breakdown `sex_en`, metric `value`, 100% stacked.
- **Bar by age group**: dimension `age_group_en`, metric `value`.
  (Indicators without disaggregation show "Not disaggregated"; add a filter
  `sex_en != Not disaggregated` on these two charts.)

## 5. Page "Country context"

- **Table** (`v_context_latest`): `country_en`, `indicator_en`, `year`, `value`,
  `direction_en` (green for Improved, red for Worsened). Drop-down on `sector_en`.
- **Time series** (`context_indicators`): dimension `year_date`, breakdown
  `country_en`, metric `value`, with a drop-down on `indicator_en`
  (default "Under-5 mortality"). Colour Palestine blue `#0F58E5`, all other
  countries grey `#64748B`, so the story country stands out.
- Source line: "Source: World Bank, World Development Indicators, via BigQuery public datasets."

## 6. Arabic pages

1. Right-click each page → **Duplicate page**, rename e.g. "نظرة عامة على البرنامج".
2. In every chart and control, swap each `_en` field for its `_ar` twin
   (`indicator_ar`, `sector_ar`, `governorate_ar`, `status_ar`, `sex_ar`,
   `age_group_ar`, `country_ar`, `direction_ar`). Conditional formatting on
   status uses the Arabic values: على المسار / متأخر قليلاً / متأخر.
3. Translate titles and the header by hand. Right-align text boxes; put the
   page navigation on the right. Looker Studio has no RTL switch, so mirror
   the layout manually (table on the right, controls at the top right).
4. Add a page-navigation bar with "English | العربية".

## 7. Share it

- **Share → Manage access → Anyone with the link can view** for the portfolio link.
  Viewers see the data with your credentials, so only share views of sample or public data this way.
- Add Obaida as **Editor** by email.
- **File → Download → PDF** for a static copy, and take screenshots of each
  page for the portfolio and the diagnostic pitch.
