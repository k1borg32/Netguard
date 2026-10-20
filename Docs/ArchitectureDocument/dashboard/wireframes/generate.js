// Generates low-fidelity SVG wireframes for the NetGuard dashboard.
// Usage (from this folder): node generate.js .
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2];
const W = 1280, H = 800, TOP = 56, SIDE = 200, CX = 224, CW = W - CX - 24;
const C = {
  line: "#9aa0a6", panel: "#f6f7f9", head: "#eceff3", text: "#202124", muted: "#6b7280",
  accent: "#3b5bdb", ok: "#2f9e44", ghost: "#d0d4da",
  sev: { LOW: "#868e96", MEDIUM: "#e8a400", HIGH: "#e8590c", CRITICAL: "#c92a2a" },
};
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function svg() {
  const parts = [];
  const g = {
    rect(x, y, w, h, o = {}) {
      parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${o.rx ?? 6}" fill="${o.fill ?? "#fff"}" stroke="${o.stroke ?? C.line}" stroke-width="${o.sw ?? 1}"${o.dash ? ' stroke-dasharray="5 4"' : ""}/>`);
    },
    text(x, y, s, o = {}) {
      parts.push(`<text x="${x}" y="${y}" font-size="${o.size ?? 13}" font-weight="${o.weight ?? 400}" fill="${o.fill ?? C.text}" text-anchor="${o.anchor ?? "start"}">${esc(s)}</text>`);
    },
    raw(s) { parts.push(s); },
    // UI pieces
    button(x, y, label, o = {}) {
      const w = o.w ?? label.length * 7.5 + 28;
      g.rect(x, y, w, 32, { fill: o.primary ? C.accent : "#fff", stroke: o.primary ? C.accent : C.line, rx: 6 });
      g.text(x + w / 2, y + 21, label, { anchor: "middle", fill: o.primary ? "#fff" : C.text, weight: 600 });
      return w;
    },
    input(x, y, w, label, value, o = {}) {
      if (label) g.text(x, y - 6, label, { size: 11, fill: C.muted });
      g.rect(x, y, w, 32, { rx: 5 });
      g.text(x + 10, y + 21, value ?? "", { fill: value && !o.placeholder ? C.text : C.muted });
      if (o.select) g.text(x + w - 16, y + 21, "▾", { fill: C.muted });
    },
    badge(x, y, sev) {
      const w = sev.length * 7.5 + 16;
      g.rect(x, y - 13, w, 19, { fill: C.sev[sev], stroke: C.sev[sev], rx: 9 });
      g.text(x + w / 2, y + 1, sev, { size: 11, fill: "#fff", weight: 700, anchor: "middle" });
    },
    status(x, y, s) {
      const isNew = s === "NEW";
      const w = s.length * 7 + 16;
      g.rect(x, y - 13, w, 19, { fill: isNew ? "#e7f0ff" : "#ebfbee", stroke: isNew ? C.accent : C.ok, rx: 9 });
      g.text(x + w / 2, y + 1, s, { size: 11, fill: isNew ? C.accent : C.ok, weight: 700, anchor: "middle" });
    },
    panel(x, y, w, h, title) {
      g.rect(x, y, w, h, { fill: "#fff" });
      if (title) g.text(x + 16, y + 26, title, { weight: 700, size: 14 });
    },
    table(x, y, w, cols, rows, o = {}) {
      const rh = o.rowH ?? 32;
      const total = cols.reduce((a, c) => a + c.w, 0);
      const k = w / total;
      g.rect(x, y, w, rh * (rows.length + 1), { fill: "#fff", rx: 4 });
      g.rect(x, y, w, rh, { fill: C.head, rx: 4 });
      let cx = x;
      cols.forEach((c) => { g.text(cx + 10, y + rh / 2 + 5, c.label, { size: 12, weight: 700, fill: C.muted }); cx += c.w * k; });
      rows.forEach((r, i) => {
        const ry = y + rh * (i + 1);
        if (i > 0) g.raw(`<line x1="${x}" y1="${ry}" x2="${x + w}" y2="${ry}" stroke="${C.ghost}"/>`);
        let cx2 = x;
        r.forEach((cell, j) => {
          const ty = ry + rh / 2 + 5;
          if (cell && typeof cell === "object") {
            if (cell.badge) g.badge(cx2 + 10, ty - 1, cell.badge);
            if (cell.status) g.status(cx2 + 10, ty - 1, cell.status);
            if (cell.link) g.text(cx2 + 10, ty, cell.link, { size: 12, fill: C.accent, weight: 600 });
            if (cell.muted) g.text(cx2 + 10, ty, cell.muted, { size: 12, fill: C.muted });
          } else if (cell !== undefined && cell !== "") {
            g.text(cx2 + 10, ty, cell, { size: 12 });
          }
          cx2 += cols[j].w * k;
        });
      });
      return rh * (rows.length + 1);
    },
    lineChart(x, y, w, h, series, o = {}) {
      g.raw(`<line x1="${x + 36}" y1="${y}" x2="${x + 36}" y2="${y + h}" stroke="${C.line}"/>`);
      g.raw(`<line x1="${x + 36}" y1="${y + h}" x2="${x + w}" y2="${y + h}" stroke="${C.line}"/>`);
      for (let i = 1; i <= 3; i++) g.raw(`<line x1="${x + 36}" y1="${y + h - (h * i) / 4}" x2="${x + w}" y2="${y + h - (h * i) / 4}" stroke="${C.ghost}" stroke-dasharray="3 4"/>`);
      (o.xLabels ?? []).forEach((l, i, a) => g.text(x + 36 + ((w - 40) * i) / (a.length - 1), y + h + 16, l, { size: 10, fill: C.muted, anchor: "middle" }));
      series.forEach((s) => {
        const pts = s.data.map((v, i) => `${(x + 36 + ((w - 40) * i) / (s.data.length - 1)).toFixed(1)},${(y + h - v * h).toFixed(1)}`).join(" ");
        g.raw(`<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2"${s.dash ? ' stroke-dasharray="6 4"' : ""}/>`);
      });
    },
    stackedBars(x, y, w, h, data, colors, o = {}) {
      g.raw(`<line x1="${x}" y1="${y + h}" x2="${x + w}" y2="${y + h}" stroke="${C.line}"/>`);
      const bw = w / data.length;
      data.forEach((stack, i) => {
        let top = y + h;
        stack.forEach((v, j) => {
          const bh = v * h;
          top -= bh;
          if (bh > 0) g.raw(`<rect x="${(x + i * bw + 3).toFixed(1)}" y="${top.toFixed(1)}" width="${(bw - 6).toFixed(1)}" height="${bh.toFixed(1)}" fill="${colors[j]}"/>`);
        });
      });
      (o.xLabels ?? []).forEach((l, i, a) => g.text(x + (w * i) / (a.length - 1), y + h + 16, l, { size: 10, fill: C.muted, anchor: "middle" }));
    },
    legend(x, y, items) {
      let cx = x;
      items.forEach(([label, color]) => {
        g.raw(`<rect x="${cx}" y="${y - 9}" width="10" height="10" rx="2" fill="${color}"/>`);
        g.text(cx + 14, y, label, { size: 11, fill: C.muted });
        cx += label.length * 6.5 + 32;
      });
    },
    note(x, y, s) { g.text(x, y, s, { size: 11, fill: C.muted }); },
    done(file) {
      const body = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">\n<rect x="0" y="0" width="${W}" height="${H}" fill="#ffffff"/>\n${parts.join("\n")}\n</svg>\n`;
      fs.writeFileSync(path.join(OUT, file), body);
      console.log("wrote", file);
    },
  };
  return g;
}

const NAV = ["Overview", "Alerts", "History", "Flows", "Settings"];

function shell(active, title, subtitle) {
  const g = svg();
  g.rect(0.5, 0.5, W - 1, H - 1, { fill: C.panel, rx: 10 });
  // top bar
  g.raw(`<rect x="1" y="1" width="${W - 2}" height="${TOP}" fill="#fff"/><line x1="0" y1="${TOP}" x2="${W}" y2="${TOP}" stroke="${C.line}"/>`);
  g.rect(20, 16, 24, 24, { fill: C.accent, stroke: C.accent, rx: 5 });
  g.text(54, 34, "NetGuard", { size: 18, weight: 700 });
  // simulator + health pills, user menu
  g.rect(720, 13, 250, 30, { rx: 15, fill: "#fff" });
  g.raw(`<circle cx="738" cy="28" r="5" fill="${C.ok}"/>`);
  g.text(750, 33, "Simulator running · 200 flows/s", { size: 12 });
  g.rect(980, 13, 110, 30, { rx: 15, fill: "#fff" });
  g.raw(`<circle cx="998" cy="28" r="5" fill="${C.ok}"/>`);
  g.text(1010, 33, "API · DB ok", { size: 12 });
  g.text(1170, 33, "admin ▾", { size: 13, weight: 600, anchor: "end" });
  g.text(1254, 33, "Log out", { size: 13, fill: C.accent, anchor: "end" });
  // sidebar
  g.raw(`<rect x="1" y="${TOP + 1}" width="${SIDE}" height="${H - TOP - 2}" fill="#fff"/><line x1="${SIDE}" y1="${TOP}" x2="${SIDE}" y2="${H}" stroke="${C.line}"/>`);
  NAV.forEach((n, i) => {
    const y = TOP + 24 + i * 44;
    if (n === active) g.rect(12, y, SIDE - 24, 36, { fill: "#e7ecff", stroke: "#e7ecff", rx: 6 });
    g.rect(26, y + 11, 14, 14, { fill: n === active ? C.accent : C.ghost, stroke: "none", rx: 3 });
    g.text(52, y + 23, n, { size: 14, weight: n === active ? 700 : 400, fill: n === active ? C.accent : C.text });
  });
  g.note(20, H - 20, "Wireframe v1 - not final design");
  // page title
  g.text(CX, TOP + 40, title, { size: 22, weight: 700 });
  if (subtitle) g.note(CX, TOP + 60, subtitle);
  return g;
}

// deterministic pseudo-random series
function series(n, base, noise, seed, spikeAt, spike) {
  let s = seed;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  return Array.from({ length: n }, (_, i) => {
    let v = base + (rnd() - 0.5) * noise;
    if (spikeAt !== undefined && Math.abs(i - spikeAt) <= 1) v += spike * (i === spikeAt ? 1 : 0.5);
    return Math.max(0.02, Math.min(0.98, v));
  });
}

const ALERT_ROWS = [
  ["12:41:07", { badge: "HIGH" }, "Port Scan", "10.66.6.6", "10.1.0.1", "0.94", { status: "NEW" }, { link: "Acknowledge" }],
  ["12:40:52", { badge: "CRITICAL" }, "DoS/DDoS-like", "10.0.0.17", "10.1.0.4", "0.98", { status: "NEW" }, { link: "Acknowledge" }],
  ["12:39:30", { badge: "MEDIUM" }, "Brute Force", "10.0.1.33", "10.1.0.2:22", "0.81", { status: "NEW" }, { link: "Acknowledge" }],
  ["12:37:12", { badge: "LOW" }, "Abnormal Traffic", "10.0.0.88", "-", "0.62", { status: "ACKNOWLEDGED" }, { muted: "by admin" }],
  ["12:35:45", { badge: "HIGH" }, "Suspicious Pattern", "10.0.0.5", "10.1.0.9", "0.77", { status: "ACKNOWLEDGED" }, { muted: "by jakub" }],
  ["12:31:02", { badge: "MEDIUM" }, "Unknown Anomaly", "10.0.0.41", "10.1.0.3", "0.55", { status: "NEW" }, { link: "Acknowledge" }],
  ["12:28:19", { badge: "HIGH" }, "Port Scan", "10.66.6.6", "10.1.0.7", "0.92", { status: "ACKNOWLEDGED" }, { muted: "by admin" }],
  ["12:22:48", { badge: "LOW" }, "Abnormal Traffic", "10.0.1.2", "-", "0.58", { status: "NEW" }, { link: "Acknowledge" }],
];

// ---------- 1. Login ----------
{
  const g = svg();
  g.rect(0.5, 0.5, W - 1, H - 1, { fill: C.panel, rx: 10 });
  const x = 440, y = 190, w = 400;
  g.rect(x, y, w, 400, { fill: "#fff", rx: 10 });
  g.rect(x + w / 2 - 20, y + 32, 40, 40, { fill: C.accent, stroke: C.accent, rx: 8 });
  g.text(x + w / 2, y + 104, "NetGuard", { size: 24, weight: 700, anchor: "middle" });
  g.text(x + w / 2, y + 126, "Network anomaly detection - lab only", { size: 12, fill: C.muted, anchor: "middle" });
  g.input(x + 40, y + 170, w - 80, "Username", "admin");
  g.input(x + 40, y + 236, w - 80, "Password", "••••••••••••");
  g.text(x + 40, y + 292, "Wrong username or password", { size: 12, fill: C.sev.CRITICAL });
  g.button(x + 40, y + 312, "Sign in", { primary: true, w: w - 80 });
  g.text(x + w / 2, y + 376, "Accounts are created by an administrator", { size: 11, fill: C.muted, anchor: "middle" });
  g.done("01-login.svg");
}

// ---------- 2. Overview ----------
{
  const g = shell("Overview", "Overview", "Live view - refreshes every 5 s");
  g.input(1046, 74, 210, "", "Last 15 minutes", { select: true });
  g.note(924, 95, "Updated 3 s ago");
  const cards = [["Flows", "182,430", "+4% vs prev. 15 min"], ["Flows / s (now)", "203", "processor x2"], ["Detections", "37", "12 HIGH or CRITICAL"], ["Open alerts", "9", "NEW, not acknowledged"]];
  const cw = (CW - 3 * 16) / 4;
  cards.forEach(([t, v, s], i) => {
    const x = CX + i * (cw + 16);
    g.panel(x, 136, cw, 96);
    g.note(x + 16, 160, t);
    g.text(x + 16, 196, v, { size: 28, weight: 700 });
    g.note(x + 16, 218, s);
  });
  // traffic chart
  const lw = 640;
  g.panel(CX, 248, lw, 250, "Traffic - flows per second");
  g.legend(CX + 360, 274, [["flows/s", C.accent], ["bytes/s", "#adb5bd"]]);
  g.lineChart(CX + 16, 296, lw - 32, 170, [
    { data: series(40, 0.45, 0.12, 7, 28, 0.35), color: C.accent },
    { data: series(40, 0.3, 0.08, 3, 28, 0.2), color: "#adb5bd", dash: true },
  ], { xLabels: ["12:27", "12:30", "12:33", "12:36", "12:39", "12:42"] });
  // by type
  const rx = CX + lw + 16, rw = CW - lw - 16;
  g.panel(rx, 248, rw, 250, "Detections by type");
  [["Port Scan", 0.9], ["DoS/DDoS-like", 0.55], ["Brute Force", 0.4], ["Abnormal Traffic", 0.3], ["Suspicious Pattern", 0.2], ["Unknown Anomaly", 0.1]].forEach(([l, v], i) => {
    const y = 286 + i * 34;
    g.note(rx + 16, y + 14, l);
    g.raw(`<rect x="${rx + 140}" y="${y}" width="${((rw - 190) * v).toFixed(0)}" height="18" rx="3" fill="${C.accent}" opacity="${1 - i * 0.12}"/>`);
    g.text(rx + 148 + (rw - 190) * v, y + 14, String(Math.round(v * 14)), { size: 11, fill: C.muted });
  });
  // detections over time
  g.panel(CX, 514, lw, 266, "Detections over time, by severity");
  g.legend(CX + 300, 540, [["LOW", C.sev.LOW], ["MEDIUM", C.sev.MEDIUM], ["HIGH", C.sev.HIGH], ["CRITICAL", C.sev.CRITICAL]]);
  const stacks = series(15, 0.12, 0.1, 11).map((v, i) => [v * 0.6, v * 0.5, i === 10 || i === 11 ? 0.3 : v * 0.3, i === 11 ? 0.15 : 0]);
  g.stackedBars(CX + 24, 562, lw - 48, 180, stacks, [C.sev.LOW, C.sev.MEDIUM, C.sev.HIGH, C.sev.CRITICAL], { xLabels: ["12:27", "12:34", "12:42"] });
  // latest alerts
  g.panel(rx, 514, rw, 266, "Latest alerts");
  g.text(rx + rw - 16, 540, "View all →", { size: 12, fill: C.accent, anchor: "end" });
  g.table(rx + 12, 554, rw - 24, [{ label: "Time", w: 70 }, { label: "Severity", w: 90 }, { label: "Type", w: 120 }, { label: "Source", w: 90 }],
    ALERT_ROWS.slice(0, 5).map((r) => [r[0], r[1], r[2], r[3]]), { rowH: 34 });
  g.done("02-overview.svg");
}

// ---------- 3. Alerts ----------
{
  const g = shell("Alerts", "Alerts", "Generated from detections. Click a row for details.");
  // filter bar
  g.rect(CX, 128, CW, 76, { fill: "#fff" });
  let x = CX + 16;
  [["Time", "Last 1 hour", 140, true], ["Status", "NEW", 110, true], ["Severity", "Any", 110, true], ["Type", "Any", 130, true], ["Source IP", "e.g. 10.0.0.5", 120, false], ["Destination IP", "", 120, false], ["Protocol", "Any", 90, true]].forEach(([l, v, w, sel]) => {
    g.input(x, 156, w, l, v, { select: sel, placeholder: v.startsWith("e.g.") });
    x += w + 12;
  });
  g.button(CX + CW - 80, 156, "Reset", { w: 64 });
  const cols = [{ label: "Time", w: 90 }, { label: "Severity", w: 100 }, { label: "Type", w: 150 }, { label: "Source", w: 110 }, { label: "Destination", w: 120 }, { label: "Confidence", w: 90 }, { label: "Status", w: 130 }, { label: "", w: 100 }];
  const th = g.table(CX, 220, CW, cols, ALERT_ROWS, { rowH: 46 });
  g.note(CX, 220 + th + 30, "Showing 1-8 of 312 · sorted by time, newest first");
  ["‹", "1", "2", "3", "…", "39", "›"].forEach((p, i) => {
    const bx = CX + CW - 7 * 40 + i * 40;
    g.rect(bx, 220 + th + 12, 34, 30, { fill: p === "1" ? C.accent : "#fff", stroke: p === "1" ? C.accent : C.line });
    g.text(bx + 17, 220 + th + 32, p, { anchor: "middle", fill: p === "1" ? "#fff" : C.text });
  });
  g.done("03-alerts.svg");
}

// ---------- 4. Alert details ----------
{
  const g = shell("Alerts", "", "");
  g.text(CX, TOP + 28, "Alerts  /  7c1e9a42-…-d03f", { size: 12, fill: C.accent });
  g.badge(CX, TOP + 62, "HIGH");
  g.text(CX + 62, TOP + 68, "Port Scan from 10.66.6.6", { size: 22, weight: 700 });
  g.status(CX + 352, TOP + 62, "NEW");
  g.button(CX + CW - 130, TOP + 44, "Acknowledge", { primary: true, w: 130 });
  // summary
  const lw = 420;
  g.panel(CX, 148, lw, 300, "Summary");
  [["Detected at", "2026-10-20 12:41:07"], ["Method", "rule (port_scan, v1)"], ["Confidence", "0.94"], ["Source", "10.66.6.6"], ["Destination", "10.1.0.1"], ["Protocol", "TCP"], ["Window", "10 s (12:40:57 - 12:41:07)"], ["Detection latency", "0.8 s"]].forEach(([k, v], i) => {
    g.note(CX + 16, 200 + i * 30, k);
    g.text(CX + 160, 200 + i * 30, v, { size: 13 });
  });
  // explanation + features
  const rx = CX + lw + 16, rw = CW - lw - 16;
  g.panel(rx, 148, rw, 110, "Explanation");
  g.text(rx + 16, 196, "10.66.6.6 contacted 212 distinct ports on 10.1.0.1 within 10 s", { size: 13 });
  g.text(rx + 16, 218, "(threshold: 3). 98% of the flows were single SYN packets.", { size: 13 });
  g.panel(rx, 270, rw, 178, "Feature values (evidence)");
  g.table(rx + 12, 306, rw - 24, [{ label: "Feature", w: 200 }, { label: "Value", w: 100 }, { label: "Threshold", w: 100 }, { label: "", w: 160 }],
    [["unique_dst_ports", "212", "3", { muted: "70x over" }], ["flows_in_window", "230", "-", ""], ["syn_only_ratio", "0.98", "-", ""]], { rowH: 34 });
  // evidence flows
  g.panel(CX, 464, CW, 316, "Contributing flows");
  g.text(CX + CW - 16, 490, "Open in Flows →", { size: 12, fill: C.accent, anchor: "end" });
  g.table(CX + 12, 504, CW - 24, [{ label: "Start", w: 110 }, { label: "Source", w: 140 }, { label: "Destination", w: 140 }, { label: "Proto", w: 60 }, { label: "Packets", w: 70 }, { label: "Bytes", w: 70 }, { label: "Flags", w: 60 }, { label: "Trace ID", w: 200 }],
    [["12:41:06.912", "10.66.6.6:51022", "10.1.0.1:22", "TCP", "1", "60", "S", { muted: "tr-8f2c…a91" }],
     ["12:41:06.907", "10.66.6.6:51022", "10.1.0.1:23", "TCP", "1", "60", "S", { muted: "tr-8f2c…a92" }],
     ["12:41:06.901", "10.66.6.6:51022", "10.1.0.1:25", "TCP", "1", "60", "S", { muted: "tr-8f2c…a93" }],
     ["12:41:06.893", "10.66.6.6:51022", "10.1.0.1:80", "TCP", "1", "60", "S", { muted: "tr-8f2c…a94" }],
     ["12:41:06.880", "10.66.6.6:51022", "10.1.0.1:110", "TCP", "1", "60", "S", { muted: "tr-8f2c…a95" }]], { rowH: 34 });
  g.note(CX + 12, 760, "Showing 5 of 230 flows · trace IDs can be followed with: make trace ID=<id>");
  g.done("04-alert-details.svg");
}

// ---------- 5. History ----------
{
  const g = shell("History", "Detection history", "All stored detections, also those without an alert (F13: time, type, severity, source)");
  g.rect(CX, 128, CW, 76, { fill: "#fff" });
  let x = CX + 16;
  [["From", "2026-10-19 00:00", 150, false], ["To", "2026-10-20 23:59", 150, false], ["Type", "Port Scan", 130, true], ["Severity", "HIGH, CRITICAL", 150, true], ["Source IP", "10.66.6.6", 140, false], ["Method", "Any", 110, true]].forEach(([l, v, w, sel]) => {
    g.input(x, 156, w, l, v, { select: sel });
    x += w + 12;
  });
  g.button(CX + CW - 96, 156, "Export CSV", { w: 84 });
  g.panel(CX, 220, CW, 150, "Detections per hour (selected range)");
  g.stackedBars(CX + 24, 252, CW - 48, 92, series(48, 0.25, 0.3, 5, 36, 0.5).map((v) => [v]), [C.accent]);
  const cols = [{ label: "Time", w: 150 }, { label: "Type", w: 150 }, { label: "Severity", w: 100 }, { label: "Method", w: 90 }, { label: "Source", w: 110 }, { label: "Destination", w: 110 }, { label: "Confidence", w: 90 }, { label: "Alert", w: 130 }];
  const rows = [
    ["2026-10-20 12:41", "Port Scan", { badge: "HIGH" }, "rule", "10.66.6.6", "10.1.0.1", "0.94", { status: "NEW" }],
    ["2026-10-20 12:28", "Port Scan", { badge: "HIGH" }, "rule", "10.66.6.6", "10.1.0.7", "0.92", { status: "ACKNOWLEDGED" }],
    ["2026-10-20 09:12", "Port Scan", { badge: "CRITICAL" }, "rule", "10.66.6.6", "10.1.0.2", "0.99", { status: "ACKNOWLEDGED" }],
    ["2026-10-19 22:03", "Port Scan", { badge: "HIGH" }, "rule", "10.66.6.6", "10.1.0.1", "0.90", { status: "ACKNOWLEDGED" }],
    ["2026-10-19 17:45", "Port Scan", { badge: "HIGH" }, "statistical", "10.66.6.6", "10.1.0.5", "0.71", { muted: "no alert" }],
    ["2026-10-19 14:20", "Port Scan", { badge: "HIGH" }, "rule", "10.66.6.6", "10.1.0.1", "0.93", { status: "ACKNOWLEDGED" }],
  ];
  const th = g.table(CX, 386, CW, cols, rows, { rowH: 46 });
  g.note(CX, 386 + th + 26, "Showing 1-6 of 64 · page 1 of 11");
  g.done("05-history.svg");
}

// ---------- 6. Flows ----------
{
  const g = shell("Flows", "Network flows", "Normalised flows as stored by the persister (flow.v1)");
  g.rect(CX, 128, CW, 76, { fill: "#fff" });
  let x = CX + 16;
  [["Time", "Last 5 minutes", 150, true], ["Source IP", "", 140, false], ["Destination IP", "10.1.0.1", 140, false], ["Protocol", "TCP", 100, true], ["Dst port", "", 90, false], ["Input", "Any", 120, true]].forEach(([l, v, w, sel]) => {
    g.input(x, 156, w, l, v, { select: sel });
    x += w + 12;
  });
  g.button(CX + CW - 80, 156, "Reset", { w: 64 });
  const cols = [{ label: "Start", w: 120 }, { label: "Duration", w: 80 }, { label: "Source", w: 110 }, { label: "Src port", w: 70 }, { label: "Destination", w: 110 }, { label: "Dst port", w: 70 }, { label: "Proto", w: 60 }, { label: "Packets", w: 70 }, { label: "Bytes", w: 80 }, { label: "Flags", w: 55 }, { label: "Input", w: 90 }];
  const rows = [
    ["12:41:06.912", "0.2 ms", "10.66.6.6", "51022", "10.1.0.1", "22", "TCP", "1", "60", "S", "simulator"],
    ["12:41:06.840", "182 ms", "10.0.0.17", "40112", "10.1.0.1", "443", "TCP", "38", "41,220", "SA", "simulator"],
    ["12:41:06.711", "12 ms", "10.0.1.90", "53001", "10.1.0.1", "53", "UDP", "2", "180", "-", "pcap"],
    ["12:41:06.520", "301 ms", "10.0.0.3", "44821", "10.1.0.1", "80", "TCP", "21", "18,004", "SA", "simulator"],
    ["12:41:06.402", "0.3 ms", "10.66.6.6", "51022", "10.1.0.1", "23", "TCP", "1", "60", "S", "simulator"],
    ["12:41:06.377", "95 ms", "10.0.0.250", "39001", "10.1.0.1", "5432", "TCP", "12", "4,310", "SA", "flowfile"],
    ["12:41:06.201", "44 ms", "10.0.1.11", "60202", "10.1.0.1", "3306", "TCP", "9", "2,870", "SA", "simulator"],
    ["12:41:06.188", "-", "10.0.0.66", "-", "10.1.0.1", "-", "ICMP", "1", "84", "-", "pcap"],
    ["12:41:06.090", "210 ms", "10.0.0.12", "41888", "10.1.0.1", "443", "TCP", "44", "52,113", "SA", "simulator"],
    ["12:41:05.973", "0.2 ms", "10.66.6.6", "51022", "10.1.0.1", "25", "TCP", "1", "60", "S", "simulator"],
  ];
  const th = g.table(CX, 220, CW, cols, rows, { rowH: 40 });
  g.note(CX, 220 + th + 26, "Page 1 · 50 per page · newest first · large result: narrow the time range");
  g.done("06-flows.svg");
}

// ---------- 7. Settings ----------
{
  const g = shell("Settings", "Settings", "Detection thresholds and traffic simulator. Changes are admin only (F16, NFR06).");
  const lw = 600;
  g.panel(CX, 128, lw, 652, "Detection configurations");
  g.table(CX + 16, 168, lw - 32, [{ label: "Type", w: 150 }, { label: "Method", w: 100 }, { label: "Active", w: 80 }, { label: "", w: 80 }],
    [["Port Scan", "rule", "active", { link: "Edit" }], ["DoS/DDoS-like", "rule", { muted: "inactive" }, { link: "Edit" }], ["Brute Force", "rule", "active", { link: "Edit" }], ["Abnormal Traffic", "z-score", "active", { link: "Edit" }]], { rowH: 38 });
  g.rect(CX + 16, 372, lw - 32, 394, { fill: C.panel, dash: true });
  g.text(CX + 32, 400, "Edit: Port Scan (rule)", { weight: 700 });
  g.input(CX + 32, 432, 250, "Window (s)", "10", { select: true });
  g.note(CX + 300, 453, "one of 1 / 10 / 60 (F05)");
  g.input(CX + 32, 496, 250, "Unique destination ports threshold", "3");
  g.input(CX + 32, 560, 250, "Minimum flows in window", "20");
  g.input(CX + 32, 624, 250, "Severity when exceeded", "HIGH", { select: true });
  g.note(CX + 32, 684, "Fields come from the configuration's parameters (JSONB).");
  g.note(CX + 32, 700, "Users without admin role see this form read-only.");
  g.button(CX + 32, 718, "Save as new version", { primary: true, w: 170 });
  g.button(CX + 214, 718, "Activate", { w: 90 });
  g.button(CX + 316, 718, "Cancel", { w: 80 });
  const rx = CX + lw + 16, rw = CW - lw - 16;
  g.panel(rx, 128, rw, 652, "Traffic simulator");
  g.raw(`<circle cx="${rx + 24}" cy="${180}" r="6" fill="${C.ok}"/>`);
  g.text(rx + 38, 185, "Running for 04:12 · 51,230 flows sent", { size: 13 });
  g.text(rx + 16, 226, "Scenarios", { size: 11, fill: C.muted });
  ["normal", "port_scan", "dos", "brute_force", "abnormal_traffic", "suspicious_pattern"].forEach((s, i) => {
    const cx = rx + 16 + (i % 2) * 190, cy = 240 + Math.floor(i / 2) * 30;
    g.rect(cx, cy, 16, 16, { rx: 3, fill: i < 2 ? C.accent : "#fff", stroke: i < 2 ? C.accent : C.line });
    if (i < 2) g.text(cx + 8, cy + 13, "✓", { size: 12, fill: "#fff", anchor: "middle" });
    g.text(cx + 26, cy + 13, s, { size: 13 });
  });
  g.input(rx + 16, 360, 180, "Rate (flows/s)", "200");
  g.input(rx + 212, 360, 180, "Hosts", "200");
  g.input(rx + 16, 424, 180, "Anomalous share (%)", "5");
  g.input(rx + 212, 424, 180, "Duration (s, 0 = until stopped)", "0");
  g.input(rx + 16, 488, 376, "Load profile", "constant", { select: true });
  g.button(rx + 16, 548, "Start", { primary: true, w: 100 });
  g.button(rx + 128, 548, "Stop", { w: 100 });
  g.note(rx + 16, 610, "F14: hosts, rate, anomalous share and load profile");
  g.note(rx + 16, 626, "are configurable. Start/stop needs a simulator control");
  g.note(rx + 16, 642, "endpoint (not in the API plan yet).");
  g.done("07-settings.svg");
}
