const els = {
  surfaceButtons: Array.from(document.querySelectorAll("[data-surface]")),
  roleSelect: document.querySelector("#roleSelect"),
  moduleNav: document.querySelector("#moduleNav"),
  pageTitle: document.querySelector("#pageTitle"),
  scopeLine: document.querySelector("#scopeLine"),
  summaryGrid: document.querySelector("#summaryGrid"),
  activeModuleEyebrow: document.querySelector("#activeModuleEyebrow"),
  activeModuleTitle: document.querySelector("#activeModuleTitle"),
  moduleContent: document.querySelector("#moduleContent"),
  detectorState: document.querySelector("#detectorState"),
  rbacList: document.querySelector("#rbacList"),
  integrationList: document.querySelector("#integrationList"),
  refreshBtn: document.querySelector("#refreshBtn"),
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
    return "https://ai-vision-backend-nasoe.ondigitalocean.app";
  }
  return window.location.origin;
})();

const state = {
  surface: localStorage.getItem("ai_vision_v2_surface") || "head",
  role: localStorage.getItem("ai_vision_v2_role") || "super_admin",
  activeModule: null,
  session: null,
  overview: null,
};

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

function renderRoles() {
  const roles = state.session?.available_roles || [];
  els.roleSelect.innerHTML = roles
    .map((role) => `<option value="${role.id}" ${role.id === state.role ? "selected" : ""}>${role.label}</option>`)
    .join("");
}

function renderShell() {
  els.surfaceButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.surface === state.surface);
  });
  els.pageTitle.textContent = state.surface === "head" ? "Head Dashboard" : "User Dashboard";
}

function renderNavigation() {
  const modules = state.session?.surfaces?.[state.surface] || [];
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
          <span>${escapeHtml(module.label)}</span>
          <small>${escapeHtml(permissionLabels[module.permission] || module.permission)}</small>
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
  ];
  if (state.surface === "head") {
    cards.push(["Saved cameras", summary.saved_cameras ?? 0], ["Audit verified", summary.audit_verified ? "Yes" : "No"]);
  } else {
    cards.push(["Verification tasks", summary.open_verification_tasks ?? 0], ["Active alerts", summary.active_alerts ?? 0]);
  }
  els.summaryGrid.innerHTML = cards
    .map(([label, value]) => `<article class="stat-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join("");
  const running = Boolean(summary.detector_running);
  els.detectorState.textContent = running ? "Detector running" : "Detector stopped";
  els.detectorState.dataset.state = running ? "good" : "bad";
}

function renderRbac() {
  const session = state.session;
  if (!session) return;
  const scope = session.scope || {};
  els.scopeLine.textContent = `${session.role_label} • ${scope.company} / ${scope.factory} / ${scope.warehouse}`;
  const permissions = (session.permissions || [])
    .slice(0, 12)
    .map((permission) => `<span>${escapeHtml(permissionLabels[permission] || permission)}</span>`)
    .join("");
  els.rbacList.innerHTML = `
    <dt>User</dt><dd>${escapeHtml(session.user?.name)}</dd>
    <dt>Role</dt><dd>${escapeHtml(session.role_label)}</dd>
    <dt>Scope</dt><dd>${escapeHtml(scope.company)} → ${escapeHtml(scope.factory)} → ${escapeHtml(scope.warehouse)}</dd>
    <dt>Permissions</dt><dd class="permission-cloud">${permissions}</dd>
  `;
}

function renderIntegrations() {
  const integrations = state.overview?.future_integrations || [
    "ERP",
    "HRM",
    "CRM",
    "Inventory Management",
    "Quality Control",
    "Predictive Analytics",
    "Multi-site Management",
    "API Integrations",
  ];
  els.integrationList.innerHTML = integrations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderModuleContent() {
  const modules = state.session?.surfaces?.[state.surface] || [];
  const module = modules.find((item) => item.id === state.activeModule);
  els.activeModuleTitle.textContent = module?.label || "Unavailable";
  els.activeModuleEyebrow.textContent = state.surface === "head" ? "Head module" : "User module";

  const summary = state.overview?.summary || {};
  const stock = state.overview?.stock || [];
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
    els.moduleContent.innerHTML = `
      <div class="split-content">
        <div>
          <h3>Operational status</h3>
          <p>Detector state, camera reachability, counts, and inventory signals are pulled from the current AI Vision backend.</p>
          <ul>
            <li>Last frame: ${escapeHtml(summary.last_frame_at || health.last_frame_at || "Waiting")}</li>
            <li>Tracked objects: ${escapeHtml(summary.last_tracked_count ?? health.last_tracked_count ?? 0)}</li>
            <li>Movement IN: ${escapeHtml(state.overview?.movement_counts?.IN ?? 0)}</li>
            <li>Movement OUT: ${escapeHtml(state.overview?.movement_counts?.OUT ?? 0)}</li>
          </ul>
        </div>
        <div>
          <h3>Recent products</h3>
          ${stock.length ? `<table><tbody>${stock.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.current_stock)}</td></tr>`).join("")}</tbody></table>` : `<p class="empty">No stock rows yet.</p>`}
        </div>
      </div>
    `;
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

async function load() {
  renderShell();
  const [session, overview] = await Promise.all([
    api("/api/v2/rbac/me"),
    api(state.surface === "head" ? "/api/v2/head/overview" : "/api/v2/user/overview"),
  ]);
  state.session = session;
  state.overview = overview;
  renderRoles();
  renderNavigation();
  renderSummary();
  renderRbac();
  renderIntegrations();
  renderModuleContent();
}

els.surfaceButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    state.surface = button.dataset.surface;
    localStorage.setItem("ai_vision_v2_surface", state.surface);
    state.activeModule = null;
    await load().catch((error) => toast(error.message));
  });
});

els.moduleNav.addEventListener("click", (event) => {
  const button = event.target.closest("[data-module]");
  if (!button) return;
  state.activeModule = button.dataset.module;
  renderNavigation();
  renderModuleContent();
});

els.roleSelect.addEventListener("change", async () => {
  state.role = els.roleSelect.value;
  localStorage.setItem("ai_vision_v2_role", state.role);
  state.activeModule = null;
  await load().catch((error) => toast(error.message));
});

els.refreshBtn.addEventListener("click", () => {
  load().then(() => toast("Dashboard V2 refreshed.")).catch((error) => toast(error.message));
});

load().catch((error) => toast(error.message));
