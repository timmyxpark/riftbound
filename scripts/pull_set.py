#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Pull a whole Playables set into merge_set.py's transfer format.

    venv/bin/python pull_set.py unleashed Unleashed

Writes set_<slug>_pull.txt, one line per card, resumable - an interrupted run
picks up where it stopped rather than refetching.

    id~name~rarity~ask~weeks~first~last~lo~hi~qLow~qHigh~qMarket~sales~asks

`asks` is the cheapest five qualifying asks, ascending, and its first entry is
`ask` itself. It comes off the listing feed already fetched for the ask, so it
costs no extra request.

`weeks` is the number of packed BINS (12 for catalog cards), not the number of
real weeks; `first`/`last` carry the real span so the month axis stays honest.
"""
import json, os, sys, time
from card_lib import ask_and_printing, ask_depth, history, sales, downsample, pack, listings

HERE = WORK
BINS = 12

slug, display = sys.argv[1], sys.argv[2]
cards = json.load(open(os.path.join(HERE, f"set_{slug}.json")))
out_path = os.path.join(HERE, f"set_{slug}_pull.txt")

done = set()
if os.path.exists(out_path):
    for line in open(out_path).read().splitlines():
        if line.strip():
            done.add(int(line.split("~")[0]))
    print(f"resuming {slug}: {len(done)} of {len(cards)} already pulled", flush=True)

print(f"{display}: {len(cards)} cards", flush=True)
failed = []
with open(out_path, "a") as fh:
    for n, c in enumerate(cards, 1):
        pid = c["id"]
        if pid in done:
            continue
        try:
            rows = listings(pid)
            ask, printing = ask_and_printing(pid, rows)
            asks = ask_depth(rows)
            time.sleep(0.25)
            weeks, lo, hi, mk = history(pid, printing)
            time.sleep(0.25)
            sl = sales(pid, printing)
        except Exception as e:
            failed.append((pid, str(e)[:60]))
            print(f"  FAIL {pid} {c['n']}: {str(e)[:60]}", flush=True)
            continue

        if len(weeks) >= 2:
            L, H, M = downsample(lo, hi, mk, BINS)
            allv = L + H + M
            b_lo, b_hi = round(min(allv), 2), round(max(allv), 2)
            nb = len(L)
            fields = [str(pid), c["n"].replace("~", "-"), c["r"] or "",
                      "" if ask is None else f"{ask}", str(nb), weeks[0], weeks[-1],
                      f"{b_lo}", f"{b_hi}",
                      pack(L, b_lo, b_hi), pack(H, b_lo, b_hi), pack(M, b_lo, b_hi),
                      ",".join(f"{v}" for v in sl),
                      ",".join(f"{v}" for v in asks)]
        else:
            # No usable Near Mint English history - ship the card anyway so the
            # row exists with its ask and sales, and let the chart fall back.
            fields = [str(pid), c["n"].replace("~", "-"), c["r"] or "",
                      "" if ask is None else f"{ask}", "0", "", "", "", "",
                      "", "", "", ",".join(f"{v}" for v in sl),
                      ",".join(f"{v}" for v in asks)]

        fh.write("~".join(fields) + "\n"); fh.flush()
        if n % 25 == 0:
            print(f"  {n}/{len(cards)}", flush=True)
        time.sleep(0.25)

print(f"{display} done. failures: {len(failed)}", flush=True)
for pid, e in failed[:10]:
    print("   ", pid, e, flush=True)
