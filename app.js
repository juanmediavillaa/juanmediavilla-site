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
  // A point process drifting across the hero: long quiet stretches, then a
  // burst. The inter-arrival times come from the fitted population rates, so the
  // rhythm on screen is the thesis's own finding rather than an invented one.
  const LAMBDA_COLD = 0.041 / 60;   // moves per second, quiet state
  const LAMBDA_HOT = 1.141 / 60;    // moves per second, busy state
  const DWELL_COLD = 37 * 60;
  const DWELL_HOT = 8 * 60;

  function mountHero() {
    const canvas = document.querySelector(".hero__canvas");
    if (!canvas || !canvas.getContext) return;

    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, dots = [], hot = false, until = 0, next = 0, raf = 0, last = 0;
    const SPEED = 26;           // px per second of drift
    const SCALE = 90;           // simulated seconds per real second

    function size() {
      const r = canvas.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = Math.max(r.width, 1); h = Math.max(r.height, 1);
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const exp = (rate) => -Math.log(1 - Math.random()) / rate;

    function seed() {
      dots = [];
      let t = 0, x = 0, isHot = false, flip = exp(1 / DWELL_COLD);
      while (x < w) {
        const gap = exp(isHot ? LAMBDA_HOT : LAMBDA_COLD);
        t += gap; x += (gap / SCALE) * SPEED;
        if (t > flip) { isHot = !isHot; flip = t + exp(1 / (isHot ? DWELL_HOT : DWELL_COLD)); }
        dots.push({ x, hot: isHot });
      }
      hot = isHot; until = flip; next = t;
    }

    function draw(now) {
      raf = requestAnimationFrame(draw);
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      const dx = dt * SPEED;
      ctx.clearRect(0, 0, w, h);
      const mid = h / 2;
      for (const d of dots) {
        d.x -= dx;
        const a = Math.min(1, Math.max(0, 1 - Math.abs(d.x - w * 0.5) / (w * 0.6)));
        ctx.beginPath();
        ctx.arc(d.x, mid + (d.hot ? -14 : 14), d.hot ? 2.6 : 1.6, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${(d.hot ? 0.85 : 0.45) * a})`;
        ctx.fill();
      }
      while (dots.length && dots[0].x < -8) dots.shift();
      const lastX = dots.length ? dots[dots.length - 1].x : 0;
      if (lastX < w + 40) {
        const t = next, gap = exp(hot ? LAMBDA_HOT : LAMBDA_COLD);
        next = t + gap;
        if (next > until) {
          hot = !hot;
          until = next + exp(1 / (hot ? DWELL_HOT : DWELL_COLD));
        }
        dots.push({ x: lastX + (gap / SCALE) * SPEED, hot });
      }
    }

    function still() {                       // one static frame, no motion
      ctx.clearRect(0, 0, w, h);
      const mid = h / 2;
      for (const d of dots) {
        ctx.beginPath();
        ctx.arc(d.x, mid + (d.hot ? -14 : 14), d.hot ? 2.6 : 1.6, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${d.hot ? 0.8 : 0.4})`;
        ctx.fill();
      }
    }

    function start() {
      if (raf || reduced.matches || document.hidden) return;
      last = performance.now();
      raf = requestAnimationFrame(draw);
    }
    function stop() { cancelAnimationFrame(raf); raf = 0; }

    size(); seed();
    if (reduced.matches) still(); else start();

    addEventListener("resize", () => { stop(); size(); seed(); reduced.matches ? still() : start(); },
      { passive: true });
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
