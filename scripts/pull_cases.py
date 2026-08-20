import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Pull the four sealed cases: chart series for merge_cases.py, plus the
derived fields it does not touch (ask, floor, momentum inputs).

Sealed product is condition "Unopened", not Near Mint, so the card filter chain
does not apply here. Floor is the second-lowest weekly low ever seen and is kept
from run to run - it is only ever lowered, never raised, so it does not expire
when a cheap week ages out of the rolling year.
"""
import sys, json, datetime
from card_lib import (_req, L_HISTORY, listings, foreign_or_graded,
                      not_the_sealed_product, tcg_summary)

CASES = {"OGN": ("Origins", 635369), "SPF": ("Spiritforged", 661937),
         "UNL": ("Unleashed", 678152), "VDT": ("Vendetta", 693382)}
# ROOT, not a laptop path: this is the last hardcoded one and it would have
# broken silently the moment the repo moved off the Desktop.
snap = json.load(open(_os.path.join(ROOT, "snapshot.json")))
by = {s["set"]: s for s in snap["sets"]}

lines, meta = [], {}
for code, (name, pid) in CASES.items():
    v = (_req(L_HISTORY.format(pid)).get("result") or [])[0]
    W, L, H, M, Q = [], [], [], [], []
    for b in reversed(v.get("buckets") or []):
        q = float(b.get("quantitySold") or 0); m = float(b.get("marketPrice") or 0)
        if q <= 0 or m <= 0:
            continue
        W.append(str(b.get("bucketStartDate"))[:10])
        L.append(round(float(b.get("lowSalePrice") or 0), 2))
        H.append(round(float(b.get("highSalePrice") or 0), 2))
        M.append(round(m, 2)); Q.append(q)

    d0 = datetime.date.fromisoformat(W[0])
    offs = [ (datetime.date.fromisoformat(w) - d0).days // 7 for w in W ]
    lines += [f"{code}|W|{W[0]}|" + ",".join(str(o) for o in offs),
              f"{code}|L|" + ",".join(f"{x}" for x in L),
              f"{code}|H|" + ",".join(f"{x}" for x in H),
              f"{code}|M|" + ",".join(f"{x}" for x in M)]

    # TCGplayer's own "from" price. Its lowestPriceWithShipping already excludes
    # the mislabelled listings that sit under a sealed id (a Chinese jumbo case
    # under the English one); its lowestPrice does NOT, so use the shipping one.
    lo, lo_ship, mkt = tcg_summary(pid, f"{name} - Booster Display Case")
    rows = [l for l in listings(pid)
            if l.get("condition") == "Unopened"
            and not foreign_or_graded((l.get("customData") or {}).get("title"))
            and not not_the_sealed_product((l.get("customData") or {}).get("title"))]
    feed_ask = min((round(float(l.get("price", 0)), 2) for l in rows), default=None)
    ask = lo_ship if lo_ship else feed_ask

    slo = sorted(L); last26 = sorted(L[-26:])
    floor_new = slo[1] if len(slo) > 1 else slo[0]
    stored_floor = by[name].get("floor")
    avg8 = sum(M[-8:]) / len(M[-8:])
    meta[name] = {
        "ask": ask,
        "floor": round(min(stored_floor, floor_new) if stored_floor else floor_new, 2),
        "floorRecent": round(last26[1] if len(last26) > 1 else last26[0], 2),
        "trendPct": round((M[-1] - avg8) / avg8 * 100, 1),
        "rangePct": round((M[-1] - min(M)) / ((max(M) - min(M)) or 1) * 100),
        "volNow": int(sum(Q[-4:])), "volPrev": int(sum(Q[-8:-4])),
    }
    print(f"{name}: {len(W)} weeks, ask {ask} (feed said {feed_ask}), "
          f"floor {meta[name]['floor']}")

open(_os.path.join(WORK, _os.path.join(WORK, "cases_pull_new.txt")), "w").write("\n".join(lines) + "\n")
json.dump(meta, open(_os.path.join(WORK, _os.path.join(WORK, "case_meta.json")), "w"), indent=2)
print(f"\nwrote cases_pull_new.txt ({len(lines)} lines) and case_meta.json")
