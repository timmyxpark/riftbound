#!/usr/bin/env python3
"""Merge a packed card-history pull into the snapshot.

    python3 merge_cards.py sig_pull.txt signatures snapshot.json snapshot.out.json

Line format, one per product:
    id|weeks|firstDate|lastDate|lo|hi|packedLow|packedHigh|packedMarket
    id|0                                    (no Near Mint English history)

lo and hi bound all three series, so one pair rescales every one of them.
"""

import json
import sys

MIN_WEEKS = 2   # a single point cannot draw a line


def parse(path):
    out, bad = {}, []
    for n, line in enumerate(open(path).read().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        p = line.split("|")
        pid = int(p[0])
        if len(p) == 2 and p[1] == "0":
            out[pid] = None
            continue
        if len(p) != 9:
            bad.append(f"line {n} (id {pid}): {len(p)} fields, expected 9")
            continue
        weeks, first, last, lo, hi = int(p[1]), p[2], p[3], float(p[4]), float(p[5])
        ql, qh, qm = p[6], p[7], p[8]

        # Each packed string must be exactly two digits per week. This is the
        # check that catches a chunk clipped mid-transfer.
        for label, q in (("low", ql), ("high", qh), ("market", qm)):
            if len(q) != weeks * 2:
                bad.append(f"id {pid}: packed {label} is {len(q)} chars, expected {weeks * 2}")
            elif not q.isdigit():
                bad.append(f"id {pid}: packed {label} has non-digits")
        if lo > hi:
            bad.append(f"id {pid}: lo {lo} above hi {hi}")
        out[pid] = {"n": weeks, "f": first, "l": last, "lo": lo, "hi": hi,
                    "sl": ql, "sh": qh, "sm": qm}
    return out, bad


def unpack(q, lo, hi):
    span = (hi - lo) or 1
    return [round(lo + int(q[i:i + 2]) / 99 * span, 2) for i in range(0, len(q), 2)]


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    pull_path, section, snap_path, out_path = sys.argv[1:]

    data, bad = parse(pull_path)
    snap = json.load(open(snap_path))
    if section not in snap:
        sys.exit(f"no section {section!r} in snapshot")

    # The catalog renderer reads ql/qh/qm; the card tables read sl/sh/sm.
    lo_f, hi_f, mk_f = (("ql", "qh", "qm") if section == "catalog" else ("sl", "sh", "sm"))

    cards = [c for g in snap[section] for c in (g.get("cards") or [])]
    want = {c["id"] for c in cards}
    got = set(data)

    missing = want - got
    extra = got - want
    if missing:
        bad.append(f"{len(missing)} cards in snapshot with no pulled line: {sorted(missing)[:5]}")
    if extra:
        bad.append(f"{len(extra)} pulled lines match no card: {sorted(extra)[:5]}")

    if bad:
        for b in bad:
            print(f"  FAIL  {b}")
        sys.exit(f"\n{len(bad)} problem(s); nothing written.")

    applied = thin = none = 0
    lagging = []
    for c in cards:
        d = data[c["id"]]
        if d is None:
            none += 1
            continue
        if d["n"] < MIN_WEEKS:
            thin += 1
            continue
        lows, highs = unpack(d["sl"], d["lo"], d["hi"]), unpack(d["sh"], d["lo"], d["hi"])
        mkts = unpack(d["sm"], d["lo"], d["hi"])
        slack = (d["hi"] - d["lo"]) / 99 * 1.5   # one quantisation step, plus slack
        for lo_v, hi_v in zip(lows, highs):
            if lo_v > hi_v + slack:
                sys.exit(f"id {c['id']}: weekly low above high after unpack")

        # Market is a trailing volume-weighted average, so on a thin card it
        # routinely sits outside that week's own low-to-high range - it lags
        # below in a rising market and above in a falling one. That is real
        # signal, not corruption, so it is counted rather than warned about.
        out = sum(1 for lo_v, hi_v, m in zip(lows, highs, mkts)
                  if m < lo_v - slack or m > hi_v + slack)
        if out:
            lagging.append((c["n"], out, len(mkts)))
        c.update({"f": d["f"], "l": d["l"], "lo": d["lo"], "hi": d["hi"],
                  lo_f: d["sl"], hi_f: d["sh"], mk_f: d["sm"]})
        if section == "catalog":
            c.pop("q", None)   # retire the old single-series form once replaced
        applied += 1

    if lagging:
        lagging.sort(key=lambda r: -r[1] / r[2])
        worst = ", ".join(f"{n} {o}/{t}" for n, o, t in lagging[:3])
        print(f"  note  market sits outside the weekly range on {len(lagging)} cards "
              f"(trailing average lag); worst: {worst}")

    print(f"\n{section}: {applied} charted, {thin} too few weeks, {none} no history "
          f"({applied + thin + none} of {len(cards)})")
    json.dump(snap, open(out_path, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
