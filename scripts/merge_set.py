#!/usr/bin/env python3
"""Add a freshly pulled set to the Playables (catalog) section of the snapshot.

    python3 merge_set.py spiritforged_pull.txt Spiritforged snapshot.json snapshot.out.json

Line format, one per card, `~` separated because card names contain commas but
never a tilde:

    id~name~rarity~ask~weeks~first~last~lo~hi~packedLow~packedHigh~packedMarket~sales

`ask` may be empty (nothing listed). `sales` is a comma list, possibly empty.
lo/hi bound all three packed series.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIELDS = 13


def parse(path):
    out, bad = {}, []
    for n, line in enumerate(open(path).read().splitlines(), 1):
        line = line.rstrip()
        if not line:
            continue
        p = line.split("~")
        if len(p) != FIELDS:
            bad.append(f"line {n}: {len(p)} fields, expected {FIELDS}")
            continue
        try:
            pid = int(p[0])
        except ValueError:
            bad.append(f"line {n}: bad id {p[0]!r}")
            continue

        weeks = int(p[4]) if p[4] else 0
        rec = {
            "id": pid, "n": p[1], "r": p[2] or None,
            "a": float(p[3]) if p[3] else None,
            "f": p[5] or None, "l": p[6] or None,
            "lo": float(p[7]) if p[7] else None,
            "hi": float(p[8]) if p[8] else None,
            "ql": p[9] or None, "qh": p[10] or None, "qm": p[11] or None,
            "c": [round(float(x), 2) for x in p[12].split(",") if x.strip()],
        }

        if rec["ql"]:
            for label, q in (("low", rec["ql"]), ("high", rec["qh"]), ("market", rec["qm"])):
                if q is None or len(q) != weeks * 2:
                    bad.append(f"id {pid}: packed {label} is "
                               f"{0 if q is None else len(q)} chars, expected {weeks * 2}")
                elif not q.isdigit():
                    bad.append(f"id {pid}: packed {label} has non-digits")
            if rec["lo"] is None or rec["hi"] is None:
                bad.append(f"id {pid}: packed series without lo/hi")
            elif rec["lo"] > rec["hi"]:
                bad.append(f"id {pid}: lo above hi")
        if len(rec["c"]) > 5:
            bad.append(f"id {pid}: {len(rec['c'])} sales, feed caps at 5")
        if not rec["n"]:
            bad.append(f"id {pid}: empty name")
        out[pid] = rec
    return out, bad


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    pull_path, set_name, snap_path, out_path = sys.argv[1:]

    data, bad = parse(pull_path)
    expected = json.load(open(os.path.join(ROOT, "catalog_ids.json"))).get(set_name.lower())
    if expected is None:
        bad.append(f"no id list for {set_name.lower()!r} in catalog_ids.json")
    else:
        missing = set(expected) - set(data)
        extra = set(data) - set(expected)
        if missing:
            bad.append(f"{len(missing)} ids in catalog_ids.json with no line: {sorted(missing)[:5]}")
        if extra:
            bad.append(f"{len(extra)} lines matching no known id: {sorted(extra)[:5]}")

    if bad:
        for b in bad:
            print(f"  FAIL  {b}")
        sys.exit(f"\n{len(bad)} problem(s); nothing written.")

    snap = json.load(open(snap_path))
    # keep the catalog ordered by ask, as the Origins group is
    cards = sorted(data.values(), key=lambda c: -(c["a"] or 0))
    for c in cards:
        for k in [k for k, v in c.items() if v is None]:
            del c[k]

    groups = snap.setdefault("catalog", [])
    groups[:] = [g for g in groups if g.get("set") != set_name]
    groups.append({"set": set_name, "cards": cards})
    order = ["Origins", "Spiritforged", "Unleashed", "Vendetta", "Radiance"]
    groups.sort(key=lambda g: order.index(g["set"]) if g["set"] in order else 99)

    charted = sum(1 for c in cards if c.get("ql"))
    withask = sum(1 for c in cards if c.get("a") is not None)
    withsales = sum(1 for c in cards if c.get("c"))
    print(f"\n{set_name}: {len(cards)} cards, {charted} charted, "
          f"{withask} with an ask, {withsales} with sales")
    json.dump(snap, open(out_path, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
