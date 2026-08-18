#!/usr/bin/env python3
"""Merge the Promos & Extras pull into snapshot["extras"].

    python3 merge_extras.py extras_pull.txt extras_list.json snapshot.json out.json

Line format is merge_set.py's:
    id~name~rarity~ask~weeks~first~last~lo~hi~qLow~qHigh~qMarket~sales~asks

Two things differ from a catalog merge and both matter:

1. The packed series are stored as sl/sh/sm, not ql/qh/qm. This section renders
   through renderCards (the signature/overnumbered renderer), and cardChart
   reads sl/sh/sm; ql/qh/qm would leave every chart blank while every other
   field looked fine.

2. There is no catalog_ids.json to validate against - this section is defined by
   subtraction (everything the other tabs do not carry), so the id list comes
   from the pull request itself. Instead of an id whitelist, the check is that
   every card asked for came back and nothing extra appeared.

Cards are grouped by their source set - Organized Play promos, a booster set's
alternate arts, Proving Grounds - rather than by booster set, because that is
what the grouping means here.
"""
import json
import sys

FIELDS = 14


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
        pid = int(p[0])
        weeks = int(p[4]) if p[4] else 0
        rec = {
            "id": pid, "n": p[1], "r": p[2] or None,
            "a": float(p[3]) if p[3] else None,
            "f": p[5] or None, "l": p[6] or None,
            "lo": float(p[7]) if p[7] else None,
            "hi": float(p[8]) if p[8] else None,
            # renamed on purpose - see the module docstring
            "sl": p[9] or None, "sh": p[10] or None, "sm": p[11] or None,
            "c": [round(float(x), 2) for x in p[12].split(",") if x.strip()],
            "a5": [], "a5d": [],
        }
        for part in p[13].split(","):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                bad.append(f"id {pid}: ask {part!r} is not a card:delivered pair")
                continue
            cp, dp = part.split(":", 1)
            rec["a5"].append(round(float(cp), 2))
            rec["a5d"].append(round(float(dp), 2))
        if rec["a5d"] != sorted(rec["a5d"]):
            bad.append(f"id {pid}: ask depth is not ordered by delivered price: {rec['a5d']}")
        if rec["a5"] and rec["a"] is not None and abs(rec["a5"][0] - rec["a"]) > 0.005:
            bad.append(f"id {pid}: ask {rec['a']} is not the first of {rec['a5']}")
        if rec["sl"]:
            for label, q in (("low", rec["sl"]), ("high", rec["sh"]), ("market", rec["sm"])):
                if q is None or len(q) != weeks * 2:
                    bad.append(f"id {pid}: packed {label} is "
                               f"{0 if q is None else len(q)} chars, expected {weeks * 2}")
                elif not q.isdigit():
                    bad.append(f"id {pid}: packed {label} has non-digits")
            if rec["lo"] is None or rec["hi"] is None:
                bad.append(f"id {pid}: packed series without lo/hi")
            elif rec["lo"] > rec["hi"]:
                bad.append(f"id {pid}: lo {rec['lo']} above hi {rec['hi']}")
        else:
            for k in ("sl", "sh", "sm"):
                rec[k] = None
        out[pid] = rec
    return out, bad


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    pull_path, list_path, snap_path, out_path = sys.argv[1:5]

    pulled, bad = parse(pull_path)
    wanted = {int(c["id"]): c for c in json.load(open(list_path))}

    missing = set(wanted) - set(pulled)
    extra = set(pulled) - set(wanted)
    if missing:
        bad.append(f"{len(missing)} requested cards not in the pull: {sorted(missing)[:5]}")
    if extra:
        bad.append(f"{len(extra)} pulled cards were not requested: {sorted(extra)[:5]}")
    if bad:
        print("REFUSING TO WRITE")
        for b in bad[:10]:
            print("  error ", b)
        return 1

    groups, order = {}, []
    for pid, rec in pulled.items():
        src = wanted[pid].get("set") or "Other"
        # A promo with no art is identified by its number and where it came
        # from, so both travel with the card rather than living only in a
        # group banner that sorting will dissolve.
        rec["num"] = wanted[pid].get("num") or None
        rec["src"] = src
        if src not in groups:
            groups[src] = []
            order.append(src)
        groups[src].append(rec)

    # Biggest source first, then alphabetical - Organized Play dominates and
    # should not be buried under a three-card judge promo group.
    order.sort(key=lambda s: (-len(groups[s]), s))
    snap = json.load(open(snap_path))
    snap["extras"] = [{"set": s, "cards": sorted(groups[s], key=lambda c: c["n"])}
                      for s in order]

    charted = sum(1 for r in pulled.values() if r["sl"])
    priced = sum(1 for r in pulled.values() if r["a"] is not None)
    sold = sum(1 for r in pulled.values() if r["c"])
    deep = sum(1 for r in pulled.values() if len(r["a5"]) >= 2)
    print(f"extras: {len(pulled)} cards in {len(order)} groups, "
          f"{charted} charted, {priced} with an ask, {sold} with sales, "
          f"{deep} with more than one ask listed")
    for s in order:
        print(f"    {len(groups[s]):>4}  {s}")

    json.dump(snap, open(out_path, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
