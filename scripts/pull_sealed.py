#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Pull the sealed boxes and the standalone sealed products.

Same shape as pull_cases.py - sealed product is condition "Unopened", not Near
Mint, so the card filter chain does not apply. Prices are the card price basis
(no shipping), like everything else on the board.

Writes sealed_pull.json: one record per product with the chart series, ask,
last-5 sales and the derived floor/momentum fields the Signal column reads.
"""
import json, os, sys, time
from card_lib import (_req, L_HISTORY, L_SALES, listings, foreign_or_graded,
                      not_the_sealed_product, tcg_summary)

HERE = WORK
# (label, code, productId, exact TCGplayer product name for the summary lookup)
BOXES = [
    ("Origins",      "OGN", 635368, "Origins - Booster Display"),
    ("Spiritforged", "SFD", 661934, "Spiritforged - Booster Display"),
    ("Unleashed",    "UNL", 678150, "Unleashed - Booster Display"),
    ("Vendetta",     "VEN", 693380, "Vendetta - Booster Display"),
]
OTHER = [
    ("Worlds Bundle 2025",  "WB25", 658333, "Riftbound: Worlds Bundle 2025"),
    ("Arcane Box Set",      "ARC",  655495, "Riftbound: League of Legends Arcane Box Set"),
    ("Secret Garden Box",   "SGB",  710238, "Secret Garden Box"),
    ("Unleashed Vault Bundle", "UVB", 678162, "Unleashed - Vault Bundle"),
    ("Vendetta Vault Bundle",  "VVB", 697970, "Vendetta - Vault Bundle"),
]


def history(pid):
    """Whichever variant actually carries sales - sealed is 'Unopened'."""
    res = _req(L_HISTORY.format(pid)).get("result") or []
    best, best_n = None, -1
    for v in res:
        live = [b for b in (v.get("buckets") or [])
                if float(b.get("quantitySold") or 0) > 0 and float(b.get("marketPrice") or 0) > 0]
        if len(live) > best_n:
            best, best_n = v, len(live)
    if not best:
        return [], [], [], [], [], None
    W, L, H, M, Q = [], [], [], [], []
    for b in reversed(best.get("buckets") or []):
        q = float(b.get("quantitySold") or 0)
        m = float(b.get("marketPrice") or 0)
        if q <= 0 or m <= 0:
            continue
        l = float(b.get("lowSalePrice") or 0)
        h = float(b.get("highSalePrice") or 0)
        if l <= 0 or h <= 0:
            continue
        W.append(str(b.get("bucketStartDate"))[:10])
        L.append(round(l, 2)); H.append(round(h, 2)); M.append(round(m, 2)); Q.append(q)
    return W, L, H, M, Q, (best.get("condition") or "").strip()


def ask_of(pid, cond):
    rows = [l for l in listings(pid)
            if (not cond or l.get("condition") == cond)
            and not foreign_or_graded((l.get("customData") or {}).get("title"))
            and not not_the_sealed_product((l.get("customData") or {}).get("title"))]
    return min((round(float(l.get("price", 0)), 2) for l in rows), default=None), len(rows)


def sales_of(pid, cond, limit=5):
    body = json.dumps({"conditions": [], "languages": [], "variants": [],
                       "listingType": "All", "limit": 25, "offset": 0}).encode()
    out = []
    for s in _req(L_SALES.format(pid), body).get("data", []):
        if len(out) >= limit:
            break
        if cond and s.get("condition") != cond:
            continue
        if foreign_or_graded(s.get("title")) or not_the_sealed_product(s.get("title")):
            continue
        out.append(round(float(s.get("purchasePrice") or 0), 2))
    return out


def build(label, code, pid, tcgname):
    W, L, H, M, Q, cond = history(pid)
    # TCGplayer's own "from" price. Its lowestPriceWithShipping already excludes
    # the mislabelled listings that sit under a sealed id, which hand-filtering
    # the feed does not reliably catch - fall back to the filtered feed only if
    # the summary is unavailable.
    lo, lo_ship, mkt = tcg_summary(pid, tcgname)
    time.sleep(0.25)
    feed_ask, nlist = ask_of(pid, cond)
    ask = lo_ship if lo_ship else feed_ask
    time.sleep(0.25)
    sales = sales_of(pid, cond)
    rec = {"set": label, "code": code, "id": pid, "ask": ask, "clears": sales,
           "condition": cond, "listings": nlist, "feedAsk": feed_ask, "tcgMarket": mkt}
    if len(W) >= 2:
        slo = sorted(L); last26 = sorted(L[-26:])
        avg8 = sum(M[-8:]) / len(M[-8:])
        rec.update({
            "weeks": W, "weekCount": len(W),
            "series": [round((a + b) / 2, 2) for a, b in zip(L, H)],
            "low": L, "high": H, "market": M,
            "floor": round(slo[1] if len(slo) > 1 else slo[0], 2),
            "floorRecent": round(last26[1] if len(last26) > 1 else last26[0], 2),
            "trendPct": round((M[-1] - avg8) / avg8 * 100, 1),
            "rangePct": round((M[-1] - min(M)) / ((max(M) - min(M)) or 1) * 100),
            # momentumScore reads these; without them the volume term silently
            # contributes nothing rather than being absent on purpose
            "volNow": int(sum(Q[-4:])), "volPrev": int(sum(Q[-8:-4])),
        })
    else:
        rec["soon"] = "not trading yet"
    return rec


out = {"boxes": [], "sealed": []}
for bucket, items in (("boxes", BOXES), ("sealed", OTHER)):
    for label, code, pid, tcgname in items:
        try:
            r = build(label, code, pid, tcgname)
        except Exception as e:
            print(f"  FAIL {label} ({pid}): {str(e)[:70]}", flush=True)
            continue
        out[bucket].append(r)
        print(f"  {label:<24} ask={r['ask']:<9} (feed said {r['feedAsk']}) "
              f"weeks={r.get('weekCount', 0)} sales={len(r['clears'])}", flush=True)
        time.sleep(0.3)

json.dump(out, open(os.path.join(HERE, "sealed_pull.json"), "w"), indent=2)
print(f"\nwrote sealed_pull.json: {len(out['boxes'])} boxes, {len(out['sealed'])} other")
