#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Enumerate a Riftbound set and classify its Playables, per HANDOFF.md.

Keep a search row when rarity is present and is not the string "None" (sealed
product uses "None", not null), and the number is a plain NNN/SIZE, a base rune
(R04), or a token (T01, or containing "//").

Drop signatures (*), overnumbered (number above set size with no letter suffix),
alt art (letter suffix below set size), showcase runes (R04a) and SP numbers.
"""
import json, re, sys, time, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
URL = "https://mp-search-api.tcgplayer.com/v1/search/request?q=&isList=false&mpfev=1"
LINE = "riftbound-league-of-legends-trading-card-game"

PLAIN = re.compile(r"^(\d+)\s*/\s*(\d+)$")          # 053/219
RUNE  = re.compile(r"^R(\d+)$", re.I)               # R04   (R04a is showcase)
TOKEN = re.compile(r"^T\d+$", re.I)                 # T01


def page(setslug, frm, size=50, tries=4):
    body = json.dumps({
        "algorithm": "", "from": frm, "size": size,
        "filters": {"term": {"productLineName": [LINE], "setName": [setslug]},
                    "range": {}, "match": {}},
        "listingSearch": {"context": {"cart": {}},
                          "filters": {"term": {}, "range": {"quantity": {"gte": 1}},
                                      "exclude": {"sellerStatus": "Banned"}}},
        "context": {"cart": {}, "shippingCountry": "US"},
        "settings": {"useFuzzySearch": True, "didYouMean": {}}, "sort": {},
    }).encode()
    last = None
    for t in range(tries):
        try:
            r = urllib.request.Request(URL, data=body, headers={
                "Content-Type": "application/json", "User-Agent": UA,
                "Origin": "https://www.tcgplayer.com",
                "Referer": "https://www.tcgplayer.com/"})
            d = json.loads(urllib.request.urlopen(r, timeout=40).read())
            res = d["results"][0]
            return res["results"], res["totalResults"]
        except Exception as e:
            last = e
            time.sleep(1.5 * (t + 1))
    raise RuntimeError(f"{setslug}@{frm}: {last}")


def fetch_all(setslug):
    rows, frm = [], 0
    while True:
        got, total = page(setslug, frm)          # page size caps at 50
        rows += got
        frm += len(got)
        if frm >= total or not got:
            break
        time.sleep(0.35)
    return rows


def classify(rows):
    """Returns (playables, dropped) where playables is [(id, name, rarity, num)]."""
    sizes = {}
    for r in rows:
        m = PLAIN.match(str((r.get("customAttributes") or {}).get("number") or "").strip())
        if m:
            sizes[int(m.group(2))] = sizes.get(int(m.group(2)), 0) + 1
    setsize = max(sizes, key=sizes.get) if sizes else 0

    keep, drop = [], []
    for r in rows:
        pid = int(r.get("productId"))
        name = r.get("productName")
        rarity = r.get("rarityName")
        num = str((r.get("customAttributes") or {}).get("number") or "").strip()

        if not rarity or rarity == "None":
            drop.append((pid, name, num, "sealed / no rarity")); continue
        if "*" in num:
            drop.append((pid, name, num, "signature")); continue
        if num.upper().startswith("SP"):
            drop.append((pid, name, num, "SP number")); continue
        if "//" in num or TOKEN.match(num):
            keep.append((pid, name, rarity, num)); continue
        if RUNE.match(num):
            keep.append((pid, name, rarity, num)); continue
        if re.match(r"^R\d+[a-z]$", num, re.I):
            drop.append((pid, name, num, "showcase rune")); continue
        m = PLAIN.match(num)
        if m:
            n = int(m.group(1))
            if n > setsize:
                drop.append((pid, name, num, "overnumbered")); continue
            keep.append((pid, name, rarity, num)); continue
        if re.match(r"^\d+[a-z]\s*/", num, re.I):
            drop.append((pid, name, num, "alt art")); continue
        drop.append((pid, name, num, "unmatched number form"))
    return keep, drop, setsize


if __name__ == "__main__":
    slug = sys.argv[1]
    rows = fetch_all(slug)
    keep, drop, setsize = classify(rows)
    print(f"{slug}: {len(rows)} products, set size {setsize} -> "
          f"{len(keep)} playables, {len(drop)} dropped", file=sys.stderr)
    from collections import Counter
    for why, n in Counter(d[3] for d in drop).most_common():
        print(f"    dropped {n:>4}  {why}", file=sys.stderr)
    json.dump([{"id": i, "n": n, "r": r, "num": u} for i, n, r, u in keep],
              open(_os.path.join(WORK, f"set_{slug}.json"), "w"))
