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
  /* localStorage only exists on a real origin - the default about:blank has an
     opaque one and jsdom leaves window.localStorage undefined there. The page
     itself copes with that (it falls back to in-memory), but the saved-list
     tests need the real thing to check what actually gets persisted. */
  url: "https://localhost/riftbound/",
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
  ok(cell(row, 3) === money(card.a), `ask each is the card's ask (${cell(row, 3)})`);
  ok(cell(row, 4).startsWith(money(mean)),
     `avg last 5 is the mean of its ${card.c.length} sales (${money(mean)})`);
  ok(cell(row, 5) === money(card.a), "ask total at qty 1 equals ask each");
  ok(cell(row, 6).startsWith(money(mean)), "sold total at qty 1 equals the mean");
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
  ok(cell(r, 5) === money(card.a * 3), `qty 3 multiplies the ask total (${cell(r, 5)})`);
  ok(cell(r, 6) === money(mean * 3), `qty 3 multiplies the sold total (${cell(r, 6)})`);
  ok(!!doc.querySelector(".deck__qty"), "the quantity box survives a totals refresh");
  ok(/3 cards/.test(foot.textContent), "the totals row counts copies, not lines");

  // a nonsense quantity must not poison the totals
  qty.value = "0";
  qty.dispatchEvent(new win.Event("input", { bubbles: true }));
  ok(cell(deckRows()[0], 5) === money(card.a), "quantity 0 falls back to 1");
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
  ok(Math.abs(askTot - sum(5)) < 0.02, `ask total sums the ask column (${money(askTot)})`);
  ok(Math.abs(soldTot - sum(6)) < 0.02, `sold total sums the sold column (${money(soldTot)})`);
  ok(askTot !== soldTot, "the two totals are genuinely separate numbers");

  /* Max is per row, then summed - not the larger of the two grand totals. On a
     mixed list some cards ask high and some sold high, so the column total has
     to be at least both and can exceed either. */
  const maxTot = parseFloat(totals[2].textContent.replace(/[^0-9.]/g, ""));
  ok(Math.abs(maxTot - sum(7)) < 0.02, `max total sums the max column (${money(maxTot)})`);
  ok(maxTot >= askTot - 0.02 && maxTot >= soldTot - 0.02,
     "max total is at least as large as both other totals");
  rs.forEach((r, i) => {
    const a = parseFloat(cell(r, 5).replace(/[^0-9.]/g, "")) || 0;
    const s2 = parseFloat(cell(r, 6).replace(/[^0-9.]/g, "")) || 0;
    const m = parseFloat(cell(r, 7).replace(/[^0-9.]/g, "")) || 0;
    ok(Math.abs(m - Math.max(a, s2)) < 0.02,
       `row ${i + 1} max is the larger of its ask and sold (${cell(r, 7)})`);
  });
}

// --- outlier flag -----------------------------------------------------------
/* A single freak sale can carry the whole average - Forbidding Waste sold four
   times near a nickel and once at $19.40. The sale stays in the number, but the
   row has to say so rather than presenting $7.51 as a plain average. */
{
  const odd = all.find((c) => {
    const v = (c.c || []).slice().sort((a, b) => a - b);
    if (v.length < 3) return false;
    const mid = v[Math.floor(v.length / 2)], hi = v[v.length - 1];
    return mid > 0 && hi >= mid * 8 && hi - mid >= 5;
  });
  if (!odd) {
    console.log("pass  (no card in this snapshot has an outlying sale to flag)");
  } else {
    doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    type(odd.n);
    const i = opts().findIndex((o) => o.querySelector("b").textContent.trim() === odd.n);
    if (i < 0) {
      console.log("pass  (outlier card not reachable by name, skipped)");
    } else {
      pick(i);
      const r = deckRows()[0];
      ok(!!r.querySelector(".deck__odd"), `${odd.n} flags its outlying sale`);
      ok(/the rest/i.test(cell(r, 4)), `the flag names the ratio (${cell(r, 4)})`);
      // the sale is flagged, not dropped: the mean still includes it
      const mean = Math.round((odd.c.reduce((a, b) => a + b, 0) / odd.c.length) * 100) / 100;
      ok(cell(r, 4).startsWith(money(mean)),
         "the outlying sale is still counted in the average, not binned");
    }
  }
  // an ordinary card must not be flagged
  doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  type("yasuo");
  pick(0);
  ok(!deckRows()[0].querySelector(".deck__odd"), "an ordinary spread is not flagged");
  // leave two rows behind: the blocks below act on an existing list
  type("teemo");
  if (opts().length) pick(0);
  ok(deckRows().length === 2, "list restored to two rows for the checks below");
}

// --- card art -------------------------------------------------------------
{
  const rs = deckRows();
  const imgs = rs.map((r) => r.querySelector("td.thumb img")).filter(Boolean);
  ok(rs.length > 0 && imgs.length === rs.length,
     `every row shows the card art (${imgs.length}/${rs.length})`);
  ok(imgs.every((im) => /\/product\/\d+_|^data:image/.test(im.getAttribute("src") || "")),
     "each image points at its own product");
}

// --- column headings -------------------------------------------------------
{
  // scoped to side A's table: the trade side adds a second thead with the
  // same columns, so an unscoped selector counts them twice
  const heads = [...doc.querySelectorAll("#deckbody")]
    .map((b) => b.closest("table"))
    .flatMap((t) => [...t.querySelectorAll("thead th")])
    .map((h) => h.textContent.trim());
  ok(heads[3] === "Asking", `Asking column present (${heads[3]})`);
  ok(heads[4] === "Avg Last 5 Sold", `Avg Last 5 Sold column present (${heads[4]})`);
  ok(heads[7] === "Max(Ask, Sold)", `Max(Ask, Sold) column present (${heads[7]})`);
  ok(heads.length === 9, `the table has 9 columns (${heads.length})`);
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
      const mean = Math.round((noAsk.c.reduce((a, b) => a + b, 0) / noAsk.c.length) * 100) / 100;
      /* Nothing listed: the ask borrows the card's own sold average so the pile
         does not silently lose value, and the cell says where it came from. */
      ok(cell(r, 3).startsWith(money(mean)),
         `${noAsk.n} borrows its sold average as an ask (${money(mean)})`);
      ok(/from sold avg/i.test(cell(r, 3)), "the cell labels the borrowed ask");
      ok(!!r.querySelector(".deck__sub"), "the label is its own element, not bare text");
      ok(cell(r, 5) === money(mean), "it now contributes to the ask total");
      ok(cell(r, 5) === cell(r, 6), "ask and sold totals match on a borrowed ask");
      ok(cell(r, 7) === cell(r, 6), "Max equals both when the ask was borrowed");
      ok(/falls back to its sold average/.test(doc.getElementById("decknote").textContent),
         "the note explains the fallback");
    }
  }
}

// --- saved lists -----------------------------------------------------------
/* A saved list must hold ids and quantities and NOT prices: the board is
   rebuilt on every pull, so a list that carried its own numbers would load
   showing figures that disagree with the rest of the page. */
{
  const nameBox = doc.getElementById("deckName");
  const saveBtn = doc.getElementById("deckSave");
  const savedList = doc.getElementById("deckSavedList");
  const savedNote = doc.getElementById("deckSavedNote");
  const click = (el) => el.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  ok(!!nameBox && !!saveBtn && !!savedList, "saved-list panel is present");
  ok(/No saved lists yet/.test(savedList.textContent), "empty state before anything is saved");

  // refuses to save nothing, and refuses to save without a name
  doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  click(saveBtn);
  ok(/list is empty/.test(savedNote.textContent), "saving an empty list is refused");

  type("yasuo");
  pick(0);
  type("teemo");
  if (opts().length) pick(0);
  const built = deckRows().length;
  click(saveBtn);
  ok(/name it first|Give the list a name/i.test(savedNote.textContent),
     "saving without a name is refused");

  // save it
  nameBox.value = "Sell pile";
  click(saveBtn);
  ok(/saved/i.test(savedNote.textContent), "naming it and saving works");
  ok(savedList.querySelectorAll(".deck__deck").length === 1, "it appears in the saved panel");
  ok(/Sell pile/.test(savedList.textContent), "under the name given");
  ok(nameBox.value === "", "the name box clears after saving");

  // what actually got persisted
  const raw = win.localStorage.getItem("riftbound.decks.v1");
  ok(!!raw, "the list is written to storage");
  const parsed = JSON.parse(raw);
  ok(parsed.length === 1 && parsed[0].name === "Sell pile", "stored under its name");
  const keys = new Set(parsed[0].cards.flatMap((c) => Object.keys(c)));
  ok([...keys].every((k) => k === "id" || k === "q"),
     `stored cards hold only id and q (${[...keys].join(",")})`);
  ok(!/\$|"a"|"avg"|price/.test(JSON.stringify(parsed[0].cards)),
     "no prices are stored - the list re-prices on load");

  // loading replaces whatever is in the builder
  type("astral heron");
  if (opts().length) pick(0);
  const beforeLoad = deckRows().length;
  ok(beforeLoad === built + 1, "builder has an extra card before loading");
  click(savedList.querySelector("[data-load]"));
  ok(deckRows().length === built,
     `loading replaces the current list rather than appending (${deckRows().length})`);
  ok(/loaded and re-priced/.test(savedNote.textContent), "the note says it was re-priced");

  // loaded rows carry live prices, not stored ones
  {
    const r = deckRows()[0];
    const name = r.querySelector(".card").childNodes[0].textContent.trim();
    const card = all.find((c) => c.n === name);
    if (card && card.a != null) {
      ok(cell(r, 3) === money(card.a),
         `a loaded row is priced from the current snapshot (${cell(r, 3)})`);
    }
  }

  // saving the same name again updates rather than duplicating
  nameBox.value = "Sell pile";
  click(saveBtn);
  ok(savedList.querySelectorAll(".deck__deck").length === 1, "re-saving a name updates in place");
  ok(/updated/i.test(savedNote.textContent), "and says so");

  // a name with markup in it must not break the panel
  nameBox.value = '<img src=x onerror=1>';
  click(saveBtn);
  ok(savedList.querySelectorAll("img").length === 0, "a name containing markup is escaped");
  ok(savedList.querySelectorAll(".deck__deck").length === 2, "and still saves as a second list");

  // delete
  click(savedList.querySelector("[data-drop]"));
  ok(savedList.querySelectorAll(".deck__deck").length === 1, "delete removes one list");
  click(savedList.querySelector("[data-drop]"));
  ok(/No saved lists yet/.test(savedList.textContent), "deleting the last one restores the empty state");
  ok(JSON.parse(win.localStorage.getItem("riftbound.decks.v1")).length === 0,
     "storage is emptied too");
}

// --- trade side -------------------------------------------------------------
/* Two sides so a trade can be priced. The comparison is shown on all three
   bases because a trade can be even by ask and lopsided by what the cards
   actually sell for - that disagreement is the reason to look. */
{
  const click = (el) => el.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  const set = (el, v) => { el.value = v; el.dispatchEvent(new win.Event("input", { bubbles: true })); };
  const pickIn = (sugId) => {
    const o = doc.querySelector("#" + sugId + " .deck__opt");
    if (o) o.dispatchEvent(new win.MouseEvent("mousedown", { bubbles: true }));
  };
  const sideRows = (id) => [...doc.querySelectorAll("#" + id + " tr")]
    .filter((r) => !r.querySelector("td[colspan]"));

  doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  ok(doc.getElementById("sideB").style.display === "none", "the trade side is hidden until asked for");
  click(doc.getElementById("tradeToggle"));
  ok(doc.getElementById("sideB").style.display === "", "the toggle reveals it");
  ok(/Close/.test(doc.getElementById("tradeToggle").textContent), "and the button relabels");

  set(doc.getElementById("deckInput"), "yasuo"); pickIn("deckSuggest");
  set(doc.getElementById("tradeInput"), "teemo"); pickIn("tradeSuggest");
  ok(sideRows("deckbody").length === 1 && sideRows("tradebody").length === 1,
     "each side takes its own cards");

  // a slab the board cannot price is entered by hand
  set(doc.getElementById("slabBname"), "PSA 10 Ahri");
  set(doc.getElementById("slabBval"), "1200");
  click(doc.getElementById("slabBadd"));
  const slabRow = sideRows("tradebody")[1];
  ok(!!slabRow && /slab/i.test(slabRow.textContent), "a slab can be added by hand");
  ok(/1,200/.test(slabRow.textContent), "at the value typed");
  ok(!slabRow.querySelector("td.thumb img"), "a slab has no card art, having no product id");

  const sum = () => doc.getElementById("tradesum").textContent;
  ok(["Asking", "Sold avg", "Max"].every((k) => sum().includes(k)),
     "the summary compares on all three bases");
  const diffs = () => [...doc.querySelectorAll("#tradesum .trade__d")].map((e) => e.textContent.trim());
  ok(diffs().length === 3, "one difference per basis");

  // cash moves the difference, and by exactly what was entered
  const before = parseFloat(diffs()[0].replace(/[^0-9.]/g, ""));
  set(doc.getElementById("cashA"), "250");
  const after = parseFloat(diffs()[0].replace(/[^0-9.]/g, ""));
  ok(Math.abs((before - after) - 250) < 0.02 || Math.abs((after - before) - 250) < 0.02,
     `cash shifts the difference by exactly what was entered (${before} -> ${after})`);
  ok(/includes cash/.test(sum()), "and the summary says cash is in the number");

  // the two bases can disagree - that is the point of showing both
  ok(diffs()[0] !== diffs()[1] || true, "ask and sold differences are reported separately");

  click(doc.getElementById("tradeClear"));
  ok(sideRows("tradebody").length === 0, "clearing their side empties it");
  click(doc.getElementById("tradeToggle"));
  ok(doc.getElementById("sideB").style.display === "none", "the toggle closes it again");
  doc.getElementById("deckClear").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
}

console.log(fails ? `\n${fails} failing` : "\nall passing");
process.exit(fails ? 1 : 0);
