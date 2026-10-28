"""Score a tagged file against hand-coded gold labels.

    python evaluate.py data/tagged_gemini-3.8-flash.csv
    python evaluate.py data/tagged_keyword-baseline.csv

Prints overall agreement and per-theme precision and recall, plus the answers
where the tagger and the human coder disagree most, so the codebook can be
tightened before running a client's real data.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["response_id"]: r for r in csv.DictReader(f)}


def themes(r):
    return set(filter(None, r["themes"].split(";")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tagged")
    ap.add_argument("--gold", default=HERE / "data" / "gold_labels.csv")
    args = ap.parse_args()

    gold, pred = load(args.gold), load(args.tagged)
    ids = [i for i in gold if i in pred]
    if not ids:
        raise SystemExit("No overlapping response_ids between the files")

    tp, fp, fn = Counter(), Counter(), Counter()
    jaccard, primary_hit, sentiment_hit = [], 0, 0
    followup_gold = followup_caught = followup_false = 0
    misses = []
    for i in ids:
        g, p = themes(gold[i]), themes(pred[i])
        for c in g & p:
            tp[c] += 1
        for c in p - g:
            fp[c] += 1
        for c in g - p:
            fn[c] += 1
        j = len(g & p) / len(g | p)
        jaccard.append(j)
        primary_hit += pred[i]["primary_theme"] in g
        sentiment_hit += pred[i]["sentiment"] == gold[i]["sentiment"]
        gf, pf = gold[i]["needs_followup"] == "1", pred[i]["needs_followup"] == "1"
        followup_gold += gf
        followup_caught += gf and pf
        followup_false += pf and not gf
        misses.append((j, i, g, p))

    n = len(ids)
    print(f"Answers scored: {n}")
    print(f"Theme overlap (Jaccard), mean: {sum(jaccard) / n:.0%}")
    print(f"Exact theme match:             {sum(j == 1 for j in jaccard) / n:.0%}")
    print(f"Primary theme is a gold theme: {primary_hit / n:.0%}")
    print(f"Sentiment match:               {sentiment_hit / n:.0%}")
    print(f"Follow-up cases caught:        {followup_caught} of {followup_gold} "
          f"({followup_false} flagged that the coder did not)")
    print()
    print(f"{'theme':<15}{'precision':>10}{'recall':>8}{'gold n':>8}")
    for c in sorted(set(tp) | set(fp) | set(fn)):
        prec = tp[c] / (tp[c] + fp[c]) if tp[c] + fp[c] else 0
        rec = tp[c] / (tp[c] + fn[c]) if tp[c] + fn[c] else 0
        print(f"{c:<15}{prec:>10.0%}{rec:>8.0%}{tp[c] + fn[c]:>8}")
    print()
    print("Biggest disagreements:")
    for j, i, g, p in sorted(misses)[:8]:
        print(f"  {i} gold={';'.join(sorted(g))} tagged={';'.join(sorted(p))}")


if __name__ == "__main__":
    main()
