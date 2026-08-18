#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Pull the Promos & Extras section into merge_extras.py's transfer format.

    venv/bin/python pull_extras.py

Writes extras_pull.txt and extras_list.json, resumable - an interrupted run
picks up where it stopped rather than refetching.

Why this exists: the section was pulled once by hand when it was built and then
never again. refresh.sh knew nothing about it, so while every other tab moved
daily these 401 promos, alternate arts and metal cards kept whatever price they
had on the day they were added. They are in the Trade Calculator now, which
makes a stale price an actively wrong one rather than a merely old one.

The id list comes from the stored snapshot rather than from a fresh
enumeration: this section is defined by subtraction - everything the other tabs
do not carry - so the snapshot is what knows its membership. New promos are
added by re-running the enumeration that built it, not by this script.
"""
import json, os, time
from card_lib import ask_and_printing, ask_depth, history, sales, downsample, pack, listings

HERE = WORK
BINS = 12

snap = json.load(open(os.path.join(ROOT, "snapshot.json")))
cards, listing = [], []
for g in snap.get("extras") or []:
    for c in (g.get("cards") or []):
        cards.append(c)
        listing.append({"id": c["id"], "n": c["n"], "r": c.get("r"),
                        "num": c.get("num"), "set": c.get("src") or g.get("set")})

list_path = os.path.join(HERE, "extras_list.json")
json.dump(listing, open(list_path, "w"))

out_path = os.path.join(HERE, "extras_pull.txt")
done = set()
if os.path.exists(out_path):
    for line in open(out_path).read().splitlines():
        if line.strip():
            done.add(int(line.split("~")[0]))
    print(f"resuming extras: {len(done)} of {len(cards)} already pulled", flush=True)

print(f"Promos & Extras: {len(cards)} cards", flush=True)
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

        name = str(c["n"]).replace("~", "-")
        if len(weeks) >= 2:
            L, H, M = downsample(lo, hi, mk, BINS)
            allv = L + H + M
            b_lo, b_hi = round(min(allv), 2), round(max(allv), 2)
            fields = [str(pid), name, c.get("r") or "",
                      "" if ask is None else f"{ask}", str(len(L)), weeks[0], weeks[-1],
                      f"{b_lo}", f"{b_hi}",
                      pack(L, b_lo, b_hi), pack(H, b_lo, b_hi), pack(M, b_lo, b_hi),
                      ",".join(f"{v}" for v in sl),
                      ",".join(f"{a}:{d}" for a, d in asks)]
        else:
            # No usable Near Mint English history - ship the card anyway so the
            # row exists with its ask and sales, and let the chart fall back.
            fields = [str(pid), name, c.get("r") or "",
                      "" if ask is None else f"{ask}", "0", "", "", "", "",
                      "", "", "", ",".join(f"{v}" for v in sl),
                      ",".join(f"{a}:{d}" for a, d in asks)]

        fh.write("~".join(fields) + "\n"); fh.flush()
        if n % 25 == 0:
            print(f"  {n}/{len(cards)}", flush=True)
        time.sleep(0.25)

print(f"extras done. failures: {len(failed)}", flush=True)
for pid, e in failed[:10]:
    print("   ", pid, e, flush=True)
