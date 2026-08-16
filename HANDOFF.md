# Riftbound board - handoff

Updated Aug 15, 2026. The board file next to this doc is working and current.
The data pull is finished: all four sets are in and every section was repriced.

## Aug 15, 2026 - full re-pull, and the ask bug it fixed

**Every endpoint except deep sales works anonymously.** Listings, weekly history
and set search all answer a plain HTTPS request with a browser User-Agent and a
tcgplayer.com Origin/Referer - no session, no browser. That is what made a
1,066-product re-pull possible in one sitting. About 3,000 requests at roughly
one every 1.2s produced **zero failures**, so the thousand-request cooldown in
the notes below appears to be a property of the signed-in session rather than
of the endpoints themselves. Do not read that as licence to hammer them.

**The asks were priced off Chinese listings.** `language` says English on
listings just as it lies on sales, and nothing in the ask pull had ever checked
`customData.title`. Yasuo, Unforgiven (Overnumbered) asked $50 against a real
Near Mint English $81, with four cheaper Chinese copies sorted above it; Seal of
Rage asked $42.98 against $63.99, its cheapest listing titled
`Seal of Rage Overnumbered (CN)`. **Sealed cases had it too** - the cheapest
"Origins case" is a Chinese jumbo-pack case at $908 against the English
$1,604.99, and Spiritforged's two cheapest are Chinese slim cases at ~$445
against $1,151.88. 92 of 137 signature and overnumbered asks changed.

Match language *names* and CJK anywhere in a title, but match two-letter codes
only when bracketed or asterisked - `(CN)`, `[JP]`, `**CN**`. A bare `\bit\b`
matches the English word "it". Audited across 95 real seller titles: 84 genuine
hits, zero false positives.

**How the filter chain was proved rather than trusted.** Every stage was checked
against data already on the board before anything was written:

| Check | Result |
|---|---|
| Sealed-case floors, all four sets | matched stored exactly |
| Origins case ask | $1,604.99, matched stored to the cent |
| Case midpoint vs stored `series` | drift 0.00 on all four |
| Control card weeks / first / last / lo / hi | matched stored exactly |
| Set classification vs `catalog_ids.json` | id-for-id on all four sets |

**Sales are the one thing still gated.** Anonymously the endpoint returns
`totalResults: 5` and an empty `nextPage`, and `offset` is ignored - verified.
Filtering leaves three or four on many cards. Origins, Spiritforged, Signatures
and Overnumbered already held a full five from a signed-in pull, so overwriting
would have been a regression: fresh sales now lead and stored ones backfill
behind them to five. 302 of 929 Playables still carry fewer than five and only a
signed-in pull can fix that.

**Counts settled.** Vendetta is 175, not the 177 in the old notes - a fresh
enumeration classified to 175 independently and matched `catalog_ids.json` id
for id. Origins is 299: 298 numbered plus token 653117 `Buff`, whose number is
null; `catalog_ids.json` was missing it and now has it. `merge_asks.py` is new.
`merge_sales.py` takes an optional section argument, defaulting to catalog.

## What the board has

| Tab | Contents | State |
|---|---|---|
| Sealed Cases | 4 cases + Radiance placeholder, full band charts | history current as of Aug 14 |
| Signature Overnumbers | 45 cards, full band charts | complete |
| Overnumbered | 92 cards incl. Baron Nashor (Ultimate), full band charts | complete |
| Playables | 529 cards: Origins 299, Spiritforged 230 | Unleashed, Vendetta to come |
| Calendar | 42 events through 2027 | complete |

Filters: set (multi-select), rarity (multi-select, All Cards only), price range
slider (All Cards only). All reset when you switch tabs.

## Latest case numbers

| Set | Ask | Floor | vs floor | Signal |
|---|---|---|---|---|
| Origins | $1,604.99 | $1,016 | 1.58x | light sell |
| Spiritforged | $1,099.00 | $800 | 1.37x | hold |
| Unleashed | $858.92 | $565 | 1.52x | hold |
| Vendetta | $862.00 | $720 | 1.20x | light buy |

## IMPORTANT - what the price fields actually mean

This took most of a day to work out, and two of my earlier conclusions were wrong.

**`marketPrice` is a trimmed, volume-weighted average across recent weeks.** It is
NOT that week's mean. On cards that actually trade, it is accurate:

| Card | Weekly low | Weekly high | Market | Real recent sales |
|---|---|---|---|---|
| Salvage | $3.49 | $22.98 | **$4.53** | $4.51 - $5.96 |
| Defy | $3.01 | $19.38 | **$3.98** | $3.39 - $6.83 |
| Miss Fortune | $3,000 | $3,000 | **$1,526** | $1,900 - $3,000 |

Market price only misleads on very thin cards - Miss Fortune had one sale that
week, so the average had not caught up. I originally generalised from that single
case and wrongly concluded market price was unreliable everywhere.

**Never plot the midpoint of weekly low and high on its own.** On Salvage that
gives $13.24 against real sales near $4.60. One odd high sale on a card moving
235+ copies a week wrecks it. This bug was live in the charts for a while.

**The right chart**: weekly low and high as light grey lines with grey shading
between them, and market price in green. The midpoint line was built and then
dropped - the two grey edges already show the range, so it only added clutter. Built and tested; see below. Waiting on data only.

## Build and tests

The board is generated, not hand-edited. `template.v2.html` holds the code with a
single `__SNAPSHOT__` marker; `build.py` injects the snapshot JSON:

    python3 build.py snapshot.json template.v2.html riftbound-case-board.html
    node test_chart.js          # chart geometry, in isolation
    node test_board.js FILE     # loads the built board in jsdom, counts rows

`build.py` refuses to write if counts drift from the expected 45 signatures, 92
overnumbered, 5 sets and the per-set catalog sizes, which is the guard against
the chunk-transfer bug that silently dropped 7 cards. It also rejects a partial
or ragged `sl`/`sh`/`sm` triple. Coverage is printed as a note, not enforced, so
a partial pull can still ship.

## Five-line charts - renderer done, data not pulled

`chart()` now takes an optional fourth series bundle and draws all five elements:
low and high as light grey lines, grey shading between them, and market in
green. The end dot sits on the market line. A colour key appears above each table, but
only on tabs whose cards actually carry the data.

**Cards without the new fields still render as the old single blue line.** That is
deliberate - a partial transfer degrades one row at a time instead of blanking the
board, and the coverage note in `build.py` tells you how far along the pull is.

Verified end to end against a synthetic fixture: 432 banded charts, no script
errors, all row counts intact. The renderer is not what is left to do.

## The midpoint bug was still live on the front tab

Found during the case pull. The catalog was fixed, but the **Sealed Cases charts
were still plotting the bare midpoint of weekly low and high**. Confirmed by
reconciling the stored `series` against the API: the shipping-inclusive midpoint
matched 48 of 48 weeks exactly on Origins. Now fixed - those charts carry the
full band, and the midpoint only appears alongside the low, high and market that
give it context.

The midpoint is still computed and still stored as `series`, and `build.py` still
checks it really is the midpoint of low and high. It just is not drawn. That
check is worth keeping: it is what caught the front-tab bug in the first place,
and it costs nothing to keep running.

Blue is now reserved for the single-series fallback and never means market price.
That matters because the fallback line is a different measure on each tab - the
midpoint on cases, the weekly low in the catalog - so a card still awaiting its
history pull cannot be mistaken for one showing market. Market is green, and is
the only green line on the board.

Worth knowing: on Origins the market line runs well below the midpoint for the
first two months. The old chart showed none of that.

## Layout: content is pinned to the top

`.wrap` is a full-height flex column. It used to carry `justify-content: center`,
which vertically centred everything - so filtering down to a handful of rows
dragged the title, tabs and filter chips into the middle of the screen. It is now
`flex-start`, and `test_filter.js` asserts that.

## Name filter

Signature Overnumbers, Overnumbered and Playables each carry a name box, next to
the set and rarity chips. It matches on a folded form - lowercased, accents
stripped, everything non-alphanumeric removed - so `kaisa` finds Kai'Sa and
`leblanc` finds LeBlanc. Matching on the raw string makes the filter look broken
on exactly the cards people search for.

Typing is debounced by 120ms, because each keystroke re-renders hundreds of
inline SVGs. The term clears on tab switch, like every other filter.

There is deliberately no match count beside the box. Playables still shows its
own "N of M cards shown" line under that table, which is a different element.

## Sales re-pull: where it stands, and the throttle

Signed-in state re-pulled: **Signatures 45/45 and Overnumbered 92/92 all show
five sales.** Playables is **323 of 529** at five; the remaining 206 still carry
the shallower anonymous-era pull. Every figure on the board is a real sale - the
mix is one of depth and vintage, not correctness.

**TCGplayer throttles hard on sustained use.** After roughly a thousand requests
the sales and history endpoints degraded from ~24 cards per 42s to about one
request every 15 seconds, and stayed there; adding backoff did not recover it.
This is a cooldown, not something to engineer around - finish the remaining 206
in a fresh session rather than pushing through.

Two practical notes for that run:

- A foreground `javascript_tool` call doing many sequential fetches will blow
  the 45-second CDP limit. Run the loop in the background writing to a `window`
  variable and poll it, as everywhere else here.
- Each card currently costs **two** requests: history to learn which printing
  the chart uses, then the sales themselves. Deriving the printing from the
  sales instead ("Normal if any qualifying Normal sale appears") agreed with the
  history-derived answer on 5 of 5 cards tested before the throttle stopped the
  test. That would halve the request count, but 5 samples is not enough to rely
  on - re-run that check to a decent sample before trusting it.

## Sharing the board

`riftbound-case-board.standalone.html` is the file to send or host. It is the
same board wrapped in a real HTML document - doctype, charset, title and, most
importantly, a **viewport tag**, without which the wide tables render at desktop
width on a phone. `riftbound-case-board.html` is the bare fragment and is not
suitable for sharing on its own.

Two things it still fetches from the internet: card thumbnails from TCGplayer's
CDN and Inter from Google Fonts. Fonts fall back to the system stack cleanly.
Thumbnails now carry an `onerror` that hides them, so offline the board loses
its images rather than showing 529 broken-image icons.

Careful with that `onerror`: it lives inside a single-quoted JS string, so its
attribute value has to use double quotes and the surrounding quotes escaped.
Writing it the obvious way terminates the string and the whole script dies -
`test_chart.js` catches it instantly, which is how it was found.

`riftbound-case-board.zip` is the same file zipped, because several mail
providers strip or block bare `.html` attachments.

## The date label covers two vintages

`pulledLabel` now reads "August 15, 2026 - Spiritforged; earlier sections August
14". Cases, signatures, overnumbered and most of the Origins catalog come from
the Aug 14 pull; Spiritforged and the two recovered Origins cards were pulled on
the 15th. A single timestamp cannot be honest about both, so it names both
rather than implying the whole board is fresh. Update it when a full re-pull
makes it true again.

## Labels vs data keys

The tab and section formerly called **All Cards** are labelled **Playables** in
the UI. The snapshot key is still `catalog`, and the table body id is still
`catbody` - renaming those would break `build.py`, `merge_cards.py`,
`merge_sales.py` and all three test suites for no gain. Note the snapshot also
carries an unrelated legacy `playables` key; do not confuse the two.

The chart column is headed **Market Price vs. High/Low Range** on all four
tables, and the blue key entry reads **Midpoint of High&Low Solds** (the
ampersand is escaped in the source).

## The end label on the green line

Every chart with a green market line prints the latest market price just right of
the green end dot, in green mono. `padR` is widened by the measured width of that
text *before* `x()` is defined, so the label always fits inside the viewBox
instead of being clipped by the svg edge; it costs the plot roughly 20px of
width on the small charts.

Rounded to the nearest whole dollar, **except under a dollar, where cents are
kept**. 214 of the 297 Origins cards have a market price below $1, so strict
integer rounding would print "0" on three quarters of the Playables column. If
whole dollars everywhere is genuinely wanted, it is one line in `chart()`.

## Signature charts are the odd one out

Signatures draw **market in green and the midpoint of weekly low and high in
blue**, with no shaded range and no grey edges. Every other section keeps the
band. The y axis on signatures scales to the two lines actually drawn, not to the
hidden low and high, which would otherwise squash both into the lower third -
Ahri's high touches 6,500 while its market sits near 3,400.

Both lines end in a dot - green on market, blue on the midpoint - drawn in that
order so blue sits on top where the two converge. Per-week dots along the lines
belong to the single-series fallback only; `test_chart.js` asserts a banded chart
emits none, so a signature chart holds exactly two circles.

Note this overrides the earlier "blue means history not pulled yet" convention on
that tab. It is not currently ambiguous, because all 438 products have history
and the single-line fallback never renders. It would become ambiguous again if a
new set landed unpulled, so if you add Radiance, give the fallback its own colour.

## Chart sizing and the y axis

Charts were enlarged - small ones from 220x70 to 240x92, large from 300x92 to
320x118, with a wider label gutter and slightly larger tick text. The SVGs scale
to the column width, so the taller viewBox is what buys the vertical room.

More importantly, `niceTicks` was rewritten. It used to fix the tick count and
push the step up until the range fit, which on a card spanning 3.49 to 22.98
chose an axis of 0 to 40 and spent half the plot on empty space. The count is now
a **ceiling**, and the smallest nice step that fits under it wins - the same card
now gets 0 to 25. Tests assert the axis never leaves more than one gridline step
of headroom, and that the ticks stay sane from sub-dollar commons up to the
6,500-dollar signatures.

Every section now shares that one axis rule. The sealed cases used to run on
fixed 500-dollar steps, which gave Vendetta an axis of 500 to 1000 - two
gridlines for data spanning 700 to 985. That branch is gone. Measured fill of
the plot area, before and after:

| Set | Before | After |
|---|---|---|
| Origins | 73%, 5 lines | 73%, 5 lines |
| Spiritforged | 82%, 4 lines | 99%, 6 lines |
| Unleashed | 77%, 4 lines | 93%, 6 lines |
| Vendetta | 57%, 2 lines | 71%, 5 lines |

Origins is unchanged because its weekly low bottoms at 999.99, just under the
1,000 that would let a 250 step start there. Not worth chasing.

A ceiling of 6 was chosen by measurement: 7 changes nothing, and 8 lifts Origins
to 84% but drops Spiritforged to 88% and Unleashed to 83%, for a busier chart.

## Sealed product carries its own contamination

Sellers list a different item under a sealed product's id and still tick
"Unopened", so condition alone cannot see it. Real examples, all found while
adding the boxes table: a **"Vendetta sleeve blister pack" at $12** under the
$135 booster box, an **"*Opened booster box*, only gold rarities were pulled"
at $60**, **"Sealed 36 Basic Runes" at $5.50** under a Vault Bundle, a
**"Vendetta Vault Promo Pack" at $12**, and a **"Riftbound Worlds Playmat" at
$65** under a bundle whose real listings start at $1,148.99.

`NOT_SEALED` in the pull library rejects them on the seller title: opened
(but not "unopened"/"never opened"/"not opened"), blister, sleeves, basic runes,
tokens, promo pack, playmat, deckbox, proxy, repack, resealed, empty, box only,
"set/pack/lot of N". It fixed the sealed CASES too - Vendetta went $881.99 to
$909.99 once a junk listing stopped setting the ask.

Watch for this whenever a sealed ask looks far under its own floor. That is the
tell: a $65 ask against a $196 floor was a playmat.

**Better still, do not filter the feed by hand for sealed product.** TCGplayer
publishes its own aggregate per product in the search row, and
`lowestPriceWithShipping` is the "from $X" the site advertises - it already
excludes the mislabelled listings. A $180 "Origins Booster Box Unopened" and a
$55 Chinese box both sit in the raw feed under the real $244.78, and the title
filter does not catch the $180 one because nothing in its title is wrong.

Note the trap: **`lowestPrice` is NOT the clean field** - it reports that $55.
Only `lowestPriceWithShipping` is filtered. So sealed asks include shipping,
which is 1-5% there and was the entire number on a five-cent card. That is a
deliberate exception to the card-price basis and the board says so on the tab.

Never use this for singles: the summary knows nothing about Near Mint.

## Price basis - the card price, with shipping excluded everywhere

**Changed Aug 16, 2026. The board used to include shipping in every price; it no
longer does.** Ask, sales and the weekly low/high are all `price` /
`purchasePrice` / `lowSalePrice` / `highSalePrice` - the card alone.

Why it changed: shipping is a flat ~$1.49 that says nothing about the card, and
on the sub-dollar half of the catalog it *was* the number. Under the old basis
**738 of 929 asks landed between $1.40 and $1.75 and not one fell below $1.40**,
because a 1-cent common shipped is $1.50. Forbidding Waste read as a $1.50 ask
against a $0.01 card. The old rationale - that shipping-inclusive low/high match
`ask` and the floor on one axis - was sound on a $1,600 sealed case where
shipping is 0.74-2.15% of price, and destructive on a 5-cent common.

It also removes a discrepancy the old basis carried. `marketPrice` has no
shipping-inclusive variant, so the green market line always sat about 1% below
a shipping-inclusive band drawn around it. All four series now share one basis
and that gap is gone.

Consequence to know: **sales depth was given up rather than mixed.** Signatures
and Overnumbered held a full five sales each from a signed-in, shipping-
inclusive pull. Padding the new card-price column with those would have put two
bases in one column, so the backfill was removed and those sections carry only
what an anonymous pull yields. `backfill_sales.py` is deliberately disabled and
says why; re-enable it only when both sides share a basis.

## Week filtering, confirmed

Keep buckets with `quantitySold > 0`; drop the rest. This reproduced the stored
Origins week set exactly - 48 weeks from 2025-09-01 to 2026-08-10 out of 52
returned. Buckets come back **newest first**, so reverse them.

Two edge cases came out of four products, so expect more across 438:

- **Vendetta 2026-06-08** had sales but `marketPrice` of 0 - the product's opening
  week, before market was established. Dropped, all four series cut together to
  stay aligned. `build.py` fails on a non-positive market price.
- **Unleashed** shifted its first sale week from 2026-03-09 to 2026-03-02 between
  the Aug 13 pull and this one. Same 23 weeks. TCGplayer revises buckets, so
  treat a fresh pull as authoritative rather than reconciling to the old one.

## Snapshot format for the pull

Signature and Overnumbered cards take `sl`/`sh`/`sm`, either as plain arrays or -
as they ship now - as packed two-digit strings rescaled by `lo`/`hi`, the same
encoding the catalog uses. Packing is what made 434 products affordable to move.

    "sl": "0400...", "sh": "0505...", "sm": "0303..."
    "lo": 1101.3, "hi": 6500                  bounds ALL THREE series
    "f": "2025-11-03", "l": "2026-08-10"      first and last week

`s` stays as the fallback for anything not yet pulled. Catalog cards are
downsampled to 12 bins - low is the min of the bin, high the max, market the
last - so spikes survive; taking every Nth week would drop them.

Catalog cards, packed as before - two digits per week, 0-99:

    "lo": 3.49, "hi": 22.98        min and max across ALL THREE series
    "ql": "...", "qh": "...", "qm": "..."
    "c": [4.51, 4.60, ...]         last 5 sales, newest first

Note the change: `lo`/`hi` used to bound the single series. They now bound all
three, so one pair rescales every line. Rescale old cards when you refill them.

## Catalog cards carry two printings - read this before re-pulling

A catalog product id can return **both a Normal and a Foil row**, each Near Mint
English. Of 297 Origins cards, 172 have a Normal row and 125 are Foil-only.
Signatures and Overnumbered never showed this - they are Foil-only - so the rule
only surfaced on the third section.

**Normal is preferred where it exists**, because it is the printing the ask
column prices and the one that carries the volume: on one card Normal moved
27,344 copies against Foil's 2,272. Taking whichever row arrives first quietly
prices some cards off the wrong printing. If the board should instead track the
foil where one exists, that is a one-line change in the pull plus a re-merge.

Also: **retry failed fetches**. A transient failure on the first card was
recorded as an empty series, which is indistinguishable from a card that never
sold. The pull now retries three times and pushes hard failures onto a list
rather than writing empty data. Zero failures across 297.

## Market lag is expected, not corruption

Market price is a trailing volume-weighted average, so on a thin card it sits
outside that week's own low-to-high range - below in a rising market, above in a
falling one. Ahri Signature's last week sold at 6,500 against a market of 3,420,
and 20 of its 23 weeks fall outside the band. The same check on the 297 catalog
cards fires on only 2, because those actually trade.

This is real signal and the charts show it: a green line running well under the
grey band means market has not caught up. `merge_cards.py` counts it and moves
on rather than warning per week.

## Remaining work

1. **History for 438 products - DONE.** All 438 carry low, high and market:
   4 sealed cases, 45 signatures, 92 overnumbered, 297 catalog.

   `merge_cases.py` does the sealed-case merge and is the working model for the
   rest: parse, assert every series is the same length, drop unusable weeks
   across all series together, then reconcile against what is already stored
   before overwriting. The transfer format is one line per series,
   `CODE|L|v,v,v`, with weeks sent as `CODE|W|first-date|0,1,4,5` - offsets in
   whole weeks, which is about a fifth the size of ISO dates.
2. **Last 5 sales for the 297 catalog cards - DONE.** All 297 carry sales.

   **The five-sale cap is lifted by signing in AND sending cookies.** Being
   logged in is not enough on its own: the fetch must carry
   `credentials: "include"`, or the API still answers with five and
   `totalResults: 5`. With cookies attached, the same product returns 25 rows
   per page and `totalResults: 5003` with `nextPage` set. `limit` caps at 25 per
   page regardless of what you ask for.

   Signed in, filtering costs almost nothing: 23 of 25 rows survive Near Mint,
   English, raw and printing filters, so every card reaches a full five.
   Signatures and Overnumbered were re-pulled on this basis - **all 137 now show
   five sales, 39 of them gaining data they did not have before.**

   Filtering, in order: Near Mint, `language === "English"` **and** a title that
   does not name another language, no grade in the title, and the same printing
   the chart uses (Normal where the product has one). The `language` field lies
   - a Kai'Sa sale came back tagged English titled `**CHINESE**`.

   **This endpoint rate-limits aggressively.** Sustained polling starts returning
   `500 Internal Server Error` within a few dozen requests; back off to a second
   or more between calls and retry, or measurements silently turn into errors.

   Filtering, in order: Near Mint, `language === "English"` **and** a title that
   does not name another language, and no grade in the title. The `language`
   field lies exactly as the handoff warned - a Kai'Sa sale came back tagged
   English with a title of `**CHINESE**`. Sales are also narrowed to the same
   printing the history used, via the variant map from that pull, so a foil sale
   never lands next to a normal card's ask.

   Nine cards show a sale far above their ask - Garbage Grabber asks 0.15 with a
   20.34 sale. Those are probably graded or foreign copies whose titles gave
   nothing away. They are kept and reported by `merge_sales.py` rather than
   dropped, because they are real sales and silently binning outliers is how a
   feed starts lying.

   **Rate limiting is real on this endpoint.** Seven products failed near the end
   of the run; a 600ms backoff was not enough. Retrying with 1.5s, escalating,
   recovered all seven. Budget for it on the remaining three sets.
3. **The other three sets** in Playables. **Spiritforged is done** (230 cards,
   all with ask, history and sales bar one). Origins is repaired to 299.
   Remaining: **Unleashed 225 and Vendetta 175**, ids already in
   `catalog_ids.json`.

   `merge_set.py` takes a whole set at once and checks the pulled ids against
   `catalog_ids.json` before writing, so a short transfer cannot land quietly.
   Pull format is one `~`-separated line per card - tilde because card names
   contain commas but never a tilde:

       id~name~rarity~ask~weeks~first~last~lo~hi~qLow~qHigh~qMarket~sales

   Spiritforged took about ten minutes to pull at three requests per card and 46
   transfer chunks. Nothing failed at ~300ms between cards, which is a safer
   pace than the sales run that started throwing 500s.

### Enumerating a set

    POST https://mp-search-api.tcgplayer.com/v1/search/request?q=&isList=false&mpfev=1

Filter keys are `productLineName` and `setName`, taking **url slugs**, e.g.
`riftbound-league-of-legends-trading-card-game` and `spiritforged`.
`productLineUrlName`/`setUrlName` silently match nothing and return the whole
site - 492,250 results - rather than erroring. **Page size caps at 50**; asking
for 100 returns a body with no `results` block at all.

### What counts as a Playables card

From the search row, keep it when: rarity is present **and not the string
`"None"`** (sealed product uses `"None"`, not null - testing `!rarity` alone
misfiles all 48 of them), and the number is either a plain `NNN/SIZE`, a base
rune (`R04`), or a token (`T01`, or containing `//`). Drop signatures (`*`),
overnumbered (number above set size, no letter), alt art (letter suffix below
set size), showcase runes (`R04a`) and `SP` numbers.

That rule reproduces **Spiritforged 230 and Unleashed 225 exactly**. Vendetta
comes to 175 against the 177 in the old notes - the two are unaccounted for, so
treat 177 as unverified rather than forcing it.

### The stored Origins catalog was wrong

Reconciling ids against a fresh search: the stored 297 is **missing two real
base cards** - 652915 Dune Drake 131/298 and 652927 Pirate's Haven 143/298 - and
the set genuinely has 298 numbered cards plus the token 653117 Buff (which has a
null number), so the correct total is **299**. This is the silent-drop failure
the notes warn about, sitting in the data the whole time. `EXPECT` now says 299;
the two missing cards still need their prices pulled.

Ids move cheaply as **delta encoding** - first id then gaps - which packs 298
ids into 606 characters, one chunk instead of three.

## Data rules - apply all of these

- **English only.** TCGplayer's `language` field on listings is unreliable; Chinese
  cards are routinely filed as English. Detect from the seller's note at
  `customData.title`, e.g. "Kai'sa Signature - **Chinese!**".
- **Near Mint only**, asks and sales both. The `condition` field is reliable.
- **Raw only.** Graded sales carry the grade in the sale `title` ("PSA 10 Teemo
  Swift Scout Signature Overnumber"). Do NOT filter on `listingType` -
  `ListingWithPhotos` includes plenty of raw cards.
- **Asks come from the paged listings endpoint**, never the search API. Search
  returns only the 3 cheapest listings, so a card with 50 listings reports a wrong
  ask or none at all.

## Endpoints

All must run from inside a loaded TCGplayer page - direct fetching is JS-gated.

    Card lists / search
      POST https://mp-search-api.tcgplayer.com/v1/search/request?q=&isList=false&mpfev=1

    Asks - paged, 50 at a time, sort price+shipping asc
      POST https://mp-search-api.tcgplayer.com/v1/product/{id}/listings?mpfev=5457

    Last 5 sales - five and no paging ANONYMOUSLY; 25 a page with nextPage when
    the request carries session cookies (credentials: "include")
      POST https://mpapi.tcgplayer.com/v2/product/{id}/latestsales?mpfev=1

    Weekly history - low, high, market, quantity per week, past year
      GET  https://infinite-api.tcgplayer.com/price/history/{id}/detailed?range=annual

## Transfer technique

Browser tool output truncates at roughly 1,000 characters and base64 is blocked, so
large pulls must be relayed as plain-text chunks. What works:

- Run the pull as a background async function writing to a `window` variable, then
  poll. A foreground call longer than 45s hits the CDP timeout.
- Chunk by **line count**, not characters, so partial rows cannot corrupt data.
- Compress series: send real min and max plus ~10 points normalised to two digits.
  About 35 characters per card instead of a full series.
- Count your chunks. An off-by-one silently dropped 7 cards and the result looked
  entirely plausible - all cheap commons, exactly what you would expect to be
  missing anyway.

## Product IDs, sealed cases

Origins 635369, Spiritforged 661937, Unleashed 678152, Vendetta 693382.
Radiance releases Oct 23, 2026, not yet on the catalog.

## Card classification

- Signature Overnumber: name ends "(Signature)", number has an asterisk (303*/298)
- Overnumbered: number above set size, no letter suffix (303/298). This rule
  catches Baron Nashor (Ultimate) 238/219, which name matching misses.
- Alt art: letter suffix below set size (039a/298) - excluded from both.
- The 48 products with no rarity are sealed product, not cards.
- The 12 Promo items are the runes - real cards, in Spiritforged and Unleashed.

## Hand-maintained, will go stale

- QUALITATIVE in update.js - reprint risk and event demand per set, from Riot
  announcements. Revisit after each State of the Game.
- CALENDAR in template.html - 42 events, currently good through 2027.
- The automation in riftbound-auto/ has never had a successful live run. Its scrape
  half is untested because the sandbox cannot reach TCGplayer.
