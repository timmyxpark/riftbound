/* Loads the built board in a real DOM and checks every tab actually populated.
   Catches the failure mode the handoff warns about: a board that renders
   cleanly while quietly holding fewer rows than it should. */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const { JSDOM } = require("jsdom");

const file = process.argv[2] || path.join(ROOT, "board.html");
/* how many Playables rows to expect; pass as argv[3] when the catalog grows */
const CATALOG_ROWS = +(process.argv[3] || 929);
const errors = [];

const dom = new JSDOM(fs.readFileSync(file, "utf8"), {
  runScripts: "dangerously",
  virtualConsole: new (require("jsdom").VirtualConsole)()
    .on("jsdomError", (e) => errors.push(e.message))
    .on("error", (m) => errors.push(m)),
});
const doc = dom.window.document;
const win = dom.window;

let fails = 0;
const ok = (cond, msg) => { console.log((cond ? "pass  " : "FAIL  ") + msg); if (!cond) fails++; };

ok(errors.length === 0, "no script errors" + (errors.length ? ": " + errors[0] : ""));

const rows = (id) => doc.querySelectorAll("#" + id + " tr:not(.setrow):not(.soon)").length;

ok(doc.querySelectorAll("#body tr").length >= 4, `case table has ${doc.querySelectorAll("#body tr").length} rows`);
/* The Sealed tab carries three tables now: cases, the boxes each case is built
   from, and the standalone products. They share one row renderer, so a break in
   one is a break in all three. */
ok(rows("boxbody") === 4, `box table has ${rows("boxbody")} rows (expect 4)`);
ok(rows("sealedbody") === 5, `other-sealed table has ${rows("sealedbody")} rows (expect 5)`);
{
  const tabs = [...doc.querySelectorAll(".tab")].map((t) => t.textContent.trim());
  ok(tabs[0] === "Sealed", `first tab is "Sealed" (${tabs[0]})`);
}
{
  // every sealed row must price something - a blank ask column would mean the
  // Unopened filter matched nothing
  const asks = [...doc.querySelectorAll("#boxbody .ask, #sealedbody .ask")]
    .map((td) => td.textContent.trim());
  ok(asks.length === 9 && asks.every((a) => /^\$[\d,]/.test(a)),
     `all 9 box/sealed rows show a price (${asks.filter((a) => /^\$/.test(a)).length}/9)`);
  // and a box must cost less than its own case, or the two are mixed up
  const caseAsk = (name) => {
    const tr = [...doc.querySelectorAll("#body tr")]
      .find((r) => (r.querySelector(".set") || {}).textContent?.startsWith(name));
    return tr ? parseFloat(tr.querySelector(".ask").textContent.replace(/[^0-9.]/g, "")) : null;
  };
  const boxAsk = (name) => {
    const tr = [...doc.querySelectorAll("#boxbody tr")]
      .find((r) => (r.querySelector(".set") || {}).textContent?.startsWith(name));
    return tr ? parseFloat(tr.querySelector(".ask").textContent.replace(/[^0-9.]/g, "")) : null;
  };
  const bad = ["Origins", "Spiritforged", "Unleashed", "Vendetta"]
    .filter((n) => !(boxAsk(n) > 0 && caseAsk(n) > 0 && boxAsk(n) < caseAsk(n)));
  ok(bad.length === 0, `every box asks less than its case${bad.length ? ": " + bad.join(", ") : ""}`);
}
ok(rows("sigbody") === 45, `signatures table has ${rows("sigbody")} card rows (expect 45)`);
ok(rows("overbody") === 92, `overnumbered table has ${rows("overbody")} card rows (expect 92)`);

/* Promos & Extras is everything the other tabs do not carry - Organized Play
   promos including the metal Prize Wall cards, alt arts and showcase runes the
   Playables classifier drops, Proving Grounds and the judge promos. */
const EXTRA_ROWS = +(process.argv[4] || 401);
ok(rows("extrabody") === EXTRA_ROWS,
   `promos & extras table has ${rows("extrabody")} card rows (expect ${EXTRA_ROWS})`);
{
  const tabs = [...doc.querySelectorAll(".tab")].map((t) => t.textContent.trim());
  ok(tabs[3] === "Promos & Alt Arts",
     `the promo tab sits after Overnumbered (${tabs.slice(1, 5).join(" | ")})`);
  ok(tabs[1] === "Signature Overnumbered",
     `the signature tab is named in full (${tabs[1]})`);
}
{
  // it renders through the signature renderer, so it must chart the same way
  const svgs = doc.querySelectorAll("#extrabody svg").length;
  ok(svgs > 0, `promos & extras draws ${svgs} charts`);
  // the metal cards are the ones the user asked about by name
  const metal = [...doc.querySelectorAll("#extrabody .card")]
    .filter((td) => /\(Metal\)/.test(td.textContent)).length;
  ok(metal > 0, `metal cards are present (${metal})`);
  /* Sorted, not grouped: ordering 401 cards by price dissolves any source
     banner, so each row has to say what it is on its own. */
  const subs = [...doc.querySelectorAll("#extrabody .card .rar")].map((e) => e.textContent);
  ok(subs.length === EXTRA_ROWS, `every row carries an identity line (${subs.length})`);
  /* The source used to ride along in the identity line; it is a sortable
     column of its own now, so that is where it has to be checked. */
  const srcs = [...doc.querySelectorAll("#extrabody .setcell")].map((e) => e.textContent.trim());
  ok(srcs.length === EXTRA_ROWS, `every row names its source in the set column (${srcs.length})`);
  ok(srcs.some((t) => /Organized Play/.test(t)), "rows name their source");
  ok(new Set(srcs).size > 1, `more than one source is represented (${new Set(srcs).size})`);
  // number forms here: 247/298, the alt-art 039a/298, and runes R04a
  const numbered = subs.filter((t) => /\d+[a-z]?\s*\/\s*\d+|R\d+[a-z]?/i.test(t)).length;
  ok(numbered > EXTRA_ROWS * 0.9,
     `rows carry the card number, which identifies an artless promo (${numbered}/${EXTRA_ROWS})`);

  /* Default sort is the LAST SALE, dearest first: an ask is one seller's
     opinion, a sale is what somebody actually paid. Cards with no sale sink to
     the bottom in either direction - the absence of a sale is not a low one. */
  const lastSold = [...doc.querySelectorAll("#extrabody tr")]
    .filter((r) => !r.querySelector("td[colspan]"))
    .map((r) => {
      const cell = r.querySelector("td.sales");
      const first = cell && cell.querySelector("div");
      const t = first ? first.textContent.trim() : "";
      return /^\$?[\d,]/.test(t) ? parseFloat(t.replace(/[^0-9.]/g, "")) : null;
    });
  const soldOnly = lastSold.filter((v) => v !== null);
  ok(soldOnly.length > 0 && soldOnly.every((v, i) => i === 0 || soldOnly[i - 1] >= v),
     `defaults to last sold descending (top ${soldOnly.slice(0, 3).map((v) => "$" + v).join(", ")})`);
  const firstNull = lastSold.indexOf(null);
  ok(firstNull === -1 || lastSold.slice(firstNull).every((v) => v === null),
     "cards with no recorded sale sort to the end, not the top");
  ok(doc.querySelectorAll("#extrasort .chip--x").length >= 4,
     `sort control offers ${doc.querySelectorAll("#extrasort .chip--x").length} orders`);
}
/* the catalog grows as sets land; read the expectation from the snapshot the
   board was built from rather than pinning a number that goes stale */
ok(rows("catbody") === CATALOG_ROWS,
   `catalog table has ${rows("catbody")} card rows (expect ${CATALOG_ROWS})`);

/* the Last 5 sales column must exist and line up with its header */
const catHeads = doc.querySelectorAll("#p-cat thead th").length;
const catCells = doc.querySelectorAll("#catbody tr:not(.setrow) td").length /
                 Math.max(rows("catbody"), 1);
ok(catHeads === 7, `catalog header has ${catHeads} columns (expect 7)`);
ok(catCells === 7, `catalog rows have ${catCells} cells (expect 7)`);

/* One table across all four sets, not one per set. The set became a column, so
   a single table must carry every set at once - the old shape would have shown
   one set's cards between two banner rows. */
{
  const sets = new Set([...doc.querySelectorAll("#catbody .setcell")].map((e) => e.textContent.trim()));
  ok(sets.size === 4, `every set shares one table (${[...sets].sort().join(", ")})`);
  ok(doc.querySelectorAll("#catbody tr.setrow").length === 0, "no per-set banner rows remain");
  ok(doc.querySelectorAll("#sigbody tr.setrow").length === 0, "nor in the signature table");
}

/* Every card section opens on the same default - last sale, dearest first.
   This runs before anything clicks a heading, so it sees the state the page
   loads in rather than whatever a previous block left behind. */
{
  const opens = (panel, body) => {
    const th = [...doc.querySelectorAll(`#${panel} thead th[data-sort]`)]
      .find((h) => h.classList.contains("is-sorted"));
    const sold = [...doc.querySelectorAll(`#${body} tr`)]
      .filter((r) => !r.querySelector("td[colspan]"))
      .map((r) => {
        const first = r.querySelector("td.sales div");
        const t = first ? first.textContent.trim() : "";
        return /^\$?[\d,]/.test(t) ? parseFloat(t.replace(/[^0-9.]/g, "")) : null;
      })
      .filter((v) => v !== null);
    ok(!!th && th.getAttribute("data-sort") === "sold",
       `${panel} opens sorted by last sold (${th ? th.textContent.trim() : "nothing marked"})`);
    ok(sold.length > 0 && sold.every((v, i) => i === 0 || sold[i - 1] >= v),
       `  dearest first (${sold.slice(0, 3).map((v) => "$" + v).join(", ")})`);
  };
  opens("p-sig", "sigbody");
  opens("p-over", "overbody");
  opens("p-extra", "extrabody");
  opens("p-cat", "catbody");
}

/* Sorting: the headings have to actually reorder the table, and unpriced cards
   have to stay at the bottom in both directions rather than leading an
   ascending sort with the absence of a price. */
{
  const th = [...doc.querySelectorAll("#p-cat thead th")].find((h) => h.getAttribute("data-sort") === "ask");
  ok(!!th, "the ask column is sortable");
  const asks = () => [...doc.querySelectorAll("#catbody tr")]
    .filter((r) => !r.querySelector("td[colspan]"))
    .map((r) => {
      const t = r.querySelectorAll("td")[4].textContent.trim();
      return /^\$/.test(t) ? parseFloat(t.replace(/[^0-9.]/g, "")) : null;
    });
  /* Sold is the default column now, so ask has to be chosen before it can be
     checked - the first click on a number column opens it descending. */
  th.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  const desc = asks().filter((v) => v !== null);
  ok(desc.every((v, i) => i === 0 || desc[i - 1] >= v), `ask sorts high to low when picked ($${desc[0]})`);
  th.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  const after = asks();
  const asc = after.filter((v) => v !== null);
  ok(asc.every((v, i) => i === 0 || asc[i - 1] <= v), `clicking reverses it ($${asc[0]} first)`);
  const firstNull = after.indexOf(null);
  ok(firstNull === -1 || after.slice(firstNull).every((v) => v === null),
     "unpriced cards stay at the bottom even sorted ascending");
  th.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));

  const setTh = [...doc.querySelectorAll("#p-cat thead th")].find((h) => h.getAttribute("data-sort") === "set");
  setTh.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  const bySet = [...doc.querySelectorAll("#catbody .setcell")].map((e) => e.textContent.trim());
  ok(bySet.every((v, i) => i === 0 || bySet[i - 1] <= v), `the set column sorts too (${bySet[0]} first)`);
}

/* the Last 5 sales column must actually carry numbers, not just exist */
{
  const catRows = [...doc.querySelectorAll("#catbody tr")].filter((r) => !r.querySelector("td[colspan]"));
  const filled = catRows.filter((r) => {
    const cell = r.querySelector("td.sales");
    return cell && !cell.querySelector(".dim") && /\$/.test(cell.textContent);
  });
  /* the sales feed genuinely returns nothing for a few cards, so require the
     bulk of them rather than every one, and check the rest say so */
  const blank = catRows.length - filled.length;
  ok(filled.length / catRows.length > 0.95,
     `${filled.length} of ${catRows.length} catalog rows show last-5 sales (${blank} blank)`);
  const dim = catRows.filter((r) => {
    const cell = r.querySelector("td.sales");
    return cell && cell.querySelector(".dim");
  }).length;
  ok(dim === blank, `the ${blank} without sales render a "none" cell (${dim})`);
  const counts = filled.map((r) => r.querySelectorAll("td.sales div").length);
  ok(counts.every((n) => n >= 1 && n <= 5),
     `sales counts within the feed cap of 5 (max ${Math.max(...counts)})`);
}

const charts = doc.querySelectorAll("#catbody svg").length +
               doc.querySelectorAll("#sigbody svg").length +
               doc.querySelectorAll("#overbody svg").length;
ok(charts > 300, `${charts} charts drawn`);

/* every chart must have real geometry */
const empty = [...doc.querySelectorAll("svg polyline")].filter((p) => !p.getAttribute("points")).length;
ok(empty === 0, `${empty} polylines without points`);

/* key stays hidden until band data lands */
const keysOn = doc.querySelectorAll(".ckey.on").length;
const anyBand = doc.querySelectorAll(".rb-band").length;
ok(keysOn === (anyBand ? keysOn : 0), `chart key shown on ${keysOn} tabs, ${anyBand} bands present`);

ok(doc.querySelectorAll("#timeline .tl__item, #timeline li, #timeline .tl__row").length > 0 ||
   doc.getElementById("timeline").textContent.trim().length > 0, "timeline rendered");

console.log(fails ? `\n${fails} failing` : "\nall passing");
process.exit(fails ? 1 : 0);
