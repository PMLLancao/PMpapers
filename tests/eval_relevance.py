"""Measure ranking signals on the labelled set (tests/relevance_eval.json).

AUC = probability that a random Good paper outranks a random Bad paper (0.5 = coin flip).
Run: PAPERSCOPE_SEMANTIC=0 python tests/eval_relevance.py
Use this BEFORE changing ranking weights or the semantic model, and report the numbers in Issue #1.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_literature as u

def auc(pairs):
    g = [s for s, l in pairs if l == "G"]; b = [s for s, l in pairs if l == "B"]
    if not g or not b: return float("nan")
    wins = sum((x > y) + 0.5 * (x == y) for x in g for y in b)
    return wins / (len(g) * len(b))

items = json.loads((ROOT / "tests" / "relevance_eval.json").read_text())["items"]
rows = []
for it in items:
    p = {"title": it["title"], "abstract": it["abstract"], "journal": it["journal"], "date": u.NOW.date().isoformat()}
    sec = it["section"]
    if it.get("semantic"): p["semantic"] = {sec: it["semantic"]}
    gate = u.gate_reason(p, sec)
    rule_only = dict(p); rule_only.pop("semantic", None)
    rows.append(dict(label=it["label"], sec=sec, title=it["title"], gate=gate,
                     score=u.score(p, sec), rules=u.score(rule_only, sec),
                     margin=(it.get("semantic") or [None, None])[1], about=(it.get("semantic") or [None])[0]))

print(f"labelled: {len(rows)}  (G={sum(r['label']=='G' for r in rows)}, B={sum(r['label']=='B' for r in rows)})\n")
print("Gates now:")
print(f"  Bad rejected outright: {sum(1 for r in rows if r['label']=='B' and r['gate'])}/{sum(r['label']=='B' for r in rows)}")
print(f"  Good wrongly rejected: {sum(1 for r in rows if r['label']=='G' and r['gate'])}  {[r['title'][:50] for r in rows if r['label']=='G' and r['gate']]}")
kept = [r for r in rows if not r["gate"]]
print(f"\nRanking signals on papers that pass the gates (n={len(kept)}), AUC:")
for k in ("score", "rules", "margin", "about"):
    pr = [(r[k], r["label"]) for r in kept if r[k] is not None]
    print(f"  {k:7} {auc(pr):.2f}")
print("\nBad papers still passing the gates (ranked by current score):")
for r in sorted([r for r in kept if r["label"] == "B"], key=lambda r: -r["score"]):
    print(f"  {r['score']:4}  {r['sec']:16} {r['title'][:70]}")
