// juanmediavilla.com — the whole of the site's JavaScript.
// No framework, no build step, no dependency, no third-party request.
//
// The rule: nothing here enables content. Every chart, every section and every
// link works with this file blocked. This adds a theme toggle, a gentle reveal,
// and a hero animation built from real data — and nothing else.

(() => {
  "use strict";

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  /* ---------------------------------------------------------------- theme */
  // The inline snippet in <head> has already applied the stored choice, so the
  // page never flashes. This only wires the control.
  const THEMES = ["system", "light", "dark"];

  function apply(mode) {
    const root = document.documentElement;
    if (mode === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", mode);
    try { localStorage.setItem("theme", mode); } catch (_) {}
    // The hero field paints from --dot / --dot-hot, which the attribute above
    // has just changed. Canvas cannot inherit a custom property, so it is told.
    dispatchEvent(new CustomEvent("themechange"));
  }

  function currentTheme() {
    try { return localStorage.getItem("theme") || "system"; } catch (_) { return "system"; }
  }

  function mountThemeToggle() {
    const slot = document.querySelector("[data-theme-slot]");
    if (!slot) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme-toggle";
    const label = () => {
      const m = currentTheme();
      btn.textContent = m === "system" ? "theme: auto" : `theme: ${m}`;
      btn.setAttribute("aria-label", `Colour theme: ${m}. Activate to change.`);
    };
    btn.addEventListener("click", () => {
      apply(THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length]);
      label();
    });
    label();
    slot.appendChild(btn);
  }

  /* -------------------------------------------------------------- reveals */
  function mountReveals() {
    const targets = document.querySelectorAll(".reveal");
    if (!targets.length || reduced.matches || !("IntersectionObserver" in window)) return;

    const show = (el) => el.classList.remove("pending");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { show(e.target); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });

    targets.forEach((el) => {
      // Anything already on screen is left alone: hiding it would mean content
      // that JS has to give back, which is the one thing this must never do.
      if (el.getBoundingClientRect().top < innerHeight * 0.9) return;
      el.classList.add("pending");
      io.observe(el);
    });
    // Insurance: nothing stays hidden because an observer never fired.
    addEventListener("load", () => setTimeout(() => targets.forEach(show), 2000));
  }

  /* ----------------------------------------------------------- hero field */
  // A simulated repricing process for one prediction market, drawn as the chart
  // it actually is: the model's intensity as a step line above a time axis, and
  // every price move as a tick below it. Both levels and both dwell times are
  // the population rates fitted in the MSc thesis, so the rhythm on screen is
  // the thesis's own finding rather than an invented one. Nothing here is
  // measured price data — only the timing model, simulated live.
  const LAMBDA_COLD = 0.041 / 60;   // moves per second, quiet state
  const LAMBDA_HOT = 1.141 / 60;    // moves per second, busy state
  const DWELL_COLD = 37 * 60;
  const DWELL_HOT = 8 * 60;

  function mountHero() {
    const canvas = document.querySelector(".field__canvas");
    if (!canvas || !canvas.getContext) return;

    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, raf = 0, last = 0;
    let moves = [];               // {x, hot} — one per simulated price move
    let runs = [];                // {x0, x1, hot} — stretches of the hidden state
    let head = 0;                 // x of the simulation frontier
    let hot = false, flipIn = 0;  // current state, and seconds until it switches
    let cold = "#C2C2CE", warm = "#4F46E5", ink3 = "#63636F", rule = "#E3E3E9";

    const SPEED = 26;           // px per second of drift
    // Simulated seconds per real second, and the only free parameter here: the
    // gaps and the dwell times come from the fitted rates, and SCALE only sets
    // how much of that timeline fits on screen.
    //
    // It is set by what the busy state needs to be legible, because the dwell
    // is exponential and therefore skewed — the mean is 8 min but the median is
    // 5.5, so most bursts are shorter than average. At 520 a typical burst was
    // ~15px on a 1000px strip, which reads as a glitch rather than as a burst.
    // At 260 the mean burst is ~48px and the median ~33px, and about four
    // quiet/busy cycles fit on screen. Widening the burst by shortening the
    // dwell would have been the dishonest fix; this changes only the zoom.
    const SCALE = 260;
    const GUT = 46;             // left gutter, reserved for the axis labels
    const PAD_T = 15;           // headroom above the busy level
    const RUG = 14;             // band below the axis holding the move ticks
    const FOOT = 18;            // footline, for the time-span label

    // Rates in moves per minute, and the log axis they are drawn on. Busy is
    // 28x quiet, so on a linear axis the quiet level sits 3.6% above the
    // baseline — it merges with the axis rule and the whole chart reads as
    // empty. A log axis separates the two levels and is the ordinary treatment
    // for a rate spanning more than a decade; the footline declares it.
    const RATE_QUIET = 0.041, RATE_BUSY = 1.141;
    const AXIS_LO = 0.02, AXIS_HI = 2.0;

    // Canvas cannot inherit a custom property, so the inks are resolved from
    // the page and re-resolved whenever the theme changes.
    function inks() {
      const cs = getComputedStyle(document.documentElement);
      cold = cs.getPropertyValue("--dot").trim() || cold;
      ink3 = cs.getPropertyValue("--ink-3").trim() || ink3;
      rule = cs.getPropertyValue("--line-2").trim() || rule;
      warm = cs.getPropertyValue("--dot-hot").trim() || warm;
      if (warm.startsWith("var")) warm = cs.getPropertyValue("--c1").trim() || "#4F46E5";
    }

    function size() {
      const r = canvas.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = Math.max(r.width, 1); h = Math.max(r.height, 1);
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const exp = (rate) => -Math.log(1 - Math.random()) / rate;
    const toPx = (secs) => (secs / SCALE) * SPEED;
    const yBase = () => h - FOOT - RUG;                  // the time axis
    const yOf = (rate) => {
      const f = (Math.log(rate) - Math.log(AXIS_LO)) / (Math.log(AXIS_HI) - Math.log(AXIS_LO));
      return yBase() - (yBase() - PAD_T) * f;
    };
    const level = (isHot) => yOf(isHot ? RATE_BUSY : RATE_QUIET);

    // Extend the simulation until it runs past the right edge.
    function extend() {
      let guard = 4000;
      while (head < w + 60 && guard-- > 0) {
        let waited = 0;
        for (;;) {
          const gap = exp(hot ? LAMBDA_HOT : LAMBDA_COLD);
          if (gap <= flipIn) { waited += gap; flipIn -= gap; break; }
          // The hidden state switches before the next move. Advance to the
          // switch and redraw the wait under the new rate — the process is
          // memoryless, so the part already waited carries no information.
          waited += flipIn;
          const xs = head + toPx(waited);
          hot = !hot;
          flipIn = exp(1 / (hot ? DWELL_HOT : DWELL_COLD));
          runs[runs.length - 1].x1 = xs;
          runs.push({ x0: xs, x1: xs, hot });
        }
        head += toPx(waited);
        runs[runs.length - 1].x1 = head;
        moves.push({ x: head, hot });
      }
    }

    function seed() {
      hot = false;
      flipIn = exp(1 / DWELL_COLD);
      head = GUT - 30;
      moves = [];
      runs = [{ x0: head, x1: head, hot }];
      extend();
    }

    function shift(dx) {
      for (const m of moves) m.x -= dx;
      for (const r of runs) { r.x0 -= dx; r.x1 -= dx; }
      head -= dx;
      while (moves.length && moves[0].x < GUT - 30) moves.shift();
      while (runs.length > 1 && runs[0].x1 < GUT - 30) runs.shift();
      extend();
    }

    function paint() {
      const base = yBase();
      ctx.clearRect(0, 0, w, h);
      ctx.lineJoin = "round";

      // everything that scrolls is clipped out of the label gutter
      ctx.save();
      ctx.beginPath();
      ctx.rect(GUT, 0, Math.max(w - GUT, 0), h);
      ctx.clip();

      // Busy stretches, tinted so a burst reads before you look at anything.
      // Filled from the busy level down to the axis, not from the top of the
      // plot: filling to the top put shading above the step line, so a wide
      // burst looked like a block the line was buried inside rather than an
      // area the line is the top edge of.
      const yHot = level(true);
      ctx.fillStyle = warm;
      ctx.globalAlpha = 0.11;
      for (const r of runs) if (r.hot) ctx.fillRect(r.x0, yHot, r.x1 - r.x0, base - yHot);
      ctx.globalAlpha = 1;

      // the intensity itself: a step line between the two fitted rates
      ctx.strokeStyle = warm;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      runs.forEach((r, i) => {
        const y = level(r.hot);
        if (i === 0) ctx.moveTo(r.x0, y); else ctx.lineTo(r.x0, y);
        ctx.lineTo(r.x1, y);
      });
      ctx.stroke();

      // one tick per price move, below the axis: the events the line explains
      ctx.lineWidth = 1;
      for (const m of moves) {
        ctx.strokeStyle = m.hot ? warm : cold;
        ctx.beginPath();
        ctx.moveTo(m.x, base + 3);
        ctx.lineTo(m.x, base + 3 + (m.hot ? 9 : 5));
        ctx.stroke();
      }
      ctx.restore();

      // the axis, and the labels that make the two levels readable
      ctx.strokeStyle = rule;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(GUT, base + 0.5);
      ctx.lineTo(w, base + 0.5);
      ctx.stroke();

      ctx.font = "12px 'Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.fillStyle = ink3;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText("1.14", GUT - 9, level(true));
      ctx.fillText("0.04", GUT - 9, level(false));

      // The hidden state, named as it switches — the thing the model infers.
      // Read at the right edge, where the newest simulated time is, rather than
      // at the frontier, which is up to 60px off-screen.
      const now = runs.find((r) => r.x0 <= w && r.x1 >= w) || runs[runs.length - 1];
      const state = now && now.hot ? "BUSY" : "QUIET";
      ctx.textAlign = "right";
      ctx.textBaseline = "alphabetic";
      ctx.fillStyle = now && now.hot ? warm : ink3;
      ctx.fillText(state, w, h - 5);

      // The footline declares the units and the log scale. At 320px the full
      // wording is wider than the canvas, so it degrades instead of colliding
      // with the state label.
      ctx.textAlign = "left";
      ctx.fillStyle = ink3;
      const hours = Math.max(1, Math.round((w - GUT) / SPEED * SCALE / 3600));
      const room = w - GUT - ctx.measureText(state).width - 14;
      const foot = [
        `${hours} h simulated  ·  moves per minute, log scale`,
        `${hours} h  ·  moves/min, log`,
        `${hours} h`,
      ].find((s) => ctx.measureText(s).width <= room);
      if (foot) ctx.fillText(foot, GUT, h - 5);
    }

    function draw(now) {
      raf = requestAnimationFrame(draw);
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      shift(dt * SPEED);
      paint();
    }

    function still() { paint(); }            // one static frame, no motion

    function start() {
      if (raf || reduced.matches || document.hidden) return;
      last = performance.now();
      raf = requestAnimationFrame(draw);
    }
    function stop() { cancelAnimationFrame(raf); raf = 0; }

    // The caption belongs to the canvas, so it is written by the same code that
    // draws it: no canvas, no orphaned sentence describing an empty strip.
    const note = document.querySelector("[data-field-note]");
    if (note) {
      note.textContent =
        "Above: a simulation of when one prediction market reprices. The step line is how fast " +
        "the price is moving — on a log scale, because the busy rate is 28 times the quiet one — " +
        "and each tick below the axis is one move. Both levels are fitted in my MSc thesis: about " +
        "one move every 25 minutes while the market is quiet, one every 53 seconds while it is " +
        "busy. Which of the two it is in is never observed, only inferred.";
    }

    inks(); size(); seed();
    if (reduced.matches) still(); else start();

    // Under reduced motion the strip is painted exactly once, which can land
    // before the mono webfont has loaded and leave the axis labels in the
    // fallback face for good. The animated path repaints anyway.
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => { if (reduced.matches) still(); });
    }

    addEventListener("resize", () => { stop(); size(); seed(); reduced.matches ? still() : start(); },
      { passive: true });
    addEventListener("themechange", () => { inks(); if (reduced.matches) still(); });
    matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => { inks(); if (reduced.matches) still(); });
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
    reduced.addEventListener("change", () => { stop(); reduced.matches ? still() : start(); });
  }

  /* ------------------------------------------------------------------ go */
  document.documentElement.classList.add("js");
  const boot = () => { mountThemeToggle(); mountReveals(); mountHero(); };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

/* ============================ round-6 motion ============================
   Everything below is additive. With this file blocked the page is complete:
   counters show their final value, the progress bar is absent, and tooltips
   are replaced by the data table that is already in the DOM under each figure. */

(() => {
  "use strict";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const idle = (fn) => (window.requestIdleCallback || setTimeout)(fn, 1);

  /* ------------------------------------------------ scroll progress */
  function mountProgress() {
    if (document.body.scrollHeight < innerHeight * 2.5) return;
    const bar = document.createElement("div");
    bar.className = "progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);
    let ticking = false;
    const paint = () => {
      const max = document.body.scrollHeight - innerHeight;
      bar.style.width = `${max > 0 ? (scrollY / max) * 100 : 0}%`;
      ticking = false;
    };
    addEventListener("scroll", () => {
      if (!ticking) { ticking = true; requestAnimationFrame(paint); }
    }, { passive: true });
    paint();
  }

  /* ------------------------------------------------ stat counters */
  // Counts to the value already in the markup, so the final state is identical
  // whether or not this runs. Tabular numerals keep the width stable.
  function mountCounters() {
    const tiles = document.querySelectorAll(".stat__v");
    if (!tiles.length || reduced.matches || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        const el = e.target;
        const final = el.textContent;
        const m = final.match(/^([\d,]+)(.*)$/);
        if (!m) return;
        const target = Number(m[1].replace(/,/g, ""));
        if (!target || target > 1e7) return;
        const t0 = performance.now(), dur = 900;
        const step = (now) => {
          const k = Math.min(1, (now - t0) / dur);
          const eased = 1 - Math.pow(1 - k, 3);
          el.textContent = Math.round(target * eased).toLocaleString("en-GB") + m[2];
          if (k < 1) requestAnimationFrame(step); else el.textContent = final;
        };
        requestAnimationFrame(step);
      });
    }, { threshold: 0.4 });
    tiles.forEach((t) => io.observe(t));
  }

  /* ------------------------------------------------ chart tooltips */
  // Built from the data table already published under each figure, so the
  // numbers cost no extra markup and stay identical to what a reader can read.
  function mountTooltips() {
    const figures = document.querySelectorAll("figure");
    let tip = null;
    const hide = () => { if (tip) { tip.remove(); tip = null; } };

    figures.forEach((fig) => {
      const img = fig.querySelector("img[src$='.svg']");
      const table = fig.querySelector("details.figdata table");
      if (!img || !table) return;
      const head = [...table.querySelectorAll("thead th")].map((th) => th.textContent.trim());
      const rows = [...table.querySelectorAll("tbody tr")]
        .map((tr) => [...tr.children].map((td) => td.textContent.trim()));
      if (!rows.length) return;

      img.addEventListener("pointermove", (e) => {
        const r = img.getBoundingClientRect();
        const k = Math.min(rows.length - 1,
          Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * rows.length)));
        const row = rows[k];
        if (!tip) {
          tip = document.createElement("div");
          tip.className = "tip";
          tip.setAttribute("role", "presentation");
          document.body.appendChild(tip);
        }
        tip.innerHTML = row
          .map((v, i) => `<b>${head[i] || ""}</b> ${v}`)
          .join("<br>");
        const w = tip.offsetWidth, h = tip.offsetHeight;
        tip.style.left = `${Math.min(e.clientX + 14, innerWidth - w - 8)}px`;
        tip.style.top = `${Math.max(8, e.clientY - h - 12)}px`;
      });
      img.addEventListener("pointerleave", hide);
      img.addEventListener("pointercancel", hide);
    });
    addEventListener("scroll", hide, { passive: true });
  }

  idle(() => { mountProgress(); mountCounters(); mountTooltips(); });
})();
