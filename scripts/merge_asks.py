#!/usr/bin/env python3
"""Merge a re-pulled Near Mint ask set into the snapshot.

    python3 merge_asks.py ask_pull.txt snapshot.json snapshot.out.json

Line format, one per product:
    id|ask|printing|nQualifying|nSeen
    id|none|-|0|nSeen              (nothing qualifying is listed right now)

Only the `a` field is touched. History, sales and names are left alone.

Why this exists: the stored asks priced some cards off listings that are not
Near Mint English raw. Yasuo, Unforgiven (Overnumbered) asked 50.00 against a
cheapest real Near Mint English copy of 81.00, because four cheaper listings are
Chinese cards filed under language "English" - the failure HANDOFF.md warns
about. The pull applies the documented filter chain; this script only checks the
result is sane before it lands.

Sealed cases are deliberately not in scope. They are not graded Near Mint, so
the condition filter does not apply to them.
"""

import json
import sys

# A single card moving more than this is not rejected, just printed, so a real
# market move is visible rather than silently absorbed.
REPORT_MOVE = 0.25

# If more than this share of asks change, something is wrong with the pull
# rather than with the stored data. Refuse rather than overwrite the board.
MAX_CHANGED_SHARE = 0.90


def parse(path):
    out, bad = {}, []
    for n, line in enumerate(open(path).read().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        p = line.split("|")
        if len(p) != 5:
            bad.append(f"line {n}: {len(p)} fields, expected 5")
            continue
        pid = int(p[0])
        if p[1] == "none":
            out[pid] = None
            continue
        try:
            ask = float(p[1])
        except ValueError:
            bad.append(f"line {n} (id {pid}): ask {p[1]!r} is not a number")
            continue
        if ask <= 0:
            bad.append(f"line {n} (id {pid}): ask {ask} is not positive")
            continue
        out[pid] = ask
    return out, bad


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    pull_path, snap_path, out_path = sys.argv[1:4]

    asks, bad = parse(pull_path)
    snap = json.load(open(snap_path))

    cards = {}
    for section in ("signatures", "overnumbered", "catalog"):
        for g in snap.get(section) or []:
            for c in g.get("cards", []):
                cards[c["id"]] = (section, g.get("set"), c)

    unknown = [pid for pid in asks if pid not in cards]
    if unknown:
        bad.append(f"{len(unknown)} pulled ids are not in the snapshot: {unknown[:5]}")

    missing = [pid for pid in cards if pid not in asks]

    if bad:
        print("REFUSING TO WRITE")
        for b in bad:
            print("  error ", b)
        return 1

    changed, cleared, moves = 0, 0, []
    for pid, ask in asks.items():
        section, setname, c = cards[pid]
        old = c.get("a")
        if old == ask:
            continue
        changed += 1
        if ask is None:
            cleared += 1
        elif old:
            moves.append((abs(ask - old) / old, section, setname, c.get("n"), old, ask))
        c["a"] = ask

    share = changed / len(asks) if asks else 0
    if share > MAX_CHANGED_SHARE:
        print(f"REFUSING TO WRITE: {changed} of {len(asks)} asks changed "
              f"({share:.0%}), above the {MAX_CHANGED_SHARE:.0%} guard")
        return 1

    moves.sort(reverse=True)
    print(f"  pulled   {len(asks)} asks")
    print(f"  changed  {changed} ({share:.0%})")
    print(f"  cleared  {cleared} to 'none listed'")
    if missing:
        print(f"  note  {len(missing)} snapshot cards had no pulled ask, left as they were")
    big = [m for m in moves if m[0] >= REPORT_MOVE]
    print(f"  note  {len(big)} asks moved by {REPORT_MOVE:.0%} or more:")
    for pct, section, setname, name, old, new in big[:15]:
        arrow = "up" if new > old else "down"
        print(f"          {str(name)[:32]:<33} {section:<13}{setname:<14}"
              f"{old:>9} -> {new:<9} {arrow} {pct:.0%}")

    json.dump(snap, open(out_path, "w"), separators=(",", ":"))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
