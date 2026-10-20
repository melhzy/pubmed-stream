/* The Aβ*56 retraction-impact viewer: a React 18 application without a build step.
   index.html loads React, ReactDOM and marked from a CDN, then data.js (window.STUDY_DATA,
   built from the study's files by scripts/build_viewer.py), then this file.
   Components are written with React.createElement (aliased h) so the page opens from disk. */
(function () {
  "use strict";
  const { useState, useEffect, useLayoutEffect, useMemo, useRef } = React;
  const h = React.createElement;
  const DATA = window.STUDY_DATA;

  /* ---------- shared helpers ---------- */
  const VIEWS = [
    ["overview", "Overview"], ["reach", "Reach"], ["citations", "How it was cited"], ["wrong", "What was wrong"],
    ["footprint", "Training footprint"], ["probes", "Model probes"], ["data", "Data & sources"],
  ];
  const KIND_LABEL = { names: "Names Aβ*56", general: "Cites it in general", doubts: "Discusses the doubts or retraction", unread: "Not read" };
  const KIND_COLOR = { names: "var(--series-1)", doubts: "var(--series-2)", general: "var(--series-3)", unread: "var(--other)" };
  const PERIODS = [[2006, 2011], [2012, 2016], [2017, 2021], [2022, 2023], [2024, 2026]];
  const periodOf = y => PERIODS.find(p => y >= p[0] && y <= p[1]);
  const periodLabel = p => p[0] + "–" + p[1];
  const thisYear = new Date().getFullYear();
  const fmt = n => (n === null || n === undefined || n === "") ? "–" : Number(n).toLocaleString("en-US");
  const pct = (a, b) => b ? Math.round(100 * a / b) + "%" : "–";
  const compact = v => v >= 1000 ? (Math.round(v / 100) / 10).toString().replace(/\.0$/, "") + "K" : String(v);
  const kindKey = k => k.startsWith("Names") ? "names" : k.startsWith("Cites") ? "general" : k.startsWith("Discusses") ? "doubts" : "unread";
  const ROWS = DATA.citing.map(r => Object.assign({}, r, { kind: kindKey(r.citation_kind), year: +r.year }));
  const EVENTS = [{ year: 2022, frac: 6 / 12, label: "Jul 2022: doubts published" }, { year: 2024, frac: 5 / 12, label: "Jun 2024: retracted" }];
  const canMarkdown = () => window.marked && typeof marked.parse === "function";

  function niceTicks(max) {
    if (max <= 0) return [0];
    const raw = max / 4, p = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => raw <= s);
    const t = []; for (let v = 0; v <= max + 1e-9; v += step) t.push(Math.round(v * 1000) / 1000);
    if (t[t.length - 1] < max) t.push(t[t.length - 1] + step);
    return t;
  }
  function topRoundedBar(x, y, w, hgt, r) {
    r = Math.min(r, w / 2, hgt); if (hgt <= 0) return "";
    return "M" + x + "," + (y + hgt) + " v" + (-(hgt - r)) + " a" + r + "," + r + " 0 0 1 " + r + ",-" + r + " h" + (w - 2 * r) + " a" + r + "," + r + " 0 0 1 " + r + "," + r + " v" + (hgt - r) + " z";
  }
  function rightRoundedBar(x, y, w, hgt, r) {
    r = Math.min(r, w / 2, hgt / 2); if (w <= 0) return "";
    return "M" + x + "," + y + " h" + (w - r) + " a" + r + "," + r + " 0 0 1 " + r + "," + r + " v" + (hgt - 2 * r) + " a" + r + "," + r + " 0 0 1 -" + r + "," + r + " h-" + (w - r) + " z";
  }
  function useWidth(ref) {
    const [w, setW] = useState(0);
    useEffect(() => {
      const node = ref.current; if (!node) return undefined;
      const measure = () => setW(node.clientWidth);
      measure();
      if (window.ResizeObserver) { const ro = new ResizeObserver(measure); ro.observe(node); return () => ro.disconnect(); }
      window.addEventListener("resize", measure); return () => window.removeEventListener("resize", measure);
    }, [ref]);
    return w;
  }

  /* ---------- small pieces ---------- */
  function Tile({ value, label, sub }) {
    return h("div", { className: "tile" }, h("div", { className: "v" }, value), h("div", { className: "l" }, label), sub ? h("div", { className: "s" }, sub) : null);
  }
  function Chip({ kind }) {
    return h("span", { className: "chip" }, h("i", { className: "dot " + kind }), KIND_LABEL[kind]);
  }
  function Tooltip({ tip, figRef }) {
    const ref = useRef(null);
    useLayoutEffect(() => {
      const node = ref.current, fig = figRef.current; if (!node || !fig) return;
      const fw = fig.clientWidth, w = node.offsetWidth, hh = node.offsetHeight;
      let left = tip.x + 12; if (left + w > fw - 8) left = tip.x - w - 12;
      let top = tip.y - hh - 8; if (top < 4) top = tip.y + 14;
      node.style.left = left + "px"; node.style.top = top + "px";
    }, [tip, figRef]);
    return h("div", { className: "tip", ref, style: { display: "block" } },
      h("b", null, tip.title),
      tip.lines.map(([v, label, color], i) => h("div", { className: "row", key: i }, color ? h("span", { className: "k", style: { background: color } }) : null, h("span", null, v + " " + label))));
  }
  function TableView({ head, rows }) {
    return h("details", { className: "tableview" }, h("summary", null, "Table"),
      h("table", null, h("thead", null, h("tr", null, head.map((c, i) => h("th", { key: i, className: i ? "num" : "" }, c)))),
        h("tbody", null, rows.map((r, i) => h("tr", { key: i }, r.map((c, j) => h("td", { key: j, className: j ? "num" : "" }, c)))))));
  }
  /* Markdown, rendered by marked (our own documents and model answers); headings get ids for a table of contents */
  function Doc({ md, id, withToc, className }) {
    const ref = useRef(null);
    const [toc, setToc] = useState([]);
    const html = useMemo(() => canMarkdown() ? marked.parse(md || "") : null, [md]);
    useEffect(() => {
      const root = ref.current; if (!root) return;
      root.querySelectorAll("a").forEach(a => { a.target = "_blank"; a.rel = "noopener"; });
      if (withToc) {
        const items = [];
        root.querySelectorAll("h2, h3").forEach((hd, i) => { hd.id = id + "-h" + i; items.push({ id: hd.id, text: hd.textContent, level: hd.tagName.toLowerCase() }); });
        setToc(items);
      }
    }, [html, id, withToc]);
    const article = html !== null
      ? h("article", { className: "doc " + (className || ""), ref, dangerouslySetInnerHTML: { __html: html } })
      : h("article", { className: "doc " + (className || ""), ref }, h("p", { className: "note" }, "The Markdown renderer could not be loaded (no network?). The text follows as written."), h("pre", { className: "raw" }, md));
    if (!withToc) return article;
    return h("div", { className: "docgrid" },
      h("nav", { className: "toc", "aria-label": "Contents" }, toc.map(t => h("a", {
        key: t.id, href: "#" + t.id, className: t.level,
        onClick: e => { e.preventDefault(); const node = document.getElementById(t.id); if (node) node.scrollIntoView({ block: "start" }); },
      }, t.text))),
      article);
  }

  /* ---------- charts ---------- */
  /* Columns, single or stacked. Bars are at most 24px wide with a 4px rounded top, stacked segments keep a 2px gap,
     the grid is a solid hairline, every bar is a hover and focus target, and a table twin sits below. */
  function ColumnChart({ title, how, series, rows, events, labelEvery, totals }) {
    const figRef = useRef(null), plotRef = useRef(null);
    const width = useWidth(plotRef);
    const [tip, setTip] = useState(null);
    const [hover, setHover] = useState(-1);
    const W = Math.max(280, width || 600), H = 250, m = { top: 26, right: 12, bottom: rows[0] && rows[0].note ? 40 : 28, left: 40 };
    const iw = W - m.left - m.right, ih = H - m.top - m.bottom;
    const sums = rows.map(r => series.reduce((a, s) => a + (r.values[s.key] || 0), 0));
    const max = Math.max(1, ...sums), ticks = niceTicks(max), yMax = ticks[ticks.length - 1];
    const band = iw / rows.length, bw = Math.min(24, band * 0.7);
    const y = v => m.top + ih - (v / yMax) * ih;
    const maxIdx = sums.indexOf(Math.max(...sums));
    const lastComplete = rows.map((r, i) => r.partial ? -1 : i).filter(i => i >= 0).pop();
    const every = labelEvery || (band < 26 ? 4 : band < 44 ? 2 : 1);
    const over = (e, i) => {
      const fr = figRef.current.getBoundingClientRect();
      let x, yy;
      if (e && e.clientX !== undefined) { x = e.clientX - fr.left; yy = e.clientY - fr.top; }
      else { const br = e.currentTarget.getBoundingClientRect(); x = br.left + br.width / 2 - fr.left; yy = br.top - fr.top; }
      const r = rows[i];
      const lines = series.map(s => [fmt(r.values[s.key] || 0), s.label, series.length > 1 ? s.color : null]).reverse();
      if (series.length > 1) lines.push([fmt(sums[i]), "in all", null]);
      setHover(i); setTip({ x, y: yy, title: r.label + (r.partial ? " (incomplete)" : ""), lines });
    };
    const out = () => { setHover(-1); setTip(null); };
    const bars = rows.map((r, i) => {
      const x0 = m.left + i * band + (band - bw) / 2; let acc = 0;
      const segs = series.map((s, si) => {
        const v = r.values[s.key] || 0; if (v <= 0) return null;
        const yTop = y(acc + v), yBot = y(acc), gap = si > 0 ? 2 : 0, hgt = Math.max(0, yBot - yTop - gap);
        const isTop = series.slice(si + 1).every(t => !(r.values[t.key] > 0));
        const d = isTop ? topRoundedBar(x0, yTop, bw, hgt, 4) : "M" + x0 + "," + (yBot - gap) + " v" + (-hgt) + " h" + bw + " v" + hgt + " z";
        acc += v;
        return h("path", { key: s.key, className: "bar" + (hover === i ? " hover" : ""), d, style: { fill: s.color }, opacity: r.partial ? 0.45 : 1 });
      });
      const label = series.map(s => fmt(r.values[s.key] || 0) + " " + s.label).join(", ");
      return h("g", {
        key: r.label, tabIndex: 0, role: "img", "aria-label": r.label + ": " + label,
        onPointerMove: e => over(e, i), onPointerLeave: out, onFocus: e => over(e, i), onBlur: out,
      }, h("rect", { className: "hit", x: m.left + i * band, y: m.top, width: band, height: ih }), segs,
        ((totals && sums[i] > 0) || i === maxIdx || i === lastComplete) ? h("text", { className: "ink", x: x0 + bw / 2, y: y(sums[i]) - 5, textAnchor: "middle" }, fmt(sums[i])) : null,
        (i % every === 0 || every === 1) ? h("text", { x: m.left + i * band + band / 2, y: m.top + ih + 15, textAnchor: "middle" }, r.label) : null,
        r.note ? h("text", { x: m.left + i * band + band / 2, y: m.top + ih + 29, textAnchor: "middle" }, r.note) : null);
    });
    const eventMarks = (events || []).map(ev => {
      const i = rows.findIndex(r => r.label === String(ev.year)); if (i < 0) return null;
      const x = m.left + (i + ev.frac) * band, right = x > W * 0.6;
      return h("g", { className: "ev", key: ev.label }, h("line", { x1: x, x2: x, y1: m.top - 4, y2: m.top + ih }),
        h("text", { x: right ? x - 4 : x + 4, y: m.top - 8, textAnchor: right ? "end" : "start" }, ev.label));
    });
    const head = [""].concat(series.map(s => s.label), rows[0] && rows[0].note ? ["Not read"] : []);
    const tableRows = rows.map(r => [r.label + (r.partial ? " (incomplete)" : "")].concat(series.map(s => fmt(r.values[s.key] || 0)), r.note ? [r.note.replace(" not read", "")] : []));
    return h("figure", { ref: figRef },
      h("figcaption", null, h("div", { className: "t" }, title), h("div", { className: "h" }, how)),
      series.length > 1 ? h("div", { className: "legend" }, series.map(s => h("span", { key: s.key }, h("i", { className: "sw", style: { background: s.color } }), h("span", null, s.label)))) : null,
      h("div", { className: "plot", ref: plotRef },
        h("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": title },
          h("g", { className: "grid" }, ticks.filter(t => t > 0).map(t => h(React.Fragment, { key: t },
            h("line", { x1: m.left, x2: W - m.right, y1: y(t), y2: y(t) }),
            h("text", { x: m.left - 6, y: y(t) + 3.5, textAnchor: "end" }, compact(t))))),
          h("line", { className: "base", x1: m.left, x2: W - m.right, y1: y(0), y2: y(0) }),
          bars, eventMarks)),
      tip ? h(Tooltip, { tip, figRef }) : null,
      h(TableView, { head, rows: tableRows }));
  }

  /* Horizontal bars with the value at every tip; claim strings above a rule, correction strings below. */
  function HBarChart({ title, how, rows, color }) {
    const figRef = useRef(null), plotRef = useRef(null);
    const width = useWidth(plotRef);
    const [tip, setTip] = useState(null);
    const [hover, setHover] = useState(-1);
    const W = Math.max(280, width || 520), rowH = 24, m = { top: 6, right: 56, bottom: 6, left: Math.min(230, W * 0.42) };
    const claim = rows.filter(r => r.kind === "claim"), corr = rows.filter(r => r.kind !== "claim"), ordered = claim.concat(corr), sepAt = claim.length;
    const H = m.top + ordered.length * rowH + 10 + m.bottom;
    const max = Math.max(1, ...ordered.map(r => r.value)), iw = W - m.left - m.right, x = v => m.left + (v / max) * iw;
    const over = (e, i) => {
      const fr = figRef.current.getBoundingClientRect(); let px, py;
      if (e && e.clientX !== undefined) { px = e.clientX - fr.left; py = e.clientY - fr.top; } else { const br = e.currentTarget.getBoundingClientRect(); px = m.left; py = br.top - fr.top; }
      const r = ordered[i];
      setHover(i); setTip({ x: px, y: py, title: r.label, lines: [[r.bad ? "not counted" : fmt(r.value), r.kind === "claim" ? "occurrences (claim)" : "occurrences (correction)", null]] });
    };
    const out = () => { setHover(-1); setTip(null); };
    const marks = ordered.map((r, i) => {
      const yy = m.top + i * rowH + (i >= sepAt ? 10 : 0), bwid = Math.max(0, x(r.value) - m.left), bh = 14, by = yy + (rowH - bh) / 2;
      return h(React.Fragment, { key: r.label },
        i === sepAt ? h("line", { className: "base", x1: m.left - 4, x2: W - m.right + 40, y1: yy - 5, y2: yy - 5 }) : null,
        h("g", { tabIndex: 0, role: "img", "aria-label": r.label + ": " + (r.bad ? "not counted" : fmt(r.value)), onPointerMove: e => over(e, i), onPointerLeave: out, onFocus: e => over(e, i), onBlur: out },
          h("rect", { className: "hit", x: 0, y: yy, width: W, height: rowH }),
          h("text", { x: m.left - 8, y: yy + rowH / 2 + 4, textAnchor: "end" }, r.label.length > 34 ? r.label.slice(0, 33) + "…" : r.label),
          bwid > 0 ? h("path", { className: "bar" + (hover === i ? " hover" : ""), d: rightRoundedBar(m.left, by, bwid, bh, 4), style: { fill: color } }) : null,
          h("text", { className: "ink", x: m.left + bwid + 6, y: yy + rowH / 2 + 4 }, r.bad ? "not counted" : fmt(r.value))));
    });
    return h("figure", { ref: figRef },
      h("figcaption", null, h("div", { className: "t" }, title), h("div", { className: "h" }, how)),
      h("div", { className: "plot", ref: plotRef },
        h("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": title },
          h("line", { className: "base", x1: m.left, x2: m.left, y1: m.top, y2: H - m.bottom }), marks)),
      tip ? h(Tooltip, { tip, figRef }) : null,
      h(TableView, { head: ["String", "Kind", "Count"], rows: ordered.map(r => [r.label, r.kind, r.bad ? "not counted" : fmt(r.value)]) }));
  }

  /* ---------- views ---------- */
  function Overview() {
    const reach = DATA.reach || {};
    const nRead = ROWS.filter(r => r.kind !== "unread").length;
    const count = k => ROWS.filter(r => r.kind === k).length;
    const dolma = DATA.strings && DATA.strings.counts && DATA.strings.counts.dolma_v1_7;
    const verdicts = [
      ["", "What is wrong", "The data record: the retraction names Fig. 2c and Supplementary Fig. 4, “excessive manipulation, including splicing, duplication and the use of an eraser tool”, and data that cannot be verified. Five Lesné papers are now retracted, including the ones that gave Aβ*56 a dose–response, a receptor and a pathway to tau. The entity was fragile all along: a dodecamer inferred from a gel band, antibodies that also bind APP fragments, a species its discoverers call rare and protocol-dependent, and no independent confirmation."],
      ["ok", "What still stands", "The general claim the paper was cited for most, that soluble Aβ oligomers impair synaptic function and memory, has independent evidence before and after 2006 (Lambert 1998, Walsh 2002, Cleary 2005, Shankar 2008). The amyloid hypothesis rests on genetics, biomarkers and antibody trials that never ran through Aβ*56."],
      ["warn", "The over-correction", "“The amyloid hypothesis was built on fraud” and “the antibody drugs came from Aβ*56” are false. A model can fail in either direction: stating Aβ*56 as fact, or rejecting the oligomer evidence because of the retraction. The probes test both."],
    ];
    return h("section", { className: "view", id: "overview" },
      h("div", { className: "block" },
        h("p", { className: "lede" }, "A retraction removes a paper from the record, but not the papers built on it, nor the text that language models were trained on. This page follows the retracted 2006 paper on Aβ*56 through the papers citing it and the papers citing those, reads how each one cited it, says exactly what was wrong, measures the claim in open training corpora, and asks models what they believe."),
        h("p", { className: "note" }, "Citing sentences from pubmed-stream's tutorial 8 run of " + DATA.snapshot_date + "; the second citation step fetched " + (reach.fetched || "–") + "; data built " + DATA.built + ".")),
      h("div", { className: "hero" },
        h("p", { className: "eyebrow" }, "Alzheimer's disease papers in PubMed since 2006 within two citation steps of the retracted paper"),
        h("div", { className: "v" }, fmt(reach.field_papers_within_two_steps) + " of " + fmt(reach.field_papers_since_first_year)),
        h("p", { className: "l" }, pct(reach.field_papers_within_two_steps, reach.field_papers_since_first_year) + " of the field, through " + fmt(reach.first_step) + " papers that cite it and " + fmt(reach.second_step) + " that cite one of those.")),
      h("div", { className: "tiles" },
        h(Tile, { value: fmt(reach.first_step), label: "papers cite it", sub: "PubMed links, " + (reach.fetched || "") }),
        h(Tile, { value: fmt(reach.second_step), label: "papers cite one of those", sub: "the second citation step" }),
        h(Tile, { value: fmt(count("names")), label: "name Aβ*56 as a finding", sub: "of " + fmt(nRead) + " citing sentences read" }),
        h(Tile, { value: fmt(count("doubts")), label: "discuss the doubts or retraction", sub: ROWS.filter(r => r.kind === "doubts" && r.year >= 2022).length + " of them from 2022 on" }),
        h(Tile, { value: fmt(DATA.external.retraction_watch_citations), label: "citations on Retraction Watch's count", sub: "the " + DATA.external.retraction_watch_rank + " most cited retracted paper" }),
        dolma ? h(Tile, { value: fmt(dolma["Aβ*56"].count), label: "times “Aβ*56” appears in Dolma v1.7", sub: "correction strings: " + fmt(dolma["Aβ*56 retracted"].count) }) : null),
      h("div", { className: "block" }, h("h2", null, "What the retraction changes, and what it does not"),
        h("div", { className: "three" }, verdicts.map(([cls, head, body]) => h("div", { key: head, className: "card stripe " + cls }, h("h3", null, head), h("p", null, body))))),
      h("div", { className: "block" }, h("h2", null, "Timeline"),
        h("div", { className: "timeline" }, DATA.timeline.map((ev, i) => h("div", { key: i, className: ev.key ? "key" : "" }, h("span", { className: "d" }, ev.date), h("span", null, ev.event))))),
      h("div", { className: "block" }, h("h2", null, "Status of the study"),
        h("div", { className: "tablewrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Step"), h("th", null, "State"))),
          h("tbody", null, DATA.status.map(([step, state], i) => h("tr", { key: i }, h("td", null, step), h("td", null, state))))))));
  }

  function Reach() {
    const reach = DATA.reach || {}, flags = DATA.hop2_flags || {};
    const years = []; for (let yr = 2006; yr <= thisYear; yr++) years.push(yr);
    const byYear = {}; ROWS.forEach(r => { byYear[r.year] = (byYear[r.year] || 0) + 1; });
    const hop2 = {}; (DATA.hop2_by_year || []).forEach(([yr, n]) => { hop2[+yr] = +n; });
    const one = [{ key: "n", label: "Papers", color: "var(--series-1)" }];
    return h("section", { className: "view", id: "reach" },
      h("div", { className: "block" }, h("h2", null, "How far the paper reached"),
        h("p", { className: "note" }, "PubMed links a citation only when the citing article's full text was deposited in PubMed Central, so these counts are lower than Google Scholar's or Web of Science's. The second step is an upper bound on influence: a paper two steps away may share nothing with Aβ*56 beyond a common review.")),
      h("div", { className: "tiles" },
        h(Tile, { value: fmt(reach.first_step), label: "papers cite it", sub: "first step" }),
        h(Tile, { value: fmt(reach.second_step), label: "papers cite one of those", sub: "second step" }),
        h(Tile, { value: pct(reach.field_papers_within_two_steps, reach.field_papers_since_first_year), label: "of Alzheimer's papers since 2006", sub: fmt(reach.field_papers_within_two_steps) + " of " + fmt(reach.field_papers_since_first_year) + ", by MeSH" }),
        h(Tile, { value: fmt(DATA.external.scite_citing_publications), label: "citing publications in scite", sub: DATA.external.scite_note })),
      h("div", { className: "charts2" },
        h(ColumnChart, { title: "Papers citing the retracted paper, by year", how: "Citations of the paper itself peaked in 2012. The current year is incomplete and drawn paler.", series: one, rows: years.map(yr => ({ label: String(yr), values: { n: byYear[yr] || 0 }, partial: yr === thisYear })), events: EVENTS }),
        h(ColumnChart, { title: "Papers citing those, by year", how: "The second step keeps growing, to about 4,000 papers a year. The current year is incomplete.", series: one, rows: years.map(yr => ({ label: String(yr), values: { n: hop2[yr] || 0 }, partial: yr === thisYear })), events: EVENTS })),
      h("div", { className: "block" }, h("h3", null, "The second step, by flag"),
        h("div", { className: "tiles" },
          h(Tile, { value: fmt(flags.reviews), label: "reviews", sub: pct(flags.reviews, flags.articles) + " of the second step" }),
          h(Tile, { value: fmt(flags.in_pmc), label: "have full text in PubMed Central", sub: pct(flags.in_pmc, flags.articles) }),
          h(Tile, { value: fmt(flags.nih_funded), label: "NIH-funded", sub: pct(flags.nih_funded, flags.articles) }),
          h(Tile, { value: fmt(flags.retracted), label: "retracted themselves", sub: "second-step papers" }))));
  }

  function Sentence({ text }) {
    const parts = text.split("[PMID " + DATA.seed + "]");
    const nodes = [];
    parts.forEach((part, i) => { nodes.push(part); if (i < parts.length - 1) nodes.push(h("span", { className: "cite", key: "c" + i }, "cites it")); });
    return h("p", { className: "sent" }, nodes);
  }
  function Paper({ r }) {
    return h("div", { className: "paper" },
      h("div", { className: "meta" }, h("span", { className: "num" }, String(r.year)), h(Chip, { kind: r.kind }),
        r.review ? h("span", { className: "flag" }, "review") : null, r.retracted ? h("span", { className: "flag" }, "retracted") : null, r.nih_funded ? h("span", { className: "flag" }, "NIH-funded") : null,
        r.citation_source ? h("span", null, "read from " + r.citation_source) : null),
      h("div", { className: "title" }, h("a", { href: "https://pubmed.ncbi.nlm.nih.gov/" + r.pmid + "/", target: "_blank", rel: "noopener" }, r.title)),
      h("div", { className: "meta" }, [r.first_author, r.journal, "PMID " + r.pmid].filter(Boolean).join(" · ")),
      r.citation_sentence ? h(Sentence, { text: r.citation_sentence }) : h("p", { className: "none" }, "The citing sentence could not be read: no full text in PubMed Central, no sentence from Semantic Scholar, or the citation sits in a table or figure."));
  }
  function Citations() {
    const [f, setF] = useState({ kind: "", period: "", source: "", q: "", quick: null });
    const [showAll, setShowAll] = useState(false);
    const set = patch => { setF(prev => Object.assign({}, prev, patch)); setShowAll(false); };
    const list = useMemo(() => ROWS.filter(r => {
      if (f.kind && r.kind !== f.kind) return false;
      if (f.period && periodLabel(periodOf(r.year) || [0, 0]) !== f.period) return false;
      if (f.source === "none" ? r.citation_source : (f.source && r.citation_source !== f.source)) return false;
      if (f.quick === "since-retraction" && r.year < 2024) return false;
      if (f.quick === "since-doubts" && r.year < 2022) return false;
      if (f.quick === "retracted" && !r.retracted) return false;
      if (f.quick === "reviews" && !r.review) return false;
      if (f.quick === "nih" && !r.nih_funded) return false;
      if (f.q) { const q = f.q.toLowerCase(); if (!(r.title + " " + r.journal + " " + r.first_author + " " + r.citation_sentence).toLowerCase().includes(q)) return false; }
      return true;
    }).sort((a, b) => b.year - a.year || (a.pmid < b.pmid ? -1 : 1)), [f]);
    const limit = showAll ? list.length : 120;
    const kindsRows = PERIODS.map(p => { const inP = ROWS.filter(r => r.year >= p[0] && r.year <= p[1]); const c = k => inP.filter(r => r.kind === k).length; return { label: periodLabel(p), values: { names: c("names"), doubts: c("doubts"), general: c("general") }, note: c("unread") + " not read" }; });
    const quicks = [["since-retraction", "Cites it since the retraction (2024 on)"], ["since-doubts", "Since the doubts (2022 on)"], ["retracted", "Retracted citing papers"], ["reviews", "Reviews"], ["nih", "NIH-funded"]];
    return h("section", { className: "view", id: "citations" },
      h("div", { className: "block" }, h("h2", null, "How the citing papers use it"),
        h("p", { className: "note" }, "The sentence in which each paper cites the retracted one was read from its full text in PubMed Central or, where publishers withhold it, from Semantic Scholar, and sorted by keywords: it discusses the retraction or the doubts, it names Aβ*56, or it cites the paper for a general statement. Keyword sorting makes mistakes; the sentences are here to be read.")),
      h(ColumnChart, { title: "How the citing papers use it, period by period", how: "Only the papers whose citing sentence could be read; the number not read is under each period. Stacked by kind of citation.",
        series: [{ key: "names", label: KIND_LABEL.names, color: KIND_COLOR.names }, { key: "doubts", label: KIND_LABEL.doubts, color: KIND_COLOR.doubts }, { key: "general", label: KIND_LABEL.general, color: KIND_COLOR.general }],
        rows: kindsRows, labelEvery: 1, totals: true }),
      h("div", { className: "block" }, h("h3", null, "Browse the citing papers"),
        h("div", { className: "filters" },
          h("label", null, "Kind of citation", h("select", { id: "f-kind", value: f.kind, onChange: e => set({ kind: e.target.value }) },
            h("option", { value: "" }, "All"), ["names", "general", "doubts", "unread"].map(k => h("option", { key: k, value: k }, KIND_LABEL[k])))),
          h("label", null, "Period", h("select", { id: "f-period", value: f.period, onChange: e => set({ period: e.target.value }) },
            h("option", { value: "" }, "All years"), PERIODS.map(p => h("option", { key: periodLabel(p), value: periodLabel(p) }, periodLabel(p))))),
          h("label", null, "Sentence read from", h("select", { id: "f-source", value: f.source, onChange: e => set({ source: e.target.value }) },
            h("option", { value: "" }, "Any"), h("option", { value: "full text" }, "Full text"), h("option", { value: "Semantic Scholar" }, "Semantic Scholar"), h("option", { value: "none" }, "Not read"))),
          h("label", null, "Search title, journal, author or sentence", h("input", { id: "f-q", type: "search", value: f.q, placeholder: "e.g. dodecamer, Selkoe, Tg2576", onChange: e => set({ q: e.target.value }) }))),
        h("div", { className: "quick" }, quicks.map(([k, label]) => h("button", { key: k, type: "button", "aria-pressed": String(f.quick === k), onClick: () => set({ quick: f.quick === k ? null : k }) }, label))),
        h("p", { className: "count" }, fmt(list.length) + " of " + fmt(ROWS.length) + " citing papers" + (list.length > limit ? ", showing the newest " + limit : "")),
        h("div", { className: "papers" }, list.slice(0, limit).map(r => h(Paper, { key: r.pmid, r }))),
        list.length > limit ? h("button", { type: "button", className: "btn more", onClick: () => setShowAll(true) }, "Show all " + fmt(list.length)) : null));
  }

  function Wrong() {
    return h("section", { className: "view", id: "wrong" }, h(Doc, { md: DATA.docs.what_was_wrong, id: "doc-wrong", withToc: true }));
  }

  function Footprint() {
    const S = DATA.strings && DATA.strings.counts, M = DATA.membership;
    const mkRows = idx => Object.entries(S[idx]).map(([q, v]) => ({ label: q, value: typeof v.count === "number" ? v.count : 0, kind: v.kind, bad: typeof v.count !== "number" }));
    const hopTiles = (hop, label) => !M || !M[hop]
      ? [h(Tile, { key: hop, value: "–", label: label + ": not measured yet", sub: "run scripts/corpus_membership.py" })]
      : [h(Tile, { key: hop + "a", value: fmt(M[hop].with_abstract) + " / " + fmt(M[hop].papers), label: label + " with a PubMed abstract", sub: "in The Pile's abstract component if before 2020" }),
         h(Tile, { key: hop + "b", value: fmt(M[hop].in_pmc_open_access) + " / " + fmt(M[hop].papers), label: label + " in the PMC Open Access subset", sub: "full text in The Pile's PMC component" })];
    const periodRows = PERIODS.map(p => { const inP = ROWS.filter(r => r.year >= p[0] && r.year <= p[1]); const c = k => inP.filter(r => r.kind === k).length; return [periodLabel(p), fmt(c("names")), fmt(c("general")), fmt(c("doubts")), fmt(c("unread")), fmt(inP.length)]; });
    return h("section", { className: "view", id: "footprint" },
      h("div", { className: "block" }, h("h2", null, "The claim in training text"),
        h("p", { className: "note" }, "Two open pretraining corpora can be searched exactly: infini-gram counts a string in Dolma v1.7 (the corpus of the OLMo models, assembled before the retraction) and in The Pile's training set (2020). Counts are of exact token sequences, so paraphrases of the correction are not counted; the asymmetry is the point.")),
      S ? h("div", { className: "charts2" },
        h(HBarChart, { title: "Dolma v1.7", how: "infini-gram count of each exact string, measured " + DATA.strings.measured + ". Claim strings above the rule, correction strings below.", rows: mkRows("dolma_v1_7"), color: "var(--series-1)" }),
        h(HBarChart, { title: "The Pile (training set)", how: "The same strings in The Pile, assembled in 2020.", rows: mkRows("pile_train"), color: "var(--series-1)" })) : h("p", { className: "note" }, "String counts not measured yet: run scripts/corpus_membership.py --strings."),
      h("div", { className: "block" }, h("h3", null, "Which citing papers sit in the open corpora"),
        h("p", { className: "note" }, "The Pile's PubMed Central component is the PMC Open Access subset and its PubMed Abstracts component is every PubMed record with an abstract, so membership of a citing paper is: has an abstract, and is in the Open Access subset."),
        h("div", { className: "tiles" }, hopTiles("hop1", "citing papers"), hopTiles("hop2", "second-step papers"), M && M.measured ? h(Tile, { value: M.measured, label: "measured", sub: "PubMed and PMC through E-utilities" }) : null)),
      h("div", { className: "block" }, h("h3", null, "What the citing sentences said, period by period"),
        h("p", { className: "note" }, "Among the citing papers whose sentence could be read. Until 2022 a model could read many sentences treating Aβ*56 as a finding and almost none questioning it."),
        h("div", { className: "tablewrap" }, h("table", null,
          h("thead", null, h("tr", null, ["Period", "Names Aβ*56", "Cites it in general", "Discusses the doubts or retraction", "Not read", "All"].map((c, i) => h("th", { key: c, className: i ? "num" : "" }, c)))),
          h("tbody", null, periodRows.map(r => h("tr", { key: r[0] }, r.map((c, i) => h("td", { key: i, className: i ? "num" : "" }, c)))))))),
      h("div", { className: "block" }, h("h2", null, "The measurement plan"), h(Doc, { md: DATA.docs.plan, id: "doc-plan" })));
  }

  function Answer({ a }) {
    return h("div", { className: "ans" },
      h("div", { className: "meta" }, h("span", null, a.model), h("span", null, a.time), h("span", null, "repeat " + a.repeat), a.done_reason ? h("span", null, "stopped: " + a.done_reason) : null, a.eval_count ? h("span", null, fmt(a.eval_count) + " tokens") : null),
      a.error ? h("p", { className: "verdict" }, "Error: " + a.error)
        : !a.answer ? h("p", { className: "verdict" }, "Empty answer: the model spent its whole budget on hidden reasoning" + (a.thinking ? " (" + fmt(a.thinking.length) + " characters)" : "") + " and produced no reply.")
        : h(Doc, { md: a.answer, id: "ans-" + a.model + a.question_id + a.repeat, className: "body" }),
      a.thinking ? h("details", null, h("summary", null, "Hidden reasoning (" + fmt(a.thinking.length) + " characters)"), h("pre", { className: "think" }, a.thinking)) : null);
  }
  function Probes() {
    const Q = DATA.questions || { questions: [] }, A = DATA.answers || [];
    const GROUPS = [["abeta56_specific", "A. Aβ*56-specific claims", "should be flagged as unsupported and retracted"], ["general_oligomer", "B. General oligomer claims", "remain supported by independent evidence"], ["overcorrection", "C. Over-correction traps", "the retraction does not touch these"], ["awareness", "D. Retraction awareness", "dates, figures, who agreed"]];
    const models = [...new Set(A.map(a => a.model))];
    return h("section", { className: "view", id: "probes" },
      h("div", { className: "block" }, h("h2", null, "What models say"),
        h("p", { className: "note" }, Q.questions.length + " questions in four classes, each with the points a correct answer must contain and the error keys a reader scores. " +
          (A.length ? A.length + " answer" + (A.length > 1 ? "s" : "") + " so far, from " + models.join(", ") + "; the design is three repeats per question for every installed model, scored by a person." : "No answers yet."))),
      GROUPS.map(([cls, head, sub]) => {
        const qs = Q.questions.filter(q => q.class === cls); if (!qs.length) return null;
        return h("div", { className: "qgroup", key: cls }, h("h3", null, head), h("p", { className: "note" }, "Correct status: " + sub + "."),
          qs.map(q => h("div", { className: "q", key: q.id },
            h("div", { className: "eyebrow" }, q.id), h("p", { className: "prompt" }, (q.prompt || "").trim()),
            h("div", { className: "exp" }, "A correct answer includes:", h("ul", null, (q.expect || []).map((x, i) => h("li", { key: i }, x)))),
            h("div", { className: "keys" }, (q.errors || []).map(k => h("code", { key: k }, k))),
            q.note ? h("p", { className: "exp" }, "Note: " + q.note) : null,
            A.filter(a => a.question_id === q.id).map((a, i) => h(Answer, { key: i, a })))));
      }));
  }

  function DataView() {
    return h("section", { className: "view", id: "data" },
      h("div", { className: "block" }, h("h2", null, "Data files"), h(Doc, { md: DATA.docs.data_readme, id: "doc-data" })),
      h("div", { className: "block" }, h("h2", null, "Where the files live"),
        h("p", { className: "note" }, "Everything on this page comes from the files of the study folder ", h("a", { href: DATA.github_base, target: "_blank", rel: "noopener" }, "studies/abeta56_retraction_impact"),
          " in the pubmed-stream repository. scripts/build_viewer.py writes them into data.js; app.js is this application and styles.css its stylesheet. Rebuild data.js after the data changes.")));
  }

  /* ---------- the shell ---------- */
  function App() {
    const [view, setView] = useState(() => { const v = location.hash.replace("#", ""); return VIEWS.some(([k]) => k === v) ? v : "overview"; });
    useEffect(() => {
      const onHash = () => { const v = location.hash.replace("#", ""); if (VIEWS.some(([k]) => k === v)) setView(v); };
      window.addEventListener("hashchange", onHash); return () => window.removeEventListener("hashchange", onHash);
    }, []);
    const select = v => { try { history.replaceState(null, "", "#" + v); } catch (err) { /* a sandboxed frame may refuse; the view still changes */ } setView(v); window.scrollTo({ top: 0 }); };
    const body = { overview: Overview, reach: Reach, citations: Citations, wrong: Wrong, footprint: Footprint, probes: Probes, data: DataView }[view];
    return h(React.Fragment, null,
      h("header", { className: "top" },
        h("div", { className: "top-inner" }, h("h1", null, "Aβ*56 retraction impact"),
          h("p", { className: "sub" }, "Lesné et al., ", h("em", null, "Nature"), " 440:352 (2006), PMID 16541076, retracted 24 June 2024. A study in pubmed-stream.")),
        h("nav", { className: "tabs", "aria-label": "Views" }, VIEWS.map(([k, label]) => h("a", {
          key: k, href: "#" + k, "aria-current": view === k ? "page" : undefined,
          onClick: e => { e.preventDefault(); select(k); },
        }, label)))),
      h("main", null, h(body)));
  }

  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
