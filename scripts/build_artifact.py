import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Turn the generated board.standalone.html into an artifact-publishable page.

board.standalone.html is build output and is never edited in place. This script
reads it and writes a separate file, applying only what the artifact host needs:

  1. strip the <!doctype>/<html>/<head>/<body> wrapper (the host supplies one)
  2. inline Inter + IBM Plex Mono as data URIs (CSP blocks font CDNs)
  3. inline the 666 TCGplayer card thumbnails as WebP data URIs (CSP blocks
     remote images), downscaled to 176px - 2x the 88px the board displays

Re-run after any rebuild:  venv/bin/python build_artifact.py
"""
import base64, glob, io, json, os, re, sys
from PIL import Image

HERE = WORK
REPO = ROOT
SRC   = os.path.join(REPO, "board.standalone.html")
FONTS = os.path.join(HERE, "fonts_inline.css")
CACHE = os.path.join(HERE, "imgcache")
OUT   = os.path.join(HERE, "riftbound-board.html")

# The publish path times out somewhere above ~6.5 MB. 1049 thumbnails at
# 176px/q60 made a 10 MB page and 144px/q52 a 7 MB one, both rejected;
# 120px still clears the 88px display size with room for a hi-dpi screen.
THUMB_W, WEBP_Q = 108, 48

# ---------- 1. encode the thumbnails ----------
imgs, raw_total = {}, 0
for path in sorted(glob.glob(os.path.join(CACHE, "*.jpg"))):
    cid = os.path.splitext(os.path.basename(path))[0]
    im = Image.open(path).convert("RGB")
    im.thumbnail((THUMB_W, THUMB_W * 10), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=WEBP_Q, method=6)
    raw_total += buf.tell()
    imgs[cid] = base64.b64encode(buf.getvalue()).decode("ascii")
print(f"encoded {len(imgs)} thumbnails: {raw_total/1024/1024:.2f} MB raw"
      f" -> {sum(len(v) for v in imgs.values())/1024/1024:.2f} MB base64")

# ---------- 2. slice the generated page ----------
# Located by content, not by line number: the board grows every time a set
# lands, and hardcoded offsets silently slice the wrong lines when it does.
src = open(SRC).read().split("\n")

def only(pred, what):
    hits = [i for i, l in enumerate(src) if pred(l)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {what}, found {len(hits)}")
    return hits[0]

i_title = only(lambda l: l.strip().startswith("<title>"), "<title> line")
i_bg    = only(lambda l: l.lstrip().startswith("<style>html,body"), "html/body style")
i_body  = only(lambda l: l.strip() == "<body>", "<body>")
i_close = only(lambda l: l.strip() == "</body>", "</body>")
i_style = only(lambda l: l.strip() == "<style>" and l == "<style>", "opening page <style>")
i_script_end = max(i for i, l in enumerate(src) if l.strip() == "</script>")

font_links = [i for i, l in enumerate(src) if "fonts.googleapis" in l or "fonts.gstatic" in l]
assert src[0].startswith("<!DOCTYPE"), src[0]
assert i_title < i_body < i_style < i_script_end < i_close
assert font_links and all(i_body < i < i_style for i in font_links), font_links

comment = src[i_body + 1]
assert comment.strip().startswith("<!--"), comment
body = [comment] + src[i_style:i_script_end + 1]
assert body[1].strip() == "<style>",    body[1]
assert body[-1].strip() == "</script>", body[-1]
assert not any("fonts.googleapis" in l or "fonts.gstatic" in l for l in body)
text = "\n".join(body)

# ---------- 3. route every <img> site through the embedded map ----------
# Three sites now: renderCatalog and renderCards write the tag on one and two
# source lines respectively, and the deck pricer keys off `e` rather than `c`.
# One pattern covers all three rather than three brittle ones, and the count is
# asserted so a fourth site cannot be added without this failing loudly.
THUMB = re.compile(
    r"'<td class=\"thumb\"><img loading=\"lazy\" alt=\"\" "
    r"onerror=\\'this\.style\.display=\"none\"\\' "
    r"(?:' \+\n\s*')?"
    r"src=\"https://tcgplayer-cdn\.tcgplayer\.com/product/' \+ ([ce])\.id \+ '_200w\.jpg\"></td>'")

text, n_thumb = THUMB.subn(lambda m: "thumbCell(%s.id)" % m.group(1), text)
assert n_thumb == 3, f"expected 3 thumbnail sites, rewrote {n_thumb}"
assert "tcgplayer-cdn" not in text, "a CDN reference survived"

helper = (
    "<script>\n"
    "/* Card art, inlined because the artifact CSP blocks remote images. Ids with\n"
    "   no art on TCGplayer (Spiritforged runes and tokens) are simply absent and\n"
    "   render as an empty cell - what the old onerror handler did. */\n"
    "var CARDIMG = " + json.dumps(imgs, separators=(",", ":")) + ";\n"
    "function thumbCell(id) {\n"
    "  var d = CARDIMG[id];\n"
    "  return '<td class=\"thumb\">' +\n"
    "    (d ? '<img loading=\"lazy\" alt=\"\" src=\"data:image/webp;base64,' + d + '\">' : '') +\n"
    "    '</td>';\n"
    "}\n"
    "</script>"
)

# ---------- 4. undo the host reset's clamp on the thumbnails ----------
# The artifact wrapper injects `img{max-width:100%}` into its own <head>. The
# board only ever sets `width` on .thumb img, and max-width is a separate
# property, so the host rule clamps every thumbnail to whatever the auto-layout
# table gives the column. Playables is the only six-column table and collapsed
# its art to 6px wide; the five-column tables shrank to 64px. Restore the
# board's own fixed size and keep the column wide enough to hold it.
override = (
    "<style>\n"
    ".thumb img { max-width: none; min-width: 88px; }\n"
    ".thumb { min-width: 102px; }   /* 88px + the cell's 14px side padding */\n"
    "</style>"
)

page = "\n".join([src[i_title], src[i_bg],
                  "<style>", open(FONTS).read(), "</style>",
                  helper, text, override]) + "\n"
open(OUT, "w").write(page)
mb = len(page.encode()) / 1024 / 1024
print(f"wrote {OUT}")
print(f"page: {mb:.2f} MB  ({'OK' if mb < 16 else 'OVER'} vs the 16 MB cap)")
