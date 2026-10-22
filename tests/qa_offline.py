"""Offline QA: re-run the current gates/ranking on the papers already stored in data/
(no network needed) and print the audit. Run: python tests/qa_offline.py"""
import json, sys, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_literature as u

def corpus():
    seen = {}
    B = json.loads((ROOT / "data/briefing.json").read_text())
    pools = [json.loads((ROOT / "data/papers.json").read_text()), B.get("top10_weekly", []),
             B["preprints"]["papers"], B["reviews"]["primary"], B["reviews"]["secondary"]]
    for s in B["sections"].values(): pools += [s.get("primary", []), s.get("secondary", [])]
    for pool in pools:
        for p in pool:
            k = u.pkey(p)
            if k in seen:
                seen[k]["sections"] = list(dict.fromkeys(seen[k].get("sections", []) + p.get("sections", [])))
            else: seen[k] = copy.deepcopy(p)
    return list(seen.values())

if __name__ == "__main__":
    allp = corpus()
    for p in allp:
        for sec in p.get("sections", []):
            r = u.gate_reason(p, sec)
            if r: u.note_rejection(sec, p, r)
    briefing, legacy, meta, audit = u.build_outputs(allp)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out: out.write_text(json.dumps({"audit": audit, "meta": meta}, indent=2, ensure_ascii=False))
    print("papers in:", len(allp))
    print("\nWEEKLY TOP 10"); [print(" ", p["date"], f"[{p['section']}]", p["title"][:105]) for p in audit["weekly_top10"]]
    for sec, s in audit["sections"].items():
        print(f"\n== {sec}  primary={s['primary_count']} secondary={s['secondary_count']}")
        for t in ("top_primary", "top_secondary"):
            for p in s[t][:6]: print(f"  {t[4]} {p['date']} | {p['journal'][:26]:26} | {p['title'][:95]}")
