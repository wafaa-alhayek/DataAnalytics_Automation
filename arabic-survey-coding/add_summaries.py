"""Add English summaries to a file tagged by a decision model (Jev or Laya).

Decision models pick themes and flags but cannot write text. This second step
sends each answer, with the themes already chosen, to Gemini on Vertex AI and
fills summary_en, plus followup_reason for flagged answers. Themes, sentiment
and flags are not changed. Rows that already have a summary are skipped.

    python add_summaries.py data/tagged_jev-latest.csv --project describe-ngo-lab-2026
"""

import argparse
import csv
import json
import re
import sys
import time

from tag_responses import OUT_FIELDS, PRICES

INSTRUCTIONS = """You write short English summaries of Arabic humanitarian survey answers
(often Palestinian, Levantine or Gulf dialect) for an NGO report.
Each item already has its themes chosen; do not change them.
summary_en: one short English sentence a donor report could quote, faithful to the answer.
followup_reason: only for items with needs_followup = 1, one short English phrase saying why
a trained staff member must read it; otherwise an empty string.
Return one result per item, using the same response_id."""

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "response_id": {"type": "STRING"},
            "summary_en": {"type": "STRING"},
            "followup_reason": {"type": "STRING"},
        },
        "required": ["response_id", "summary_en", "followup_reason"],
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tagged", help="tagged CSV from tag_responses.py")
    ap.add_argument("--project", required=True, help="Google Cloud project id")
    ap.add_argument("--location", default="global")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--batch-size", type=int, default=20)
    args = ap.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=args.project, location=args.location)
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCTIONS,
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=0,
    )

    with open(args.tagged, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    todo = [r for r in rows if not r["summary_en"].strip()]
    print(f"{len(rows)} rows, {len(todo)} need a summary")

    tokens_in = tokens_out = 0
    for i in range(0, len(todo), args.batch_size):
        batch = todo[i:i + args.batch_size]
        payload = [{"response_id": r["response_id"], "answer": r["answer"], "themes": r["themes"],
                    "needs_followup": r["needs_followup"]} for r in batch]
        prompt = "Summarise these answers:\n" + json.dumps(payload, ensure_ascii=False)
        for attempt in range(5):
            try:
                resp = client.models.generate_content(model=args.model, contents=prompt, config=config)
                break
            except Exception as e:  # quota and transient errors: back off and retry
                wait = 2 ** (attempt + 1)
                print(f"  retry in {wait}s after error: {e}", file=sys.stderr)
                time.sleep(wait)
        else:
            raise SystemExit("Gemini call failed 5 times; rerun later to resume")
        tokens_in += resp.usage_metadata.prompt_token_count or 0
        tokens_out += resp.usage_metadata.candidates_token_count or 0
        results = {str(x.get("response_id")): x for x in json.loads(resp.text)}
        for r in batch:
            res = results.get(r["response_id"], {})
            r["summary_en"] = re.sub(r"\s+", " ", res.get("summary_en", "")).strip()
            if r["needs_followup"] == "1":
                r["followup_reason"] = re.sub(r"\s+", " ", res.get("followup_reason", "")).strip()
            r["model"] = f"{r['model']}+{args.model}"
        print(f"  summarised {len(batch)} answers")

        # Save after every batch so a crash keeps the work done so far.
        with open(args.tagged, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
            w.writeheader()
            w.writerows(rows)

    p_in, p_out = PRICES.get(args.model, (0, 0))
    print(f"Tokens: {tokens_in} in, {tokens_out} out, about ${tokens_in / 1e6 * p_in + tokens_out / 1e6 * p_out:.4f}")


if __name__ == "__main__":
    main()
