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
  ok(tabs[3] === "Promos & Extras",
     `the new tab sits after Overnumbered (${tabs.slice(1, 5).join(" | ")})`);
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
  ok(subs.some((t) => /Organized Play/.test(t)), "rows name their source");
  // number forms here: 247/298, the alt-art 039a/298, and runes R04a
  const numbered = subs.filter((t) => /\d+[a-z]?\s*\/\s*\d+|R\d+[a-z]?/i.test(t)).length;
  ok(numbered > EXTRA_ROWS * 0.9,
     `rows carry the card number, which identifies an artless promo (${numbered}/${EXTRA_ROWS})`);

  // default sort is price, highest first, with unpriced cards last
  const asks = [...doc.querySelectorAll("#extrabody tr")]
    .filter((r) => !r.querySelector("td[colspan]"))
    .map((r) => {
      const t = r.querySelectorAll("td")[2].textContent.trim();
      return /^\$/.test(t) ? parseFloat(t.replace(/[^0-9.]/g, "")) : null;
    });
  const priced = asks.filter((v) => v !== null);
  ok(priced.length > 0 && priced.every((v, i) => i === 0 || priced[i - 1] >= v),
     `defaults to price descending (top ${priced.slice(0, 3).map((v) => "$" + v).join(", ")})`);
  const firstNull = asks.indexOf(null);
  ok(firstNull === -1 || asks.slice(firstNull).every((v) => v === null),
     "cards with no ask sort to the end, not the top");
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
ok(catHeads === 6, `catalog header has ${catHeads} columns (expect 6)`);
ok(catCells === 6, `catalog rows have ${catCells} cells (expect 6)`);

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
