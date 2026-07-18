const els = {
  moduleNav: document.querySelector("#moduleNav"),
  scopeLine: document.querySelector("#scopeLine"),
  summaryGrid: document.querySelector("#summaryGrid"),
  activeModuleEyebrow: document.querySelector("#activeModuleEyebrow"),
  activeModuleTitle: document.querySelector("#activeModuleTitle"),
  moduleContent: document.querySelector("#moduleContent"),
  detectorState: document.querySelector("#detectorState"),
  refreshBtn: document.querySelector("#refreshBtn"),
  shell: document.querySelector(".v2-shell"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  toast: document.querySelector("#toast"),
};

const API_BASE = (() => {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    localStorage.setItem("ai_vision_v2_api_base", param.replace(/\/+$/, ""));
  }
  const saved = localStorage.getItem("ai_vision_v2_api_base");
  if (saved) return saved;
  if (window.location.hostname.endsWith("vercel.app")) {
    return "https://67-205-160-8.sslip.io";
  }
  return window.location.origin;
})();

const state = {
  role: "super_admin",
  activeModule: null,
  session: null,
  overview: null,
};

const HEAD_MODULE_IDS = new Set(["overview", "users"]);

const MODULE_OVERRIDES = {
  users: { label: "Company Control", subtitle: "Companies, roles & access" },
};

function moduleLabel(module) {
  return MODULE_OVERRIDES[module.id]?.label || module.label;
}

const permissionLabels = {
  view_dashboard: "View dashboard",
  view_organizations: "View organizations",
  manage_organizations: "Manage organizations",
  view_users: "View users",
  manage_users: "Manage users",
  view_permissions: "View permissions",
  manage_permissions: "Manage permissions",
  view_controllers: "View controllers / NVR",
  configure_cameras: "Configure cameras",
  view_cameras: "View cameras",
  view_live_monitoring: "View live monitoring",
  view_products: "View products",
  manage_products: "Manage products",
  configure_ai: "Configure AI",
  view_counts: "View counts",
  correct_counts: "Correct counts",
  view_alerts: "View alerts",
  manage_alerts: "Manage alerts",
  view_analytics: "View analytics",
  view_reports: "View reports",
  export_reports: "Export reports",
  view_system_health: "View system health",
  configure_system: "Configure system",
  view_audit_logs: "View audit logs",
  manage_integrations: "Manage integrations",
  view_settings: "View settings",
};

async function api(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "X-AI-Role": state.role,
      "X-AI-User-Name": "Dashboard V2 Preview",
      "X-AI-Company": "All Companies",
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.setTimeout(() => els.toast.classList.remove("show"), 2600);
}

function renderNavigation() {
  const modules = (state.session?.surfaces?.head || []).filter((module) =>
    HEAD_MODULE_IDS.has(module.id)
  );
  if (!modules.length) {
    state.activeModule = null;
    els.moduleNav.innerHTML = `<p class="empty">No modules are available for this role.</p>`;
    return;
  }
  if (!state.activeModule || !modules.some((module) => module.id === state.activeModule)) {
    state.activeModule = modules[0].id;
  }
  els.moduleNav.innerHTML = modules
    .map(
      (module) => `
        <button class="${module.id === state.activeModule ? "active" : ""}" data-module="${module.id}" type="button">
          <span>${escapeHtml(moduleLabel(module))}</span>
          <small>${escapeHtml(MODULE_OVERRIDES[module.id]?.subtitle || permissionLabels[module.permission] || module.permission)}</small>
        </button>
      `
    )
    .join("");
}

function renderSummary() {
  const summary = state.overview?.summary || {};
  const cards = [
    ["Active cameras", summary.active_cameras ?? 0],
    ["Frames read", summary.frames_read ?? 0],
    ["Last detections", summary.last_detection_count ?? 0],
    ["Stock items", summary.stock_items ?? 0],
    ["Saved cameras", summary.saved_cameras ?? 0],
    ["Audit verified", summary.audit_verified ? "Yes" : "No"],
  ];
  els.summaryGrid.innerHTML = cards
    .map(([label, value]) => `<article class="stat-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join("");
  const running = Boolean(summary.detector_running);
  els.detectorState.textContent = running ? "Detector running" : "Detector stopped";
  els.detectorState.dataset.state = running ? "good" : "bad";
}

function renderScope() {
  const session = state.session;
  if (!session) return;
  const scope = session.scope || {};
  els.scopeLine.textContent = `${session.role_label} • ${scope.company} / ${scope.factory} / ${scope.warehouse}`;
}

function renderModuleContent() {
  const modules = state.session?.surfaces?.head || [];
  const module = modules.find((item) => item.id === state.activeModule);
  els.activeModuleTitle.textContent = module ? moduleLabel(module) : "Unavailable";
  els.activeModuleEyebrow.textContent = "Head module";
  els.summaryGrid.hidden = module?.id === "users";

  const summary = state.overview?.summary || {};
  const movements = state.overview?.recent_movements || [];
  const health = state.overview?.health || {};

  if (!module) {
    els.moduleContent.innerHTML = `<p class="empty">This role has no access to modules on this surface.</p>`;
    return;
  }

  if (module.id === "live") {
    els.moduleContent.innerHTML = `
      <div class="live-preview">
        ${Array.from({ length: Math.min(Number(summary.active_cameras || health.camera_count || 10), 10) }, (_, index) => {
          const slot = index + 1;
          return `<figure><img src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
        }).join("")}
      </div>
    `;
    return;
  }

  if (module.id === "counting" || module.id === "home" || module.id === "overview") {
    renderAnalytics(els.moduleContent);
    return;
  }

  if (module.id === "users") {
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (module.id === "activity" || module.id === "reports") {
    els.moduleContent.innerHTML = movements.length
      ? `<table><tbody>${movements
          .map((item) => `<tr><td>${escapeHtml(item.product_name)}</td><td>${escapeHtml(item.direction)}</td><td>${escapeHtml(item.quantity)}</td></tr>`)
          .join("")}</tbody></table>`
      : `<p class="empty">No recent activity is available yet.</p>`;
    return;
  }

  els.moduleContent.innerHTML = `
    <div class="module-placeholder">
      <h3>${escapeHtml(module.label)} is ready for implementation</h3>
      <p>This module is registered in the V2 architecture and protected by <code>${escapeHtml(module.permission)}</code>. It can evolve independently without restructuring the dashboard.</p>
    </div>
  `;
}

// ---- Company Control --------------------------------------------------------
// Companies/roles live in localStorage for now; swap the store helpers for
// backend endpoints later.

const COMPANY_STORE_KEY = "ai_vision_v2_companies";
const ACCESS_OPTIONS = [
  { key: "camera", label: "Camera Control" },
  { key: "analytics", label: "Analytics" },
];

function loadCompanies() {
  try {
    const parsed = JSON.parse(localStorage.getItem(COMPANY_STORE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveCompanies(companies) {
  localStorage.setItem(COMPANY_STORE_KEY, JSON.stringify(companies));
}

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

const revealedPasswords = new Set();
let ccDraft = null;
let ccDirty = false;

function ccCompanies() {
  if (!ccDraft) ccDraft = loadCompanies();
  return ccDraft;
}

function renderCompanyControl(container) {
  const companies = ccCompanies();

  const companyCards = companies
    .map((company) => {
      const roles = (company.roles || [])
        .map((role) => {
          const revealed = revealedPasswords.has(role.id);
          const credentials = role.login
            ? `
              <div class="cc-credentials">
                <span class="cc-cred"><em>Login:</em> ${escapeHtml(role.login)}</span>
                <span class="cc-cred"><em>Password:</em> ${revealed ? escapeHtml(role.password || "") : "••••••••"}</span>
                <button type="button" class="cc-chip cc-chip-small" data-cc-action="toggle-password"
                        data-company="${company.id}" data-role="${role.id}">
                  ${revealed ? "Hide" : "Show"}
                </button>
              </div>
            `
            : "";
          return `
            <div class="cc-role">
              <div class="cc-role-head">
                <strong>${escapeHtml(role.name)}</strong>
                <button type="button" class="cc-remove" data-cc-action="remove-role"
                        data-company="${company.id}" data-role="${role.id}" aria-label="Remove role">✕</button>
              </div>
              ${credentials}
              <div class="cc-access">
                <span>Give access:</span>
                ${ACCESS_OPTIONS.map(
                  (option) => `
                    <button type="button" class="cc-chip ${role.access?.[option.key] ? "on" : ""}"
                            data-cc-action="toggle-access" data-company="${company.id}"
                            data-role="${role.id}" data-access="${option.key}"
                            aria-pressed="${Boolean(role.access?.[option.key])}">
                      ${option.label}
                    </button>
                  `
                ).join("")}
              </div>
            </div>
          `;
        })
        .join("");

      return `
        <article class="cc-company">
          <header class="cc-company-head">
            <h3>${escapeHtml(company.name)}</h3>
            <button type="button" class="cc-remove" data-cc-action="remove-company"
                    data-company="${company.id}" aria-label="Remove company">✕</button>
          </header>
          ${roles || `<p class="empty">No roles yet.</p>`}
          <form class="cc-add cc-add-role" data-cc-form="role" data-company="${company.id}">
            <input name="name" placeholder="Role name" required maxlength="60" autocomplete="off" />
            <input name="login" placeholder="Username (login)" required maxlength="60" autocomplete="off" />
            <input name="password" type="password" placeholder="Password" required maxlength="120" autocomplete="new-password" />
            <button type="submit">Add role</button>
          </form>
        </article>
      `;
    })
    .join("");

  container.innerHTML = `
    <p class="chart-note">Stored in this browser for now — backend hookup pending.</p>
    <form class="cc-add cc-add-company" data-cc-form="company">
      <input name="name" placeholder="Company name" required maxlength="60" autocomplete="off" />
      <button type="submit">Add company</button>
    </form>
    <div class="cc-list">
      ${companyCards || `<p class="empty">No companies yet — add the first one above.</p>`}
    </div>
    <div class="cc-save-row">
      ${ccDirty ? `<span class="cc-unsaved">Unsaved changes</span>` : ""}
      <button type="button" class="cc-save" data-cc-action="save" ${ccDirty ? "" : "disabled"}>Save changes</button>
    </div>
  `;
}

function handleCompanySubmit(event) {
  const form = event.target.closest("[data-cc-form]");
  if (!form) return;
  event.preventDefault();
  const name = form.elements.name.value.trim();
  if (!name) return;
  const companies = ccCompanies();

  if (form.dataset.ccForm === "company") {
    companies.push({ id: newId(), name, roles: [] });
    toast(`Company "${name}" added.`);
  } else {
    const company = companies.find((item) => item.id === form.dataset.company);
    if (!company) return;
    const login = form.elements.login.value.trim();
    const password = form.elements.password.value;
    if (!login || !password) return;
    company.roles = company.roles || [];
    company.roles.push({
      id: newId(),
      name,
      login,
      password,
      access: { camera: false, analytics: false },
    });
    toast(`Role "${name}" added to ${company.name}.`);
  }

  ccDirty = true;
  renderCompanyControl(els.moduleContent);
}

function handleCompanyClick(event) {
  const button = event.target.closest("[data-cc-action]");
  if (!button) return;

  if (button.dataset.ccAction === "save") {
    saveCompanies(ccCompanies());
    ccDirty = false;
    toast("Changes saved.");
    renderCompanyControl(els.moduleContent);
    return;
  }

  const companies = ccCompanies();
  const company = companies.find((item) => item.id === button.dataset.company);
  if (!company) return;

  if (button.dataset.ccAction === "remove-company") {
    ccDraft = companies.filter((item) => item.id !== company.id);
    ccDirty = true;
  } else if (button.dataset.ccAction === "remove-role") {
    company.roles = (company.roles || []).filter((role) => role.id !== button.dataset.role);
    ccDirty = true;
  } else if (button.dataset.ccAction === "toggle-password") {
    if (revealedPasswords.has(button.dataset.role)) revealedPasswords.delete(button.dataset.role);
    else revealedPasswords.add(button.dataset.role);
  } else if (button.dataset.ccAction === "toggle-access") {
    const role = (company.roles || []).find((item) => item.id === button.dataset.role);
    if (!role) return;
    role.access = role.access || {};
    role.access[button.dataset.access] = !role.access[button.dataset.access];
    ccDirty = true;
  }

  renderCompanyControl(els.moduleContent);
}

// ---- Analytics charts -------------------------------------------------------
// Sample data for now; swap sampleAnalytics() for a backend endpoint later.

const CHART_COLORS = { blue: "#0284c7", green: "#15803d" };
const CHART_W = 960;
const CHART_H = 250;
const CHART_PAD = { top: 22, right: 14, bottom: 30, left: 50 };
const chartRegistry = new Map();

function mulberry32(seed) {
  let a = seed | 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function lastDays(count) {
  const days = [];
  const now = new Date();
  for (let i = count - 1; i >= 0; i -= 1) {
    const day = new Date(now);
    day.setDate(now.getDate() - i);
    days.push(day);
  }
  return days;
}

function shortDate(day) {
  return day.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function sampleAnalytics() {
  const rand = mulberry32(20260717);
  const companies = lastDays(30).map((date, index) => ({
    date,
    value: Math.max(0, Math.round(rand() * 3 + index / 14 - 0.4)),
  }));
  const uptime = lastDays(7).map((date) => ({
    date,
    value: Math.round((88 + rand() * 11.5) * 10) / 10,
  }));
  const movements = lastDays(14).map((date) => ({
    date,
    in: Math.round(22 + rand() * 38),
    out: Math.round(16 + rand() * 36),
  }));
  return { companies, uptime, movements };
}

function axisMax(value) {
  const candidates = [2, 4, 5, 8, 10, 20, 30, 40, 50, 60, 80, 100, 200, 500, 1000];
  return candidates.find((candidate) => candidate >= value) || Math.ceil(value / 1000) * 1000;
}

function axisTicks(max, min = 0) {
  const span = max - min;
  let step;
  if (span <= 6) step = 1;
  else step = [4, 3, 2].map((parts) => span / parts).find((candidate) => Number.isInteger(candidate)) || span / 4;
  const ticks = [];
  for (let v = min; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(2));
  return ticks;
}

function chartScales({ count, yMin, yMax }) {
  const plotW = CHART_W - CHART_PAD.left - CHART_PAD.right;
  const plotH = CHART_H - CHART_PAD.top - CHART_PAD.bottom;
  return {
    plotW,
    plotH,
    slotW: plotW / count,
    x: (index) => CHART_PAD.left + (plotW / count) * index,
    xCenter: (index) => CHART_PAD.left + (plotW / count) * (index + 0.5),
    y: (value) => CHART_PAD.top + plotH * (1 - (value - yMin) / (yMax - yMin)),
  };
}

function gridSvg(ticks, yMin, yMax, scale, formatTick) {
  return ticks
    .map((tick) => {
      const y = scale.y(tick);
      const isBase = tick === yMin;
      return `
        <line x1="${CHART_PAD.left}" x2="${CHART_W - CHART_PAD.right}" y1="${y}" y2="${y}"
              class="${isBase ? "chart-baseline" : "chart-gridline"}" />
        <text x="${CHART_PAD.left - 8}" y="${y + 3.5}" class="chart-tick" text-anchor="end">${formatTick(tick)}</text>
      `;
    })
    .join("");
}

function xLabelIndexes(count, want) {
  if (count <= want) return Array.from({ length: count }, (_, index) => index);
  const step = (count - 1) / (want - 1);
  return Array.from({ length: want }, (_, index) => Math.round(index * step));
}

function xLabelsSvg(points, scale, want = 5) {
  return xLabelIndexes(points.length, want)
    .map((index) => `<text x="${scale.xCenter(index)}" y="${CHART_H - 8}" class="chart-tick" text-anchor="middle">${shortDate(points[index].date)}</text>`)
    .join("");
}

function roundedBarPath(x, yTop, width, yBase) {
  const height = yBase - yTop;
  if (height <= 0) return "";
  const r = Math.min(4, height, width / 2);
  return `M ${x} ${yBase}
          L ${x} ${yTop + r}
          Q ${x} ${yTop} ${x + r} ${yTop}
          L ${x + width - r} ${yTop}
          Q ${x + width} ${yTop} ${x + width} ${yTop + r}
          L ${x + width} ${yBase} Z`;
}

function barChartSvg(id, points, { color, formatValue }) {
  const dataMax = Math.max(...points.map((point) => point.value));
  const yMax = axisMax(dataMax || 1);
  const scale = chartScales({ count: points.length, yMin: 0, yMax });
  const yBase = scale.y(0);
  const barW = Math.max(3, scale.slotW * 0.62);
  const maxIndex = points.reduce((best, point, index) => (point.value > points[best].value ? index : best), 0);

  const bars = points
    .map((point, index) => {
      const x = scale.xCenter(index) - barW / 2;
      const yTop = scale.y(point.value);
      const label =
        index === maxIndex && point.value > 0
          ? `<text x="${scale.xCenter(index)}" y="${yTop - 6}" class="chart-value" text-anchor="middle">${formatValue(point.value)}</text>`
          : "";
      return `
        <g class="chart-slot" data-index="${index}">
          <rect x="${scale.x(index)}" y="${CHART_PAD.top}" width="${scale.slotW}" height="${scale.plotH}" fill="transparent" />
          <path d="${roundedBarPath(x, yTop, barW, yBase)}" fill="${color}" />
          ${label}
        </g>
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Bar chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax), 0, yMax, scale, formatValue)}
      ${bars}
      ${xLabelsSvg(points, scale)}
    </svg>
  `;
}

function lineChartSvg(id, points, { color, yMin, yMax, formatValue }) {
  const scale = chartScales({ count: points.length, yMin, yMax });
  const coords = points.map((point, index) => [scale.xCenter(index), scale.y(point.value)]);
  const path = coords.map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const [lastX, lastY] = coords[coords.length - 1];
  const areaPath = `${path} L ${lastX.toFixed(1)} ${scale.y(yMin)} L ${coords[0][0].toFixed(1)} ${scale.y(yMin)} Z`;

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Line chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax, yMin), yMin, yMax, scale, formatValue)}
      <path d="${areaPath}" fill="${color}" opacity="0.14" />
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <line class="chart-crosshair" x1="0" x2="0" y1="${CHART_PAD.top}" y2="${CHART_PAD.top + scale.plotH}" hidden />
      <circle class="chart-focus" r="4.5" fill="${color}" stroke="var(--panel-strong)" stroke-width="2" hidden />
      <text x="${lastX - 8}" y="${lastY - 10}" class="chart-value" text-anchor="end">${formatValue(points[points.length - 1].value)}</text>
      ${xLabelsSvg(points, scale, points.length)}
    </svg>
  `;
}

function groupedBarChartSvg(id, points, { seriesKeys, seriesLabels, colors, formatValue }) {
  const dataMax = Math.max(...points.flatMap((point) => seriesKeys.map((key) => point[key])));
  const yMax = axisMax(dataMax || 1);
  const scale = chartScales({ count: points.length, yMin: 0, yMax });
  const yBase = scale.y(0);
  const gap = 2;
  const barW = Math.max(3, (scale.slotW * 0.66 - gap) / seriesKeys.length);

  const groups = points
    .map((point, index) => {
      const groupW = barW * seriesKeys.length + gap;
      const startX = scale.xCenter(index) - groupW / 2;
      const bars = seriesKeys
        .map((key, keyIndex) => {
          const x = startX + keyIndex * (barW + gap);
          const yTop = scale.y(point[key]);
          return `<path d="${roundedBarPath(x, yTop, barW, yBase)}" fill="${colors[keyIndex]}" />`;
        })
        .join("");
      return `
        <g class="chart-slot" data-index="${index}">
          <rect x="${scale.x(index)}" y="${CHART_PAD.top}" width="${scale.slotW}" height="${scale.plotH}" fill="transparent" />
          ${bars}
        </g>
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Grouped bar chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax), 0, yMax, scale, formatValue)}
      ${groups}
      ${xLabelsSvg(points, scale)}
    </svg>
  `;
}

function chartTableHtml(spec) {
  const header = `<tr><th>Date</th>${spec.series.map((series) => `<th>${escapeHtml(series.label)}</th>`).join("")}</tr>`;
  const rows = spec.points
    .map(
      (point) =>
        `<tr><td>${shortDate(point.date)}</td>${spec.series
          .map((series) => `<td>${spec.formatValue(point[series.key])}</td>`)
          .join("")}</tr>`
    )
    .join("");
  return `<div class="chart-table-wrap"><table class="chart-table"><thead>${header}</thead><tbody>${rows}</tbody></table></div>`;
}

function chartCardHtml(spec) {
  const legend =
    spec.series.length > 1
      ? `<div class="chart-legend">${spec.series
          .map((series, index) => `<span><i style="background:${spec.colors[index]}"></i>${escapeHtml(series.label)}</span>`)
          .join("")}</div>`
      : "";
  return `
    <article class="chart-card" data-chart="${spec.id}">
      <header class="chart-head">
        <div>
          <h3>${escapeHtml(spec.title)}</h3>
          <p class="chart-sub">${escapeHtml(spec.subtitle)}</p>
        </div>
        <button type="button" class="chart-toggle" data-chart-toggle="${spec.id}">Table</button>
      </header>
      ${legend}
      <div class="chart-body" data-chart-body="${spec.id}">${spec.svg}<div class="chart-tip" hidden></div></div>
    </article>
  `;
}

function tipHtml(spec, index) {
  const point = spec.points[index];
  const rows = spec.series
    .map(
      (series, seriesIndex) =>
        `<div><i style="background:${spec.colors[seriesIndex]}"></i>${escapeHtml(series.label)}: <strong>${spec.formatValue(point[series.key])}</strong></div>`
    )
    .join("");
  return `<em>${shortDate(point.date)}</em>${rows}`;
}

function moveTip(tip, body, clientX) {
  const rect = body.getBoundingClientRect();
  const x = clientX - rect.left;
  tip.style.left = `${Math.min(Math.max(x, 70), rect.width - 70)}px`;
}

function wireCharts(root) {
  root.querySelectorAll("[data-chart]").forEach((card) => {
    const spec = chartRegistry.get(card.dataset.chart);
    if (!spec) return;
    const body = card.querySelector("[data-chart-body]");
    const tip = () => card.querySelector(".chart-tip");

    card.querySelector("[data-chart-toggle]").addEventListener("click", (event) => {
      spec.showTable = !spec.showTable;
      event.target.textContent = spec.showTable ? "Chart" : "Table";
      body.innerHTML = spec.showTable ? chartTableHtml(spec) : `${spec.svg}<div class="chart-tip" hidden></div>`;
    });

    body.addEventListener("pointerleave", () => {
      const tipEl = tip();
      if (tipEl) tipEl.hidden = true;
      const svg = body.querySelector("svg");
      svg?.querySelector(".chart-crosshair")?.setAttribute("hidden", "");
      svg?.querySelector(".chart-focus")?.setAttribute("hidden", "");
    });

    body.addEventListener("pointermove", (event) => {
      const svg = body.querySelector("svg");
      const tipEl = tip();
      if (!svg || !tipEl || spec.showTable) return;
      const svgRect = svg.getBoundingClientRect();
      const xRatio = (event.clientX - svgRect.left) / svgRect.width;
      const plotStart = CHART_PAD.left / CHART_W;
      const plotEnd = (CHART_W - CHART_PAD.right) / CHART_W;
      if (xRatio < plotStart || xRatio > plotEnd) return;
      const index = Math.min(
        spec.points.length - 1,
        Math.max(0, Math.floor(((xRatio - plotStart) / (plotEnd - plotStart)) * spec.points.length))
      );
      tipEl.innerHTML = tipHtml(spec, index);
      tipEl.hidden = false;
      moveTip(tipEl, body, event.clientX);

      if (spec.type === "line") {
        const scale = chartScales({ count: spec.points.length, yMin: spec.yMin, yMax: spec.yMax });
        const crosshair = svg.querySelector(".chart-crosshair");
        const focus = svg.querySelector(".chart-focus");
        const cx = scale.xCenter(index);
        crosshair.setAttribute("x1", cx);
        crosshair.setAttribute("x2", cx);
        crosshair.removeAttribute("hidden");
        focus.setAttribute("cx", cx);
        focus.setAttribute("cy", scale.y(spec.points[index].value));
        focus.removeAttribute("hidden");
      }
    });
  });
}

function renderAnalytics(container) {
  const data = sampleAnalytics();
  const count = (value) => String(Math.round(value));
  const pct = (value) => `${value}%`;

  const specs = [
    {
      id: "companies",
      type: "bar",
      title: "Companies activated",
      subtitle: "New companies per day — past 30 days",
      points: data.companies,
      series: [{ key: "value", label: "Companies" }],
      colors: [CHART_COLORS.blue],
      formatValue: count,
      svg: null,
    },
    {
      id: "uptime",
      type: "line",
      title: "Active cameras",
      subtitle: "Share of cameras online — past 7 days",
      points: data.uptime,
      series: [{ key: "value", label: "Online" }],
      colors: [CHART_COLORS.blue],
      formatValue: pct,
      yMin: 80,
      yMax: 100,
      svg: null,
    },
    {
      id: "movements",
      type: "grouped",
      title: "Warehouse movements",
      subtitle: "Items in vs out per day — past 14 days",
      points: data.movements,
      series: [
        { key: "in", label: "IN" },
        { key: "out", label: "OUT" },
      ],
      colors: [CHART_COLORS.blue, CHART_COLORS.green],
      formatValue: count,
      svg: null,
    },
  ];

  specs.forEach((spec) => {
    if (spec.type === "bar") {
      spec.svg = barChartSvg(spec.id, spec.points, { color: spec.colors[0], formatValue: spec.formatValue });
    } else if (spec.type === "line") {
      spec.svg = lineChartSvg(spec.id, spec.points, {
        color: spec.colors[0],
        yMin: spec.yMin,
        yMax: spec.yMax,
        formatValue: spec.formatValue,
      });
    } else {
      spec.svg = groupedBarChartSvg(spec.id, spec.points, {
        seriesKeys: spec.series.map((series) => series.key),
        seriesLabels: spec.series.map((series) => series.label),
        colors: spec.colors,
        formatValue: spec.formatValue,
      });
    }
    spec.showTable = false;
    chartRegistry.set(spec.id, spec);
  });

  container.innerHTML = `
    <p class="chart-note">Sample data — analytics endpoints are not wired to the backend yet.</p>
    <div class="chart-grid">${specs.map(chartCardHtml).join("")}</div>
  `;
  wireCharts(container);
}

async function load() {
  const [session, overview] = await Promise.all([
    api("/api/v2/rbac/me"),
    api("/api/v2/head/overview"),
  ]);
  state.session = session;
  state.overview = overview;
  renderNavigation();
  renderSummary();
  renderScope();
  renderModuleContent();
}

els.moduleContent.addEventListener("submit", handleCompanySubmit);
els.moduleContent.addEventListener("click", handleCompanyClick);

els.moduleNav.addEventListener("click", (event) => {
  const button = event.target.closest("[data-module]");
  if (!button) return;
  state.activeModule = button.dataset.module;
  renderNavigation();
  renderModuleContent();
});

function applySidebarState(collapsed) {
  els.shell.classList.toggle("sidebar-collapsed", collapsed);
  els.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
}

applySidebarState(localStorage.getItem("ai_vision_v2_sidebar") === "collapsed");

els.sidebarToggle.addEventListener("click", () => {
  const collapsed = !els.shell.classList.contains("sidebar-collapsed");
  applySidebarState(collapsed);
  localStorage.setItem("ai_vision_v2_sidebar", collapsed ? "collapsed" : "open");
});

els.refreshBtn.addEventListener("click", () => {
  load().then(() => toast("Dashboard V2 refreshed.")).catch((error) => toast(error.message));
});

load().catch((error) => toast(error.message));
