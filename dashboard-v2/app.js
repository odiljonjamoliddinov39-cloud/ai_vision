const els = {
  moduleNav: document.querySelector("#moduleNav"),
  pageTitle: document.querySelector("#pageTitle"),
  scopeLine: document.querySelector("#scopeLine"),
  companiesSection: document.querySelector("#companiesSection"),
  summaryGrid: document.querySelector("#summaryGrid"),
  activeModuleEyebrow: document.querySelector("#activeModuleEyebrow"),
  activeModuleTitle: document.querySelector("#activeModuleTitle"),
  moduleContent: document.querySelector("#moduleContent"),
  detectorState: document.querySelector("#detectorState"),
  refreshBtn: document.querySelector("#refreshBtn"),
  shell: document.querySelector(".v2-shell"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  brandAvatar: document.querySelector("#brandAvatar"),
  headerProfile: document.querySelector("#headerProfile"),
  sideProfile: document.querySelector("#sideProfile"),
  themeToggle: document.querySelector("#themeToggle"),
  sideCompanies: document.querySelector("#sideCompanies"),
  toast: document.querySelector("#toast"),
};

const API_BASE = (() => {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    localStorage.setItem("ai_vision_v2_api_base", param.replace(/\/+$/, ""));
  }
  const saved = localStorage.getItem("ai_vision_v2_api_base");
  if (saved) return saved;
  // Default to same-origin so Vercel rewrites can proxy /api to the DO backend.
  return window.location.origin;
})();

const state = {
  role: "super_admin",
  activeModule: null,
  session: null,
  overview: null,
  cameraRegistry: null,
};

const HEAD_MODULE_IDS = new Set(["overview", "users", "cameras"]);

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

async function apiJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-AI-Role": state.role,
      "X-AI-User-Name": "Dashboard V2 Preview",
      "X-AI-Company": "All Companies",
      ...(options.headers || {}),
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

const NAV_ICONS = {
  overview: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>`,
  users: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1M9 13h1M14 9h1M14 13h1M10 21v-4h4v4"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`,
  analytics: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 4 3 5-8"/></svg>`,
  feed: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
  ai: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="7" width="16" height="12" rx="2"/><path d="M12 7V4M8 4h8M9 12h.01M15 12h.01M9 16h6"/></svg>`,
  dimension: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>`,
};

function renderNavigation() {
  const modules = (state.session?.surfaces?.head || []).filter((module) =>
    HEAD_MODULE_IDS.has(module.id)
  );
  const known =
    state.activeModule === "settings" || modules.some((module) => module.id === state.activeModule);
  if (!state.activeModule || !known) {
    state.activeModule = modules[0]?.id || "settings";
  }
  const buttons = modules.map(
    (module) => `
      <button class="${module.id === state.activeModule ? "active" : ""}" data-module="${module.id}" type="button">
        ${NAV_ICONS[module.id] || ""}
        <span>${escapeHtml(moduleLabel(module))}</span>
      </button>
    `
  );
  buttons.push(`
    <button class="${state.activeModule === "settings" ? "active" : ""}" data-module="settings" type="button">
      ${NAV_ICONS.settings}
      <span>Settings</span>
    </button>
  `);
  els.moduleNav.innerHTML = buttons.join("");
}

const PENCIL_SVG = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>`;

function renderSideCompanies() {
  const companies = loadCompanies();
  els.sideCompanies.innerHTML = companies.length
    ? companies
        .map(
          (company) => `
            <li>
              <span>${escapeHtml(company.name)}</span>
              <button type="button" data-edit-company="${company.id}" aria-label="Edit ${escapeHtml(company.name)}">${PENCIL_SVG}</button>
            </li>
          `
        )
        .join("")
    : `<li class="side-empty">No companies yet</li>`;
}

const STAT_ICONS = {
  "Active cameras": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`,
  "Frames read": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="2.2"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/></svg>`,
  "Last detections": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"/></svg>`,
  "Stock items": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>`,
  "Saved cameras": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>`,
  "Audit verified": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
};

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
  const deltas = {
    "Active cameras": { text: "+1 this week", dir: "up" },
    "Frames read": { text: "no change", dir: "flat" },
    "Last detections": { text: "-2 vs yesterday", dir: "down" },
    "Stock items": { text: "no change", dir: "flat" },
    "Saved cameras": { text: "+1 this month", dir: "up" },
    "Audit verified": { text: "all systems normal", dir: "up" },
  };
  els.summaryGrid.innerHTML = cards
    .map(([label, value]) => {
      const delta = deltas[label];
      return `
        <article class="stat-card">
          <div class="stat-icon">${STAT_ICONS[label] || ""}</div>
          <div class="stat-body">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
            ${delta ? `<em class="stat-delta ${delta.dir}">${escapeHtml(delta.text)}</em>` : ""}
          </div>
        </article>
      `;
    })
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
  if (state.activeModule === "settings") {
    els.activeModuleTitle.textContent = "Settings";
    els.activeModuleEyebrow.textContent = "Head module";
    els.summaryGrid.hidden = true;
    renderSettings(els.moduleContent);
    return;
  }
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

  if (module.id === "cameras") {
    const cameras = state.cameraRegistry?.cameras || [];
    els.moduleContent.innerHTML = cameras.length
      ? `
        <table>
          <thead>
            <tr><th>Name</th><th>Slot</th><th>Status</th><th>Source</th></tr>
          </thead>
          <tbody>
            ${cameras
              .map(
                (camera) => `
                  <tr>
                    <td>${escapeHtml(camera.name)}</td>
                    <td>${escapeHtml(camera.slot_number ?? "-")}</td>
                    <td>${escapeHtml((camera.status || "unknown").toUpperCase())}</td>
                    <td>${escapeHtml(camera.masked_stream_url || "")}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      `
      : `<p class="empty">No cameras are stored in the database yet.</p>`;
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
// Companies/roles are persisted on the backend so public account links work
// across devices and through the Vercel public domain.

const ACCESS_OPTIONS = [
  { key: "camera", label: "Camera Control" },
  { key: "analytics", label: "Analytics" },
];

let companyStore = [];
let publicDashboardUrl = window.location.origin;

function loadCompanies() {
  return companyStore;
}

function saveCompanies(companies) {
  companyStore = Array.isArray(companies) ? companies : [];
}

async function loadCompanyControl() {
  const result = await api("/api/v2/company-control");
  saveCompanies(result.companies);
  publicDashboardUrl = result.public_dashboard_url || window.location.origin;
  return companyStore;
}

async function persistCompanyControl(companies) {
  const result = await apiJson("/api/v2/company-control", {
    method: "POST",
    body: JSON.stringify({ companies }),
  });

  saveCompanies(result.companies);
  publicDashboardUrl = result.public_dashboard_url || window.location.origin;
  return companyStore;
}

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

const revealedPasswords = new Set();
let ccDraft = null;
let ccDirty = false;
let ccEditingCompany = null;

function ccCompanies() {
  if (!ccDraft) ccDraft = loadCompanies();
  return ccDraft;
}

function accountLink(role) {
  if (role.link) return role.link;
  if (role.token) {
    return `${publicDashboardUrl}/dashboard-v2#acc=${encodeURIComponent(role.token)}`;
  }
  return "";
}

function renderRoleView(company, role) {
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
  const link = role.link
    ? `
      <div class="cc-link">
        <a href="${escapeHtml(role.link)}" title="${escapeHtml(role.link)}">${escapeHtml(role.link)}</a>
        <button type="button" class="cc-chip cc-chip-small" data-cc-action="copy-link" data-link="${escapeHtml(role.link)}">Copy</button>
      </div>
    `
    : `<p class="cc-link-pending">Account link is generated when you press Save.</p>`;
  return `${credentials}${link}`;
}

function renderRoleEdit(company, role) {
  return `
    <div class="cc-edit-grid">
      <input data-cc-edit="role-name" data-company="${company.id}" data-role="${role.id}"
             value="${escapeHtml(role.name)}" placeholder="Role name" maxlength="60" />
      <input data-cc-edit="role-login" data-company="${company.id}" data-role="${role.id}"
             value="${escapeHtml(role.login || "")}" placeholder="Username (login)" maxlength="60" />
      <input data-cc-edit="role-password" data-company="${company.id}" data-role="${role.id}"
             value="${escapeHtml(role.password || "")}" placeholder="Password" maxlength="120" />
    </div>
  `;
}

function renderCompanyControl(container) {
  const companies = ccCompanies();

  const companyCards = companies
    .map((company) => {
      const editing = company.id === ccEditingCompany;
      const roles = (company.roles || [])
        .map(
          (role) => `
            <div class="cc-role">
              <div class="cc-role-head">
                ${editing ? "" : `<strong>${escapeHtml(role.name)}</strong>`}
                <button type="button" class="cc-remove" data-cc-action="remove-role"
                        data-company="${company.id}" data-role="${role.id}" aria-label="Remove role">✕</button>
              </div>
              ${editing ? renderRoleEdit(company, role) : renderRoleView(company, role)}
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
          `
        )
        .join("");

      const heading = editing
        ? `<input class="cc-name-input" data-cc-edit="company-name" data-company="${company.id}"
                  value="${escapeHtml(company.name)}" maxlength="60" aria-label="Company name" />`
        : `<h3>${escapeHtml(company.name)}</h3>`;
      const editButton = editing
        ? `<button type="button" class="cc-chip cc-chip-small on" data-cc-action="done-edit">Done</button>`
        : `<button type="button" class="cc-remove" data-cc-action="edit-company" data-company="${company.id}" aria-label="Edit ${escapeHtml(company.name)}">${PENCIL_SVG}</button>`;

      return `
        <article class="cc-company ${editing ? "editing" : ""}" data-company-card="${company.id}">
          <header class="cc-company-head">
            ${heading}
            <div class="cc-head-actions">
              ${editButton}
              <button type="button" class="cc-remove" data-cc-action="remove-company"
                      data-company="${company.id}" aria-label="Remove company">✕</button>
            </div>
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
    <p class="chart-note">Stored securely on the DigitalOcean backend.</p>
    <form class="cc-add cc-add-company" data-cc-form="company">
      <input name="name" placeholder="Company name" required maxlength="60" autocomplete="off" />
      <button type="submit">Add company</button>
    </form>
    <div class="cc-list">
      ${companyCards || `<p class="empty">No companies yet — add the first one above.</p>`}
    </div>
    <div class="cc-save-row">
      <span class="cc-unsaved" ${ccDirty ? "" : "hidden"}>Unsaved changes</span>
      <button type="button" class="cc-save" data-cc-action="save" ${ccDirty ? "" : "disabled"}>Save changes</button>
    </div>
  `;
}

function refreshSaveState() {
  const button = els.moduleContent.querySelector(".cc-save");
  const badge = els.moduleContent.querySelector(".cc-unsaved");
  if (button) button.disabled = !ccDirty;
  if (badge) badge.hidden = !ccDirty;
}

function handleCompanyInput(event) {
  const input = event.target.closest("[data-cc-edit]");
  if (!input) return;
  const companies = ccCompanies();
  const company = companies.find((item) => item.id === input.dataset.company);
  if (!company) return;
  const value = input.value;
  const field = input.dataset.ccEdit;
  if (field === "company-name") {
    company.name = value;
  } else {
    const role = (company.roles || []).find((item) => item.id === input.dataset.role);
    if (!role) return;
    if (field === "role-name") role.name = value;
    else if (field === "role-login") role.login = value;
    else if (field === "role-password") role.password = value;
  }
  ccDirty = true;
  refreshSaveState();
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

async function handleCompanyClick(event) {
  const button = event.target.closest("[data-cc-action]");
  if (!button) return;

  if (button.dataset.ccAction === "save") {
    try {
      const saved = await persistCompanyControl(ccCompanies());
      ccDraft = saved;
      ccDirty = false;
      ccEditingCompany = null;
      toast("Changes saved on DigitalOcean — public links are ready.");
      renderCompanyControl(els.moduleContent);
      renderSideCompanies();
    } catch (error) {
      toast(error instanceof Error ? error.message : String(error));
    }
    return;
  }

  if (button.dataset.ccAction === "copy-link") {
    navigator.clipboard?.writeText(button.dataset.link).then(
      () => toast("Account link copied."),
      () => toast("Could not copy — select the link manually.")
    );
    return;
  }

  if (button.dataset.ccAction === "done-edit") {
    ccEditingCompany = null;
    renderCompanyControl(els.moduleContent);
    return;
  }

  const companies = ccCompanies();
  const company = companies.find((item) => item.id === button.dataset.company);
  if (!company) return;

  if (button.dataset.ccAction === "edit-company") {
    ccEditingCompany = company.id;
    renderCompanyControl(els.moduleContent);
    return;
  }

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

// ---- Settings (profile & security) ------------------------------------------
// Stored in localStorage for now, like the company data.

const PROFILE_KEY = "ai_vision_v2_profile";

function loadProfile() {
  try {
    return { login: "admin", password: "", avatar: null, ...JSON.parse(localStorage.getItem(PROFILE_KEY) || "{}") };
  } catch {
    return { login: "admin", password: "", avatar: null };
  }
}

function saveProfile(profile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  updateBrandAvatar();
}

function updateBrandAvatar() {
  const profile = loadProfile();
  if (profile.avatar) {
    els.brandAvatar.src = profile.avatar;
    els.brandAvatar.hidden = false;
  } else {
    els.brandAvatar.hidden = true;
    els.brandAvatar.removeAttribute("src");
  }
  renderHeaderProfile();
}

function renderHeaderProfile(name) {
  const profile = loadProfile();
  const label = name || profile.login || "admin";
  const initial = label.slice(0, 1).toUpperCase();
  const avatar =
    !name && profile.avatar
      ? `<img src="${profile.avatar}" alt="" />`
      : `<span class="hp-initial">${escapeHtml(initial)}</span>`;
  els.headerProfile.innerHTML = `${avatar}<span class="hp-name">${escapeHtml(label)}</span>`;
  if (!name) renderSideProfile();
}

function renderSideProfile(login, subtitle) {
  const profile = loadProfile();
  const label = login || profile.login || "admin";
  const sub = subtitle || "Super Admin";
  const avatar =
    !login && profile.avatar
      ? `<img src="${profile.avatar}" alt="" />`
      : `<span class="hp-initial">${escapeHtml(label.slice(0, 1).toUpperCase())}</span>`;
  els.sideProfile.innerHTML = `${avatar}<div class="side-profile-text"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(sub)}</small></div>`;
}

function renderSettings(container) {
  const profile = loadProfile();
  container.innerHTML = `
    <p class="chart-note">Stored in this browser for now — backend hookup pending.</p>
    <div class="settings-grid">
      <section class="cc-company">
        <header class="cc-company-head"><h3>Profile picture</h3></header>
        <div class="settings-avatar-row">
          ${
            profile.avatar
              ? `<img class="settings-avatar" src="${profile.avatar}" alt="Profile picture" />`
              : `<div class="settings-avatar settings-avatar-empty">${escapeHtml((profile.login || "A").slice(0, 1).toUpperCase())}</div>`
          }
          <div class="settings-avatar-actions">
            <label class="cc-chip settings-upload">
              Upload picture
              <input id="avatarInput" type="file" accept="image/*" hidden />
            </label>
            ${profile.avatar ? `<button type="button" class="cc-chip cc-chip-small" data-settings-action="remove-avatar">Remove</button>` : ""}
          </div>
        </div>
      </section>
      <section class="cc-company">
        <header class="cc-company-head"><h3>Login &amp; password</h3></header>
        <p class="cc-cred"><em>Current login:</em> ${escapeHtml(profile.login)}</p>
        <form class="cc-add cc-add-role" data-settings-form="security">
          <input name="login" placeholder="New login" value="${escapeHtml(profile.login)}" required maxlength="60" autocomplete="username" />
          <input name="password" type="password" placeholder="New password" required maxlength="120" autocomplete="new-password" />
          <input name="confirm" type="password" placeholder="Confirm new password" required maxlength="120" autocomplete="new-password" />
          <button type="submit">Update credentials</button>
        </form>
      </section>
    </div>
  `;
}

function handleSettingsSubmit(event) {
  const form = event.target.closest("[data-settings-form]");
  if (!form) return;
  event.preventDefault();
  const login = form.elements.login.value.trim();
  const password = form.elements.password.value;
  const confirm = form.elements.confirm.value;
  if (!login || !password) return;
  if (password !== confirm) {
    toast("Passwords do not match.");
    return;
  }
  const profile = loadProfile();
  profile.login = login;
  profile.password = password;
  saveProfile(profile);
  toast("Credentials updated.");
  renderSettings(els.moduleContent);
}

function handleSettingsChange(event) {
  if (event.target.id !== "avatarInput") return;
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    toast("Picture is too large — keep it under 2 MB.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const profile = loadProfile();
    profile.avatar = String(reader.result);
    saveProfile(profile);
    toast("Profile picture updated.");
    renderSettings(els.moduleContent);
  };
  reader.readAsDataURL(file);
}

function handleSettingsClick(event) {
  const button = event.target.closest("[data-settings-action]");
  if (!button) return;
  if (button.dataset.settingsAction === "remove-avatar") {
    const profile = loadProfile();
    profile.avatar = null;
    saveProfile(profile);
    renderSettings(els.moduleContent);
  }
}

// ---- User dashboard (account links) -----------------------------------------

function accountTokenFromHash() {
  const match = window.location.hash.match(/acc=([^&]+)/i);
  return match ? decodeURIComponent(match[1]) : null;
}

async function resolveAccountFromHash() {
  const token = accountTokenFromHash();
  if (!token) return null;

  return apiJson(`/api/v2/company-control/accounts/public/${encodeURIComponent(token)}`, {
    headers: {
      "X-AI-Role": "viewer",
      "X-AI-User-Name": "Public account",
      "X-AI-Company": "Assigned company",
    },
  });
}

function livePreviewHtml(summary, health) {
  const slots = Math.min(Number(summary.active_cameras || health.camera_count || 4), 10);
  return `
    <div class="live-preview">
      ${Array.from({ length: slots }, (_, index) => {
        const slot = index + 1;
        return `<figure><img src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
      }).join("")}
    </div>
  `;
}

const MAX_NVRS = 5;
const MAX_NVR_SLOTS = 50;
let accountState = null;
let accountModule = null;

const QUALITY_OPTIONS = [
  { id: "low", label: "Low · 480p", hint: "fastest serving" },
  { id: "medium", label: "Medium · 720p", hint: "balanced" },
  { id: "high", label: "High · 1080p", hint: "best picture" },
];

function companyConfig(company) {
  if (!company.cameraConfig) company.cameraConfig = { nvrs: [], quality: "high" };
  if (!company.cameraConfig.nvrs) company.cameraConfig.nvrs = [];
  if (!company.ai) company.ai = { products: [], mode: "once" };
  if (!company.ai.products) company.ai.products = [];
  return company;
}

async function persistAccountCompany() {
  const token = accountTokenFromHash();
  if (!token || !accountState?.company) return;

  accountState = await apiJson(
    `/api/v2/company-control/accounts/public/${encodeURIComponent(token)}`,
    {
      method: "PUT",
      body: JSON.stringify({ company: accountState.company }),
      headers: {
        "X-AI-Role": "viewer",
        "X-AI-User-Name": "Public account",
        "X-AI-Company": accountState.company.name || "Assigned company",
      },
    }
  );
}

function accountMenus(role) {
  const menus = [];
  if (role.access?.camera) menus.push({ id: "camera", label: "Camera Control", sub: "NVR & vision quality" });
  if (role.access?.analytics) menus.push({ id: "analytics", label: "Analytics", sub: "Charts & trends" });
  if (role.access?.camera) menus.push({ id: "feed", label: "Camera Feed", sub: "Live slots" });
  menus.push({ id: "ai", label: "AI Check-in", sub: "Products to count" });
  menus.push({ id: "dimension", label: "3D Dimensioning", sub: "Item measurements" });
  return menus;
}

function productDims(name) {
  let seed = 7;
  for (const char of name) seed = (seed * 31 + char.charCodeAt(0)) | 0;
  const rand = mulberry32(seed);
  return {
    w: 10 + Math.round(rand() * 70),
    h: 8 + Math.round(rand() * 50),
    d: 10 + Math.round(rand() * 60),
  };
}

function dimBoxSvg({ w, h, d }) {
  const stroke = currentTheme() === "dark" ? "#38bdf8" : "#2563eb";
  const rgb = currentTheme() === "dark" ? "56,189,248" : "37,99,235";
  const scale = 1.6;
  const bw = Math.max(30, w * scale);
  const bh = Math.max(24, h * scale);
  const bd = Math.max(16, d * scale * 0.5);
  const x = 64;
  const y = 20 + bd;
  const width = x + bw + bd + 60;
  const height = y + bh + 34;
  return `
    <svg viewBox="0 0 ${width} ${height}" class="dim-svg" role="img" aria-label="3D box ${w} by ${h} by ${d} centimeters">
      <path d="M ${x} ${y} l ${bd} ${-bd} h ${bw} l ${-bd} ${bd} Z" fill="rgba(${rgb},0.14)" stroke="${stroke}" stroke-width="1.5" />
      <rect x="${x}" y="${y}" width="${bw}" height="${bh}" fill="rgba(${rgb},0.06)" stroke="${stroke}" stroke-width="1.5" />
      <path d="M ${x + bw} ${y} l ${bd} ${-bd} v ${bh} l ${-bd} ${bd} Z" fill="rgba(${rgb},0.10)" stroke="${stroke}" stroke-width="1.5" />
      <text x="${x + bw / 2}" y="${y + bh + 18}" class="dim-label" text-anchor="middle">W ${w} cm</text>
      <text x="${x - 8}" y="${y + bh / 2}" class="dim-label" text-anchor="end">H ${h} cm</text>
      <text x="${x + bw + bd / 2 + 6}" y="${y - bd / 2}" class="dim-label">D ${d} cm</text>
    </svg>
  `;
}

function renderAccountModule() {
  const { company, role } = accountState;
  companyConfig(company);
  const menus = accountMenus(role);
  const menu = menus.find((item) => item.id === accountModule) || menus[0];
  accountModule = menu?.id || null;

  els.moduleNav.innerHTML = menus
    .map(
      (item) => `
        <button class="${item.id === accountModule ? "active" : ""}" data-acc-module="${item.id}" type="button">
          ${NAV_ICONS[item.id] || ""}
          <span>${escapeHtml(item.label)}</span>
        </button>
      `
    )
    .join("");

  els.activeModuleEyebrow.textContent = "User module";
  els.activeModuleTitle.textContent = menu ? menu.label : `Welcome, ${role.name}`;

  if (!menu) {
    els.moduleContent.innerHTML = `<p class="empty">No modules have been granted to this account yet. Ask your administrator for access.</p>`;
    return;
  }

  const config = company.cameraConfig;
  const ai = company.ai;
  const summary = state.overview?.summary || {};
  const health = state.overview?.health || {};

  if (menu.id === "camera") {
    const atLimit = config.nvrs.length >= MAX_NVRS;
    const nvrCards = config.nvrs
      .map(
        (nvr) => `
          <article class="cc-company">
            <header class="cc-company-head">
              <h3>${escapeHtml(nvr.name)}</h3>
              <button type="button" class="cc-remove" data-acc-action="remove-nvr" data-nvr="${nvr.id}" aria-label="Remove NVR">✕</button>
            </header>
            <p class="cc-cred"><em>RTSP:</em> <span class="nvr-rtsp" title="${escapeHtml(nvr.rtsp)}">${escapeHtml(nvr.rtsp)}</span></p>
            <p class="cc-cred"><em>Camera slots:</em> ${nvr.slots} / ${MAX_NVR_SLOTS}</p>
          </article>
        `
      )
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">NVR connections: ${config.nvrs.length}/${MAX_NVRS} — each NVR can expose up to ${MAX_NVR_SLOTS} camera slots.</p>
      <div class="cc-list">${nvrCards || `<p class="empty">No NVRs connected yet — add the first one below.</p>`}</div>
      <form class="cc-add cc-add-role nvr-form" data-acc-form="nvr" ${atLimit ? "hidden" : ""}>
        <input name="name" placeholder="NVR name (e.g. Warehouse North)" required maxlength="60" autocomplete="off" />
        <input name="rtsp" placeholder="rtsp://user:pass@192.168.1.10:554/stream" required maxlength="200" autocomplete="off" />
        <input name="slots" type="number" min="1" max="${MAX_NVR_SLOTS}" value="8" required aria-label="Camera slots" />
        <button type="submit">Add NVR</button>
      </form>
      ${atLimit ? `<p class="empty">NVR limit reached (${MAX_NVRS}). Remove one to add another.</p>` : ""}
      <section class="acc-block quality-block">
        <h3>Vision quality</h3>
        <p class="chart-note">Lower quality serves video faster over slow connections.</p>
        <div class="cc-access">
          ${QUALITY_OPTIONS.map(
            (option) => `
              <button type="button" class="cc-chip ${config.quality === option.id ? "on" : ""}"
                      data-acc-action="quality" data-quality="${option.id}">
                ${option.label} <small>· ${option.hint}</small>
              </button>
            `
          ).join("")}
        </div>
      </section>
    `;
    return;
  }

  if (menu.id === "analytics") {
    els.moduleContent.innerHTML = `<div id="accCharts"></div>`;
    renderAnalytics(els.moduleContent.querySelector("#accCharts"));
    return;
  }

  if (menu.id === "feed") {
    if (!config.nvrs.length) {
      els.moduleContent.innerHTML = `<p class="empty">No NVRs connected — set one up in Camera Control first.</p>`;
      return;
    }
    let globalSlot = 0;
    const sections = config.nvrs
      .map((nvr) => {
        const tiles = Array.from({ length: nvr.slots }, (_, index) => {
          globalSlot += 1;
          if (globalSlot <= Math.max(Number(summary.active_cameras || health.camera_count || 1), 1)) {
            const count = 200 + Math.round(mulberry32(globalSlot * 97)() * 900);
            return `<figure><span class="feed-count">Count: ${count}</span><img src="${API_BASE}/api/live_frame?slot=${globalSlot}&v=${Date.now()}" alt="${escapeHtml(nvr.name)} slot ${index + 1}" /><figcaption>${escapeHtml(nvr.name)} · slot ${index + 1}</figcaption></figure>`;
          }
          return `<figure class="feed-empty"><div>No signal yet</div><figcaption>${escapeHtml(nvr.name)} · slot ${index + 1}</figcaption></figure>`;
        }).join("");
        return `<section class="acc-block"><h3>${escapeHtml(nvr.name)} <small class="muted">(${nvr.slots} slots)</small></h3><div class="live-preview">${tiles}</div></section>`;
      })
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">Streaming at ${escapeHtml((QUALITY_OPTIONS.find((option) => option.id === config.quality) || QUALITY_OPTIONS[2]).label)} quality.</p>
      ${sections}
    `;
    return;
  }

  if (menu.id === "ai") {
    const rows = ai.products
      .map(
        (product) => `
          <div class="cc-role ai-product">
            <div class="cc-role-head">
              <strong>${escapeHtml(product.name)}</strong>
              <button type="button" class="cc-remove" data-acc-action="remove-product" data-product="${product.id}" aria-label="Remove product">✕</button>
            </div>
            <div class="cc-access">
              <button type="button" class="cc-chip ${product.counting ? "on" : ""}" data-acc-action="toggle-product" data-product="${product.id}">
                ${product.counting ? "Counting ✓" : "Not counting"}
              </button>
              ${product.dims ? `<span class="cc-cred"><em>Measured once:</em> ${product.dims.w}×${product.dims.h}×${product.dims.d} cm</span>` : ""}
            </div>
          </div>
        `
      )
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">Check in the products the AI should count — everything else is ignored.</p>
      <form class="cc-add" data-acc-form="product">
        <input name="name" placeholder="Product name (e.g. Bread crate)" required maxlength="60" autocomplete="off" />
        <button type="submit">Check in product</button>
      </form>
      <div class="cc-list ai-list">${rows || `<p class="empty">No products checked in yet.</p>`}</div>
      <section class="acc-block">
        <h3>Recognition mode</h3>
        <div class="cc-access">
          <button type="button" class="cc-chip ${ai.mode === "once" ? "on" : ""}" data-acc-action="mode" data-mode="once">Count &amp; dimension once</button>
          <button type="button" class="cc-chip ${ai.mode === "interval" ? "on" : ""}" data-acc-action="mode" data-mode="interval">Re-check every 5 minutes</button>
        </div>
        <p class="chart-note">${ai.mode === "once" ? "Each item is counted and measured a single time at first detection — no repeat scans." : "Items are re-recognized on a 5-minute cycle."}</p>
      </section>
    `;
    return;
  }

  if (menu.id === "dimension") {
    const measured = ai.products.filter((product) => product.counting && product.dims);
    els.moduleContent.innerHTML = `
      <p class="chart-note">What the AI draws when it looks at your checked-in items. ${ai.mode === "once" ? "Measured once at first detection — never re-measured on the 5-minute cycle." : "Re-measured every 5 minutes."}</p>
      ${
        measured.length
          ? `<div class="cc-list dim-list">${measured
              .map(
                (product) => `
                  <article class="cc-company dim-card">
                    <header class="cc-company-head"><h3>${escapeHtml(product.name)}</h3><span class="cc-chip cc-chip-small on">Counted once ✓</span></header>
                    ${dimBoxSvg(product.dims)}
                    <p class="cc-cred"><em>Volume:</em> ${((product.dims.w * product.dims.h * product.dims.d) / 1000).toFixed(1)} L</p>
                  </article>
                `
              )
              .join("")}</div>`
          : `<p class="empty">No measured items yet — check in a product in AI Check-in and enable counting.</p>`
      }
    `;
    return;
  }
}

function handleAccountSubmit(event) {
  const form = event.target.closest("[data-acc-form]");
  if (!form || !accountState) return;
  event.preventDefault();
  const { company } = accountState;
  companyConfig(company);

  if (form.dataset.accForm === "nvr") {
    if (company.cameraConfig.nvrs.length >= MAX_NVRS) return;
    const name = form.elements.name.value.trim();
    const rtsp = form.elements.rtsp.value.trim();
    const slots = Math.min(MAX_NVR_SLOTS, Math.max(1, Number(form.elements.slots.value) || 1));
    if (!name || !rtsp) return;
    company.cameraConfig.nvrs.push({ id: newId(), name, rtsp, slots });
    toast(`NVR "${name}" connected with ${slots} slots.`);
  } else if (form.dataset.accForm === "product") {
    const name = form.elements.name.value.trim();
    if (!name) return;
    company.ai.products.push({ id: newId(), name, counting: true, dims: productDims(name), measuredAt: Date.now() });
    toast(`"${name}" checked in — counted and measured once.`);
  } else {
    return;
  }

  persistAccountCompany().catch((error) =>
    toast(error instanceof Error ? error.message : String(error))
  );
  renderAccountModule();
}

function handleAccountClick(event) {
  const button = event.target.closest("[data-acc-action]");
  if (!button || !accountState) return;
  const { company } = accountState;
  companyConfig(company);
  const action = button.dataset.accAction;

  if (action === "remove-nvr") {
    company.cameraConfig.nvrs = company.cameraConfig.nvrs.filter((nvr) => nvr.id !== button.dataset.nvr);
  } else if (action === "quality") {
    company.cameraConfig.quality = button.dataset.quality;
  } else if (action === "toggle-product") {
    const product = company.ai.products.find((item) => item.id === button.dataset.product);
    if (product) product.counting = !product.counting;
  } else if (action === "remove-product") {
    company.ai.products = company.ai.products.filter((item) => item.id !== button.dataset.product);
  } else if (action === "mode") {
    company.ai.mode = button.dataset.mode;
  } else {
    return;
  }

  persistAccountCompany().catch((error) =>
    toast(error instanceof Error ? error.message : String(error))
  );
  renderAccountModule();
}

function renderAccountView({ company, role, missing }) {
  els.pageTitle.textContent = "User Dashboard";
  els.companiesSection.hidden = true;
  els.summaryGrid.hidden = true;
  els.activeModuleEyebrow.textContent = "User module";

  const summary = state.overview?.summary || {};
  const running = Boolean(summary.detector_running);
  els.detectorState.textContent = running ? "Detector running" : "Detector stopped";
  els.detectorState.dataset.state = running ? "good" : "bad";

  if (missing) {
    els.moduleNav.innerHTML = "";
    els.scopeLine.textContent = "Account access";
    els.activeModuleTitle.textContent = "Account not found";
    els.moduleContent.innerHTML = `
      <p class="empty">This account link isn't available on this device yet — account data is stored
      in the browser where it was created until the backend hookup.</p>
    `;
    return;
  }

  accountState = { company, role };
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";
  els.pageTitle.textContent = `${greeting}, ${role.name} 👋`;
  els.scopeLine.textContent = `${company.name} • login: ${role.login}`;
  renderHeaderProfile(role.login);
  renderSideProfile(role.login, `${role.name} @ ${company.name}`);
  renderAccountModule();
}

// ---- Analytics charts -------------------------------------------------------
// Sample data for now; swap sampleAnalytics() for a backend endpoint later.

const THEME_KEY = "ai_vision_v2_theme";

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

// Both palettes validated against their own surface (light: #ffffff, dark: #0f172a).
function chartColors() {
  return currentTheme() === "dark"
    ? { blue: "#0284c7", green: "#15803d" }
    : { blue: "#2a78d6", green: "#008300" };
}
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
      colors: [chartColors().blue],
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
      colors: [chartColors().blue],
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
      colors: [chartColors().blue, chartColors().green],
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

  const alerts = [
    { title: "Camera Offline", where: "Slot 2 · 2 min ago", sev: "high", color: "var(--bad)" },
    { title: "NVR Disconnected", where: "Warehouse Central · 10 min ago", sev: "critical", color: "#dc2626" },
    { title: "Low Production Rate", where: "Line 2 · 15 min ago", sev: "medium", color: "var(--warn)" },
  ];
  const resources = [
    { name: "CPU Usage", pct: 42, color: "#2a78d6" },
    { name: "GPU Usage", pct: 67, color: "#7c3aed" },
    { name: "Storage Usage", pct: 58, color: "#0891b2" },
    { name: "Memory Usage", pct: 71, color: "#db2777" },
  ];
  container.innerHTML = `
    <p class="chart-note">Sample data — analytics endpoints are not wired to the backend yet.</p>
    <div class="chart-grid">${specs.map(chartCardHtml).join("")}</div>
    <div class="ov-grid">
      <section class="ov-card">
        <h3>Recent Alerts</h3>
        ${alerts
          .map(
            (alert) => `
              <div class="alert-row">
                <span class="alert-dot" style="background:${alert.color}"></span>
                <div class="alert-main"><strong>${alert.title}</strong><small>${alert.where}</small></div>
                <span class="sev-chip ${alert.sev}">${alert.sev.charAt(0).toUpperCase() + alert.sev.slice(1)}</span>
              </div>
            `
          )
          .join("")}
      </section>
      <section class="ov-card">
        <h3>System Resources</h3>
        ${resources
          .map(
            (res) => `
              <div class="res-row">
                <div class="res-head"><strong>${res.name}</strong><span>${res.pct}%</span></div>
                <div class="res-bar"><i style="width:${res.pct}%;background:${res.color}"></i></div>
              </div>
            `
          )
          .join("")}
      </section>
    </div>
  `;
  wireCharts(container);
}

async function load() {
  const token = accountTokenFromHash();
  if (token) {
    const account = await resolveAccountFromHash();
    renderAccountView(account);
    return;
  }

  const [session, overview, _companies, cameraRegistry] = await Promise.all([
    api("/api/v2/rbac/me"),
    api("/api/v2/head/overview"),
    loadCompanyControl(),
    api("/api/cameras"),
  ]);
  state.session = session;
  state.overview = overview;
  state.cameraRegistry = cameraRegistry;
  renderSideCompanies();
  els.pageTitle.textContent = "Head Dashboard";
  els.companiesSection.hidden = false;
  renderNavigation();
  renderSummary();
  renderScope();
  renderModuleContent();
}

els.moduleContent.addEventListener("submit", (event) => {
  handleCompanySubmit(event);
  handleSettingsSubmit(event);
  handleAccountSubmit(event);
});
els.moduleContent.addEventListener("click", (event) => {
  handleCompanyClick(event);
  handleSettingsClick(event);
  handleAccountClick(event);
});
els.moduleContent.addEventListener("input", handleCompanyInput);
els.moduleContent.addEventListener("change", handleSettingsChange);

els.sideCompanies.addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-company]");
  if (!button) return;
  ccEditingCompany = button.dataset.editCompany;
  state.activeModule = "users";
  renderNavigation();
  renderModuleContent();
  els.moduleContent
    .querySelector(`[data-company-card="${ccEditingCompany}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
});

els.moduleNav.addEventListener("click", (event) => {
  const accButton = event.target.closest("[data-acc-module]");
  if (accButton && accountState) {
    accountModule = accButton.dataset.accModule;
    renderAccountModule();
    return;
  }
  const button = event.target.closest("[data-module]");
  if (!button) return;
  state.activeModule = button.dataset.module;
  renderNavigation();
  renderModuleContent();
});

const SUN_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>`;
const MOON_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  els.themeToggle.innerHTML = theme === "dark" ? SUN_SVG : MOON_SVG;
  els.themeToggle.title = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
}

applyTheme(localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light");

els.themeToggle.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
  if (accountState) renderAccountModule();
  else renderModuleContent();
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

window.addEventListener("hashchange", () => window.location.reload());

renderSideCompanies();
updateBrandAvatar();
load().catch((error) => toast(error.message));
