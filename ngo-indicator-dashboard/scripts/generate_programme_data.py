"""Generate the SAMPLE programme data for the NGO indicator dashboard.

All programme figures are made up (fixed random seed) so the dashboard can be
shown publicly. They are labelled as sample data everywhere they appear.

Writes:
  data/governorates.csv
  data/indicators.csv
  data/targets.csv
  data/monthly_reach.csv
  sql/03_load_programme_data.sql   (one file that creates and fills the tables)

Run from the ngo-indicator-dashboard folder:  python scripts/generate_programme_data.py
"""
import csv
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SQL = ROOT / "sql"
DATASET = "describe-ngo-lab-2026.ngo_demo"

random.seed(2026)

PROGRAMME = "Sample Emergency Response Programme 2026"

# code, English, Arabic, latitude, longitude, share of total target
GOVERNORATES = [
    ("NG", "North Gaza", "شمال غزة", 31.5450, 34.5000, 0.17),
    ("GZ", "Gaza", "غزة", 31.5017, 34.4668, 0.30),
    ("DB", "Deir al-Balah", "دير البلح", 31.4181, 34.3517, 0.18),
    ("KY", "Khan Younis", "خان يونس", 31.3462, 34.3061, 0.23),
    ("RF", "Rafah", "رفح", 31.2969, 34.2455, 0.12),
]

# code, sector_en, sector_ar, name_en, name_ar, unit_en, unit_ar,
# disaggregated (sex/age), annual target, expected performance (1.0 = on pace)
INDICATORS = [
    ("WASH-1", "Water, sanitation and hygiene", "المياه والصرف الصحي والنظافة",
     "People reached with safe drinking water", "عدد الأشخاص الذين حصلوا على مياه شرب آمنة",
     "people", "شخص", True, 120000, 1.05),
    ("WASH-2", "Water, sanitation and hygiene", "المياه والصرف الصحي والنظافة",
     "Hygiene kits distributed", "عدد حقائب النظافة الموزعة",
     "kits", "حقيبة", False, 30000, 0.92),
    ("FS-1", "Food security", "الأمن الغذائي",
     "Households receiving food parcels", "عدد الأسر التي استلمت طروداً غذائية",
     "households", "أسرة", False, 25000, 0.97),
    ("FS-2", "Food security", "الأمن الغذائي",
     "Multipurpose cash disbursed", "المساعدات النقدية متعددة الأغراض المصروفة",
     "USD", "دولار أمريكي", False, 1500000, 0.68),
    ("EDU-1", "Education", "التعليم",
     "Children attending temporary learning spaces", "عدد الأطفال الملتحقين بمساحات التعلم المؤقتة",
     "children", "طفل", True, 18000, 0.81),
    ("PSS-1", "Child protection", "حماية الطفل",
     "Children receiving psychosocial support", "عدد الأطفال الذين تلقوا دعماً نفسياً اجتماعياً",
     "children", "طفل", True, 12000, 1.10),
    ("HLT-1", "Health", "الصحة",
     "Medical consultations provided", "عدد الاستشارات الطبية المقدمة",
     "consultations", "استشارة", True, 60000, 0.88),
]

SEXES = [("F", "Female", "إناث"), ("M", "Male", "ذكور")]
# Age groups differ by indicator: children-only indicators use the child bands.
AGE_ALL = [("0-17", "Children (0-17)", "أطفال (0-17)", 0.48),
           ("18-59", "Adults (18-59)", "بالغون (18-59)", 0.44),
           ("60+", "Older people (60+)", "كبار السن (60+)", 0.08)]
AGE_CHILD = [("0-5", "Young children (0-5)", "أطفال صغار (0-5)", 0.25),
             ("6-11", "Children (6-11)", "أطفال (6-11)", 0.45),
             ("12-17", "Adolescents (12-17)", "يافعون (12-17)", 0.30)]
CHILD_ONLY = {"EDU-1", "PSS-1"}

MONTHS = [date(2026, m, 1) for m in range(1, 10)]  # Jan-Sep 2026 reported so far


def split(total, weights):
    """Split an integer total by weights, keeping the sum exact."""
    raw = [total * w for w in weights]
    parts = [int(r) for r in raw]
    rest = total - sum(parts)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - parts[i], reverse=True)
    for i in order[:rest]:
        parts[i] += 1
    return parts


def main():
    DATA.mkdir(exist_ok=True)
    gov_rows, ind_rows, target_rows, reach_rows = [], [], [], []

    for code, en, ar, lat, lon, _ in GOVERNORATES:
        gov_rows.append({"governorate_code": code, "governorate_en": en,
                         "governorate_ar": ar, "latitude": lat, "longitude": lon,
                         "lat_long": f"{lat},{lon}"})

    for (code, sec_en, sec_ar, name_en, name_ar, unit_en, unit_ar,
         disagg, target, pace) in INDICATORS:
        ind_rows.append({"indicator_code": code, "sector_en": sec_en, "sector_ar": sec_ar,
                         "indicator_en": name_en, "indicator_ar": name_ar,
                         "unit_en": unit_en, "unit_ar": unit_ar,
                         "disaggregated": str(disagg).lower(), "annual_target": target})

        gov_targets = split(target, [g[5] for g in GOVERNORATES])
        for (g_code, *_), g_target in zip(GOVERNORATES, gov_targets):
            target_rows.append({"programme": PROGRAMME, "year": 2026,
                                "indicator_code": code, "governorate_code": g_code,
                                "target": g_target})

            # Slow start, then ramp up; each governorate performs a bit differently.
            gov_pace = pace * random.uniform(0.85, 1.12)
            ramp = [0.45, 0.65, 0.85, 1.0, 1.05, 1.1, 1.1, 1.15, 1.15]
            for month, r in zip(MONTHS, ramp):
                month_value = round(g_target / 12 * gov_pace * r * random.uniform(0.85, 1.15))
                if not disagg:
                    reach_rows.append({"month": month.isoformat(), "indicator_code": code,
                                       "governorate_code": g_code, "sex": "", "age_group": "",
                                       "value": month_value})
                    continue
                ages = AGE_CHILD if code in CHILD_ONLY else AGE_ALL
                female_share = random.uniform(0.49, 0.56)
                for s_code, (sex_part) in zip(["F", "M"], split(month_value, [female_share, 1 - female_share])):
                    for (a_code, *_ , a_w), part in zip(ages, split(sex_part, [a[3] for a in ages])):
                        reach_rows.append({"month": month.isoformat(), "indicator_code": code,
                                           "governorate_code": g_code, "sex": s_code,
                                           "age_group": a_code, "value": part})

    write_csv(DATA / "governorates.csv", gov_rows)
    write_csv(DATA / "indicators.csv", ind_rows)
    write_csv(DATA / "targets.csv", target_rows)
    write_csv(DATA / "monthly_reach.csv", reach_rows)
    write_sql(gov_rows, ind_rows, target_rows, reach_rows)
    print(f"{len(reach_rows)} reach rows, {len(target_rows)} target rows")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def q(v):
    if v is None or v == "":
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def write_sql(gov_rows, ind_rows, target_rows, reach_rows):
    age_rows = ([{"age_group": a[0], "age_group_en": a[1], "age_group_ar": a[2]} for a in AGE_ALL]
                + [{"age_group": a[0], "age_group_en": a[1], "age_group_ar": a[2]} for a in AGE_CHILD])
    sex_rows = [{"sex": s[0], "sex_en": s[1], "sex_ar": s[2]} for s in SEXES]

    out = [
        "-- 03_load_programme_data.sql",
        "-- SAMPLE programme data (made up, for demonstration only). Generated by",
        "-- scripts/generate_programme_data.py; edit the script, not this file.",
        "-- Run the whole file once in the BigQuery console (project describe-ngo-lab-2026).",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.dim_governorate` (",
        "  governorate_code STRING, governorate_en STRING, governorate_ar STRING,",
        "  latitude FLOAT64, longitude FLOAT64, lat_long STRING);",
        f"INSERT INTO `{DATASET}.dim_governorate` VALUES",
        ",\n".join(f"  ({q(r['governorate_code'])}, {q(r['governorate_en'])}, {q(r['governorate_ar'])}, "
                   f"{r['latitude']}, {r['longitude']}, {q(r['lat_long'])})" for r in gov_rows) + ";",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.dim_indicator` (",
        "  indicator_code STRING, sector_en STRING, sector_ar STRING, indicator_en STRING,",
        "  indicator_ar STRING, unit_en STRING, unit_ar STRING, disaggregated BOOL, annual_target INT64);",
        f"INSERT INTO `{DATASET}.dim_indicator` VALUES",
        ",\n".join(f"  ({q(r['indicator_code'])}, {q(r['sector_en'])}, {q(r['sector_ar'])}, "
                   f"{q(r['indicator_en'])}, {q(r['indicator_ar'])}, {q(r['unit_en'])}, "
                   f"{q(r['unit_ar'])}, {r['disaggregated'].upper()}, {r['annual_target']})"
                   for r in ind_rows) + ";",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.dim_sex` (sex STRING, sex_en STRING, sex_ar STRING);",
        f"INSERT INTO `{DATASET}.dim_sex` VALUES",
        ",\n".join(f"  ({q(r['sex'])}, {q(r['sex_en'])}, {q(r['sex_ar'])})" for r in sex_rows) + ";",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.dim_age_group` (age_group STRING, age_group_en STRING, age_group_ar STRING);",
        f"INSERT INTO `{DATASET}.dim_age_group` VALUES",
        ",\n".join(f"  ({q(r['age_group'])}, {q(r['age_group_en'])}, {q(r['age_group_ar'])})" for r in age_rows) + ";",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.fact_target` (",
        "  programme STRING, year INT64, indicator_code STRING, governorate_code STRING, target INT64);",
        f"INSERT INTO `{DATASET}.fact_target` VALUES",
        ",\n".join(f"  ({q(r['programme'])}, {r['year']}, {q(r['indicator_code'])}, "
                   f"{q(r['governorate_code'])}, {r['target']})" for r in target_rows) + ";",
        "",
        f"CREATE OR REPLACE TABLE `{DATASET}.fact_monthly_reach` (",
        "  month DATE, indicator_code STRING, governorate_code STRING, sex STRING,",
        "  age_group STRING, value INT64);",
        f"INSERT INTO `{DATASET}.fact_monthly_reach` VALUES",
        ",\n".join(f"  (DATE {q(r['month'])}, {q(r['indicator_code'])}, {q(r['governorate_code'])}, "
                   f"{q(r['sex'])}, {q(r['age_group'])}, {r['value']})" for r in reach_rows) + ";",
        "",
    ]
    (SQL / "03_load_programme_data.sql").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
