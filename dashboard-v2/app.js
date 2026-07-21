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

const LOAD_RETRY_DELAYS_MS = [500, 1000, 2000];
let loadRetryTimer = null;

// The backend intentionally exposes stable JPEG snapshots instead of one
// long-lived MJPEG connection per camera. Refresh only the images that are
// currently mounted so camera pages stay live without rebuilding any module.
// Target two updates per second. The per-image loading guard below makes this
// self-throttling on slower links instead of stacking duplicate requests.
const LIVE_FRAME_REFRESH_MS = 500;
let liveFrameTimer = null;

function liveFrameUrl(slot) {
  const url = new URL(`${API_BASE}/api/live_frame`);
  url.searchParams.set("slot", slot);
  url.searchParams.set("v", Date.now());
  return url.toString();
}

function setFeedBadgeLive(image, isLive) {
  const badge = image.parentElement?.querySelector(".feed-transmitting");
  if (!badge) return;
  badge.textContent = isLive ? "Transmitting live" : "No signal";
  badge.classList.toggle("feed-stale-badge", !isLive);
}

async function refreshLiveFrameImage(image) {
  if (image.dataset.liveLoading === "true") return;
  const slot = image.dataset.liveSlot;
  if (!slot) return;

  image.dataset.liveLoading = "true";
  try {
    const response = await fetch(liveFrameUrl(slot), { cache: "no-store" });
    if (!response.ok) throw new Error(`Live frame request failed: ${response.status}`);
    const frame = await response.blob();
    if (!image.isConnected) return;

    const previousObjectUrl = image.dataset.liveObjectUrl;
    const nextObjectUrl = URL.createObjectURL(frame);
    image.onload = () => {
      if (previousObjectUrl) URL.revokeObjectURL(previousObjectUrl);
      image.classList.remove("feed-stale");
      image.removeAttribute("title");
      image.dataset.liveLastUpdate = new Date().toISOString();
      setFeedBadgeLive(image, true);
      delete image.dataset.liveLoading;
    };
    image.onerror = () => {
      URL.revokeObjectURL(nextObjectUrl);
      image.classList.add("feed-stale");
      image.title = "Waiting for a fresh camera frame";
      setFeedBadgeLive(image, false);
      delete image.dataset.liveLoading;
    };
    image.dataset.liveObjectUrl = nextObjectUrl;
    image.src = nextObjectUrl;
  } catch {
    if (image.isConnected) {
      image.classList.add("feed-stale");
      image.title = "Waiting for a fresh camera frame";
      setFeedBadgeLive(image, false);
    }
    delete image.dataset.liveLoading;
  }
}

function refreshLiveFrames() {
  if (document.hidden) return;
  els.moduleContent.querySelectorAll("img[data-live-frame]").forEach(refreshLiveFrameImage);
}

function stopLiveFrameRefresh() {
  if (liveFrameTimer !== null) {
    window.clearInterval(liveFrameTimer);
    liveFrameTimer = null;
  }
}

function syncLiveFrameRefresh() {
  const hasLiveFrames = Boolean(els.moduleContent.querySelector("img[data-live-frame]"));
  if (document.hidden || !hasLiveFrames) {
    stopLiveFrameRefresh();
    return;
  }
  refreshLiveFrames();
  if (liveFrameTimer === null) {
    liveFrameTimer = window.setInterval(refreshLiveFrames, LIVE_FRAME_REFRESH_MS);
  }
}

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

function renderSideCompaniesFromCache() {
  const companies = ccCompaniesCache || [];
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

async function renderSideCompanies() {
  try {
    await ensureCompaniesLoaded();
  } catch {
    // Best effort — Company Control will surface the real error if opened.
  }
  renderSideCompaniesFromCache();
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
          return `<figure><img data-live-frame data-live-slot="${slot}" src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
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

// Companies, roles, and accounts are stored on the server (database/accounts_db.py)
// so an account link works from any browser or device, not just the one it was
// created on. `ccCompaniesCache` is a local read cache kept in sync with the API.

const ACCESS_OPTIONS = [
  { key: "camera", label: "Camera Control" },
  { key: "analytics", label: "Analytics" },
];

async function accountsApi(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = (await response.text()) || detail;
    }
    throw new Error(detail || "Request failed.");
  }
  if (response.status === 204) return null;
  return response.json();
}

let ccCompaniesCache = null;
let ccEditingCompany = null;
let ccEditValues = null;
let ccPasswordEditRole = null;

// One-time recovery for companies/roles created before the server-side
// database existed (they were only ever in this browser's localStorage).
// Matches by company name / role login so re-visiting from the same browser
// doesn't create duplicates. Old account links from that era point at ids
// that only existed locally, so they can never resolve — this migration
// gives every recovered role a new, working server-backed link.
const LEGACY_COMPANIES_KEY = "ai_vision_v2_companies";
const LEGACY_MIGRATED_KEY = "ai_vision_v2_companies_migrated_at";
const LEGACY_BACKUP_KEY = "ai_vision_v2_companies_legacy_backup";

async function migrateLegacyLocalStorage() {
  const raw = localStorage.getItem(LEGACY_COMPANIES_KEY);
  if (!raw) return null;
  if (localStorage.getItem(LEGACY_MIGRATED_KEY)) {
    localStorage.removeItem(LEGACY_COMPANIES_KEY);
    return null;
  }

  let legacyCompanies;
  try {
    legacyCompanies = JSON.parse(raw);
  } catch {
    legacyCompanies = null;
  }
  if (!Array.isArray(legacyCompanies) || !legacyCompanies.length) {
    localStorage.removeItem(LEGACY_COMPANIES_KEY);
    return null;
  }

  let existing;
  try {
    existing = await ensureCompaniesLoaded();
  } catch {
    return null; // Server unreachable — leave the key in place and retry next load.
  }

  let companiesCreated = 0;
  let rolesCreated = 0;
  let failures = 0;

  for (const oldCompany of legacyCompanies) {
    const name = String(oldCompany?.name || "").trim();
    if (!name) continue;

    let company = existing.find((item) => item.name.toLowerCase() === name.toLowerCase());
    if (!company) {
      try {
        company = await accountsApi("/api/v2/companies", { method: "POST", body: JSON.stringify({ name }) });
        existing.push(company);
        companiesCreated += 1;
      } catch {
        failures += 1;
        continue;
      }
    }
    company.roles = company.roles || [];

    const oldCameraConfig = oldCompany?.cameraConfig;
    if (oldCameraConfig?.nvrs?.length && !company.cameraConfig?.nvrs?.length) {
      try {
        company.cameraConfig = await accountsApi(`/api/v2/companies/${company.id}/camera-config`, {
          method: "PUT",
          body: JSON.stringify({ cameraConfig: oldCameraConfig }),
        }).then(() => oldCameraConfig);
      } catch {
        // Non-fatal — camera setup can be redone from Company Control.
      }
    }

    for (const oldRole of oldCompany?.roles || []) {
      const roleName = String(oldRole?.name || "").trim();
      const login = String(oldRole?.login || "").trim();
      if (!roleName || !login) continue;
      if (company.roles.some((role) => role.login.toLowerCase() === login.toLowerCase())) continue;

      try {
        const role = await accountsApi(`/api/v2/companies/${company.id}/roles`, {
          method: "POST",
          body: JSON.stringify({
            name: roleName,
            login,
            password: oldRole.password || Math.random().toString(36).slice(2, 12),
            access_camera: Boolean(oldRole.access?.camera),
            access_analytics: Boolean(oldRole.access?.analytics),
          }),
        });
        company.roles.push(role);
        rolesCreated += 1;
      } catch {
        failures += 1;
      }
    }
  }

  localStorage.setItem(LEGACY_MIGRATED_KEY, new Date().toISOString());
  localStorage.setItem(LEGACY_BACKUP_KEY, raw);
  localStorage.removeItem(LEGACY_COMPANIES_KEY);

  return { companiesCreated, rolesCreated, failures };
}

async function ensureCompaniesLoaded() {
  if (ccCompaniesCache) return ccCompaniesCache;
  const payload = await accountsApi("/api/v2/companies");
  ccCompaniesCache = payload.companies || [];
  return ccCompaniesCache;
}

function ccCompanyById(id) {
  return (ccCompaniesCache || []).find((company) => company.id === id);
}

function refreshCompanyUI() {
  renderSideCompaniesFromCache();
  if (state.activeModule === "users") renderCompanyControl(els.moduleContent);
}

function accountLink(role) {
  return `${window.location.origin}/dashboard-v2#acc=${role.id}`;
}

function renderRoleView(role) {
  const changingPassword = ccPasswordEditRole === role.id;
  const passwordForm = changingPassword
    ? `
      <form class="cc-add" data-cc-form="password" data-role="${role.id}">
        <input name="password" type="password" placeholder="New password" required maxlength="120" autocomplete="new-password" />
        <button type="submit">Set password</button>
      </form>
    `
    : "";
  const link = accountLink(role);
  return `
    <div class="cc-credentials">
      <span class="cc-cred"><em>Login:</em> ${escapeHtml(role.login)}</span>
      <span class="cc-cred"><em>Password:</em> •••••••• (hashed on the server)</span>
      <button type="button" class="cc-chip cc-chip-small" data-cc-action="toggle-password-edit" data-role="${role.id}">
        ${changingPassword ? "Cancel" : "Change password"}
      </button>
    </div>
    ${passwordForm}
    <div class="cc-link">
      <a href="${escapeHtml(link)}" title="${escapeHtml(link)}">${escapeHtml(link)}</a>
      <button type="button" class="cc-chip cc-chip-small" data-cc-action="copy-link" data-link="${escapeHtml(link)}">Copy</button>
    </div>
  `;
}

function renderRoleEdit(role) {
  const edited = ccEditValues?.roles?.[role.id] || { name: role.name, login: role.login };
  return `
    <div class="cc-edit-grid">
      <input data-cc-edit="role-name" data-role="${role.id}" value="${escapeHtml(edited.name)}" placeholder="Role name" maxlength="60" />
      <input data-cc-edit="role-login" data-role="${role.id}" value="${escapeHtml(edited.login)}" placeholder="Username (login)" maxlength="60" />
    </div>
  `;
}

function renderCompanyControl(container) {
  if (!ccCompaniesCache) {
    container.innerHTML = `<p class="chart-note">Loading companies…</p>`;
    ensureCompaniesLoaded()
      .then(() => {
        if (state.activeModule === "users") renderCompanyControl(els.moduleContent);
      })
      .catch((error) => {
        if (state.activeModule === "users") {
          els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
        }
      });
    return;
  }

  const companyCards = ccCompaniesCache
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
              ${editing ? renderRoleEdit(role) : renderRoleView(role)}
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
        ? `<input class="cc-name-input" data-cc-edit="company-name" value="${escapeHtml(ccEditValues?.companyName ?? company.name)}" maxlength="60" aria-label="Company name" />`
        : `<h3>${escapeHtml(company.name)}</h3>`;
      const editActions = editing
        ? `
          <button type="button" class="cc-chip cc-chip-small on" data-cc-action="save-edit">Save</button>
          <button type="button" class="cc-chip cc-chip-small" data-cc-action="cancel-edit">Cancel</button>
        `
        : `<button type="button" class="cc-remove" data-cc-action="edit-company" data-company="${company.id}" aria-label="Edit ${escapeHtml(company.name)}">${PENCIL_SVG}</button>`;

      return `
        <article class="cc-company ${editing ? "editing" : ""}" data-company-card="${company.id}">
          <header class="cc-company-head">
            ${heading}
            <div class="cc-head-actions">
              ${editActions}
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
    <p class="chart-note">Companies and accounts are stored on the server — links work on any device.</p>
    <form class="cc-add cc-add-company" data-cc-form="company">
      <input name="name" placeholder="Company name" required maxlength="60" autocomplete="off" />
      <button type="submit">Add company</button>
    </form>
    <div class="cc-list">
      ${companyCards || `<p class="empty">No companies yet — add the first one above.</p>`}
    </div>
  `;
}

function handleCompanyInput(event) {
  const input = event.target.closest("[data-cc-edit]");
  if (!input || !ccEditValues) return;
  const field = input.dataset.ccEdit;
  if (field === "company-name") {
    ccEditValues.companyName = input.value;
  } else if (field === "role-name") {
    ccEditValues.roles[input.dataset.role] = { ...ccEditValues.roles[input.dataset.role], name: input.value };
  } else if (field === "role-login") {
    ccEditValues.roles[input.dataset.role] = { ...ccEditValues.roles[input.dataset.role], login: input.value };
  }
}

async function handleCompanySubmit(event) {
  const form = event.target.closest("[data-cc-form]");
  if (!form) return;
  event.preventDefault();
  const kind = form.dataset.ccForm;

  if (kind === "company") {
    const name = form.elements.name.value.trim();
    if (!name) return;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const company = await accountsApi("/api/v2/companies", { method: "POST", body: JSON.stringify({ name }) });
      ccCompaniesCache = [...(ccCompaniesCache || []), company];
      toast(`Company "${name}" added.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }

  if (kind === "role") {
    const company = ccCompanyById(form.dataset.company);
    if (!company) return;
    const name = form.elements.name.value.trim();
    const login = form.elements.login.value.trim();
    const password = form.elements.password.value;
    if (!name || !login || !password) return;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const role = await accountsApi(`/api/v2/companies/${company.id}/roles`, {
        method: "POST",
        body: JSON.stringify({ name, login, password, access_camera: false, access_analytics: false }),
      });
      company.roles = [...(company.roles || []), role];
      toast(`"${name}" added — account link: ${accountLink(role)}`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }

  if (kind === "password") {
    const roleId = form.dataset.role;
    const password = form.elements.password.value;
    if (!password) return;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      await accountsApi(`/api/v2/roles/${roleId}`, { method: "PUT", body: JSON.stringify({ password }) });
      ccPasswordEditRole = null;
      toast("Password updated.");
      renderCompanyControl(els.moduleContent);
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
  }
}

async function handleCompanyClick(event) {
  const button = event.target.closest("[data-cc-action]");
  if (!button) return;
  const action = button.dataset.ccAction;

  if (action === "copy-link") {
    navigator.clipboard?.writeText(button.dataset.link).then(
      () => toast("Account link copied."),
      () => toast("Could not copy — select the link manually.")
    );
    return;
  }

  if (action === "toggle-password-edit") {
    ccPasswordEditRole = ccPasswordEditRole === button.dataset.role ? null : button.dataset.role;
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "edit-company") {
    const company = ccCompanyById(button.dataset.company);
    if (!company) return;
    ccEditingCompany = company.id;
    ccEditValues = {
      companyName: company.name,
      roles: Object.fromEntries((company.roles || []).map((role) => [role.id, { name: role.name, login: role.login }])),
    };
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "cancel-edit") {
    ccEditingCompany = null;
    ccEditValues = null;
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "save-edit") {
    const company = ccCompanyById(ccEditingCompany);
    if (!company || !ccEditValues) return;
    button.disabled = true;
    try {
      if (ccEditValues.companyName !== company.name) {
        const updated = await accountsApi(`/api/v2/companies/${company.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: ccEditValues.companyName }),
        });
        company.name = updated.name;
      }
      for (const role of company.roles || []) {
        const edited = ccEditValues.roles[role.id];
        if (!edited || (edited.name === role.name && edited.login === role.login)) continue;
        const updated = await accountsApi(`/api/v2/roles/${role.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: edited.name, login: edited.login }),
        });
        role.name = updated.name;
        role.login = updated.login;
      }
      ccEditingCompany = null;
      ccEditValues = null;
      toast("Changes saved.");
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
    return;
  }

  const company = ccCompanyById(button.dataset.company);
  if (!company) return;

  if (action === "remove-company") {
    if (!window.confirm(`Remove "${company.name}" and all of its roles? This cannot be undone.`)) return;
    try {
      await accountsApi(`/api/v2/companies/${company.id}`, { method: "DELETE" });
      ccCompaniesCache = ccCompaniesCache.filter((item) => item.id !== company.id);
      if (ccEditingCompany === company.id) {
        ccEditingCompany = null;
        ccEditValues = null;
      }
      toast(`"${company.name}" removed.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
    }
    return;
  }

  if (action === "remove-role") {
    const role = (company.roles || []).find((item) => item.id === button.dataset.role);
    if (!role) return;
    if (!window.confirm(`Remove the "${role.name}" account? Its link will stop working.`)) return;
    try {
      await accountsApi(`/api/v2/roles/${role.id}`, { method: "DELETE" });
      company.roles = company.roles.filter((item) => item.id !== role.id);
      toast(`"${role.name}" removed.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
    }
    return;
  }

  if (action === "toggle-access") {
    const role = (company.roles || []).find((item) => item.id === button.dataset.role);
    if (!role) return;
    const key = button.dataset.access;
    const nextValue = !role.access?.[key];
    button.disabled = true;
    try {
      const field = key === "camera" ? "access_camera" : "access_analytics";
      const updated = await accountsApi(`/api/v2/roles/${role.id}`, {
        method: "PUT",
        body: JSON.stringify({ [field]: nextValue }),
      });
      role.access = updated.access;
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
  }
}

// ---- Settings (profile & security) ------------------------------------------
// Stored on the server (single admin profile row) so it follows you across devices.

let ccProfileCache = null;

async function ensureProfileLoaded() {
  if (ccProfileCache) return ccProfileCache;
  ccProfileCache = await accountsApi("/api/v2/admin/profile");
  return ccProfileCache;
}

function updateBrandAvatarFromCache() {
  const profile = ccProfileCache || { login: "admin", avatar: null };
  if (profile.avatar) {
    els.brandAvatar.src = profile.avatar;
    els.brandAvatar.hidden = false;
  } else {
    els.brandAvatar.hidden = true;
    els.brandAvatar.removeAttribute("src");
  }
  renderHeaderProfile();
}

async function updateBrandAvatar() {
  try {
    await ensureProfileLoaded();
  } catch {
    // Best effort — the header falls back to the "admin" placeholder.
  }
  updateBrandAvatarFromCache();
}

function renderHeaderProfile(name) {
  const profile = ccProfileCache || { login: "admin", avatar: null };
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
  const profile = ccProfileCache || { login: "admin", avatar: null };
  const label = login || profile.login || "admin";
  const sub = subtitle || "Super Admin";
  const avatar =
    !login && profile.avatar
      ? `<img src="${profile.avatar}" alt="" />`
      : `<span class="hp-initial">${escapeHtml(label.slice(0, 1).toUpperCase())}</span>`;
  els.sideProfile.innerHTML = `${avatar}<div class="side-profile-text"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(sub)}</small></div>`;
}

function renderSettings(container) {
  if (!ccProfileCache) {
    container.innerHTML = `<p class="chart-note">Loading profile…</p>`;
    ensureProfileLoaded()
      .then(() => {
        if (state.activeModule === "settings") renderSettings(els.moduleContent);
      })
      .catch((error) => {
        if (state.activeModule === "settings") {
          els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
        }
      });
    return;
  }

  const profile = ccProfileCache;
  container.innerHTML = `
    <p class="chart-note">Stored on the server — your login and picture follow you to any device.</p>
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

async function handleSettingsSubmit(event) {
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
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    ccProfileCache = await accountsApi("/api/v2/admin/profile", {
      method: "PUT",
      body: JSON.stringify({ login, password }),
    });
    toast("Credentials updated.");
    updateBrandAvatarFromCache();
    renderSettings(els.moduleContent);
  } catch (error) {
    toast(error.message);
    submit.disabled = false;
  }
}

async function handleSettingsChange(event) {
  if (event.target.id !== "avatarInput") return;
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    toast("Picture is too large — keep it under 2 MB.");
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      ccProfileCache = await accountsApi("/api/v2/admin/profile", {
        method: "PUT",
        body: JSON.stringify({ avatar: String(reader.result) }),
      });
      toast("Profile picture updated.");
      updateBrandAvatarFromCache();
      renderSettings(els.moduleContent);
    } catch (error) {
      toast(error.message);
    }
  };
  reader.readAsDataURL(file);
}

async function handleSettingsClick(event) {
  const button = event.target.closest("[data-settings-action]");
  if (!button) return;
  if (button.dataset.settingsAction === "remove-avatar") {
    try {
      ccProfileCache = await accountsApi("/api/v2/admin/profile", {
        method: "PUT",
        body: JSON.stringify({ remove_avatar: true }),
      });
      updateBrandAvatarFromCache();
      renderSettings(els.moduleContent);
    } catch (error) {
      toast(error.message);
    }
  }
}

// ---- User dashboard (account links) -----------------------------------------

async function resolveAccountFromHash() {
  const match = window.location.hash.match(/acc=([a-z0-9]+)/i);
  if (!match) return null;
  try {
    const response = await fetch(`${API_BASE}/api/v2/accounts/${encodeURIComponent(match[1])}`);
    if (response.status === 404) {
      return { company: null, role: null, missing: true, error: null };
    }
    if (!response.ok) {
      throw new Error(`Account lookup failed (${response.status}).`);
    }
    const payload = await response.json();
    return { company: payload.company, role: payload.role, missing: false, error: null };
  } catch (error) {
    return { company: null, role: null, missing: true, error: error instanceof Error ? error.message : String(error) };
  }
}

function livePreviewHtml(summary, health) {
  const slots = Math.min(Number(summary.active_cameras || health.camera_count || 4), 10);
  return `
    <div class="live-preview">
      ${Array.from({ length: slots }, (_, index) => {
        const slot = index + 1;
        return `<figure><img data-live-frame data-live-slot="${slot}" src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
      }).join("")}
    </div>
  `;
}

const MAX_NVRS = 5;
const MAX_NVR_SLOTS = 50;
let accountState = null;
let accountModule = null;

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

const QUALITY_OPTIONS = [
  { id: "low", label: "Low · 480p", hint: "fastest serving" },
  { id: "medium", label: "Medium · 720p", hint: "balanced" },
  { id: "high", label: "High · 1080p", hint: "best picture" },
];

function companyConfig(company) {
  if (!company.cameraConfig) company.cameraConfig = { nvrs: [], quality: "high" };
  if (!company.cameraConfig.nvrs) company.cameraConfig.nvrs = [];
  return company;
}

async function persistAccountCompany() {
  const { company } = accountState;
  const updated = await accountsApi(`/api/v2/companies/${company.id}/camera-config`, {
    method: "PUT",
    body: JSON.stringify({ cameraConfig: company.cameraConfig }),
  });
  company.cameraConfig = updated.cameraConfig;
}

function parseNvrConnectionInput(raw) {
  const value = raw.trim();
  const result = { host: value, port: null, username: null, password: null, path: null };
  if (!value) return result;

  if (value.includes("://")) {
    try {
      const url = new URL(value);
      result.host = url.hostname || value;
      if (url.port) result.port = Number(url.port);
      if (url.username) result.username = decodeURIComponent(url.username);
      if (url.password) result.password = decodeURIComponent(url.password);
      if (url.pathname && url.pathname !== "/") result.path = url.pathname;
      return result;
    } catch {
      return result;
    }
  }

  const hostPortMatch = value.match(/^([^:/]+):(\d{1,5})$/);
  if (hostPortMatch) {
    result.host = hostPortMatch[1];
    result.port = Number(hostPortMatch[2]);
  }
  return result;
}

async function nextAvailableCameraSlot() {
  const { cameras } = await accountsApi("/api/cameras");
  const usedSlots = (cameras || [])
    .filter((camera) => camera.is_active && camera.slot_number != null)
    .map((camera) => Number(camera.slot_number));
  // Must stay within [1, MAX_NVR_SLOTS] - the backend's start_slot field
  // rejects anything higher with a 422, even though it's perfectly able to
  // register channels beyond the free-slot budget as inactive instead of
  // failing the whole request (see _register_controller_channels). Without
  // this clamp, once every slot up to MAX_NVR_SLOTS is in use, adding any
  // new NVR fails outright instead of falling back to that behavior.
  const next = usedSlots.length ? Math.max(...usedSlots) + 1 : 1;
  return Math.min(next, MAX_NVR_SLOTS);
}

async function registerNvrController(fields) {
  const startSlot = await nextAvailableCameraSlot();
  const payload = {
    name: fields.name,
    host: fields.host,
    protocol: fields.protocol,
    channel_count: fields.channels,
    channel_start: 1,
    start_slot: startSlot,
    make_active: true,
    test_controller: true,
    test_streams: false,
  };
  if (fields.port) payload.port = fields.port;
  if (fields.username) payload.username = fields.username;
  if (fields.password) payload.password = fields.password;
  if (fields.streamPath) payload.stream_path_template = fields.streamPath;

  const response = await accountsApi("/api/camera-controller", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return {
    port: response.controller.port,
    controllerMessage: response.controller.public_reachability_warning || response.controller.message,
    channelsDetail: response.results.map((result) => ({
      camera_id: result.camera_id,
      channel: result.channel,
      slot_number: result.slot_number,
      status: result.status,
      message: result.message,
      active: result.active,
    })),
  };
}

async function deleteNvrCameras(nvr) {
  const channels = nvr.channelsDetail || [];
  await Promise.all(
    channels.map((channel) =>
      accountsApi(`/api/cameras/${channel.camera_id}`, { method: "DELETE" }).catch(() => null)
    )
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

function catalogScopeId() {
  return accountState?.company?.id || "default";
}

function catalogApiPath(path) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}scope_id=${encodeURIComponent(catalogScopeId())}`;
}

async function catalogRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || "Catalog request failed.");
  }
  return response.json();
}

function formatCatalogTime(value) {
  if (!value) return "Pending first recognition run";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function catalogDimensions(result) {
  if (!result?.width_m || !result?.height_m || !result?.depth_m) return null;
  return {
    w: Math.round(Number(result.width_m) * 1000) / 10,
    h: Math.round(Number(result.height_m) * 1000) / 10,
    d: Math.round(Number(result.depth_m) * 1000) / 10,
  };
}

async function renderCatalogEnrollment(container) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/items"));
    if (!container.isConnected || accountModule !== "ai") return;
    const rows = payload.items
      .map(
        (item) => `
          <article class="cc-role ai-product catalog-product">
            <div class="cc-role-head">
              <div><strong>${escapeHtml(item.name)}</strong><small>${item.image_count} reference images</small></div>
              <button type="button" class="cc-remove" data-acc-action="remove-catalog-item" data-product="${item.id}" aria-label="Remove ${escapeHtml(item.name)}">✕</button>
            </div>
            <div class="catalog-thumbs">
              ${item.images.map((image) => `<img src="${API_BASE}${image.url}" alt="${escapeHtml(item.name)} reference" />`).join("")}
            </div>
            <span class="cc-chip cc-chip-small on">Catalog recognition enabled ✓</span>
          </article>
        `
      )
      .join("");
    container.innerHTML = `
      <p class="chart-note">Add only the items the AI is allowed to recognize. Every item requires multiple reference images; anything outside this catalog is ignored by scheduled recognition.</p>
      <form class="catalog-form" data-acc-form="catalog-product">
        <label class="catalog-name-field">
          <span>Item name</span>
          <input name="name" placeholder="e.g. Bread crate" required maxlength="60" autocomplete="off" />
        </label>
        <label class="catalog-upload">
          <span>Reference images</span>
          <input name="images" type="file" accept="image/*" multiple required />
        </label>
        <small class="catalog-upload-help" data-image-count>Choose at least 2 clear images from different angles.</small>
        <button type="submit">Add item to AI catalog</button>
      </form>
      <div class="recognition-schedule">
        <strong>Automatic recognition every ${payload.schedule.interval_hours} hours</strong>
        <span>Last: ${escapeHtml(formatCatalogTime(payload.schedule.last_run_at))}</span>
        <span>Next: ${escapeHtml(formatCatalogTime(payload.schedule.next_run_at))}</span>
      </div>
      <div class="cc-list ai-list">${rows || `<p class="empty">No catalog items yet. Add an item name and at least two images above.</p>`}</div>
    `;
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

async function renderCatalogResults(container) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results"));
    if (!container.isConnected || accountModule !== "analytics") return;
    const rows = payload.results
      .map((result) => {
        const dims = catalogDimensions(result);
        return `
          <tr>
            <td><strong>${escapeHtml(result.item_name)}</strong></td>
            <td class="count-cell">${Number(result.quantity).toLocaleString()}</td>
            <td>${Math.round(Number(result.confidence) * 100)}%</td>
            <td>${dims ? `${dims.w} × ${dims.h} × ${dims.d} cm` : "Pending 3D measurement"}</td>
          </tr>
        `;
      })
      .join("");
    container.innerHTML = `
      <section class="detected-list">
        <header class="detected-list-head">
          <div>
            <h3>Detected catalog items</h3>
            <p>Latest 12-hour recognition run: ${escapeHtml(formatCatalogTime(payload.run?.completed_at))}</p>
          </div>
          <a class="export-button" href="${API_BASE}${catalogApiPath("/api/catalog/results/export.xlsx")}">Export to Excel</a>
        </header>
        ${
          rows
            ? `<div class="detected-table-wrap"><table class="detected-table"><thead><tr><th>Item</th><th>Count</th><th>Confidence</th><th>3D measurement</th></tr></thead><tbody>${rows}</tbody></table></div>`
            : `<p class="empty">No checked-in catalog item was detected in the latest run yet.</p>`
        }
        <p class="catalog-next-run">Next automatic recognition: ${escapeHtml(formatCatalogTime(payload.schedule.next_run_at))}</p>
      </section>
    `;
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

async function renderCatalogDimensions(container) {
  try {
    const [catalog, recognition] = await Promise.all([
      catalogRequest(catalogApiPath("/api/catalog/items")),
      catalogRequest(catalogApiPath("/api/catalog/results")),
    ]);
    if (!container.isConnected || accountModule !== "dimension") return;
    const items = new Map(catalog.items.map((item) => [item.id, item]));
    const cards = recognition.results
      .map((result) => {
        const dims = catalogDimensions(result);
        if (!dims) return "";
        const item = items.get(result.item_id);
        return `
          <article class="cc-company dim-card">
            <header class="cc-company-head"><h3>${escapeHtml(result.item_name)}</h3><span class="cc-chip cc-chip-small on">Recognized ×${result.quantity}</span></header>
            <div class="dimension-visual">
              ${item?.images?.[0] ? `<img src="${API_BASE}${item.images[0].url}" alt="${escapeHtml(result.item_name)} reference" />` : ""}
              ${dimBoxSvg(dims)}
            </div>
            <p class="cc-cred"><em>Measured:</em> ${dims.w} × ${dims.h} × ${dims.d} cm</p>
            <p class="cc-cred"><em>Volume:</em> ${((dims.w * dims.h * dims.d) / 1000).toFixed(1)} L · ${escapeHtml(result.measurement_method || "3D vision")}</p>
          </article>
        `;
      })
      .join("");
    container.innerHTML = `
      <p class="chart-note">3D drawings are created only for checked-in catalog items that receive a spatial measurement during recognition.</p>
      ${cards ? `<div class="cc-list dim-list">${cards}</div>` : `<p class="empty">No recognized item has a 3D measurement yet. The next recognition runs at ${escapeHtml(formatCatalogTime(recognition.schedule.next_run_at))}.</p>`}
    `;
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
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

  if (menu.id === "camera") {
    const atLimit = config.nvrs.length >= MAX_NVRS;
    const nvrCards = config.nvrs
      .map((nvr) => {
        const channels = nvr.channelsDetail || [];
        const transmitting = channels.filter((channel) => channel.active).length;
        const overallOk = channels.length > 0 && transmitting > 0;
        const channelRows = channels.length
          ? `<ul class="nvr-channels">${channels
              .map((channel) => {
                const stateClass = channel.active ? "ok" : channel.status === "connected" ? "pending" : "bad";
                const label = channel.active
                  ? "Transmitting"
                  : channel.status === "connected"
                    ? "Waiting for a free slot"
                    : "Not connected";
                const slotLabel = channel.slot_number != null ? `slot ${channel.slot_number}` : "no slot yet";
                return `
                  <li class="nvr-channel ${stateClass}">
                    <span>Ch ${channel.channel} · ${slotLabel}</span>
                    <span class="nvr-channel-status">${label}</span>
                  </li>
                `;
              })
              .join("")}</ul>`
          : "";
        return `
          <article class="cc-company">
            <header class="cc-company-head">
              <h3>${escapeHtml(nvr.name)}</h3>
              <button type="button" class="cc-remove" data-acc-action="remove-nvr" data-nvr="${nvr.id}" aria-label="Remove NVR">✕</button>
            </header>
            <p class="cc-cred"><em>Address:</em> <span class="nvr-rtsp" title="${escapeHtml(nvr.protocol)}://${escapeHtml(nvr.host)}:${nvr.port}">${escapeHtml(nvr.protocol)}://${escapeHtml(nvr.host)}:${nvr.port}</span></p>
            <p class="cc-cred"><em>Channels:</em> ${transmitting}/${channels.length || nvr.channels || 0} transmitting</p>
            <p class="nvr-status ${overallOk ? "ok" : "bad"}">${escapeHtml(nvr.controllerMessage || "Not tested yet.")}</p>
            ${channelRows}
          </article>
        `;
      })
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">NVR connections: ${config.nvrs.length}/${MAX_NVRS} — each NVR can expose up to ${MAX_NVR_SLOTS} camera channels. Cameras must be reachable from this server over the internet (a public IP, port-forward, or DDNS hostname) — local-only addresses like 192.168.x.x won't connect from the cloud.</p>
      <div class="cc-list">${nvrCards || `<p class="empty">No NVRs connected yet — add the first one below.</p>`}</div>
      <form class="cc-add cc-add-role nvr-form" data-acc-form="nvr" ${atLimit ? "hidden" : ""}>
        <input name="name" placeholder="NVR name (e.g. Warehouse North)" required maxlength="60" autocomplete="off" />
        <input name="host" placeholder="Host, host:port, or a full rtsp://user:pass@host:port/path URL" required maxlength="200" autocomplete="off" />
        <select name="protocol" aria-label="Stream protocol">
          <option value="rtsp" selected>RTSP</option>
          <option value="http">HTTP</option>
          <option value="https">HTTPS</option>
        </select>
        <input name="port" type="number" min="1" max="65535" placeholder="Port (default 554)" />
        <input name="username" placeholder="Username (optional)" autocomplete="off" />
        <input name="password" type="password" placeholder="Password (optional)" autocomplete="new-password" />
        <input name="channels" type="number" min="1" max="${MAX_NVR_SLOTS}" value="4" required aria-label="Camera channels" />
        <input name="streamPath" placeholder="Stream path template (optional, e.g. /Streaming/Channels/{channel}01)" maxlength="200" autocomplete="off" />
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
    els.moduleContent.innerHTML = `<div id="accCharts"></div><div id="catalogResults" class="catalog-results-loading"><p class="empty">Loading detected items…</p></div>`;
    renderAnalytics(els.moduleContent.querySelector("#accCharts"), true);
    void renderCatalogResults(els.moduleContent.querySelector("#catalogResults"));
    return;
  }

  if (menu.id === "feed") {
    if (!config.nvrs.length) {
      els.moduleContent.innerHTML = `<p class="empty">No NVRs connected — set one up in Camera Control first.</p>`;
      return;
    }
    const sections = config.nvrs
      .map((nvr) => {
        const channels = nvr.channelsDetail || [];
        const tiles = channels.length
          ? channels
              .map((channel) => {
                if (channel.active && channel.slot_number != null) {
                  return `<figure><span class="feed-transmitting">Transmitting live</span><img data-live-frame data-live-slot="${channel.slot_number}" src="${API_BASE}/api/live_frame?slot=${channel.slot_number}&v=${Date.now()}" alt="${escapeHtml(nvr.name)} channel ${channel.channel}" /><figcaption>${escapeHtml(nvr.name)} · channel ${channel.channel}</figcaption></figure>`;
                }
                return `<figure class="feed-empty"><div>${escapeHtml(channel.message || "No signal yet")}</div><figcaption>${escapeHtml(nvr.name)} · channel ${channel.channel}</figcaption></figure>`;
              })
              .join("")
          : `<figure class="feed-empty"><div>Remove and re-add this NVR to reconnect it</div><figcaption>${escapeHtml(nvr.name)}</figcaption></figure>`;
        return `<section class="acc-block"><h3>${escapeHtml(nvr.name)} <small class="muted">(${channels.length || nvr.channels || 0} channels)</small></h3><div class="live-preview">${tiles}</div></section>`;
      })
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">Live transmission at ${escapeHtml((QUALITY_OPTIONS.find((option) => option.id === config.quality) || QUALITY_OPTIONS[2]).label)} quality. This view is not recording continuous video.</p>
      ${sections}
    `;
    return;
  }

  if (menu.id === "ai") {
    els.moduleContent.innerHTML = `<p class="empty">Loading AI catalog…</p>`;
    void renderCatalogEnrollment(els.moduleContent);
    return;
  }

  if (menu.id === "dimension") {
    els.moduleContent.innerHTML = `<p class="empty">Loading 3D recognition results…</p>`;
    void renderCatalogDimensions(els.moduleContent);
    return;
  }
}

async function handleAccountSubmit(event) {
  const form = event.target.closest("[data-acc-form]");
  if (!form || !accountState) return;
  event.preventDefault();
  const { company } = accountState;
  companyConfig(company);

  if (form.dataset.accForm === "catalog-product") {
    const name = form.elements.name.value.trim();
    const files = Array.from(form.elements.images.files || []);
    if (!name || files.length < 2) {
      toast("Add an item name and at least two reference images.");
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Adding item…";
    const payload = new FormData();
    payload.append("scope_id", catalogScopeId());
    payload.append("name", name);
    files.forEach((file) => payload.append("files", file));
    try {
      await catalogRequest("/api/catalog/items", { method: "POST", body: payload });
      toast(`"${name}" added with ${files.length} reference images.`);
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
      submit.textContent = "Add item to AI catalog";
    }
    return;
  }

  if (form.dataset.accForm !== "nvr") return;
  if (company.cameraConfig.nvrs.length >= MAX_NVRS) return;
  const name = form.elements.name.value.trim();
  const channels = Math.min(MAX_NVR_SLOTS, Math.max(1, Number(form.elements.channels.value) || 1));
  // The host field also accepts "host:port" or a full rtsp://user:pass@host:port/path
  // URL pasted straight from an NVR's spec sheet, so a port typed there (instead of the
  // dedicated Port field) doesn't silently fall back to the protocol default.
  const parsedHost = parseNvrConnectionInput(form.elements.host.value);
  const host = parsedHost.host;
  const protocol = form.elements.protocol.value;
  const port = Number(form.elements.port.value) || parsedHost.port || null;
  const username = form.elements.username.value.trim() || parsedHost.username || "";
  const password = form.elements.password.value || parsedHost.password || "";
  const streamPath =
    form.elements.streamPath.value.trim() || (channels === 1 && parsedHost.path) || "";
  if (!name || !host) return;

  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = "Connecting…";
  try {
    const registration = await registerNvrController({
      name,
      host,
      protocol,
      port,
      username,
      password,
      channels,
      streamPath,
    });
    const previousNvrs = company.cameraConfig.nvrs;
    const newNvr = {
      id: newId(),
      name,
      host,
      protocol,
      port: registration.port,
      channels,
      controllerMessage: registration.controllerMessage,
      channelsDetail: registration.channelsDetail,
    };
    company.cameraConfig.nvrs = [...previousNvrs, newNvr];
    try {
      await persistAccountCompany();
      const transmitting = registration.channelsDetail.filter((channel) => channel.active).length;
      const waiting = registration.channelsDetail.filter(
        (channel) => !channel.active && channel.status === "connected"
      ).length;
      if (transmitting > 0 && waiting > 0) {
        toast(
          `NVR "${name}" connected — ${transmitting}/${channels} channels transmitting, ` +
            `${waiting} registered but waiting for a free slot.`
        );
      } else if (transmitting > 0) {
        toast(`NVR "${name}" connected — ${transmitting}/${channels} channels transmitting.`);
      } else if (waiting > 0) {
        toast(
          `NVR "${name}" reachable, but no free camera slots are available right now — ` +
            `${waiting} channels are registered and will activate once a slot frees up.`
        );
      } else {
        toast(`NVR "${name}" saved but not reachable: ${registration.controllerMessage}`);
      }
    } catch (error) {
      company.cameraConfig.nvrs = previousNvrs;
      await deleteNvrCameras(newNvr);
      toast(error.message);
    }
  } catch (error) {
    toast(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Add NVR";
  }
  renderAccountModule();
}

async function handleAccountClick(event) {
  const button = event.target.closest("[data-acc-action]");
  if (!button || !accountState) return;
  const { company } = accountState;
  companyConfig(company);
  const action = button.dataset.accAction;

  if (action === "remove-catalog-item") {
    button.disabled = true;
    try {
      await catalogRequest(catalogApiPath(`/api/catalog/items/${encodeURIComponent(button.dataset.product)}`), {
        method: "DELETE",
      });
      toast("Catalog item removed.");
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
    return;
  }

  if (action !== "remove-nvr" && action !== "quality") return;
  const previousConfig = { ...company.cameraConfig, nvrs: [...company.cameraConfig.nvrs] };
  let removedNvr = null;
  if (action === "remove-nvr") {
    removedNvr = company.cameraConfig.nvrs.find((nvr) => nvr.id === button.dataset.nvr) || null;
    company.cameraConfig.nvrs = company.cameraConfig.nvrs.filter((nvr) => nvr.id !== button.dataset.nvr);
  } else {
    company.cameraConfig.quality = button.dataset.quality;
  }
  try {
    await persistAccountCompany();
    if (removedNvr) await deleteNvrCameras(removedNvr);
  } catch (error) {
    company.cameraConfig = previousConfig;
    toast(error.message);
  }
  renderAccountModule();
}

function handleCatalogImageChange(event) {
  const input = event.target.closest('input[name="images"][multiple]');
  if (!input) return;
  const label = input.closest("label")?.querySelector("[data-image-count]");
  if (!label) return;
  const count = input.files?.length || 0;
  label.textContent = count ? `${count} images selected${count < 2 ? " — add at least one more" : " ✓"}` : "Choose at least 2 clear images from different angles.";
}

function renderAccountView({ company, role, missing, error }) {
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
    if (error) {
      els.activeModuleTitle.textContent = "Couldn't load this account";
      els.moduleContent.innerHTML = `
        <p class="empty">${escapeHtml(error)} Check your connection and try refreshing — this is not
        the same as the account being deleted.</p>
        <button type="button" data-retry-dashboard>Try again</button>
      `;
    } else {
      els.activeModuleTitle.textContent = "Account not found";
      els.moduleContent.innerHTML = `
        <p class="empty">This account link doesn't match any saved account. It may have been deleted,
        mistyped, or created before this dashboard moved account storage to the server — ask an admin
        to open Company Control and copy the current link for this account.</p>
      `;
    }
    return;
  }

  accountState = { company, role };
  if (!accountModule && role.access?.camera) accountModule = "feed";
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

function currentOperationalAlerts() {
  const summary = state.overview?.summary || {};
  const health = state.overview?.health || {};
  const cameraCount = Number(health.camera_count || 0);

  if (health.error) {
    return [{ title: "Detector error", where: String(health.error), sev: "critical", color: "#dc2626" }];
  }
  if (!summary.detector_running) {
    return [{ title: "Detector stopped", where: "Camera processing is not running", sev: "critical", color: "#dc2626" }];
  }
  if (cameraCount === 0) {
    return [{ title: "No camera feeds connected", where: "Detector is running without an active feed", sev: "high", color: "var(--bad)" }];
  }
  if (!health.last_frame_at) {
    return [{ title: "Waiting for camera frames", where: `${cameraCount} camera feed${cameraCount === 1 ? "" : "s"} connecting`, sev: "medium", color: "var(--warn)" }];
  }
  return [];
}

function renderAnalytics(container, catalogMode = false) {
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

  const alerts = currentOperationalAlerts();
  const health = state.overview?.health || {};
  const cameraCount = Number(health.camera_count || 0);
  const resources = [
    { name: "CPU Usage", pct: 42, color: "#2a78d6" },
    { name: "GPU Usage", pct: 67, color: "#7c3aed" },
    { name: "Storage Usage", pct: 58, color: "#0891b2" },
    { name: "Memory Usage", pct: 71, color: "#db2777" },
  ];
  container.innerHTML = `
    <p class="chart-note">${catalogMode ? "Operational overview with scheduled catalog recognition results below." : "Sample data — analytics endpoints are not wired to the backend yet."}</p>
    <div class="chart-grid">${specs.map(chartCardHtml).join("")}</div>
    <div class="ov-grid">
      <section class="ov-card">
        <h3>Active Alerts</h3>
        ${alerts.length
          ? alerts
              .map(
                (alert) => `
              <div class="alert-row">
                <span class="alert-dot" style="background:${alert.color}"></span>
                <div class="alert-main"><strong>${escapeHtml(alert.title)}</strong><small>${escapeHtml(alert.where)}</small></div>
                <span class="sev-chip ${alert.sev}">${alert.sev.charAt(0).toUpperCase() + alert.sev.slice(1)}</span>
              </div>
            `
              )
              .join("")
          : `<div class="alert-empty-state">
              <span class="alert-dot" style="background:var(--good)"></span>
              <div class="alert-main">
                <strong>No active alerts</strong>
                <small>Detector running · ${cameraCount} camera feed${cameraCount === 1 ? "" : "s"} connected</small>
              </div>
            </div>`}
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
  const [session, overview] = await Promise.all([
    api("/api/v2/rbac/me"),
    api("/api/v2/head/overview"),
  ]);
  state.session = session;
  state.overview = overview;
  const account = await resolveAccountFromHash();
  if (account) {
    renderAccountView(account);
    return;
  }
  els.pageTitle.textContent = "Head Dashboard";
  els.companiesSection.hidden = false;
  renderNavigation();
  renderSummary();
  renderScope();
  renderModuleContent();
}

function renderLoadFailure(error, retrying) {
  const message = error instanceof Error ? error.message : String(error || "Unknown error");
  els.scopeLine.textContent = retrying ? "Dashboard service connection interrupted — retrying…" : "Unable to load dashboard data";
  els.detectorState.textContent = retrying ? "Reconnecting…" : "Connection failed";
  els.detectorState.dataset.state = retrying ? "" : "bad";
  els.moduleContent.innerHTML = retrying
    ? `<div class="module-placeholder"><h3>Reconnecting to the dashboard service…</h3><p>The dashboard will resume automatically.</p></div>`
    : `<div class="module-placeholder">
        <h3>Dashboard data could not be loaded</h3>
        <p>${escapeHtml(message)}</p>
        <button type="button" data-retry-dashboard>Try again</button>
      </div>`;
}

async function loadDashboard(attempt = 0) {
  if (loadRetryTimer !== null) {
    window.clearTimeout(loadRetryTimer);
    loadRetryTimer = null;
  }
  try {
    await load();
    return true;
  } catch (error) {
    const retrying = attempt < LOAD_RETRY_DELAYS_MS.length;
    renderLoadFailure(error, retrying);
    if (retrying) {
      loadRetryTimer = window.setTimeout(() => loadDashboard(attempt + 1), LOAD_RETRY_DELAYS_MS[attempt]);
    } else {
      toast(error instanceof Error ? error.message : String(error));
    }
    return false;
  }
}

els.moduleContent.addEventListener("submit", (event) => {
  handleCompanySubmit(event);
  handleSettingsSubmit(event);
  handleAccountSubmit(event);
});
els.moduleContent.addEventListener("click", (event) => {
  if (event.target.closest("[data-retry-dashboard]")) {
    loadDashboard();
    return;
  }
  handleCompanyClick(event);
  handleSettingsClick(event);
  handleAccountClick(event);
});
els.moduleContent.addEventListener("input", handleCompanyInput);
els.moduleContent.addEventListener("change", handleSettingsChange);
els.moduleContent.addEventListener("change", handleCatalogImageChange);

els.sideCompanies.addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-company]");
  if (!button) return;
  const company = ccCompanyById(button.dataset.editCompany);
  if (!company) return;
  ccEditingCompany = company.id;
  ccEditValues = {
    companyName: company.name,
    roles: Object.fromEntries((company.roles || []).map((role) => [role.id, { name: role.name, login: role.login }])),
  };
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
  loadDashboard().then((loaded) => {
    if (loaded) toast("Dashboard V2 refreshed.");
  });
});

window.addEventListener("hashchange", () => window.location.reload());

const liveFrameObserver = new MutationObserver(syncLiveFrameRefresh);
liveFrameObserver.observe(els.moduleContent, { childList: true, subtree: true });
document.addEventListener("visibilitychange", syncLiveFrameRefresh);
window.addEventListener("beforeunload", stopLiveFrameRefresh);

migrateLegacyLocalStorage()
  .then((result) => {
    if (!result) return;
    if (result.companiesCreated || result.rolesCreated) {
      const companyWord = result.companiesCreated === 1 ? "company" : "companies";
      const accountWord = result.rolesCreated === 1 ? "account" : "accounts";
      toast(
        `Recovered ${result.companiesCreated} ${companyWord} and ${result.rolesCreated} ${accountWord} from this browser onto the server — open Company Control for the new links.`
      );
    } else if (result.failures) {
      toast(`Could not automatically recover ${result.failures} saved item(s) from this browser. Recreate them in Company Control.`);
    }
  })
  .catch(() => {})
  .finally(() => {
    renderSideCompanies();
    updateBrandAvatar();
    loadDashboard();
  });
