"""Make three made-up NGO survey exports with realistic problems planted in them.

  python samples/make_samples.py

Writes samples/kobo_household_survey.xlsx, samples/google_forms_feedback.csv and
samples/excel_beneficiary_register.xlsx. Every name, ID and answer is invented.
The planted problems are listed in samples/README.md, so the checks can be
tested against a known answer.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EASTERN = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def kobo(rng: random.Random, n: int = 420) -> pd.DataFrame:
    govs = ["Khan Younis", "Rafah", "Deir al-Balah", "Gaza", "North Gaza"]
    sources = ["casual_labour", "assistance", "small_business", "none", "salary"]
    enums = [f"enum_{i:02d}" for i in range(1, 11)]
    rows = []
    day0 = datetime(2026, 9, 14, 8, 0)
    for i in range(n):
        enum = rng.choice(enums)
        start = day0 + timedelta(days=rng.randint(0, 27), minutes=rng.randint(0, 540))
        minutes = rng.uniform(14, 35)
        if enum == "enum_07" and rng.random() < 0.55:
            minutes = rng.uniform(1.5, 4.5)               # rushed interviews
        end = start + timedelta(minutes=minutes)
        received = rng.random() < 0.6
        income = rng.choice([0, 200, 350, 500, 800, 1200, 1500]) + rng.randint(0, 99)
        rows.append({
            "start": start.strftime("%Y-%m-%dT%H:%M:%S.000+03:00"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S.000+03:00"),
            "today": start.strftime("%Y-%m-%d"),
            "deviceid": f"collect:{rng.randint(10**9, 10**10)}",
            "enumerator": enum,
            "consent/consent": "yes",
            "respondent/beneficiary_id": f"HH-{10000 + i}",
            "respondent/governorate": rng.choice(govs),
            "respondent/gender": rng.choice(["female", "female", "male"]),
            "respondent/age": rng.randint(18, 78),
            "respondent/hh_size": rng.randint(1, 12),
            "respondent/disability": rng.choice(["no", "no", "no", "yes"]),
            "livelihood/main_income_source": rng.choice(sources),
            "livelihood/income_last_month": income,
            "livelihood/other_income_specify": None,
            "food/fcs_score": rng.randint(12, 90),
            "food/meals_yesterday": rng.choice([1, 2, 2, 3]),
            "assistance/received_cash": "yes" if received else "no",
            "assistance/cash_amount": rng.choice([300, 500, 700]) if received else None,
            "feedback/comments": rng.choice(["", "", "المساعدة تأخرت هذا الشهر",
                                             "نحتاج مساعدة غذائية", "شكرا", ""]),
        })
    df = pd.DataFrame(rows).astype(object)

    def pick(k, mask=None):
        pool = list(df.index if mask is None else df.index[mask])
        return rng.sample(pool, k)

    # Same answer written several ways.
    for i in pick(22):
        df.at[i, "respondent/gender"] = rng.choice(["Female", "F", "أنثى", "female ", "Male"])
    for i in pick(30):
        df.at[i, "respondent/governorate"] = rng.choice(
            ["khan younis", "Khan  Younis", "Deir Al Balah", "Deir al Balah", "rafah "])
    # Numbers typed with Arabic-Indic digits, impossible values and text.
    for i in pick(14):
        df.at[i, "respondent/hh_size"] = str(df.at[i, "respondent/hh_size"]).translate(EASTERN)
    for i in pick(6):
        df.at[i, "respondent/age"] = str(df.at[i, "respondent/age"]).translate(EASTERN)
    for i in pick(3):
        df.at[i, "respondent/age"] = rng.choice([250, 340, 0])
    for i in pick(9):
        df.at[i, "livelihood/income_last_month"] = rng.choice(["500 NIS", "unknown", "لا أعرف"])
    for i in pick(int(n * 0.31)):
        df.at[i, "livelihood/income_last_month"] = None
    for i in pick(int(n * 0.08)):
        df.at[i, "food/fcs_score"] = None
    # One data collector leaves many more blanks.
    for i in df.index[df.enumerator == "enum_07"]:
        if rng.random() < 0.6:
            for col in ("food/meals_yesterday", "respondent/disability", "food/fcs_score"):
                df.at[i, col] = None
    # Contradictions: no cash received but an amount recorded.
    for i in pick(6, df["assistance/received_cash"] == "no"):
        df.at[i, "assistance/cash_amount"] = 500
    # Gender left blank on a few records.
    for i in pick(7):
        df.at[i, "respondent/gender"] = None
    # Two families given the same ID.
    for a, b in zip(pick(4), pick(4)):
        if a != b:
            df.at[b, "respondent/beneficiary_id"] = df.at[a, "respondent/beneficiary_id"]
    # Phone clock wrong, and test submissions from before fieldwork.
    for i in pick(3):
        df.at[i, "today"] = "2027-09-30"
    tests = df.sample(5, random_state=1).copy()
    tests["today"] = "2026-09-02"
    tests["respondent/beneficiary_id"] = [f"TEST-{k}" for k in range(5)]
    # The form sent twice from the same phone.
    copies = df.sample(6, random_state=2).copy()
    df = pd.concat([df, tests, copies], ignore_index=True)

    df["_id"] = range(500100, 500100 + len(df))
    df["_uuid"] = [str(uuid.UUID(int=rng.getrandbits(128))) for _ in range(len(df))]
    df["_submission_time"] = [(datetime(2026, 9, 14) + timedelta(days=rng.randint(0, 28)))
                              .strftime("%Y-%m-%dT%H:%M:%S") for _ in range(len(df))]
    df["_validation_status"] = None
    df["_index"] = range(1, len(df) + 1)
    return df.sample(frac=1, random_state=3).reset_index(drop=True)


def google_forms(rng: random.Random, n: int = 160) -> pd.DataFrame:
    rows = []
    for i in range(n):
        ts = datetime(2026, 10, 1, 9) + timedelta(hours=rng.randint(0, 600))
        rows.append({
            "Timestamp": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "Phone number": f"059{rng.randint(1000000, 9999999)}",
            "Gender / الجنس": rng.choice(["Female", "Male", "Female"]),
            "Age": rng.randint(18, 70),
            "Which centre did you visit?": rng.choice(["Al Nour Centre", "Al Amal Centre",
                                                       "Mobile clinic"]),
            "How satisfied are you with the service? (1-5)": rng.randint(1, 5),
            "Did staff treat you with respect?": rng.choice(["Yes", "Yes", "No"]),
            "Anything else you want to tell us?": rng.choice(["", "", "شكرا لكم",
                                                              "Long waiting time", ""]),
        })
    df = pd.DataFrame(rows).astype(object)
    for i in rng.sample(range(n), 10):
        df.at[i, "Gender / الجنس"] = rng.choice(["female", "أنثى", "ذكر", "M"])
    for i in rng.sample(range(n), 6):
        df.at[i, "Which centre did you visit?"] = rng.choice(["al nour centre", "Al-Nour Centre"])
    for i in rng.sample(range(n), 4):
        df.at[i, "How satisfied are you with the service? (1-5)"] = rng.choice([7, 0, "٤"])
    for i in rng.sample(range(n), 50):
        df.at[i, "Age"] = None
    copies = df.sample(4, random_state=4).copy()
    copies["Timestamp"] = [(datetime(2026, 10, 20, 10) + timedelta(minutes=k))
                           .strftime("%m/%d/%Y %H:%M:%S") for k in range(4)]
    return pd.concat([df, copies], ignore_index=True)


def excel_register(rng: random.Random, n: int = 240) -> pd.DataFrame:
    first = ["أحمد", "محمد", "فاطمة", "مريم", "يوسف", "سارة", "علي", "هدى", "خالد", "آمنة"]
    last = ["سالم", "حسن", "عوض", "منصور", "داود", "شاهين", "نصار", "عيسى"]
    rows = []
    for i in range(n):
        rows.append({
            "الاسم": f"{rng.choice(first)} {rng.choice(last)}",
            "رقم الهوية": str(400000000 + rng.randint(0, 99999999)),
            "الجنس": rng.choice(["أنثى", "ذكر", "أنثى"]),
            "العمر": rng.randint(1, 85),
            "المحافظة": rng.choice(["خان يونس", "رفح", "دير البلح", "غزة"]),
            "عدد افراد الاسرة": rng.randint(1, 11),
            "تاريخ التسجيل": (datetime(2026, 8, 1) + timedelta(days=rng.randint(0, 80)))
            .strftime("%d/%m/%Y"),
            "ملاحظات": "",
        })
    df = pd.DataFrame(rows).astype(object)
    for i in rng.sample(range(n), 12):
        df.at[i, "المحافظة"] = rng.choice(["خانيونس", "خان يونس ", "دير  البلح"])
    for i in rng.sample(range(n), 8):
        df.at[i, "الجنس"] = rng.choice(["انثى", "انثي", "Female"])
    for i in rng.sample(range(n), 10):
        df.at[i, "عدد افراد الاسرة"] = str(df.at[i, "عدد افراد الاسرة"]).translate(EASTERN)
    for a, b in zip(rng.sample(range(n), 5), rng.sample(range(n), 5)):
        if a != b:
            df.at[b, "رقم الهوية"] = df.at[a, "رقم الهوية"]
    for i in rng.sample(range(n), 3):
        df.at[i, "تاريخ التسجيل"] = "15/03/2027"
    return df


def main() -> None:
    rng = random.Random(2026)
    k = kobo(rng)
    with pd.ExcelWriter(HERE / "kobo_household_survey.xlsx") as xl:
        k.to_excel(xl, sheet_name="Household survey 2026", index=False)
    google_forms(rng).to_csv(HERE / "google_forms_feedback.csv", index=False,
                             encoding="utf-8-sig")
    with pd.ExcelWriter(HERE / "excel_beneficiary_register.xlsx") as xl:
        excel_register(rng).to_excel(xl, sheet_name="السجل", index=False)
    print("Wrote 3 sample files to", HERE)


if __name__ == "__main__":
    main()
