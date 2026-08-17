#!/bin/bash
# Full price refresh: pull every product, merge, rebuild, test.
#
#   scripts/refresh.sh            normal run
#   RIFTBOUND_WORK=/tmp/x  ...    put working files somewhere else
#
# Takes roughly 1.5-2 hours for ~1,079 products. Safe to re-run: every pull
# step resumes, so an interrupted run picks up where it stopped rather than
# starting over. Nothing is written to snapshot.json until every set is
# complete, and each merge script validates before writing, so a short pull
# leaves the board untouched rather than half-updated.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WORK="${RIFTBOUND_WORK:-$ROOT/.pullcache}"
mkdir -p "$WORK"
export RIFTBOUND_WORK="$WORK"
PY="${RIFTBOUND_PYTHON:-python3}"

say() { echo; echo "=== $* ($(date +%H:%M:%S)) ==="; }

# Each run starts from empty pull files. They resume by product id, which is
# what makes an interrupted run cheap to restart - but across days it would
# keep yesterday's price for every id already present and mix two vintages in
# one snapshot. The image cache is kept: card art does not change.
say "clearing the previous run's pull files"
rm -f "$WORK"/set_*_pull.txt "$WORK"/sig_hist.txt "$WORK"/ovr_hist.txt \
      "$WORK"/sigovr_sales_new.txt "$WORK"/*_sales.txt "$WORK"/ask_sigovr.txt \
      "$WORK"/cases_pull_new.txt "$WORK"/case_meta.json "$WORK"/sealed_pull.json \
      "$WORK"/m*.json "$WORK"/set_*.json
echo "  cleared (image cache kept)"

say "enumerating sets"
for s in origins spiritforged unleashed vendetta; do
  [ -f "$WORK/set_$s.json" ] || $PY scripts/enumerate_set.py "$s"
done
# Origins carries one token with a null number that the classifier drops; it is
# a real card and catalog_ids.json expects it.
$PY - <<'PYEOF'
import json, os
work = os.environ["RIFTBOUND_WORK"]
p = os.path.join(work, "set_origins.json")
cards = json.load(open(p))
if not any(c["id"] == 653117 for c in cards):
    cards.append({"id": 653117, "n": "Buff", "r": "Common", "num": ""})
    json.dump(cards, open(p, "w"))
    print("  re-added the null-numbered Origins token 653117")
PYEOF

say "pulling the four catalog sets"
for pass in 1 2 3; do
  $PY scripts/pull_set.py unleashed    Unleashed
  $PY scripts/pull_set.py vendetta     Vendetta
  $PY scripts/pull_set.py origins      Origins
  $PY scripts/pull_set.py spiritforged Spiritforged
  short=0
  for f in unleashed:225 vendetta:175 origins:299 spiritforged:230; do
    slug="${f%%:*}"; want="${f##*:}"
    have=$(wc -l < "$WORK/set_${slug}_pull.txt" 2>/dev/null || echo 0)
    [ "$have" -lt "$want" ] && { echo "  $slug $have/$want - retrying"; short=1; }
  done
  [ "$short" -eq 0 ] && break
done

say "signatures and overnumbered"
$PY scripts/pull_sigovr.py
say "sealed cases"
$PY scripts/pull_cases.py
say "boxes and other sealed"
$PY scripts/pull_sealed.py

say "merging"
$PY scripts/merge_set.py "$WORK/set_origins_pull.txt"      Origins      snapshot.json "$WORK/m1.json"
$PY scripts/merge_set.py "$WORK/set_spiritforged_pull.txt" Spiritforged "$WORK/m1.json" "$WORK/m2.json"
$PY scripts/merge_set.py "$WORK/set_unleashed_pull.txt"    Unleashed    "$WORK/m2.json" "$WORK/m3.json"
$PY scripts/merge_set.py "$WORK/set_vendetta_pull.txt"     Vendetta     "$WORK/m3.json" "$WORK/m4.json"
# The 90% guard stays live here on purpose. It fires when the meaning of a price
# changes, not when prices move, and a routine run should stop rather than
# quietly overwrite the board.
$PY scripts/merge_asks.py "$WORK/ask_sigovr.txt" "$WORK/m4.json" "$WORK/m5.json"
$PY scripts/merge_cards.py "$WORK/sig_hist.txt" signatures   "$WORK/m5.json" "$WORK/m6.json"
$PY scripts/merge_cards.py "$WORK/ovr_hist.txt" overnumbered "$WORK/m6.json" "$WORK/m7.json"
$PY - <<'PYEOF'
import json, os
work = os.environ["RIFTBOUND_WORK"]
snap = json.load(open(f"{work}/m7.json"))
lines = [l for l in open(f"{work}/sigovr_sales_new.txt").read().splitlines() if l.strip()]
for sec in ("signatures", "overnumbered"):
    ids = {c["id"] for g in snap[sec] for c in (g.get("cards") or [])}
    out = [l for l in lines if int(l.split("|")[0]) in ids]
    open(f"{work}/{sec}_sales.txt", "w").write("\n".join(out) + "\n")
PYEOF
$PY scripts/merge_sales.py "$WORK/signatures_sales.txt"   "$WORK/m7.json" "$WORK/m8.json" signatures
$PY scripts/merge_sales.py "$WORK/overnumbered_sales.txt" "$WORK/m8.json" "$WORK/m9.json" overnumbered
$PY scripts/merge_cases.py "$WORK/cases_pull_new.txt"     "$WORK/m9.json" "$WORK/m10.json"
$PY - <<'PYEOF'
import datetime, json, os
work = os.environ["RIFTBOUND_WORK"]
root = os.environ.get("RIFTBOUND_ROOT") or os.getcwd()
snap = json.load(open(f"{work}/m10.json"))
meta = json.load(open(f"{work}/case_meta.json"))
for s in snap["sets"]:
    m = meta.get(s["set"])
    if m:
        for f in ("ask", "floor", "floorRecent", "trendPct", "rangePct", "volNow", "volPrev"):
            s[f] = m[f]

pull = json.load(open(f"{work}/sealed_pull.json"))
by_set = {s["set"]: s for s in snap["sets"]}
def finish(rec, inherit=None):
    if inherit and inherit in by_set:
        src = by_set[inherit]
        rec["reprint"], rec["reprintWhy"] = src.get("reprint", 0), src.get("reprintWhy", "")
        rec["event"], rec["eventWhy"] = src.get("event", 0), src.get("eventWhy", "")
    else:
        rec["reprint"], rec["reprintWhy"] = 0, "no reprint schedule published for this product"
        rec["event"], rec["eventWhy"] = 0, "not part of the competitive calendar"
    for k in ("condition", "listings", "feedAsk", "tcgMarket"):
        rec.pop(k, None)
    return rec
snap["boxes"]  = [finish(r, r["set"]) for r in pull["boxes"]]
snap["sealed"] = [finish(r) for r in pull["sealed"]]

today = datetime.date.today()
snap["pulled"] = today.isoformat()
snap["pulledLabel"] = today.strftime("%B %-d, %Y")
json.dump(snap, open(os.path.join(root, "snapshot.json"), "w"), indent=2, ensure_ascii=False)
print(f"  snapshot dated {snap['pulledLabel']}")
PYEOF

say "rebuild and test"
npm run all

say "what moved"
$PY scripts/whatmoved.py || true
say "REFRESH COMPLETE"
