const els = {
  refreshBtn: document.querySelector("#refreshBtn"),
  stats: document.querySelector("#overview"),
  userForm: document.querySelector("#userForm"),
  userName: document.querySelector("#userName"),
  userEmail: document.querySelector("#userEmail"),
  usersTable: document.querySelector("#usersTable"),
  selectedUser: document.querySelector("#selectedUser"),
  roleSelect: document.querySelector("#roleSelect"),
  moduleSelect: document.querySelector("#moduleSelect"),
  permissionSelect: document.querySelector("#permissionSelect"),
  assignRoleBtn: document.querySelector("#assignRoleBtn"),
  allowModuleBtn: document.querySelector("#allowModuleBtn"),
  denyModuleBtn: document.querySelector("#denyModuleBtn"),
  allowPermissionBtn: document.querySelector("#allowPermissionBtn"),
  denyPermissionBtn: document.querySelector("#denyPermissionBtn"),
  scopeType: document.querySelector("#scopeType"),
  scopeIds: document.querySelector("#scopeIds"),
  assignScopeBtn: document.querySelector("#assignScopeBtn"),
  rolesList: document.querySelector("#rolesList"),
  modulesList: document.querySelector("#modulesList"),
  auditLog: document.querySelector("#auditLog"),
  toast: document.querySelector("#toast"),
};

const API_BASE = (() => {
  const param = new URLSearchParams(location.search).get("api");
  if (param) localStorage.setItem("ai_v2_api", param.replace(/\/+$/, ""));
  return localStorage.getItem("ai_v2_api") || (location.hostname.endsWith("vercel.app") ? "https://ai-vision-backend-nasoe.ondigitalocean.app" : location.origin);
})();
const ADMIN_EMAIL = "admin@ai-vision.local";
let state = { users: [], roles: [], permissions: [], modules: [], overview: null };

const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const toast = (message) => {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 2200);
};
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", "X-AI-User-Email": ADMIN_EMAIL };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function load() {
  const [bootstrap, overview] = await Promise.all([api("/api/v2/admin/bootstrap"), api("/api/v2/admin/overview")]);
  state = { ...bootstrap, overview };
  render();
}

function render() {
  const totals = state.overview?.totals || {};
  els.stats.innerHTML = Object.entries(totals)
    .map(([key, value]) => `<article><span>${esc(key.replaceAll("_", " "))}</span><strong>${esc(value)}</strong></article>`)
    .join("");
  els.usersTable.innerHTML = state.users
    .map((user) => `<tr>
      <td><strong>${esc(user.name)}</strong><small>${esc(user.email)}</small></td>
      <td>${esc(user.status)}</td>
      <td>${esc((user.roles || []).join(", ") || "No role")}</td>
      <td>
        <button data-user="${user.id}" data-action="disable">Disable</button>
        <button data-user="${user.id}" data-action="reactivate">Reactivate</button>
        <a href="/app-v2?user_email=${encodeURIComponent(user.email)}">Open app</a>
      </td>
    </tr>`)
    .join("");
  els.selectedUser.innerHTML = state.users.map((user) => `<option value="${user.id}">${esc(user.name)} (${esc(user.email)})</option>`).join("");
  els.roleSelect.innerHTML = state.roles.map((role) => `<option value="${role.code}">${esc(role.name)}</option>`).join("");
  els.moduleSelect.innerHTML = state.modules.map((module) => `<option value="${module.code}">${esc(module.name)}</option>`).join("");
  els.permissionSelect.innerHTML = state.permissions.map((permission) => `<option value="${permission.code}">${esc(permission.code)}</option>`).join("");
  els.rolesList.innerHTML = state.roles.map((role) => `<li>${esc(role.name)} <small>${esc(role.code)}</small></li>`).join("");
  els.modulesList.innerHTML = state.modules
    .map((module) => `<li><strong>${esc(module.name)}</strong><span>${esc(module.route)}</span><small>${esc(module.required_permission)}</small></li>`)
    .join("");
  els.auditLog.textContent = JSON.stringify(state.overview?.recent_activity || [], null, 2);
}

const selectedUserId = () => Number(els.selectedUser.value);
els.refreshBtn.addEventListener("click", () => load().then(() => toast("Refreshed")).catch((e) => toast(e.message)));
els.userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/api/v2/admin/users", { method: "POST", body: JSON.stringify({ name: els.userName.value, email: els.userEmail.value }) });
  els.userForm.reset();
  await load();
  toast("Blank user created");
});
els.assignRoleBtn.addEventListener("click", async () => {
  await api(`/api/v2/admin/users/${selectedUserId()}/roles`, { method: "POST", body: JSON.stringify({ role_code: els.roleSelect.value }) });
  await load();
  toast("Role assigned");
});
els.allowModuleBtn.addEventListener("click", () => assignModule("allow"));
els.denyModuleBtn.addEventListener("click", () => assignModule("deny"));
async function assignModule(effect) {
  await api(`/api/v2/admin/users/${selectedUserId()}/modules`, { method: "POST", body: JSON.stringify({ module_code: els.moduleSelect.value, effect }) });
  await load();
  toast(effect === "allow" ? "Module allowed" : "Module removed");
}
els.allowPermissionBtn.addEventListener("click", () => assignPermission("allow"));
els.denyPermissionBtn.addEventListener("click", () => assignPermission("deny"));
async function assignPermission(effect) {
  await api(`/api/v2/admin/users/${selectedUserId()}/permissions`, { method: "POST", body: JSON.stringify({ permission_code: els.permissionSelect.value, effect }) });
  await load();
  toast("Permission updated");
}
els.assignScopeBtn.addEventListener("click", async () => {
  const scope_ids = els.scopeIds.value.split(",").map((item) => item.trim()).filter(Boolean);
  await api(`/api/v2/admin/users/${selectedUserId()}/scopes`, { method: "POST", body: JSON.stringify({ scope_type: els.scopeType.value, scope_ids }) });
  await load();
  toast("Scope assigned");
});
els.usersTable.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-user]");
  if (!button) return;
  await api(`/api/v2/admin/users/${button.dataset.user}/${button.dataset.action}`, { method: "POST" });
  await load();
  toast(`User ${button.dataset.action}d`);
});
load().catch((e) => toast(e.message));
