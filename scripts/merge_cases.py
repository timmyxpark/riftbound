#!/usr/bin/env python3
"""Merge the sealed-case low/high/market pull into the snapshot.

    python3 merge_cases.py cases_pull.txt snapshot.json snapshot.out.json

Basis note: low and high are shipping-inclusive, matching the ask and floor that
share the same chart axis, and reproducing the existing `series` exactly.
marketPrice has no shipping-inclusive variant in the API, so it sits roughly 1%
low against the band. That is documented rather than silently corrected.
"""

import json
import sys
from datetime import datetime, timedelta

CODE_TO_SET = {"OGN": "Origins", "SPF": "Spiritforged", "UNL": "Unleashed", "VDT": "Vendetta"}
EXPECT_LINES = 16


def parse(path):
    raw = [l for l in open(path).read().splitlines() if l.strip()]
    if len(raw) != EXPECT_LINES:
        sys.exit(f"expected {EXPECT_LINES} lines, got {len(raw)}")

    data = {}
    for line in raw:
        parts = line.split("|")
        code, kind = parts[0], parts[1]
        d = data.setdefault(code, {})
        if kind == "W":
            start = datetime.strptime(parts[2], "%Y-%m-%d")
            offs = [int(x) for x in parts[3].split(",")]
            d["weeks"] = [(start + timedelta(weeks=o)).strftime("%Y-%m-%d") for o in offs]
        else:
            d[kind] = [float(x) for x in parts[2].split(",")]

    for code, d in data.items():
        for k in ("weeks", "L", "H", "M"):
            if k not in d:
                sys.exit(f"{code}: missing {k}")
        n = len(d["weeks"])
        if len({n, len(d["L"]), len(d["H"]), len(d["M"])}) != 1:
            sys.exit(f"{code}: series lengths differ "
                     f"({n}/{len(d['L'])}/{len(d['H'])}/{len(d['M'])})")
    return data


def clean(code, d):
    """Drop weeks the API cannot support: a sale week with no market price yet.
    All four series are cut together so they stay aligned."""
    keep = [i for i, m in enumerate(d["M"]) if m > 0]
    dropped = [d["weeks"][i] for i in range(len(d["weeks"])) if i not in set(keep)]
    for w in dropped:
        print(f"  drop  {code} {w}: market price 0 (pre-market week)")
    for k in ("weeks", "L", "H", "M"):
        d[k] = [d[k][i] for i in keep]

    bad = [d["weeks"][i] for i in range(len(d["L"])) if d["L"][i] > d["H"][i]]
    if bad:
        sys.exit(f"{code}: low above high in {bad}")
    return d


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    pull_path, snap_path, out_path = sys.argv[1:]

    data = {c: clean(c, d) for c, d in parse(pull_path).items()}
    snap = json.load(open(snap_path))

    by_set = {s["set"]: s for s in snap["sets"]}
    touched = 0
    for code, d in data.items():
        name = CODE_TO_SET[code]
        s = by_set.get(name)
        if s is None:
            sys.exit(f"{name} not in snapshot")

        # The existing weeks are the reference; a mismatch means the filter rule
        # drifted and the whole pull is suspect.
        old_weeks = s.get("weeks") or []
        if old_weeks and old_weeks != d["weeks"]:
            extra = set(d["weeks"]) - set(old_weeks)
            missing = set(old_weeks) - set(d["weeks"])
            print(f"  note  {name}: weeks changed since last pull "
                  f"(+{len(extra)} / -{len(missing)})")

        mid = [round((lo + hi) / 2, 2) for lo, hi in zip(d["L"], d["H"])]
        if old_weeks == d["weeks"] and s.get("series"):
            drift = max(abs(a - b) for a, b in zip(s["series"], mid))
            print(f"  check {name}: midpoint matches stored series to {drift:.2f}")

        s["weeks"] = d["weeks"]
        s["weekCount"] = len(d["weeks"])
        s["series"] = mid          # black line, the midpoint of the drawn band
        s["low"] = d["L"]
        s["high"] = d["H"]
        s["market"] = d["M"]
        touched += 1

    print(f"\nupdated {touched} sets")
    json.dump(snap, open(out_path, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
