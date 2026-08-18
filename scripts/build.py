#!/usr/bin/env python3
"""Build the Riftbound board from template.v2.html + a snapshot JSON.

    python3 build.py snapshot.json template.v2.html riftbound-case-board.html

Every check here exists because of a failure noted in HANDOFF.md. The one that
matters most is the count check: a chunked transfer that silently drops rows
produces a board that looks entirely plausible, so counts are asserted against
expectations rather than eyeballed.
"""

import json
import sys

# Expected product counts. Update deliberately, not to make a build pass.
EXPECT = {
    "sets": 5,               # 4 cases + Radiance placeholder
    "signatures": 45,
    "overnumbered": 92,
    # Origins was 297 in the original pull; that count was wrong - see HANDOFF.
    "catalog": {"Origins": 299, "Spiritforged": 230, "Unleashed": 225, "Vendetta": 175},
    "boxes": 4,              # one booster display per released set
    "sealed": 5,             # standalone bundles and box sets
    # Promos & Extras is defined by subtraction - every card the other tabs do
    # not carry - so this number moves whenever a set lands or the Playables
    # classifier changes. Update it deliberately.
    "extras": 401,
}


def cards_of(groups):
    return [c for g in groups or [] for c in (g.get("cards") or [])]


def as_series(v, lo, hi):
    """Series arrive either as plain arrays or as packed two-digit strings that
    rescale against lo/hi. Comparing packed strings directly compares characters,
    which silently reports nonsense, so always widen to numbers first."""
    if v is None:
        return None
    if isinstance(v, str):
        if lo is None or hi is None or len(v) % 2:
            return None
        span = (hi - lo) or 1
        return [lo + int(v[i:i + 2]) / 99 * span for i in range(0, len(v), 2)]
    return list(v)


def check(snap):
    """Returns (errors, warnings). Errors block the build."""
    errs, warns = [], []

    n_sets = len(snap.get("sets") or [])
    if n_sets != EXPECT["sets"]:
        errs.append(f"sets: {n_sets}, expected {EXPECT['sets']}")

    for key in ("signatures", "overnumbered", "extras"):
        n = len(cards_of(snap.get(key)))
        if n != EXPECT[key]:
            errs.append(f"{key}: {n} cards, expected {EXPECT[key]}")

    # Sealed cases, boxes and the standalone products all render through the
    # same row renderer, so they all get the same integrity check: series,
    # weeks and the three band series must line up or the chart silently drops
    # back to a bare midpoint line.
    def check_band(label, s, errs):
        """True when this record carries a usable low/high/market band."""
        series, weeks = s.get("series") or [], s.get("weeks") or []
        if series and weeks and len(series) != len(weeks):
            errs.append(f"{label}: {len(series)} points against {len(weeks)} weeks")
            return False
        trio = [s.get("low"), s.get("high"), s.get("market")]
        if not any(t is not None for t in trio):
            return False
        if any(t is None for t in trio):
            errs.append(f"{label}: partial low/high/market")
        elif len({len(t) for t in trio} | {len(series)}) != 1:
            errs.append(f"{label}: low/high/market do not match series length")
        elif any(lo > hi for lo, hi in zip(s["low"], s["high"])):
            errs.append(f"{label}: weekly low above high")
        elif any(m <= 0 for m in s["market"]):
            errs.append(f"{label}: non-positive market price")
        else:
            drift = max(abs(round((lo + hi) / 2, 2) - m)
                        for lo, hi, m in zip(s["low"], s["high"], series))
            if drift > 0.51:
                errs.append(f"{label}: series is not the midpoint of low/high (off by {drift:.2f})")
            else:
                return True
        return False

    for key in ("sets", "boxes", "sealed"):
        recs = snap.get(key) or []
        if key != "sets":
            if len(recs) != EXPECT[key]:
                errs.append(f"{key}: {len(recs)}, expected {EXPECT[key]}")
        banded = sum(1 for s in recs if check_band(f"{key}/{s.get('set')}", s, errs))
        warns.append(f"{key}: {banded}/{len(recs)} have low/high/market history")

    # Catalog is checked per set, since it lands one set at a time.
    for g in snap.get("catalog") or []:
        name, n = g.get("set"), len(g.get("cards") or [])
        want = EXPECT["catalog"].get(name)
        if want is None:
            warns.append(f"catalog: unrecognised set {name!r} ({n} cards)")
        elif n != want:
            errs.append(f"catalog/{name}: {n} cards, expected {want}")
    have = {g.get("set") for g in snap.get("catalog") or []}
    for name in EXPECT["catalog"]:
        if name not in have:
            warns.append(f"catalog: {name} not present yet")

    # Series integrity. A ragged triple renders as a bare line rather than
    # crashing, which is exactly the kind of silent downgrade worth failing on.
    for key in ("signatures", "overnumbered"):
        for c in cards_of(snap.get(key)):
            raw = [c.get("sl"), c.get("sh"), c.get("sm")]
            if not any(t is not None for t in raw):
                continue
            if any(t is None for t in raw):
                errs.append(f"{key}/{c.get('n')}: partial sl/sh/sm")
                continue
            trio = [as_series(t, c.get("lo"), c.get("hi")) for t in raw]
            if any(t is None for t in trio):
                errs.append(f"{key}/{c.get('n')}: packed series without usable lo/hi")
            elif len({len(t) for t in trio}) != 1:
                errs.append(f"{key}/{c.get('n')}: sl/sh/sm lengths differ")
            elif len(trio[0]) < 2:
                errs.append(f"{key}/{c.get('n')}: fewer than 2 weeks")
            else:
                slack = ((c.get("hi") or 0) - (c.get("lo") or 0)) / 99 * 1.5
                if any(lo > hi + slack for lo, hi in zip(trio[0], trio[1])):
                    errs.append(f"{key}/{c.get('n')}: weekly low above high")

    for g in snap.get("catalog") or []:
        for c in g.get("cards") or []:
            trio = [c.get("ql"), c.get("qh"), c.get("qm")]
            if any(t is not None for t in trio):
                if any(t is None for t in trio):
                    errs.append(f"catalog/{c.get('n')}: partial ql/qh/qm")
                elif len({len(t) for t in trio}) != 1:
                    errs.append(f"catalog/{c.get('n')}: ql/qh/qm lengths differ")
                elif c.get("lo") is None or c.get("hi") is None:
                    errs.append(f"catalog/{c.get('n')}: packed series without lo/hi")
                elif any(len(t) % 2 for t in trio):
                    errs.append(f"catalog/{c.get('n')}: odd-length packed series")

    # Coverage, reported not enforced, so a partial pull can still ship.
    for label, cards, field in (
        ("signatures", cards_of(snap.get("signatures")), "sl"),
        ("overnumbered", cards_of(snap.get("overnumbered")), "sl"),
        ("catalog", cards_of(snap.get("catalog")), "ql"),
    ):
        if cards:
            n = sum(1 for c in cards if c.get(field))
            warns.append(f"{label}: {n}/{len(cards)} have low/high/market history")
    cat = cards_of(snap.get("catalog"))
    if cat:
        n = sum(1 for c in cat if c.get("c"))
        warns.append(f"catalog: {n}/{len(cat)} have last-5 sales")

    return errs, warns


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    snap_path, tpl_path, out_path = sys.argv[1:]

    snap = json.load(open(snap_path))
    errs, warns = check(snap)

    for w in warns:
        print(f"  note  {w}")
    for e in errs:
        print(f"  FAIL  {e}")
    if errs:
        sys.exit(f"\n{len(errs)} problem(s); nothing written.")

    tpl = open(tpl_path).read()
    if tpl.count("__SNAPSHOT__") != 1:
        sys.exit("template must contain exactly one __SNAPSHOT__ marker")

    payload = json.dumps(snap, indent=2, ensure_ascii=False)
    # </script> inside a string literal would close the block early.
    payload = payload.replace("</", "<\\/")
    open(out_path, "w").write(tpl.replace("__SNAPSHOT__", payload))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
