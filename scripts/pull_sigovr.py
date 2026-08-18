#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Refresh history and sales for the Signature and Overnumbered sections.

Asks for these 137 come from ask_sigovr.txt, already pulled. This adds:
    sig_hist.txt / ovr_hist.txt   id|weeks|first|last|lo|hi|sl|sh|sm   (merge_cards)
    sigovr_sales_new.txt          id|p,p,p                             (merge_sales)
    ask_sigovr.txt                id|ask|printing|0|0|p,p,p,p,p        (merge_asks)

History ships at full weekly resolution here, not the catalog's 12 bins - it is
only 137 cards, and the signature charts are the ones people actually read.

Sales: NO backfill from the stored snapshot on this run. The stored sales are
shipping-inclusive and everything here is now the card price alone; padding a
card-price column with shipping-inclusive figures would put two bases in one
column and quietly overstate the tail. Depth is given up rather than mixing -
these sections drop from five to whatever survives filtering.
"""
import json, os, sys, time
from card_lib import ask_and_printing, ask_depth, history, sales, pack, listings

HERE = WORK
REPO = ROOT
snap = json.load(open(os.path.join(REPO, "snapshot.json")))
sections = {"signatures": _os.path.join(WORK, "sig_hist.txt"), "overnumbered": _os.path.join(WORK, "ovr_hist.txt")}

sales_lines, asks, failed = [], [], []
for section, hist_name in sections.items():
    cards = [c for g in snap[section] for c in (g.get("cards") or [])]
    hp = os.path.join(HERE, hist_name)
    done = set()
    if os.path.exists(hp):
        for line in open(hp).read().splitlines():
            if line.strip():
                done.add(int(line.split("|")[0]))
    print(f"{section}: {len(cards)} cards ({len(done)} already done)", flush=True)

    with open(hp, "a") as fh:
        for n, c in enumerate(cards, 1):
            pid = c["id"]
            if pid in done:
                continue
            try:
                # One listing fetch, reused for the ask and its depth.
                rows = listings(pid)
                ask, pr = ask_and_printing(pid, rows)
                depth = ",".join(f"{v}" for v in ask_depth(rows))
                asks.append(f"{pid}|{ask if ask is not None else 'none'}|{pr or '-'}|0|0|{depth}")
                time.sleep(0.25)
                weeks, lo, hi, mk = history(pid, pr)
                time.sleep(0.25)
                fresh = sales(pid, pr)
            except Exception as e:
                failed.append((pid, str(e)[:60]))
                print(f"  FAIL {pid} {c.get('n')}: {str(e)[:60]}", flush=True)
                continue

            if len(weeks) >= 2:
                allv = lo + hi + mk
                b_lo, b_hi = round(min(allv), 2), round(max(allv), 2)
                fh.write("|".join([str(pid), str(len(weeks)), weeks[0], weeks[-1],
                                   f"{b_lo}", f"{b_hi}",
                                   pack(lo, b_lo, b_hi), pack(hi, b_lo, b_hi),
                                   pack(mk, b_lo, b_hi)]) + "\n")
            else:
                fh.write(f"{pid}|0\n")
            fh.flush()

            sales_lines.append(f"{pid}|" + ",".join(f"{v}" for v in fresh))

            if n % 25 == 0:
                print(f"  {n}/{len(cards)}", flush=True)
            time.sleep(0.25)

if asks:
    with open(os.path.join(HERE, "ask_sigovr.txt"), "a") as fh:
        fh.write("\n".join(asks) + "\n")
if sales_lines:
    with open(os.path.join(HERE, "sigovr_sales_new.txt"), "a") as fh:
        fh.write("\n".join(sales_lines) + "\n")
print(f"done. failures: {len(failed)}", flush=True)
for pid, e in failed[:10]:
    print("   ", pid, e, flush=True)
