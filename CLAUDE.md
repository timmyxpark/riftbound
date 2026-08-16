# Riftbound pricing board

A static HTML board of Riftbound (League of Legends TCG) prices: sealed cases,
signature overnumbers, overnumbered cards and a Playables catalog. Data comes
from TCGplayer.

## The board is generated. Never hand-edit it.

`template.html` holds all the code and one `__SNAPSHOT__` marker.
`snapshot.json` holds all the data. `build.py` injects one into the other.

```bash
python3 scripts/build.py snapshot.json template.html board.html
node scripts/test_chart.js               # chart geometry in isolation
node scripts/test_board.js board.html    # loads the built board in jsdom
node scripts/test_filter.js board.html   # types into the name filter, checks rows
node scripts/test_deck.js board.html     # drives the deck pricer, checks totals
```

Editing `board.html` directly means the next build silently discards the change.
Change `template.html` or `snapshot.json`.

`npm install` first (jsdom is the only dependency).

## Run the tests before saying anything works

All four suites must pass. They exist because of specific bugs that shipped:

- `build.py` fails the build on drifted card counts. The stored Origins catalog
  was missing two real cards for weeks before a count check caught it.
- `test_chart.js` catches broken SVG and axis regressions. It caught a quoting
  bug in an `onerror` attribute that killed the entire page script.
- Two suites take an expected catalog row count as `argv[3]`, because Playables
  grows as sets land. Update it deliberately, don't delete the assertion.
- `test_deck.js` recomputes the deck pricer's totals from `snapshot.json`
  rather than trusting the page, so an ask/sold mix-up cannot pass.

## Data rules that are easy to get wrong

- **English only, and that applies to asks as much as sales.** The `language`
  field lies - listings and sales come back tagged English with titles reading
  `**CHINESE**`, `Chinese Yasuo - Unforgiven` or `Seal of Rage Overnumbered (CN)`.
  Match on `customData.title` too. This was live in the asks for months: Yasuo,
  Unforgiven (Overnumbered) asked $50 against a real Near Mint English $81
  because four cheaper Chinese copies sorted above it, and the cheapest "Origins
  case" is a Chinese jumbo-pack case at $908 against the English $1,604.99.
  Match spelled-out language names and CJK anywhere in the title, but only match
  two-letter codes like `(CN)` when they are set off by brackets or asterisks -
  a bare `\bit\b` matches the English word "it" and throws away good listings.
- **Near Mint, raw only.** Grades appear in the sale title, not `listingType`.
- **Printing.** A product can carry both a Normal and a Foil row. Prefer Normal
  where it exists; it is what the ask column prices and where the volume is.
- **Market price is a trailing average** and legitimately sits outside a given
  week's low-to-high range on thin cards. That is signal, not corruption.
- **Prices exclude shipping.** Ask, sales and the weekly low/high are all the
  card price alone. Shipping is a flat ~$1.49; including it used to pin 738 of
  929 asks between $1.40 and $1.75 with none below $1.40, because a 1-cent
  common shipped is $1.50. Never mix the two bases in one column - see HANDOFF.
- **Sales need `credentials: "include"`.** Being logged in is not enough; without
  cookies the API returns five sales and `totalResults: 5`.

## Pulling data

Everything runs from inside a loaded TCGplayer page - the endpoints are JS-gated
and session-bound. Nothing can be fetched from a plain script. Run long pulls in
the background writing to a `window` variable and poll, or a foreground call will
blow the 45-second timeout.

TCGplayer throttles hard on sustained use. Roughly a thousand requests in a
session degrades it to about one request every 15 seconds and it does not
recover; that is a cooldown, not something to tune around.

`pulls/` holds the raw transferred data. The merge scripts validate before
writing - counts, packed-series lengths, ids against `catalog_ids.json` - and
refuse to write anything if a check fails.

## Read HANDOFF.md

It carries the full history: endpoints, classification rules, the reasoning
behind the chart design, and every trap found so far. It is the most valuable
file here.

## Outstanding

- **Sales depth is the one thing still gated on being signed in.** Anonymously
  the sales endpoint answers `totalResults: 5` with an empty `nextPage` no
  matter what `limit`/`offset` you send, so a card can only ever reach five and
  usually lands on three or four. Signatures and Overnumbered are five-deep and
  Playables is 929/929 with sales, but 302 of those carry fewer than five. Only
  a signed-in pull with `credentials: "include"` can fill them.
- Playables now covers all four sets: Origins 299, Spiritforged 230,
  Unleashed 225, Vendetta 175 - **929 cards**.
- Vendetta is **175**, confirmed. A fresh enumeration classified independently
  to 175 and matched `catalog_ids.json` id for id, so the 177 in the original
  notes is simply wrong. Origins is 299: 298 numbered plus the null-numbered
  token 653117 `Buff`, which was missing from `catalog_ids.json` and is now in it.
