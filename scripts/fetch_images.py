import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

REPO = ROOT
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), _os.path.join(WORK, "imgcache"))
os.makedirs(CACHE, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

snap = json.load(open(os.path.join(REPO, "snapshot.json")))
ids = []
for k in ("signatures", "overnumbered", "catalog"):
    for g in snap.get(k) or []:
        for c in g.get("cards", []):
            if c.get("id") is not None and c["id"] not in ids:
                ids.append(c["id"])
print("unique ids:", len(ids), flush=True)

def grab(i):
    dest = os.path.join(CACHE, f"{i}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return ("cached", i)
    url = f"https://tcgplayer-cdn.tcgplayer.com/product/{i}_200w.jpg"
    for attempt in range(3):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA})
            data = urllib.request.urlopen(r, timeout=30).read()
            if len(data) < 1000:
                return ("tiny", i)
            open(dest, "wb").write(data)
            return ("ok", i)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return (f"http{e.code}", i)
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return ("fail", i)

res = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for n, out in enumerate(ex.map(grab, ids), 1):
        res.append(out)
        if n % 100 == 0:
            print(f"  {n}/{len(ids)}", flush=True)

from collections import Counter
print(dict(Counter(s for s, _ in res)))
missing = [i for s, i in res if s not in ("ok", "cached")]
json.dump(missing, open(os.path.join(CACHE, "_missing.json"), "w"))
print("missing:", len(missing), missing[:10])
