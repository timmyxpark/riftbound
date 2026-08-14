#!/usr/bin/env python3
"""Merge the catalog last-5-sales pull into the snapshot.

    python3 merge_sales.py sales_pull.txt snapshot.json snapshot.out.json

Line format: `id|p,p,p` newest first, shipping included, or `id|` for none.

The feed caps at five sales per product with no paging (offset is ignored), and
those five are then filtered to Near Mint, English and raw, so a card can end up
with fewer than five. That is the ceiling, not a partial transfer.
"""

import json
import sys

MAX_SALES = 5


def parse(path):
    out, bad = {}, []
    for n, line in enumerate(open(path).read().splitlines(), 1):
        line = line.rstrip()
        if not line:
            continue
        pid, _, rest = line.partition("|")
        try:
            pid = int(pid)
        except ValueError:
            bad.append(f"line {n}: bad id {pid!r}")
            continue
        vals = []
        for tok in rest.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                v = float(tok)
            except ValueError:
                bad.append(f"id {pid}: non-numeric sale {tok!r}")
                continue
            if v <= 0:
                bad.append(f"id {pid}: non-positive sale {v}")
            vals.append(round(v, 2))
        if len(vals) > MAX_SALES:
            bad.append(f"id {pid}: {len(vals)} sales, feed caps at {MAX_SALES}")
        out[pid] = vals
    return out, bad


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    pull_path, snap_path, out_path = sys.argv[1:]

    data, bad = parse(pull_path)
    snap = json.load(open(snap_path))
    cards = [c for g in snap["catalog"] for c in (g.get("cards") or [])]

    want = {c["id"] for c in cards}
    missing, extra = want - set(data), set(data) - want
    if missing:
        bad.append(f"{len(missing)} cards with no pulled line: {sorted(missing)[:5]}")
    if extra:
        bad.append(f"{len(extra)} lines matching no card: {sorted(extra)[:5]}")
    if bad:
        for b in bad:
            print(f"  FAIL  {b}")
        sys.exit(f"\n{len(bad)} problem(s); nothing written.")

    applied = empty = 0
    dist = {}
    odd = []
    for c in cards:
        v = data[c["id"]]
        dist[len(v)] = dist.get(len(v), 0) + 1
        if not v:
            c.pop("c", None)
            empty += 1
            continue
        c["c"] = v
        applied += 1
        # A sale far above the ask usually means a graded or foreign copy slipped
        # the title filter. Reported, not dropped - it is a real sale either way.
        if c.get("a"):
            worst = max(v)
            if worst > c["a"] * 8 and worst - c["a"] > 5:
                odd.append((c["n"], c["a"], worst))

    print("  sales per card: " + ", ".join(
        f"{k}:{dist[k]}" for k in sorted(dist)))
    if odd:
        odd.sort(key=lambda r: -r[2] / r[1])
        print(f"  note  {len(odd)} cards have a sale far above their ask "
              f"(likely graded or foreign, kept): " +
              "; ".join(f"{n} ask {a} sale {w}" for n, a, w in odd[:3]))
    print(f"\ncatalog sales: {applied} with sales, {empty} without "
          f"({applied + empty} of {len(cards)})")
    json.dump(snap, open(out_path, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
