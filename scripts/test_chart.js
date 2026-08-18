/* Pulls the chart functions out of template.v2.html and exercises them in
   isolation, so a broken SVG shows up here rather than in a 9,800-line board. */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");

const html = fs.readFileSync(path.join(ROOT, "template.html"), "utf8");
/* Market green and midpoint blue, read from the template so a palette change
   updates the tests with it rather than breaking four assertions. */
const GREEN = (html.match(/var green = "(#[0-9A-Fa-f]{6})"/) || [])[1];
const BLUE  = (html.match(/var line = "(#[0-9A-Fa-f]{6})"/) || [])[1];
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));

// Stub the DOM the top-level code touches, then take the functions we need.
const el = () => ({
  innerHTML: "", textContent: "", className: "", style: {}, dataset: {},
  classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
  addEventListener() {}, appendChild() {}, setAttribute() {}, removeAttribute() {},
  querySelector: () => el(), querySelectorAll: () => [], offsetWidth: 0,
});
const sandbox = {
  document: {
    getElementById: () => el(),
    createElement: () => el(),
    querySelector: () => el(),
    querySelectorAll: () => [],
    addEventListener() {},
  },
  window: { addEventListener() {} },
  console,
};
const body = js.replace("var SEED = __SNAPSHOT__;", "var SEED = " + JSON.stringify(require(path.join(ROOT, "snapshot.json"))) + ";") +
  "\n;module.exports = { chart, catChart, cardChart, unpack, midpoints, niceTicks, weeksFromSpan };";
const fn = new Function("document", "window", "console", "module", body);
const mod = { exports: {} };
try {
  fn(sandbox.document, sandbox.window, console, mod);
} catch (e) {
  console.log("FAIL  template JS threw on load: " + e.message);
  process.exit(1);
}
const { chart, catChart, cardChart, unpack, midpoints, weeksFromSpan } = mod.exports;

let fails = 0;
const ok = (cond, msg) => { console.log((cond ? "pass  " : "FAIL  ") + msg); if (!cond) fails++; };

/* ---- the Salvage case from HANDOFF.md ------------------------------------
   weekly low $3.49, high $22.98, market $4.53. The midpoint is $13.24 - far
   above real sales near $4.60. The point of the five-element chart is that
   both are visible at once, so assert both are actually drawn. */
const n = 12;
const lows  = Array.from({ length: n }, (_, i) => 3.49 + i * 0.02);
const highs = Array.from({ length: n }, (_, i) => 22.98 - i * 0.05);
const mkt   = Array.from({ length: n }, (_, i) => 4.53 + i * 0.03);
const mid   = midpoints(lows, highs);

ok(Math.abs(mid[0] - 13.24) < 0.01, `midpoint of 3.49/22.98 is ${mid[0]} (expect 13.24)`);

const weeks = weeksFromSpan("2025-10-06", "2026-08-10", n);
const svg = chart(mid, weeks, null, Math.max(...highs), 0, 6, true, { lo: lows, hi: highs, mkt: mkt });

ok(svg.startsWith("<svg") && svg.trim().endsWith("</svg>"), "banded chart returns a closed svg");
ok((svg.match(/<polygon class="rb-band"/g) || []).length === 1, "one shaded low-to-high band");
ok((svg.match(/<polyline class="rb-edge"/g) || []).length === 2, "two grey edge lines");
ok(!!GREEN && !!BLUE, `chart colours read from the template (${GREEN} / ${BLUE})`);
ok(svg.includes('stroke="' + GREEN + '"'), "market drawn in green");
ok(!svg.includes('stroke="' + BLUE + '"'), "no blue on a banded chart");
ok((svg.match(new RegExp('class="rb-dot"[^>]*fill="' + GREEN + '"')) || []).length === 1,
   "end dot sits on the market line, in green");
ok(!svg.includes("#2C333D"), "no black midpoint line");
ok((svg.match(/<polyline/g) || []).length === 3, "banded chart draws exactly 3 polylines (low, high, market)");
/* the latest market price is printed right of the green end dot */
{
  const label = svg.match(/<text class="rb-dot"[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"[^>]*fill="([^"]+)"[^>]*>([^<]+)<\/text>/);
  ok(!!label, "banded chart prints an end label");
  if (label) {
    const dot = svg.match(/<circle class="rb-dot"[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"/);
    ok(+label[1] > +dot[1], `label sits right of the dot (${label[1]} > ${dot[1]})`);
    ok(Math.abs(+label[2] - +dot[2]) < 6, "label is vertically level with the dot");
    ok(label[3] === GREEN, `label is green (${label[3]})`);
    ok(label[4] === String(Math.round(mkt[mkt.length - 1])),
       `label is the latest market price rounded (${label[4]})`);
    /* it must fit inside the viewBox, or the svg edge clips it */
    const vb = +svg.match(/viewBox="0 0 ([\d.]+)/)[1];
    ok(+label[1] + label[4].length * 6 <= vb,
       `label fits inside the viewBox (${label[1]} + text vs ${vb})`);
  }
}

/* under a dollar, whole-dollar rounding would print "0", so cents are kept */
{
  const cheapLo = lows.map(() => 0.21), cheapHi = lows.map(() => 0.31), cheapMk = lows.map(() => 0.27);
  const s = chart(midpoints(cheapLo, cheapHi), weeks, null, 0.31, 0, 6, true,
                  { lo: cheapLo, hi: cheapHi, mkt: cheapMk });
  const txt = s.match(/<text class="rb-dot"[^>]*>([^<]+)<\/text>/);
  ok(txt && txt[1] === "0.27", `sub-dollar market shows cents, not 0 (got ${txt && txt[1]})`);
}

/* the fallback has no green line, so nothing to label */
{
  const p2 = chart(mkt, weeks, null, Math.max(...mkt), 0, 6, true);
  ok(!/<text class="rb-dot"/.test(p2), "unbanded fallback prints no end label");
}

/* per-week dots belong to the single-series fallback only; a banded chart
   showing three or four series gets none */
ok(!svg.includes('class="rb-pt"'), "banded chart draws no per-week dots");

/* the band polygon must be a closed ring: n points out along the high series
   and n back along the low series */
const poly = svg.match(/<polygon class="rb-band"[^>]*points="([^"]+)"/)[1];
ok(poly.trim().split(/\s+/).length === n * 2, `band polygon has ${n * 2} points`);

/* y axis has to cover the whole range, not just the midpoint line */
const ys = [...svg.matchAll(/(?:^|\s)[\d.]+,([\d.]+)/g)].map((m) => +m[1]);
ok(ys.length > 0 && Math.max(...ys) - Math.min(...ys) > 20, "series span the plot vertically");

/* axis labels must bracket the true low and high, or the band is clipped */
const labels = [...svg.matchAll(/>([\d.]+k?)<\/text>/g)]
  .map((m) => (m[1].endsWith("k") ? parseFloat(m[1]) * 1000 : parseFloat(m[1])))
  .filter((v) => !Number.isNaN(v));
ok(Math.min(...labels) <= Math.min(...lows) && Math.max(...labels) >= Math.max(...highs),
   `axis ${Math.min(...labels)}-${Math.max(...labels)} contains 3.49-22.98`);

/* the axis must also be tight: no more than one full gridline step of empty
   space beyond the data at either end, or the series shrinks into a corner */
{
  const sorted = [...new Set(labels)].sort((a, b) => a - b);
  const step = sorted[1] - sorted[0];
  const headroom = Math.max(...labels) - Math.max(...highs);
  const footroom = Math.min(...lows) - Math.min(...labels);
  ok(headroom < step && footroom < step,
     `axis is tight (headroom ${headroom.toFixed(2)}, footroom ${footroom.toFixed(2)}, step ${step})`);
  ok(sorted.length <= 6, `${sorted.length} gridlines (ceiling 6)`);
}

/* niceTicks must stay sane across magnitudes, not just this one card */
{
  const { niceTicks } = mod.exports;
  let bad = [];
  for (const [lo, hi] of [[0.03, 0.09], [3.49, 22.98], [975, 2466], [1, 1],
                          [0, 0.5], [1520, 1526], [12, 6500]]) {
    const ts = niceTicks(lo, hi, 6);
    const step = ts[1] - ts[0];
    if (!(ts[0] <= lo && ts[ts.length - 1] >= hi)) bad.push(`${lo}-${hi} does not contain data`);
    else if (ts.length > 6) bad.push(`${lo}-${hi} gave ${ts.length} ticks`);
    else if (!(step > 0) || !isFinite(step)) bad.push(`${lo}-${hi} bad step ${step}`);
    else if (ts.some((v) => String(v).replace("-", "").replace(".", "").length > 12))
      bad.push(`${lo}-${hi} float drift: ${ts.join(",")}`);
  }
  ok(bad.length === 0, "niceTicks across magnitudes" + (bad.length ? ": " + bad[0] : ""));
}

/* ---- fallback: no band data ---------------------------------------------- */
const plain = chart(mkt, weeks, null, Math.max(...mkt), 0, 6, true);
ok(!plain.includes("rb-band"), "unbanded chart draws no band");
ok(plain.includes('class="rb-pt"'), "unbanded chart keeps its per-week dots");
ok(plain.includes('stroke="' + BLUE + '"') && !plain.includes(GREEN),
   "unbanded fallback stays blue, never green");

/* ---- packed catalog form -------------------------------------------------- */
const pack = (arr, lo, hi) => arr
  .map((v) => String(Math.round(((v - lo) / (hi - lo)) * 99)).padStart(2, "0")).join("");
const LO = Math.min(...lows), HI = Math.max(...highs);
const packed = {
  n: "Salvage", id: 1, r: "Common", a: 4.6, lo: LO, hi: HI,
  ql: pack(lows, LO, HI), qh: pack(highs, LO, HI), qm: pack(mkt, LO, HI),
};
const cat = catChart(packed, 0);
ok(cat.includes("rb-band"), "catChart uses the band when ql/qh/qm present");
const back = unpack(packed.ql, LO, HI);
ok(Math.abs(back[0] - lows[0]) < 0.25, `packed round-trip 3.49 -> ${back[0]}`);

ok(catChart({ n: "x", lo: 1, hi: 2, q: "0099" }, 0).includes("<svg"), "catChart still renders old q form");
ok(catChart({ n: "x" }, 0).includes("no sales"), "catChart handles a card with no history");

/* ---- ragged input must degrade, not throw -------------------------------- */
const ragged = cardChart({ n: "x", f: "2025-10-06", l: "2026-08-10",
  s: mkt, sl: lows, sh: highs.slice(0, 5), sm: mkt }, 0);
ok(ragged.includes("<svg") && !ragged.includes("rb-band"),
   "mismatched series lengths fall back to the single line");
ok(cardChart({ n: "x" }, 0).includes("too few weeks"), "card with no series says so");

/* every section shares one axis rule now; the sealed cases used to be exempt */
{
  const { niceTicks } = mod.exports;
  const cases = [[1000, 2466], [764, 2000], [540, 1698], [700, 985]];
  let worst = 1;
  for (const [lo, hi] of cases) {
    const ts = niceTicks(lo, hi, 6);
    worst = Math.min(worst, (hi - lo) / (ts[ts.length - 1] - ts[0]));
    if (ts.length < 3) worst = 0;   // two gridlines is unreadable
  }
  ok(worst > 0.65, `sealed-case axes all fill at least 65% (worst ${(worst * 100).toFixed(0)}%)`);
}

/* a chart called without an explicit ceiling must not fall back to a
   fixed-step axis; that branch is gone */
{
  const wide = chart([700, 985], ["2026-06-08", "2026-08-10"], 720, 862, 0, null, false);
  const ls = [...wide.matchAll(/>([\d.]+k?)<\/text>/g)]
    .map((x) => (x[1].endsWith("k") ? parseFloat(x[1]) * 1000 : parseFloat(x[1])))
    .filter((v) => !Number.isNaN(v));
  ok(new Set(ls).size >= 4, `default axis gives ${new Set(ls).size} gridlines, not 2`);
}

console.log(fails ? `\n${fails} failing` : "\nall passing");
process.exit(fails ? 1 : 0);
