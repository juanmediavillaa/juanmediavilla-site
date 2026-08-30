#!/usr/bin/env node
// Every browser-measured check for this site, in one pass.
//
//   node tools/audit.js
//
// Needs a Chrome with remote debugging on 9222; tools/audit.sh starts one.
//
// Why measured rather than reviewed: three separate defects on this site were
// rules written into CONTENT-RULES.md that nothing enforced —
//   * --muted documented as graphical-only while 20 rules used it for text
//   * a reveal animation that gated content behind JavaScript
//   * charts pinned to 640px that overflowed every phone
// A stylesheet review found none of them. Measuring the rendered page found all
// three in seconds. Anything that matters here gets a checker, not a paragraph.

const http = require("http");
const net = require("net");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PORT = 9222;
const SITE = path.resolve(__dirname, "..");
const WIN = process.argv[2]; // windows-style site root with forward slashes
const PAGES = [
  "index.html", "projects/index.html",
  "projects/prediction-market/index.html", "projects/wallet-intelligence/index.html",
  "projects/fund-terminal/index.html", "projects/data-portal/index.html",
  "projects/agent-research-programme/index.html",
  "research/index.html", "research/msc/index.html", "research/bsc/index.html",
  "research/thesis/index.html", "how-i-work/index.html", "about/index.html",
  "cv/index.html", "glossary/index.html",
  // /notes is generated, and is not in the sitemap. The audit only checks pages
  // it is told about, so every generated page is registered here.
  "notes/index.html", "notes/investing/index.html", "notes/books/index.html",
  "notes/investing/meta-platforms/index.html", "notes/investing/duolingo/index.html",
  "notes/investing/alphabet/index.html", "notes/investing/reddit/index.html",
  "notes/investing/robinhood-markets/index.html",
  "notes/investing/hims-and-hers-health/index.html",
  "notes/books/when-genius-failed/index.html",
  // Both carry figures, so both need the chart-label check below.
  "notes/investing/amazon/index.html", "notes/investing/micron-technology/index.html",
  "notes/investing/fair-isaac/index.html", "notes/investing/hinge-health/index.html",
];
// Home + five sections. Defined in tools/sitegen.py NAV; change both together.
const NAV_LINKS = 6;
const WIDTHS = [320, 390, 768, 1440];
const MIN_FONT_PX = 12;


/* -------------------------------------------------- chart label collisions */
// Charts are authored on a constant 640-wide canvas, so column count alone
// decides whether the labels underneath still fit: nine quarters leaves ~64px
// per column for a period label that wants ~50px. Overlapping SVG text does not
// overflow its container and is not under 12px, so neither existing check sees
// it — it just renders as an unreadable smudge. Every pair of <text> nodes in a
// figure is tested for an actual rectangle intersection.
const CHART_TEXT = `(() => {
  const out = [];
  document.querySelectorAll("figure svg").forEach((svg, si) => {
    const name = (svg.getAttribute("aria-label") || ("figure " + si)).split(":")[0];
    const t = [...svg.querySelectorAll("text")]
      .map((n) => { const r = n.getBoundingClientRect(); return {
        l: r.left, r: r.right, t: r.top, b: r.bottom, s: n.textContent }; })
      .filter((n) => n.r > n.l);
    for (let i = 0; i < t.length; i++)
      for (let j = i + 1; j < t.length; j++) {
        const a = t[i], b = t[j];
        // Stacked lines 14px apart at 12px type have em boxes that touch by
        // about half a pixel. That is not a collision, so a pair only counts
        // when it overlaps vertically by a third of the shorter box - a genuine
        // clash between two labels on one baseline overlaps by the whole box.
        const vy = Math.min(a.b, b.b) - Math.max(a.t, b.t);
        const need = Math.min(a.b - a.t, b.b - b.t) / 3;
        if (a.l < b.r && b.l < a.r && vy > need)
          out.push({ chart: name, a: a.s, b: b.s,
                     px: +(Math.min(a.r, b.r) - Math.max(a.l, b.l)).toFixed(1),
                     vy: +(Math.min(a.b, b.b) - Math.max(a.t, b.t)).toFixed(1),
                     ah: +(a.b - a.t).toFixed(1) });
      }
  });
  return JSON.stringify(out);
})()`;

/* ------------------------------------------------------------------ CDP */
const getJSON = (p) => new Promise((res, rej) => {
  http.get({ host: "127.0.0.1", port: PORT, path: p }, (r) => {
    let d = ""; r.on("data", (c) => (d += c)); r.on("end", () => res(JSON.parse(d)));
  }).on("error", rej);
});

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const u = new URL(wsUrl);
    const key = crypto.randomBytes(16).toString("base64");
    const sock = net.connect(Number(u.port), u.hostname, () => {
      sock.write(`GET ${u.pathname}${u.search} HTTP/1.1\r\nHost: ${u.host}\r\n` +
        `Upgrade: websocket\r\nConnection: Upgrade\r\n` +
        `Sec-WebSocket-Key: ${key}\r\nSec-WebSocket-Version: 13\r\n\r\n`);
    });
    let buf = Buffer.alloc(0), open = false;
    const pending = new Map(), waiters = []; let id = 0;
    const api = {
      send(method, params = {}) {
        return new Promise((res2, rej2) => {
          const msg = { id: ++id, method, params };
          pending.set(msg.id, { res: res2, rej: rej2 }); frame(JSON.stringify(msg));
        });
      },
      once(method, timeout = 15000) {
        return new Promise((res2) => {
          const w = { method, res: res2 }; waiters.push(w);
          setTimeout(() => { const i = waiters.indexOf(w); if (i >= 0) { waiters.splice(i, 1); res2(null); } }, timeout);
        });
      },
      close: () => sock.end(),
    };
    function frame(str) {
      const p = Buffer.from(str), len = p.length; let head;
      if (len < 126) head = Buffer.from([0x81, 0x80 | len]);
      else if (len < 65536) { head = Buffer.alloc(4); head[0] = 0x81; head[1] = 0x80 | 126; head.writeUInt16BE(len, 2); }
      else { head = Buffer.alloc(10); head[0] = 0x81; head[1] = 0x80 | 127; head.writeBigUInt64BE(BigInt(len), 2); }
      const mask = crypto.randomBytes(4), m = Buffer.allocUnsafe(len);
      for (let i = 0; i < len; i++) m[i] = p[i] ^ mask[i % 4];
      sock.write(Buffer.concat([head, mask, m]));
    }
    sock.on("data", (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      if (!open) {
        const end = buf.indexOf("\r\n\r\n"); if (end === -1) return;
        if (!/101/.test(buf.slice(0, end).toString())) return reject(new Error("handshake failed"));
        buf = buf.slice(end + 4); open = true; resolve(api);
      }
      for (;;) {
        if (buf.length < 2) return;
        const l0 = buf[1] & 0x7f; let off = 2, len = l0;
        if (l0 === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
        else if (l0 === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
        if (buf.length < off + len) return;
        const data = buf.slice(off, off + len).toString(); buf = buf.slice(off + len);
        let msg; try { msg = JSON.parse(data); } catch { continue; }
        if (msg.id && pending.has(msg.id)) {
          const p = pending.get(msg.id); pending.delete(msg.id);
          msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
        } else if (msg.method) {
          for (let i = waiters.length - 1; i >= 0; i--)
            if (waiters[i].method === msg.method) { waiters[i].res(msg.params); waiters.splice(i, 1); }
        }
      }
    });
    sock.on("error", reject);
  });
}

/* -------------------------------------------------------------- probes */
// Layout. Compared against the EMULATED device width, never window.innerWidth:
// under mobile emulation the layout viewport stretches to fit overflowing
// content, so innerWidth grows to match scrollWidth and the test silently passes.
const LAYOUT = (W, minFont) => `(() => {
  const DEVICE = ${W}, MIN = ${minFont};
  const de = document.documentElement;
  const scrollers = new Set();
  document.querySelectorAll('*').forEach(el => {
    const st = getComputedStyle(el);
    if (/(auto|scroll)/.test(st.overflowX)) scrollers.add(el);
  });
  const insideScroller = (el) => { let n = el.parentElement;
    while (n) { if (scrollers.has(n)) return true; n = n.parentElement; } return false; };

  const wide = [];
  document.querySelectorAll('body *').forEach(el => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || st.position === 'fixed') return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    // an element that overflows its own scroll container is fine; one that
    // overflows the page, or overflows a NON-scrolling parent, is not
    // SVG children have no meaningful clientWidth; they are laid out by the
    // viewBox, so measuring them as scroll boxes produces false positives.
    const inSvg = el.ownerSVGElement || el.tagName.toLowerCase() === 'svg';
    const overflowsSelf = !inSvg && el.scrollWidth > el.clientWidth + 1
      && !/(auto|scroll)/.test(st.overflowX);
    const pastViewport = r.right > DEVICE + 1 && !insideScroller(el);
    if (overflowsSelf || pastViewport) {
      wide.push({ tag: el.tagName.toLowerCase(),
        cls: (el.className && String(el.className).slice(0, 30)) || '',
        w: Math.round(r.width), sw: el.scrollWidth, cw: el.clientWidth,
        right: Math.round(r.right),
        why: pastViewport ? 'past viewport' : 'overflows itself' });
    }
  });

  const tiny = [];
  document.querySelectorAll('body *').forEach(el => {
    const direct = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!direct) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    const px = parseFloat(st.fontSize);
    if (px && px < MIN) tiny.push({ tag: el.tagName.toLowerCase(),
      cls: (el.className && String(el.className).slice(0, 30)) || '', px: +px.toFixed(1),
      text: (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 30) });
  });

  const uniq = (a, k) => { const s = new Set(), o = [];
    for (const x of a) { const key = k(x); if (!s.has(key)) { s.add(key); o.push(x); } } return o; };
  return JSON.stringify({
    docScroll: de.scrollWidth, device: DEVICE,
    pageOverflow: de.scrollWidth > DEVICE + 1 || window.innerWidth > DEVICE + 1,
    wide: uniq(wide, x => x.tag + x.cls + x.why).slice(0, 8),
    tiny: uniq(tiny, x => x.tag + x.cls + x.px).slice(0, 8),
    scrollRegions: [...scrollers].filter(el => el.scrollWidth > el.clientWidth + 1).map(el => ({
      cls: (el.className && String(el.className).slice(0, 24)) || el.tagName.toLowerCase(),
      labelled: !!(el.getAttribute('role') && el.getAttribute('aria-label')),
      focusable: el.tabIndex >= 0 })),
  });
})()`;

// Contrast. Resolves the effective background through the ancestor chain and
// skips gradients, which cannot be reduced to a single colour.
const CONTRAST = `(() => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(',').map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lin = (v) => { v /= 255; return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  const lum = (c) => .2126 * lin(c.r) + .7152 * lin(c.g) + .0722 * lin(c.b);
  const over = (f, b) => ({ r: f.a*f.r+(1-f.a)*b.r, g: f.a*f.g+(1-f.a)*b.g, b: f.a*f.b+(1-f.a)*b.b, a: 1 });
  function bgOf(el) { let acc = null, n = el;
    while (n && n.nodeType === 1) { const st = getComputedStyle(n);
      if (st.backgroundImage && st.backgroundImage !== 'none') return null;
      const c = parse(st.backgroundColor);
      if (c && c.a > 0) { acc = acc ? over(acc, c) : c; if (acc.a >= .999) return acc; }
      n = n.parentElement; }
    return acc || { r: 255, g: 255, b: 255, a: 1 }; }
  const out = [];
  document.querySelectorAll('body *, body svg text').forEach(el => {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1)) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) return;
    // SVG text is painted by fill, not color. Reading color here measured an
    // inherited value that never reaches the screen, so SVG text went unchecked.
    const inSvg = !!el.ownerSVGElement;
    const paint = inSvg ? (st.fill && st.fill !== 'none' ? st.fill : st.color) : st.color;
    const fg = parse(paint), bg = bgOf(el); if (!fg || !bg) return;
    const ratio = (Math.max(lum(fg), lum(bg)) + .05) / (Math.min(lum(fg), lum(bg)) + .05);
    const px = parseFloat(st.fontSize), bold = (parseInt(st.fontWeight, 10) || 400) >= 700;
    const need = (px >= 24 || (bold && px >= 18.66)) ? 3 : 4.5;
    if (ratio < need) out.push({ tag: el.tagName.toLowerCase(),
      cls: (el.className && String(el.className).slice(0, 28)) || '',
      ratio: +ratio.toFixed(2), need, color: st.color,
      text: (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 34) });
  });
  const s = new Set(), u = [];
  for (const o of out) { const k = o.tag + o.cls + o.ratio; if (!s.has(k)) { s.add(k); u.push(o); } }
  return JSON.stringify(u.slice(0, 10));
})()`;

// Structure, and what survives with scripting off.
const STRUCT = `(() => {
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => +h.tagName[1]);
  const skips = []; for (let i = 1; i < hs.length; i++) if (hs[i] - hs[i-1] > 1) skips.push(hs[i-1]+'->'+hs[i]);
  return JSON.stringify({
    h1: document.querySelectorAll('h1').length, skips,
    nav: document.querySelectorAll('nav.nav .wrap > a').length,
    main: !!document.querySelector('main'), skip: !!document.querySelector('a.skip'),
    deadAnchors: [...document.querySelectorAll('a[href^="#"]')]
      .map(a => a.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id)),
    // Subresources only. rel=canonical / alternate / me are metadata: they name
    // a URL for crawlers and are never fetched, so an absolute one costs the
    // reader nothing. Everything that IS fetched — stylesheet, icon, preload,
    // script, img, iframe — still fails here if it points off-origin.
    external: [...document.querySelectorAll('link[href],script[src],img[src],iframe[src]')]
      .filter(e => !(e.tagName === 'LINK' &&
        /^(canonical|alternate|me|author)$/i.test(e.getAttribute('rel') || '')))
      .map(e => e.getAttribute('href') || e.getAttribute('src'))
      .filter(u => /^(https?:)?\\/\\//.test(u)),
    hidden: [...document.querySelectorAll('section, article, figure, .card')].filter(el => {
      const st = getComputedStyle(el), r = el.getBoundingClientRect();
      return st.display === 'none' || st.visibility === 'hidden' ||
             parseFloat(st.opacity) < 0.9 || (r.width === 0 && r.height === 0); }).length,
    figures: document.querySelectorAll('figure img, figure svg').length,
    tables: document.querySelectorAll('details.figdata table').length,
  });
})()`;

/* -------------------------------------------------------------- runner */
(async () => {
  const targets = await getJSON("/json/list");
  const cdp = await connect(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");

  let fails = 0;
  const load = async (rel, w, opts = {}) => {
    await cdp.send("Emulation.setDeviceMetricsOverride",
      { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 700, screenWidth: w });
    if (opts.theme) {
      await cdp.send("Emulation.setEmulatedMedia",
        { features: [{ name: "prefers-color-scheme", value: opts.theme }] });
    }
    await cdp.send("Emulation.setScriptExecutionDisabled", { value: !!opts.noJs });
    const loaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: `file:///${WIN}/${rel}` });
    await loaded;
    await new Promise((r) => setTimeout(r, 140));
  };
  const evalIn = async (expr) =>
    JSON.parse((await cdp.send("Runtime.evaluate", { expression: expr, returnByValue: true })).result.value);

  /* ---- layout across widths ---- */
  console.log("\n=== LAYOUT (overflow, and text under 12px) ===");
  for (const w of WIDTHS) {
    for (const rel of PAGES) {
      await load(rel, w);
      const r = await evalIn(LAYOUT(w, MIN_FONT_PX));
      const bad = r.pageOverflow || r.wide.length || r.tiny.length;
      if (bad) {
        fails++;
        console.log(`  ${String(w).padEnd(5)} ${rel}`);
        if (r.pageOverflow) console.log(`      PAGE OVERFLOW doc=${r.docScroll} vs ${r.device}`);
        r.wide.forEach((x) => console.log(
          `      wide  ${x.tag}.${x.cls} w=${x.w} scroll=${x.sw}/${x.cw} (${x.why})`));
        r.tiny.forEach((x) => console.log(
          `      tiny  ${x.px}px  ${x.tag}.${x.cls}  "${x.text}"`));
      }
      (r.scrollRegions || []).forEach((s) => {
        if (!s.labelled || !s.focusable) {
          fails++;
          console.log(`  ${String(w).padEnd(5)} ${rel}\n      scroll region .${s.cls} ` +
            `labelled=${s.labelled} keyboard=${s.focusable}`);
        }
      });
    }
  }
  if (!fails) console.log("  clean at 320, 390, 768 and 1440");

  /* ---- contrast in both themes ---- */
  console.log("\n=== CONTRAST (computed, both themes) ===");
  let cfail = 0;
  for (const theme of ["light", "dark"]) {
    for (const rel of PAGES) {
      await load(rel, 1280, { theme });
      const rows = await evalIn(CONTRAST);
      rows.forEach((x) => {
        cfail++; fails++;
        console.log(`  ${theme} ${rel}: ${x.ratio}:1 (need ${x.need}) ${x.tag}.${x.cls} "${x.text}"`);
      });
    }
  }
  if (!cfail) console.log("  0 failing text/background pairs");

  /* ---- structure, and the no-JS pass ---- */
  console.log("\n=== STRUCTURE + NO-JS ===");
  let sfail = 0;
  for (const noJs of [false, true]) {
    for (const rel of PAGES) {
      await load(rel, 1280, { noJs });
      const r = await evalIn(STRUCT);
      const problems = [];
      if (r.h1 !== 1) problems.push(`h1=${r.h1}`);
      if (r.skips.length) problems.push(`heading skips ${r.skips.join(",")}`);
      if (r.nav !== NAV_LINKS) problems.push(`nav=${r.nav} (want ${NAV_LINKS})`);
      if (!r.main || !r.skip) problems.push("missing landmark or skip link");
      if (r.deadAnchors.length) problems.push(`dead anchors ${r.deadAnchors.join(",")}`);
      if (r.external.length) problems.push(`EXTERNAL ${r.external.join(",")}`);
      if (noJs && r.hidden) problems.push(`${r.hidden} hidden with JS off`);
      if (problems.length) {
        sfail++; fails++;
        console.log(`  ${noJs ? "no-js" : "js   "} ${rel}: ${problems.join("; ")}`);
      }
    }
  }
  if (!sfail) console.log("  clean with scripting on and off");

  /* ---- chart labels must not sit on top of each other ---- */
  console.log("\n=== CHART LABELS (measured overlap) ===");
  let lfail = 0;
  for (const w of [320, 1440]) {
    // Every page, not an allow-list of two path fragments. The filter here used to
    // be `/investing/` or `/research/`, which silently skipped every other page
    // carrying a chart — including /how-i-work and /projects/agent-research-programme,
    // whose slug contains "research" but not "/research/". The probe returns nothing
    // for a page with no `figure svg`, so checking all of them costs a page load and
    // removes the class of blind spot rather than one instance of it.
    for (const rel of PAGES) {
      await load(rel, w);
      for (const hit of await evalIn(CHART_TEXT)) {
        lfail++; fails++;
        console.log(`  ${String(w).padEnd(5)} ${rel}`);
        console.log(`      "${hit.a}" / "${hit.b}"  x=${hit.px} y=${hit.vy} boxh=${hit.ah}  ${hit.chart}`);
      }
    }
  }
  if (!lfail) console.log("  no overlapping chart labels at 320 or 1440");

  console.log(`\n${fails === 0 ? "PASS" : "FAIL"} — ${fails} finding(s)`);
  cdp.close();
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error("ERROR", e.message); process.exit(2); });
