/* Drives the built board in jsdom: types into the name box and checks what
   each section actually renders. */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const { JSDOM, VirtualConsole } = require("jsdom");

const file = process.argv[2] || path.join(ROOT, "board.html");
/* Playables grows as sets land; pass the expected row count as argv[3] */
const CATALOG_ROWS = +(process.argv[3] || 929);
const errors = [];
const dom = new JSDOM(fs.readFileSync(file, "utf8"), {
  runScripts: "dangerously",
  virtualConsole: new VirtualConsole()
    .on("jsdomError", (e) => errors.push(e.message))
    .on("error", (m) => errors.push(m)),
});
const { document: doc, window: win } = { document: dom.window.document, window: dom.window };

let fails = 0;
const ok = (c, m) => { console.log((c ? "pass  " : "FAIL  ") + m); if (!c) fails++; };
/* a real card row has no colspan cell; set headers, "not released" notes and
   the empty state all do */
const rows = (id) => [...doc.querySelectorAll("#" + id + " tr")]
  .filter((r) => !r.querySelector("td[colspan]")).length;

ok(errors.length === 0, "no script errors" + (errors.length ? ": " + errors[0] : ""));

/* Filtering down to a handful of rows must not drag the header to the middle:
   the wrapper is a full-height column, so it has to start its content at the
   top rather than centring it. */
{
  const cs = win.getComputedStyle(doc.querySelector(".wrap"));
  ok(cs.justifyContent === "flex-start",
     `page content pinned to top (justify-content: ${cs.justifyContent})`);
}

// --- signature chart mode -------------------------------------------------
const sigSvg = doc.querySelector("#sigbody svg");
ok(!!sigSvg, "signature charts render");
ok(sigSvg && sigSvg.querySelectorAll("polygon.rb-band").length === 0, "signatures draw no shaded band");
ok(sigSvg && sigSvg.querySelectorAll("polyline.rb-edge").length === 0, "signatures draw no grey low/high lines");
const sigLines = sigSvg ? [...sigSvg.querySelectorAll("polyline")] : [];
ok(sigLines.length === 2, `signature chart has exactly 2 lines (got ${sigLines.length})`);
const sigStrokes = sigLines.map((l) => l.getAttribute("stroke")).sort();
ok(sigStrokes.join(",") === "#2F7F55,#3F5E9C",
   `signature lines are green market + blue midpoint (got ${sigStrokes.join(",")})`);

/* both signature lines end in a dot; other sections keep just the one */
{
  const dots = [...sigSvg.querySelectorAll("circle.rb-dot")];
  const fills = dots.map((c) => c.getAttribute("fill")).sort();
  ok(dots.length === 2, `signature chart has 2 end dots (got ${dots.length})`);
  ok(fills.join(",") === "#2F7F55,#3F5E9C",
     `end dots are green and blue (got ${fills.join(",")})`);
  const lines = [...sigSvg.querySelectorAll("polyline")];
  const endOf = (el) => el.getAttribute("points").trim().split(/\s+/).pop();
  const dotAt = (c) => c.getAttribute("cx") + "," + c.getAttribute("cy");
  const lineEnds = lines.map(endOf).sort();
  ok(dots.map(dotAt).sort().join(" ") === lineEnds.join(" "),
     "each dot sits on the end of its own line");
}
{
  /* :first-of-type matches per-parent, and each row has its own svg, so scope
     to a single chart explicitly */
  const ovrDots = doc.querySelector("#overbody svg").querySelectorAll("circle.rb-dot");
  ok(ovrDots.length === 1, `banded sections keep a single end dot (got ${ovrDots.length})`);
}

// other sections keep the band
const ovrSvg = doc.querySelector("#overbody svg");
ok(ovrSvg && ovrSvg.querySelectorAll("polygon.rb-band").length === 1, "overnumbered keeps its band");
const catSvg = doc.querySelector("#catbody svg");
ok(catSvg && catSvg.querySelectorAll("polygon.rb-band").length === 1, "all cards keeps its band");

// --- name filter ----------------------------------------------------------
const box = doc.getElementById("nameInput");
ok(!!box, "name input exists");

const before = { sig: rows("sigbody"), ovr: rows("overbody"), cat: rows("catbody") };
ok(before.sig === 45 && before.ovr === 92 && before.cat === CATALOG_ROWS,
   `unfiltered: ${before.sig}/${before.ovr}/${before.cat}`);

function type(v) {
  box.value = v;
  box.dispatchEvent(new win.Event("input", { bubbles: true }));
  // the handler debounces; jsdom timers are synchronous enough to flush
  return new Promise((r) => setTimeout(r, 220));
}

(async () => {
  await type("ahri");
  const a = { sig: rows("sigbody"), ovr: rows("overbody"), cat: rows("catbody") };
  ok(a.sig > 0 && a.sig < 45, `"ahri" narrows signatures to ${a.sig}`);
  ok(a.ovr > 0 && a.ovr < 92, `"ahri" narrows overnumbered to ${a.ovr}`);
  ok(a.cat < CATALOG_ROWS, `"ahri" narrows Playables to ${a.cat}`);
  const names = [...doc.querySelectorAll("#sigbody .card")].map((e) => e.textContent);
  ok(names.every((n) => n.toLowerCase().includes("ahri")), "every shown signature matches the term");

  // apostrophes and case must not defeat the match
  await type("kaisa");
  ok(rows("catbody") > 0, `"kaisa" matches Kai'Sa despite the apostrophe (${rows("catbody")} rows)`);
  await type("KAI'SA");
  ok(rows("catbody") > 0, `"KAI'SA" matches too (${rows("catbody")} rows)`);

  await type("zzzznope");
  ok(rows("sigbody") === 0, "no matches leaves the signature table empty");
  ok(doc.querySelector("#sigbody .emptynote") !== null ||
     doc.querySelector("#sigbody td[colspan]") !== null, "empty state shown");

  await type("");
  const back = { sig: rows("sigbody"), ovr: rows("overbody"), cat: rows("catbody") };
  ok(back.sig === 45 && back.ovr === 92 && back.cat === CATALOG_ROWS,
     `clearing restores all rows: ${back.sig}/${back.ovr}/${back.cat}`);

  // switching tabs must clear the term, like every other filter
  await type("ahri");
  doc.querySelector('.tab[data-panel="p-over"]').dispatchEvent(new win.Event("click", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 50));
  ok(box.value === "", "switching tabs clears the name box");
  ok(rows("overbody") === 92, `switching tabs restores rows (${rows("overbody")})`);

  console.log(fails ? `\n${fails} failing` : "\nall passing");
  process.exit(fails ? 1 : 0);
})();
