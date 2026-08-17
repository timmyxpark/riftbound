#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Generate the paste-into-TCGplayer script that deepens the short sales.

The sales endpoint caps at five rows and sets no nextPage unless the request
carries session cookies, so this half cannot run from here - it has to run in a
logged-in tab. This writes that script, pre-loaded with the ids that are short
and the printing each product should be filtered to.

    python3 gen_sales_script.py > deepen_sales.js
"""
import json, os, sys

REPO = ROOT
HERE = WORK
snap = json.load(open(os.path.join(REPO, "snapshot.json")))

# printing per product, from the ask re-pull (Normal where the product has one)
printing = {}
for line in open(os.path.join(HERE, "ask_pull.txt")).read().splitlines():
    if not line.strip():
        continue
    p = line.split("|")
    if p[2] in ("Normal", "Foil"):
        printing[int(p[0])] = p[2]

short = []
for g in snap.get("catalog") or []:
    for c in g.get("cards", []):
        if len(c.get("c") or []) < 5:
            short.append(c["id"])

print(f"""// Deepen the last-5 sales for the {len(short)} Playables cards that carry fewer
// than five. Run this in the console of a loaded, SIGNED-IN tcgplayer.com tab.
//
// Why it has to run there: the sales endpoint answers anonymous callers with
// totalResults 5 and an empty nextPage no matter what limit/offset you send.
// With cookies attached the same product returns 25 rows per page and pages
// properly, which is what lets the filter chain reach a full five.
//
// It runs in the background and writes to window.__salesOut, so it cannot hit
// the 45s foreground limit. Watch window.__salesProgress, then when it is done:
//     copy(window.__salesOut)
// and paste into pulls/sales_deep.txt.

(() => {{
  const IDS = {json.dumps(short)};
  const PRINTING = {json.dumps({k: v for k, v in printing.items() if k in set(short)})};

  const FOREIGN_NAME = /chinese|japanese|korean|french|german|spanish|italian|portuguese|russian|vietnamese|indonesian|\\bjpn\\b|\\bchn\\b|\\bkor\\b|[\\u4e00-\\u9fff\\u3040-\\u30ff\\uac00-\\ud7af]/i;
  const FOREIGN_CODE = /[(\\[*\\-\\/|]\\s*(?:CN|JP|KR|FR|DE|ES|IT|PT|RU|TH|VN)\\s*[)\\]*\\-\\/|]/;
  const GRADED = /\\b(psa|bgs|cgc|sgc|beckett|ace)\\b\\s*\\.?\\s*\\d|graded|\\bgem\\s*mt\\b/i;

  const ok = (s, want) => {{
    if (s.condition !== "Near Mint") return false;
    if (s.language !== "English") return false;
    if (want && s.variant && s.variant !== want) return false;
    const t = s.title || "";
    if (FOREIGN_NAME.test(t) || FOREIGN_CODE.test(t) || GRADED.test(t)) return false;
    return true;
  }};

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  async function page(id, offset) {{
    const r = await fetch(
      "https://mpapi.tcgplayer.com/v2/product/" + id + "/latestsales?mpfev=1",
      {{ method: "POST",
        credentials: "include",                 // <-- the whole point
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ conditions: [], languages: [], variants: [],
                              listingType: "All", limit: 25, offset }}) }});
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }}

  window.__salesOut = "";
  window.__salesProgress = "0/" + IDS.length;
  window.__salesFailed = [];

  (async () => {{
    const lines = [];
    for (let i = 0; i < IDS.length; i++) {{
      const id = IDS[i], want = PRINTING[id] || null;
      const keep = [];
      let offset = 0, guard = 0;
      try {{
        while (keep.length < 5 && guard++ < 6) {{
          const d = await page(id, offset);
          const rows = d.data || [];
          if (!rows.length) break;
          for (const s of rows) {{
            if (keep.length >= 5) break;
            if (ok(s, want)) keep.push(+(s.purchasePrice + (s.shippingPrice || 0)).toFixed(2));
          }}
          if (!d.nextPage) break;               // no more pages for this product
          offset += rows.length;
          await sleep(400);                     // this endpoint 500s if pushed
        }}
        lines.push(id + "|" + keep.join(","));
      }} catch (e) {{
        window.__salesFailed.push([id, String(e)]);
      }}
      window.__salesProgress = (i + 1) + "/" + IDS.length +
                               "  failed:" + window.__salesFailed.length;
      window.__salesOut = lines.join("\\n");
      await sleep(400);
    }}
    window.__salesProgress = "DONE " + lines.length + "/" + IDS.length +
                             "  failed:" + window.__salesFailed.length;
  }})();
}})();""")
