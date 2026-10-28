"""Tag open-ended Arabic survey answers with themes using Gemini on Vertex AI.

Reads a CSV with response_id and answer columns, sends the answers to Gemini
in batches with the codebook, and writes two CSVs ready for BigQuery:

  <out>.csv       one row per answer (themes, sentiment, follow-up flag, summary)
  <out>_long.csv  one row per answer and theme, for counting themes in dashboards

Runs are resumable: answers already in the output file are skipped, so a
crash or a quota error never pays for the same answer twice.

    # offline keyword baseline, no Google Cloud needed
    python tag_responses.py --mock

    # Gemini on Vertex AI (run in Cloud Shell, project describe-ngo-lab)
    python tag_responses.py --project describe-ngo-lab
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

# USD per million tokens, standard tier on the global endpoint (Oct 2026).
# Only used for the cost estimate printed at the end.
PRICES = {
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}

OUT_FIELDS = [
    "response_id", "question_id", "site", "gender", "answer",
    "themes", "primary_theme", "sentiment", "needs_followup",
    "followup_reason", "summary_en", "model", "tagged_at",
]


def load_codebook(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_instructions(codebook):
    lines = [
        "You code open-ended answers from humanitarian surveys for an NGO.",
        "Answers are in Arabic, often in Palestinian, Levantine or Gulf dialect.",
        "For each answer, choose every theme from the codebook that the answer clearly mentions.",
        "Put the most important theme first. Use OTHER only when nothing else fits.",
        "Do not guess beyond what the person wrote.",
        "",
        "Codebook:",
    ]
    for t in codebook["themes"]:
        lines.append(f"- {t['code']} ({t['ar']} / {t['en']}): {t['description']}")
    lines += [
        "",
        "Sentiment is the overall tone toward their situation or the service: "
        + ", ".join(codebook["sentiment"]) + ".",
        codebook["followup_rule"],
        "followup_reason: one short English phrase, empty when needs_followup is false.",
        "summary_en: one short English sentence that a donor report could quote.",
        "Return one result per answer, using the same response_id.",
    ]
    return "\n".join(lines)


def response_schema(codebook):
    codes = [t["code"] for t in codebook["themes"]]
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "response_id": {"type": "STRING"},
                "themes": {"type": "ARRAY", "items": {"type": "STRING", "enum": codes}},
                "sentiment": {"type": "STRING", "enum": codebook["sentiment"]},
                "needs_followup": {"type": "BOOLEAN"},
                "followup_reason": {"type": "STRING"},
                "summary_en": {"type": "STRING"},
            },
            "required": ["response_id", "themes", "sentiment", "needs_followup",
                         "followup_reason", "summary_en"],
        },
    }


class GeminiTagger:
    def __init__(self, project, location, model, codebook):
        from google import genai
        from google.genai import types

        self.client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=build_instructions(codebook),
            response_mime_type="application/json",
            response_schema=response_schema(codebook),
            temperature=0,
        )
        self.tokens_in = 0
        self.tokens_out = 0

    def tag(self, batch):
        payload = [{"response_id": r["response_id"], "question": r.get("question_text", ""),
                    "answer": r["answer"]} for r in batch]
        prompt = "Code these answers:\n" + json.dumps(payload, ensure_ascii=False)
        for attempt in range(5):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=self.config)
                usage = resp.usage_metadata
                self.tokens_in += usage.prompt_token_count or 0
                self.tokens_out += usage.candidates_token_count or 0
                return json.loads(resp.text)
            except Exception as e:  # quota and transient errors: back off and retry
                wait = 2 ** (attempt + 1)
                print(f"  retry in {wait}s after error: {e}", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError("Gemini call failed 5 times; rerun later to resume")

    def cost(self):
        p_in, p_out = PRICES.get(self.model, (0, 0))
        return self.tokens_in / 1e6 * p_in + self.tokens_out / 1e6 * p_out


# Keyword baseline: a cheap, offline stand-in for testing the pipeline, and a
# reference point that shows how much better the model does.
KEYWORDS = {
    "FOOD": ["أكل", "اكل", "طعام", "الطحين", "طحين", "حليب", "خضار", "معلبات", "الغذاء"],
    "CASH": ["نقدي", "نقدية", "كاش", "مصاري", "كوبون", "ديون", "الإيجار", "المبلغ"],
    "SHELTER": ["خيمة", "الخيمة", "شوادر", "فرشات", "أغطية", "بطانيات", "البيت", "ترميم", "الإيجار", "ملابس شتوية"],
    "WASH": ["مياه", "المي", "ماي", "حمام", "الحمامات", "صابون", "فوط", "تنظيف", "حفاضات", "خزان"],
    "HEALTH": ["دواء", "الدواء", "عيادة", "العيادة", "علاج", "سكري", "انسولين", "حامل", "إعاقة", "يمرضون", "ضغط"],
    "EDUCATION": ["مدرسة", "المدرسة", "تعليمية", "دراستهم", "قرطاسية"],
    "LIVELIHOODS": ["شغل", "عمل", "مشروع", "تدريب مهني", "الدخل", "بشتغل"],
    "ENERGY": ["كهرباء", "الكهرباء", "غاز", "طاقة شمسية", "حطب", "إضاءة", "إنترنت"],
    "PROTECTION": ["خطر", "آمن", "مفقود", "تزويج", "بيخافوا", "عراك", "الأوراق الثبوتية"],
    "MENTAL_HEALTH": ["نفسي", "نفسيًا", "تخاف", "عصبي"],
    "DISTRIBUTION": ["الطابور", "التوزيع", "القوائم", "الكشف", "التسجيل", "واسطة", "نقطة التوزيع"],
    "INFORMATION": ["بلغنا", "الرقم", "رسائل", "الرسائل", "المعايير", "شكوى", "اسألونا", "بتسألونا"],
    "STAFF_CONDUCT": ["الموظف", "الموظفين", "المتطوعين", "المتطوعات", "صرخ"],
    "AID_QUALITY": ["ما بكفي", "الكمية", "منتهية الصلاحية", "مقاس", "مقاسات"],
    "APPRECIATION": ["شكرًا", "شكرا", "الله يجزيكم", "الحمد لله", "منيح", "أحسن"],
}


class KeywordTagger:
    model = "keyword-baseline"

    def tag(self, batch):
        out = []
        for r in batch:
            text = r["answer"]
            themes = [c for c, words in KEYWORDS.items() if any(w in text for w in words)]
            out.append({
                "response_id": r["response_id"],
                "themes": themes or ["OTHER"],
                "sentiment": "positive" if "APPRECIATION" in themes else "neutral",
                "needs_followup": False,
                "followup_reason": "",
                "summary_en": "",
            })
        return out

    def cost(self):
        return 0.0


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def chunks(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def write_long(tagged_path, long_path, codebook):
    labels = {t["code"]: t for t in codebook["themes"]}
    with open(long_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["response_id", "question_id", "site", "gender", "theme_code",
                    "theme_ar", "theme_en", "theme_rank", "sentiment", "needs_followup"])
        for r in read_rows(tagged_path):
            for rank, code in enumerate(filter(None, r["themes"].split(";")), start=1):
                t = labels.get(code, {"ar": code, "en": code})
                w.writerow([r["response_id"], r["question_id"], r["site"], r["gender"], code,
                            t["ar"], t["en"], rank, r["sentiment"], r["needs_followup"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=HERE / "data" / "sample_responses.csv")
    ap.add_argument("--codebook", default=HERE / "codebook.json")
    ap.add_argument("--out", default=None, help="output CSV (default: data/tagged_<model>.csv)")
    ap.add_argument("--project", help="Google Cloud project id, e.g. describe-ngo-lab")
    ap.add_argument("--location", default="global")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--limit", type=int, help="only tag the first N answers (for a cheap test)")
    ap.add_argument("--mock", action="store_true", help="use the offline keyword baseline")
    args = ap.parse_args()

    codebook = load_codebook(args.codebook)
    valid = {t["code"] for t in codebook["themes"]}

    if args.mock:
        tagger = KeywordTagger()
    else:
        if not args.project:
            ap.error("--project is required unless --mock is used")
        tagger = GeminiTagger(args.project, args.location, args.model, codebook)

    out = Path(args.out or HERE / "data" / f"tagged_{tagger.model}.csv")
    rows = [r for r in read_rows(args.input) if r.get("answer", "").strip()]
    if args.limit:
        rows = rows[:args.limit]

    done = {r["response_id"] for r in read_rows(out)} if out.exists() else set()
    todo = [r for r in rows if r["response_id"] not in done]
    print(f"{len(rows)} answers, {len(done)} already tagged, {len(todo)} to tag with {tagger.model}")

    new_file = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if new_file:
            w.writeheader()
        for batch in chunks(todo, args.batch_size):
            results = {str(x.get("response_id")): x for x in tagger.tag(batch)}
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for r in batch:
                res = results.get(r["response_id"])
                if res is None:
                    print(f"  {r['response_id']}: no result returned, will retry next run", file=sys.stderr)
                    continue
                themes = [c for c in res.get("themes", []) if c in valid] or ["OTHER"]
                themes = list(dict.fromkeys(themes))
                w.writerow({
                    "response_id": r["response_id"],
                    "question_id": r.get("question_id", ""),
                    "site": r.get("site", ""),
                    "gender": r.get("gender", ""),
                    "answer": r["answer"],
                    "themes": ";".join(themes),
                    "primary_theme": themes[0],
                    "sentiment": res.get("sentiment", ""),
                    "needs_followup": int(bool(res.get("needs_followup"))),
                    "followup_reason": re.sub(r"\s+", " ", res.get("followup_reason", "")).strip(),
                    "summary_en": re.sub(r"\s+", " ", res.get("summary_en", "")).strip(),
                    "model": tagger.model,
                    "tagged_at": now,
                })
            f.flush()
            print(f"  tagged {len(batch)} answers")

    long_path = out.with_name(out.stem + "_long.csv")
    write_long(out, long_path, codebook)
    print(f"Wrote {out} and {long_path}")
    if not args.mock:
        print(f"Tokens: {tagger.tokens_in} in, {tagger.tokens_out} out, about ${tagger.cost():.4f}")


if __name__ == "__main__":
    main()
