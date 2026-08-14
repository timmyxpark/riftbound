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
```

Editing `board.html` directly means the next build silently discards the change.
Change `template.html` or `snapshot.json`.

`npm install` first (jsdom is the only dependency).

## Run the tests before saying anything works

All three suites must pass. They exist because of specific bugs that shipped:

- `build.py` fails the build on drifted card counts. The stored Origins catalog
  was missing two real cards for weeks before a count check caught it.
- `test_chart.js` catches broken SVG and axis regressions. It caught a quoting
  bug in an `onerror` attribute that killed the entire page script.
- Two suites take an expected catalog row count as `argv[3]`, because Playables
  grows as sets land. Update it deliberately, don't delete the assertion.

## Data rules that are easy to get wrong

- **English only.** The `language` field lies - sales come back tagged English
  with titles reading `**CHINESE**`. Match on the seller's title too.
- **Near Mint, raw only.** Grades appear in the sale title, not `listingType`.
- **Printing.** A product can carry both a Normal and a Foil row. Prefer Normal
  where it exists; it is what the ask column prices and where the volume is.
- **Market price is a trailing average** and legitimately sits outside a given
  week's low-to-high range on thin cards. That is signal, not corruption.
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

- Sales depth uneven: Signatures 45/45 and Overnumbered 92/92 are five-deep,
  Playables is 323 of 529. The rest need re-pulling after the throttle clears.
- Playables covers Origins and Spiritforged. **Unleashed (225) and Vendetta
  (175) are still missing** - ids are already classified in `catalog_ids.json`.
- Vendetta classifies to 175, against 177 in the original notes. Unexplained;
  treat 177 as unverified rather than bending the classifier to reach it.
