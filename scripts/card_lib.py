#!/usr/bin/env python3
import os as _os, sys as _sys
# Repo-relative: these scripts used to hardcode a laptop path and keep their
# working files in a temp scratchpad, which meant a refresh could not be run
# from a clone or a scheduled job.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORK = _os.environ.get("RIFTBOUND_WORK") or _os.path.join(ROOT, ".pullcache")
_os.makedirs(WORK, exist_ok=True)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
"""Pull ask, weekly history and last-5 sales for one Riftbound product.

All three endpoints answer anonymous callers, with one documented exception:
latestsales caps at five rows and sets no nextPage without session cookies, so
`sales()` returns at most five and often fewer once filtered. That is a ceiling,
not a failed transfer - see HANDOFF.md.

Filter chain, applied everywhere: Near Mint; English by BOTH the language field
and the seller's title (the field lies); raw (no grade named in the title); and
the same printing throughout - Normal where the product has one, else Foil.

PRICE BASIS: the card price, WITHOUT shipping. Shipping is a flat ~$1.49 that
has nothing to do with the card, and on the sub-dollar half of the catalog it
was the whole number - 738 of 929 asks landed between $1.40 and $1.75 and not
one fell below $1.40, because a $0.01 common shipped is $1.50. It also happens
to fix a discrepancy the old basis carried: marketPrice has no shipping-
inclusive variant, so a shipping-inclusive low/high sat about 1% above the
market line it was drawn against. Everything is now on one basis.
"""
import json, re, time, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HDR = {"Content-Type": "application/json", "User-Agent": UA,
       "Origin": "https://www.tcgplayer.com", "Referer": "https://www.tcgplayer.com/"}

L_LISTINGS = "https://mp-search-api.tcgplayer.com/v1/product/{}/listings?mpfev=5457"
L_SALES    = "https://mpapi.tcgplayer.com/v2/product/{}/latestsales?mpfev=1"
L_HISTORY  = "https://infinite-api.tcgplayer.com/price/history/{}/detailed?range=annual"

FOREIGN_NAME = re.compile(
    r"chinese|japanese|korean|french|german|spanish|italian|portuguese|russian"
    r"|vietnamese|indonesian|\bjpn\b|\bchn\b|\bkor\b"
    r"|[一-鿿぀-ヿ가-힯]", re.I)
FOREIGN_CODE = re.compile(r"[(\[*\-/|]\s*(?:CN|JP|KR|FR|DE|ES|IT|PT|RU|TH|VN)\s*[)\]*\-/|]")
GRADED = re.compile(r"\b(psa|bgs|cgc|sgc|beckett|ace)\b\s*\.?\s*\d|graded|\bgem\s*mt\b", re.I)


# Sealed product carries its own contamination: sellers list a different item
# under a sealed id and still tick "Unopened". Observed on real listings - a
# "Vendetta sleeve blister pack" at $12 under the $135 booster box, an "*Opened
# booster box, only gold rarities were [pulled]*" at $60, and "Sealed 36 Basic
# Runes" at $5.50 under a Vault Bundle. Condition alone cannot see any of these.
#
# `opened` is matched only when not preceded by "un", so "Unopened" is safe.
NOT_SEALED = re.compile(
    r"(?<!un)(?<!never )(?<!not )opened|blister|\bsleeves?\b|basic runes|\btokens?\b|promo pack|playmat|deck ?box|\bmat only\b|\bdice\b|proxy|repack"
    r"|resealed|\bempty\b|box only|no box|\b(?:set|pack|lot)\s+of\s+\d", re.I)


def not_the_sealed_product(t):
    return bool(NOT_SEALED.search(t or ""))


def foreign_or_graded(t):
    t = t or ""
    return bool(FOREIGN_NAME.search(t) or FOREIGN_CODE.search(t) or GRADED.search(t))


def _req(url, body=None, tries=4):
    last = None
    for t in range(tries):
        try:
            r = urllib.request.Request(url, data=body, headers=HDR)
            return json.loads(urllib.request.urlopen(r, timeout=40).read())
        except Exception as e:
            last = e
            time.sleep(1.5 * (t + 1))
    raise RuntimeError(str(last)[:80])


# ---------------------------------------------------------------- listings
def listings(pid):
    out = []
    for frm in (0, 50, 100):
        body = json.dumps({
            "filters": {"term": {"sellerStatus": "Live", "channelId": 0},
                        "range": {"quantity": {"gte": 1}},
                        "exclude": {"channelExclusion": 0}},
            "from": frm, "size": 50,
            "sort": {"field": "price+shipping", "order": "asc"},
            "context": {"shippingCountry": "US", "cart": {}}}).encode()
        res = _req(L_LISTINGS.format(pid), body)["results"][0]
        out += res["results"]
        if len(out) >= res["totalResults"] or not res["results"]:
            break
        time.sleep(0.3)
    return out


def clean_asks(rows):
    """(ascending card-only prices, printing) for the qualifying listings.

    The filter chain lives here once so the ask and the ask depth can never
    disagree. That matters more than it looks: the whole point of showing five
    asks is to say whether the cheapest is a lone undercut, and a depth list
    filtered any more loosely would seat a Chinese copy at position two, under
    the English ones - the exact failure the ask column was fixed for.
    """
    ok = [l for l in rows
          if l.get("condition") == "Near Mint"
          and l.get("language") == "English"
          and not foreign_or_graded((l.get("customData") or {}).get("title"))]
    if not ok:
        return [], None
    normals = [l for l in ok if l.get("printing") == "Normal"]
    pick = normals if normals else ok
    printing = "Normal" if normals else (pick[0].get("printing") or "Foil")
    price = lambda l: round(float(l.get("price", 0)), 2)   # card only, no shipping
    return sorted(price(l) for l in pick), printing


def ask_and_printing(pid, rows=None):
    """(ask, printing). Printing is decided here and reused by history+sales."""
    prices, printing = clean_asks(listings(pid) if rows is None else rows)
    return (prices[0] if prices else None), printing


def ask_depth(rows, depth=5):
    """The cheapest few qualifying asks, ascending - the cheapest one first.

    Takes rows the caller already fetched rather than fetching its own, so depth
    costs no extra request: every pull already has the listing feed in hand when
    it works out the ask.
    """
    prices, _ = clean_asks(rows)
    return prices[:depth]


# ---------------------------------------------------------------- history
def history(pid, printing=None):
    """Weekly Near Mint buckets, oldest first, keeping only weeks that sold.

    Returns (weeks, lows, highs, markets) on the card-price basis, which is what
    `ask`, the floor line and marketPrice all use.
    """
    res = _req(L_HISTORY.format(pid)).get("result") or []
    cand = [v for v in res if (v.get("condition") or "").strip() == "Near Mint"]
    if not cand:
        return [], [], [], []
    if printing:
        same = [v for v in cand if (v.get("variant") or "").strip() == printing]
        if same:
            cand = same
    else:
        normals = [v for v in cand if (v.get("variant") or "").strip() == "Normal"]
        if normals:
            cand = normals
    buckets = cand[0].get("buckets") or []

    weeks, lo, hi, mk = [], [], [], []
    for b in reversed(buckets):                       # API returns newest first
        try:
            qty = float(b.get("quantitySold") or 0)
            market = float(b.get("marketPrice") or 0)
        except ValueError:
            continue
        if qty <= 0 or market <= 0:                   # opening weeks have market 0
            continue
        try:
            l = float(b.get("lowSalePrice") or 0)
            h = float(b.get("highSalePrice") or 0)
        except ValueError:
            continue
        if l <= 0 or h <= 0:
            continue
        weeks.append(str(b.get("bucketStartDate"))[:10])
        lo.append(l); hi.append(h); mk.append(market)
    return weeks, lo, hi, mk


# ---------------------------------------------------------------- sales
def sales(pid, printing=None, limit=5):
    body = json.dumps({"conditions": [], "languages": [], "variants": [],
                       "listingType": "All", "limit": 25, "offset": 0}).encode()
    d = _req(L_SALES.format(pid), body)
    out = []
    for s in d.get("data", []):
        if len(out) >= limit:
            break
        if s.get("condition") != "Near Mint":            continue
        if s.get("language") != "English":               continue
        if printing and s.get("variant") and s.get("variant") != printing: continue
        if foreign_or_graded(s.get("title")):            continue
        out.append(round(float(s.get("purchasePrice") or 0), 2))   # card only
    return out


# ---------------------------------------------------------------- packing
def pack(series, lo, hi):
    span = (hi - lo) or 1
    return "".join(f"{max(0, min(99, round((v - lo) / span * 99))):02d}" for v in series)


def downsample(lows, highs, markets, bins=12):
    """Catalog series ship as 12 bins: low is the bin's min, high its max, market
    its last. Taking every Nth week instead would drop spikes."""
    n = len(lows)
    if n <= bins:
        return lows[:], highs[:], markets[:]
    edges = [round(i * n / bins) for i in range(bins + 1)]
    L, H, M = [], [], []
    for i in range(bins):
        a, b = edges[i], max(edges[i + 1], edges[i] + 1)
        L.append(min(lows[a:b])); H.append(max(highs[a:b])); M.append(markets[b - 1])
    return L, H, M


# ---------------------------------------------------------------- tcg summary
L_SEARCH = "https://mp-search-api.tcgplayer.com/v1/search/request?q={}&isList=false&mpfev=1"
PRODUCT_LINE = "riftbound-league-of-legends-trading-card-game"


def tcg_summary(pid, name):
    """TCGplayer's own per-product aggregate: (lowest, lowestWithShipping, market).

    For SEALED product this beats filtering the listing feed by hand.
    `lowestPriceWithShipping` is the "from $X" TCGplayer advertises and it
    already excludes the junk that the raw feed carries - a $180 "Origins
    Booster Box Unopened" and a $55 Chinese box both sit in the feed under the
    real $244.78. Note `lowestPrice` is NOT the clean one: it reports that $55.

    Do not use this for singles - it does not know about Near Mint.
    """
    import urllib.parse
    body = json.dumps({
        "algorithm": "", "from": 0, "size": 50,
        "filters": {"term": {"productLineName": [PRODUCT_LINE]}, "range": {}, "match": {}},
        "listingSearch": {"context": {"cart": {}},
                          "filters": {"term": {}, "range": {"quantity": {"gte": 1}},
                                      "exclude": {"sellerStatus": "Banned"}}},
        "context": {"cart": {}, "shippingCountry": "US"},
        "settings": {"useFuzzySearch": True, "didYouMean": {}}, "sort": {}}).encode()
    d = _req(L_SEARCH.format(urllib.parse.quote(name)), body)
    for r in d["results"][0]["results"]:
        if int(r.get("productId", 0)) == pid:
            return (r.get("lowestPrice"), r.get("lowestPriceWithShipping"), r.get("marketPrice"))
    return (None, None, None)
