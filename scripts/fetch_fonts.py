import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import re, base64, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CSS = ("https://fonts.googleapis.com/css2?"
       "family=Inter:wght@400;500;600;700&"
       "family=IBM+Plex+Mono:wght@400;500;600&display=swap")

def get(url, binary=False):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    d = urllib.request.urlopen(r, timeout=30).read()
    return d if binary else d.decode("utf-8")

css = get(CSS)
blocks = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
print("total @font-face blocks:", len(blocks))

out, kept = [], 0
for b in blocks:
    ur = re.search(r"unicode-range:\s*([^;]+);", b)
    # latin subset only - the block that covers basic ASCII/Latin-1
    if not ur or "U+0000-00FF" not in ur.group(1):
        continue
    fam = re.search(r"font-family:\s*'([^']+)'", b).group(1)
    wt  = re.search(r"font-weight:\s*(\d+)", b).group(1)
    sty = re.search(r"font-style:\s*(\w+)", b).group(1)
    url = re.search(r"url\((https://[^)]+\.woff2)\)", b).group(1)
    data = get(url, binary=True)
    b64 = base64.b64encode(data).decode("ascii")
    kept += 1
    print(f"  {fam} {wt} {sty}: {len(data)/1024:.1f} KB -> {len(b64)/1024:.1f} KB b64")
    out.append(
        "@font-face{font-family:'%s';font-style:%s;font-weight:%s;font-display:swap;"
        "src:url(data:font/woff2;base64,%s) format('woff2');}" % (fam, sty, wt, b64)
    )

print("kept:", kept)
with open(_os.path.join(WORK, _os.path.join(WORK, "FONTS_OUT")), "w") as f:
    f.write("<style>\n" + "\n".join(out) + "\n</style>\n")
