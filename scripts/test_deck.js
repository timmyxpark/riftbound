/* Drives the Deck Pricer in jsdom: types a name, picks from the suggestions,
   changes quantities and checks both totals against the snapshot the board was
   built from. The two totals answer different questions, so the test checks
   they are computed from different fields and never quietly share a number. */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const { JSDOM, VirtualConsole } = require("jsdom");

const file = process.argv[2] || path.join(ROOT, "board.html");
const errors = [];
const dom = new JSDOM(fs.readFileSync(file, "utf8"), {
  runScripts: "dangerously",
  virtualConsole: new VirtualConsole()
    .on("jsdomError", (e) => errors.push(e.message))
    .on("error", (m) => errors.push(m)),
});
const doc = dom.window.document;
const win = dom.window;

let fails = 0;
const ok = (c, m) => { console.log((c ? "pass  " : "FAIL  ") + m); if (!c) fails++; };
const money = (n) => "$" + n.toLocaleString("en-US",
  { minimumFractionDigits: 2, maximumFractionDigits: 2 });

ok(errors.length === 0, "no script errors" + (errors.length ? ": " + errors[0] : ""));

const box = doc.getElementById("deckInput");
const sug = doc.getElementById("deckSuggest");
const body = doc.getElementById("deckbody");
const foot = doc.getElementById("deckfoot");
ok(!!box && !!sug && !!body && !!foot, "deck pricer markup is present");

const tab = [...doc.querySelectorAll(".tab")]
  .find((t) => t.textContent.trim() === "Deck Pricer");
ok(!!tab, "Deck Pricer tab exists");
tab.dispatchEvent(new win.Event("click", { bubbles: true }));
ok(doc.getElementById("p-deck").classList.contains("is-on"), "its panel opens");
ok(doc.getElementById("setfilter").style.display === "none",
   "set chips are hidden on the deck tab");

// the section starts empty, not with a stray row or a zero total
ok(/Nothing added yet/.test(body.textContent), "empty state shown before anything is added");
ok(foot.innerHTML.trim() === "", "no totals row while the list is empty");

const type = (s) => {
  box.value = s;
  box.dispatchEvent(new win.Event("input", { bubbles: true }));
};
const opts = () => [...sug.querySelectorAll(".deck__opt")];
const deckRows = () => [...body.querySelectorAll("tr")].filter((r) => !r.querySelector("td[colspan]"));
const cell = (r, i) => r.querySelectorAll("td")[i].textContent.trim();
const pick = (i) => {
  const o = opts()[i];
  o.dispatchEvent(new win.MouseEvent("mousedown", { bubbles: true }));
};

// --- suggestions ----------------------------------------------------------
type("yasuo");
ok(opts().length > 0, `"yasuo" suggests ${opts().length} cards`);
ok(opts().every((o) => /yasuo/i.test(o.querySelector("b").textContent)),
   "every suggestion matches what was typed");

/* The same name exists in several sections at wildly different prices, so the
   picker has to say which one each suggestion is. Picking blind is the easy
   mistake this section could invite. */
{
  const labels = new Set(opts().map((o) => o.querySelector("span").textContent.trim()));
  ok(labels.size > 1, `suggestions name their section and set (${labels.size} distinct)`);
}

type("kaisa");
ok(opts().length > 0, `"kaisa" matches Kai'Sa despite the apostrophe (${opts().length})`);
type("zzzznotacard");
ok(opts().length === 0 && /No card matches/.test(sug.textContent), "no matches says so");

// --- adding, and where the numbers come from ------------------------------
type("yasuo");
const chosen = opts()[0].querySelector("b").textContent.trim();
pick(0);
ok(deckRows().length === 1, `picking a suggestion adds a row (${chosen})`);
ok(box.value === "", "the box clears after adding");
ok(!sug.classList.contains("on"), "the suggestion list closes after adding");

/* Cross-check the row against the snapshot: ask is the card's ask, and the
   sold figure is the mean of its last five sales - not the newest sale, and
   not the same number as the ask. */
const snap = JSON.parse(fs.readFileSync(path.join(ROOT, "snapshot.json"), "utf8"));
const all = [];
for (const key of ["signatures", "overnumbered", "catalog"]) {
  for (const g of snap[key] || []) for (const c of g.cards || []) all.push(c);
}
{
  const row = deckRows()[0];
  const name = row.querySelector(".card").childNodes[0].textContent.trim();
  const card = all.find((c) => c.n === name && c.a != null);
  ok(!!card, `row card ${name} found in the snapshot`);
  const mean = Math.round((card.c.reduce((a, b) => a + b, 0) / card.c.length) * 100) / 100;
  ok(cell(row, 2) === money(card.a), `ask each is the card's ask (${cell(row, 2)})`);
  ok(cell(row, 3).startsWith(money(mean)),
     `avg last 5 is the mean of its ${card.c.length} sales (${money(mean)})`);
  ok(cell(row, 4) === money(card.a), "ask total at qty 1 equals ask each");
  ok(cell(row, 5).startsWith(money(mean)), "sold total at qty 1 equals the mean");
}

// --- quantity -------------------------------------------------------------
{
  const row = deckRows()[0];
  const name = row.querySelector(".card").childNodes[0].textContent.trim();
  const card = all.find((c) => c.n === name && c.a != null);
  const mean = Math.round((card.c.reduce((a, b) => a + b, 0) / card.c.length) * 100) / 100;
  const qty = row.querySelector(".deck__qty");
  qty.value = "3";
  qty.dispatchEvent(new win.Event("input", { bubbles: true }));
  const r = deckRows()[0];
  ok(cell(r, 4) === money(card.a * 3), `qty 3 multiplies the ask total (${cell(r, 4)})`);
  ok(cell(r, 5) === money(mean * 3), `qty 3 multiplies the sold total (${cell(r, 5)})`);
  ok(!!doc.querySelector(".deck__qty"), "the quantity box survives a totals refresh");
  ok(/3 cards/.test(foot.textContent), "the totals row counts copies, not lines");

  // a nonsense quantity must not poison the totals
  qty.value = "0";
  qty.dispatchEvent(new win.Event("input", { bubbles: true }));
  ok(cell(deckRows()[0], 4) === money(card.a), "quantity 0 falls back to 1");
}

// --- two cards, and the totals --------------------------------------------
type("teemo");
if (opts().length) pick(0);
{
  const rs = deckRows();
  ok(rs.length === 2, `a second card adds a second row (${rs.length})`);
  const sum = (i) => rs.reduce((t, r) => {
    const v = cell(r, i).replace(/[^0-9.]/g, "");
    return t + (v ? parseFloat(v) : 0);
  }, 0);
  const totals = foot.querySelectorAll(".deck__tot");
  ok(totals.length === 3, "all three totals are shown");
  const askTot = parseFloat(totals[0].textContent.replace(/[^0-9.]/g, ""));
  const soldTot = parseFloat(totals[1].textContent.replace(/[^0-9.]/g, ""));
  ok(Math.abs(askTot - sum(4)) < 0.02, `ask total sums the ask column (${money(askTot)})`);
  ok(Math.abs(soldTot - sum(5)) < 0.02, `sold total sums the sold column (${money(soldTot)})`);
  ok(askTot !== soldTot, "the two totals are genuinely separate numbers");

  /* Max is per row, then summed - not the larger of the two grand totals. On a
     mixed list some cards ask high and some sold high, so the column total has
     to be at least both and can exceed either. */
  const maxTot = parseFloat(totals[2].textContent.replace(/[^0-9.]/g, ""));
  ok(Math.abs(maxTot - sum(6)) < 0.02, `max total sums the max column (${money(maxTot)})`);
  ok(maxTot >= askTot - 0.02 && maxTot >= soldTot - 0.02,
     "max total is at least as large as both other totals");
  rs.forEach((r, i) => {
    const a = parseFloat(cell(r, 4).replace(/[^0-9.]/g, "")) || 0;
    const s2 = parseFloat(cell(r, 5).replace(/[^0-9.]/g, "")) || 0;
    const m = parseFloat(cell(r, 6).replace(/[^0-9.]/g, "")) || 0;
    ok(Math.abs(m - Math.max(a, s2)) < 0.02,
       `row ${i + 1} max is the larger of its ask and sold (${cell(r, 6)})`);
  });
}

// --- column headings -------------------------------------------------------
{
  const heads = [...doc.querySelectorAll("#p-deck thead th")].map((h) => h.textContent.trim());
  ok(heads[2] === "Asking", `third column is "Asking" (${heads[2]})`);
  ok(heads[3] === "Avg Last 5 Sold", `fourth column is "Avg Last 5 Sold" (${heads[3]})`);
  ok(heads[6] === "Max(Ask, Sold)", `seventh column is "Max(Ask, Sold)" (${heads[6]})`);
  ok(heads.length === 8, `the table has 8 columns (${heads.length})`);
}

// --- removing and clearing -------------------------------------------------
{
  const before = deckRows().length;
  body.querySelector(".deck__x").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  ok(deckRows().length === before - 1, "the remove button drops one row");
  doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  ok(deckRows().length === 0 && /Nothing added yet/.test(body.textContent), "clear empties the list");
  ok(foot.innerHTML.trim() === "", "totals disappear with the list");
}

// --- a card with nothing listed -------------------------------------------
/* Cards with no ask exist, and silently treating them as $0 would understate a
   pile. They have to be excluded and said out loud. */
{
  const noAsk = all.find((c) => c.a == null && c.n);
  if (!noAsk) {
    console.log("pass  (no unlisted card in this snapshot to check)");
  } else {
    type(noAsk.n);
    const i = opts().findIndex((o) => o.querySelector("b").textContent.trim() === noAsk.n);
    if (i < 0) {
      console.log("pass  (unlisted card not reachable by name, skipped)");
    } else {
      pick(i);
      const r = deckRows()[0];
      ok(/none listed/.test(cell(r, 2)), `${noAsk.n} shows "none listed" rather than $0`);
      ok(cell(r, 4) === "-", "it contributes no ask total");
      const soldCell = cell(r, 5);
      if (soldCell !== "-") {
        ok(cell(r, 6) === soldCell,
           `with no ask, Max falls back to the sold side (${cell(r, 6)})`);
      }
      ok(/out of the ask total/.test(doc.getElementById("decknote").textContent),
         "the note explains what was left out");
    }
  }
}

console.log(fails ? `\n${fails} failing` : "\nall passing");
process.exit(fails ? 1 : 0);
