# Sample exports

Made-up NGO data with problems planted on purpose, so the checks can be shown
and tested. Every name, ID and answer is invented. Rebuild them with
`python samples/make_samples.py` (same output every time).

| File | Looks like | Planted problems |
|---|---|---|
| `kobo_household_survey.xlsx` | KoboToolbox XLS export (group paths, `_uuid`, `start`/`end`) | 6 resubmitted forms, 4 shared household IDs, gender and governorate spelled several ways (incl. Arabic), Arabic-Indic digits in age and household size, impossible ages, text in the income column, 31% blank income, 3 future dates, 5 test submissions before fieldwork, rushed interviews by one data collector (`enum_07`) who also leaves more blanks, 6 "no cash received" with an amount, one empty column |
| `google_forms_feedback.csv` | Google Forms CSV (`Timestamp` first, questions as headers) | 4 double submissions, mixed gender spellings in two languages, centre names spelled 3 ways, satisfaction scores outside 1-5 and in Arabic digits, 30% blank age |
| `excel_beneficiary_register.xlsx` | Hand-kept Excel register with Arabic headers | 5 shared ID numbers, governorate and gender spelling variants, Arabic-Indic digits in family size, 3 registration dates in 2027, an empty notes column |

`configs/example-kobo-household.yaml` is the client settings file for the Kobo sample.
