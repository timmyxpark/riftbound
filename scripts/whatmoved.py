#!/usr/bin/env python3
"""Summarise what a refresh changed, against the last committed snapshot.

Run after a refresh, before committing. The point is to make a bad pull
obvious: a refresh where everything moves, or nothing does, is a refresh worth
looking at before it lands on the board.
"""
import json
import os
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def committed_snapshot():
    r = subprocess.run(["git", "-C", ROOT, "show", "HEAD:snapshot.json"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)


def cards(snap):
    out = {}
    for sec in ("signatures", "overnumbered", "catalog"):
        for g in snap.get(sec) or []:
            for c in g.get("cards") or []:
                out[c["id"]] = (sec, c)
    return out


def main():
    old = committed_snapshot()
    if old is None:
        print("  no committed snapshot to compare against")
        return 0
    new = json.load(open(os.path.join(ROOT, "snapshot.json")))

    o, n = cards(old), cards(new)
    moves = []
    for pid, (sec, c) in n.items():
        prev = o.get(pid)
        if prev and prev[1].get("a") and c.get("a") is not None:
            a, b = prev[1]["a"], c["a"]
            moves.append(((b - a) / a, sec, c.get("n"), a, b))
    moves.sort()

    if not moves:
        print("  nothing comparable - is this the first refresh on this snapshot?")
    else:
        same = sum(1 for m in moves if abs(m[0]) < 0.005)
        print(f"  {len(moves)} cards compared: {same} unchanged, "
              f"{sum(1 for m in moves if m[0] > 0.005)} up, "
              f"{sum(1 for m in moves if m[0] < -0.005)} down, "
              f"median {statistics.median(m[0] for m in moves):+.1%}")
        # Everything moving, or nothing moving, both mean something is wrong.
        if same == len(moves):
            print("  WARNING: not one ask changed - did the pull actually reach TCGplayer?")
        elif same < len(moves) * 0.05:
            print("  WARNING: almost every ask changed - check the pull before committing")
        print("  biggest drops:")
        for p, sec, nm, a, b in moves[:3]:
            print(f"     {str(nm)[:30]:<31}{a:>9} -> {b:<9} {p:+.0%}")
        print("  biggest rises:")
        for p, sec, nm, a, b in moves[-3:]:
            print(f"     {str(nm)[:30]:<31}{a:>9} -> {b:<9} {p:+.0%}")

    for key in ("sets", "boxes", "sealed"):
        prev = {r["set"]: r for r in (old.get(key) or [])}
        rows = [(r["set"], prev.get(r["set"], {}).get("ask"), r.get("ask"))
                for r in (new.get(key) or [])]
        changed = [(s, a, b) for s, a, b in rows if a and b and a != b]
        if changed:
            print(f"  {key}:")
            for s, a, b in changed:
                print(f"     {s[:24]:<25}{a:>10} -> {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
