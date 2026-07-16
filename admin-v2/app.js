const els = {
  loginScreen: document.querySelector("#loginScreen"),
  loginForm: document.querySelector("#loginForm"),
  loginEmail: document.querySelector("#loginEmail"),
  loginPassword: document.querySelector("#loginPassword"),
  biometricLoginBtn: document.querySelector("#biometricLoginBtn"),
  setupPasswordBtn: document.querySelector("#setupPasswordBtn"),
  loginHint: document.querySelector("#loginHint"),
  refreshBtn: document.querySelector("#refreshBtn"),
  stats: document.querySelector("#overview"),
  userForm: document.querySelector("#userForm"),
  userName: document.querySelector("#userName"),
  userEmail: document.querySelector("#userEmail"),
  usersTable: document.querySelector("#usersTable"),
  selectedUser: document.querySelector("#selectedUser"),
  roleSelect: document.querySelector("#roleSelect"),
  passwordInput: document.querySelector("#passwordInput"),
  setPasswordBtn: document.querySelector("#setPasswordBtn"),
  saveAuthPreferenceBtn: document.querySelector("#saveAuthPreferenceBtn"),
  registerPasskeyBtn: document.querySelector("#registerPasskeyBtn"),
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
let ADMIN_EMAIL = localStorage.getItem("ai_v2_admin_email") || "admin@ai-vision.local";
let AUTH_TOKEN = localStorage.getItem("ai_v2_admin_token") || "";
let state = { users: [], roles: [], permissions: [], modules: [], overview: null };

const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const toast = (message) => {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 2200);
};
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : { "X-AI-User-Email": ADMIN_EMAIL }) };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
const bufferToBase64Url = (buffer) => btoa(String.fromCharCode(...new Uint8Array(buffer))).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
const base64UrlToBuffer = (value) => {
  const base64 = String(value).replaceAll("-", "+").replaceAll("_", "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0)).buffer;
};
function publicKeyForGet(options) {
  const publicKey = { ...options.publicKey };
  publicKey.challenge = base64UrlToBuffer(publicKey.challenge);
  publicKey.allowCredentials = (publicKey.allowCredentials || []).map((credential) => ({ ...credential, id: base64UrlToBuffer(credential.id) }));
  return publicKey;
}
function publicKeyForCreate(options) {
  const publicKey = { ...options.publicKey };
  publicKey.challenge = base64UrlToBuffer(publicKey.challenge);
  publicKey.user = { ...publicKey.user, id: base64UrlToBuffer(publicKey.user.id) };
  publicKey.excludeCredentials = (publicKey.excludeCredentials || []).map((credential) => ({ ...credential, id: base64UrlToBuffer(credential.id) }));
  return publicKey;
}
function credentialForServer(credential) {
  const response = {
    clientDataJSON: bufferToBase64Url(credential.response.clientDataJSON),
  };
  if (credential.response.attestationObject) response.attestationObject = bufferToBase64Url(credential.response.attestationObject);
  if (credential.response.authenticatorData) response.authenticatorData = bufferToBase64Url(credential.response.authenticatorData);
  if (credential.response.signature) response.signature = bufferToBase64Url(credential.response.signature);
  if (credential.response.userHandle) response.userHandle = bufferToBase64Url(credential.response.userHandle);
  return { id: credential.id, rawId: bufferToBase64Url(credential.rawId), type: credential.type, response };
}
function saveAuth(result) {
  AUTH_TOKEN = result.token;
  ADMIN_EMAIL = result.user?.email || ADMIN_EMAIL;
  localStorage.setItem("ai_v2_admin_token", AUTH_TOKEN);
  localStorage.setItem("ai_v2_admin_email", ADMIN_EMAIL);
  els.loginScreen.classList.add("hidden");
}

async function load() {
  const [bootstrap, overview] = await Promise.all([api("/api/v2/admin/bootstrap"), api("/api/v2/admin/overview")]);
  state = { ...bootstrap, overview };
  render();
}

function render() {
  const totals = state.overview?.totals || {};
  els.stats.innerHTML = Object.entries(totals)
    .map(([key, value]) => `<article class="stat-card"><span>${esc(key.replaceAll("_", " "))}</span><strong>${esc(value)}</strong><small>Current platform metric</small></article>`)
    .join("");
  els.usersTable.innerHTML = state.users
    .map((user) => `<tr>
      <td><strong>${esc(user.name)}</strong><small>${esc(user.email)}</small></td>
      <td><span class="badge ${user.status === "active" ? "good" : "bad"}">${esc(user.status)}</span></td>
      <td>
        <span class="role-line">${esc((user.roles || []).join(", ") || "No role")}</span>
        <small>${user.has_password ? "Password set" : "No password"} · ${esc(user.passkey_count || 0)} passkey(s)</small>
        <small>Preferred: ${esc((user.preferred_auth_method || "biometric_first").replaceAll("_", " "))}</small>
      </td>
      <td>
        <div class="table-actions">
          <button data-user="${user.id}" data-action="disable">Disable</button>
          <button data-user="${user.id}" data-action="reactivate">Reactivate</button>
          <a href="/app-v2?user_email=${encodeURIComponent(user.email)}">Open app</a>
        </div>
      </td>
    </tr>`)
    .join("");
  els.selectedUser.innerHTML = state.users.map((user) => `<option value="${user.id}">${esc(user.name)} (${esc(user.email)})</option>`).join("");
  syncAuthPreference();
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
const selectedUser = () => state.users.find((user) => Number(user.id) === selectedUserId());
const selectedAuthPreference = () => document.querySelector("input[name='authPreference']:checked")?.value || "biometric_first";
function syncAuthPreference() {
  const preference = selectedUser()?.preferred_auth_method || "biometric_first";
  document.querySelectorAll("input[name='authPreference']").forEach((input) => {
    input.checked = input.value === preference;
  });
}
els.refreshBtn.addEventListener("click", () => load().then(() => toast("Refreshed")).catch((e) => toast(e.message)));
els.selectedUser.addEventListener("change", syncAuthPreference);
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
els.setPasswordBtn.addEventListener("click", async () => {
  await api(`/api/v2/admin/users/${selectedUserId()}/password`, { method: "POST", body: JSON.stringify({ password: els.passwordInput.value }) });
  els.passwordInput.value = "";
  await load();
  toast("Password set");
});
els.saveAuthPreferenceBtn.addEventListener("click", async () => {
  await api(`/api/v2/admin/users/${selectedUserId()}/auth-preference`, { method: "POST", body: JSON.stringify({ preferred_auth_method: selectedAuthPreference() }) });
  await load();
  toast("Login preference saved");
});
els.registerPasskeyBtn.addEventListener("click", () => registerPasskey().catch((e) => toast(e.message)));
async function registerPasskey() {
  if (!window.PublicKeyCredential) throw new Error("This browser does not support Fingerprint / Face ID passkeys.");
  const options = await api("/api/v2/auth/passkeys/register/options", { method: "POST", body: JSON.stringify({ name: "Primary biometric device" }) });
  const credential = await navigator.credentials.create({ publicKey: publicKeyForCreate(options) });
  await api("/api/v2/auth/passkeys/register/verify", {
    method: "POST",
    body: JSON.stringify({ challenge_id: options.challenge_id, credential: credentialForServer(credential), name: "Primary biometric device" }),
  });
  await load();
  toast("Fingerprint / Face ID registered");
}
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
async function loginWithPassword(event) {
  event.preventDefault();
  const result = await api("/api/v2/auth/login", { method: "POST", body: JSON.stringify({ email: els.loginEmail.value, password: els.loginPassword.value }) });
  if (result.requires_passkey) {
    await finishPasskeyLogin(result, els.loginEmail.value);
    return;
  }
  saveAuth(result);
  await load();
  toast("Logged in");
}
async function loginWithBiometric() {
  if (!window.PublicKeyCredential) throw new Error("This browser does not support Fingerprint / Face ID passkeys.");
  const email = els.loginEmail.value || ADMIN_EMAIL;
  els.loginEmail.value = email;
  const options = await api("/api/v2/auth/login/passkey/options", { method: "POST", body: JSON.stringify({ email }) });
  await finishPasskeyLogin(options, email);
}
async function finishPasskeyLogin(options, email) {
  const credential = await navigator.credentials.get({ publicKey: publicKeyForGet(options) });
  const result = await api("/api/v2/auth/login/passkey", {
    method: "POST",
    body: JSON.stringify({ email, challenge_id: options.challenge_id, credential: credentialForServer(credential) }),
  });
  saveAuth(result);
  await load();
  toast("Biometric login complete");
}
els.loginForm.addEventListener("submit", (event) => loginWithPassword(event).catch((e) => {
  els.loginHint.textContent = e.message;
  toast(e.message);
}));
els.biometricLoginBtn.addEventListener("click", () => loginWithBiometric().catch((e) => {
  els.loginHint.textContent = e.message;
  toast(e.message);
}));
els.setupPasswordBtn.addEventListener("click", () => setupFirstPassword().catch((e) => {
  els.loginHint.textContent = e.message;
  toast(e.message);
}));
async function setupFirstPassword() {
  const result = await api("/api/v2/auth/setup-password", { method: "POST", body: JSON.stringify({ email: els.loginEmail.value, password: els.loginPassword.value }) });
  saveAuth(result);
  await load();
  toast("First password set");
}
els.loginEmail.value = ADMIN_EMAIL;
if (AUTH_TOKEN) {
  els.loginScreen.classList.add("hidden");
  load().catch((e) => {
    localStorage.removeItem("ai_v2_admin_token");
    AUTH_TOKEN = "";
    els.loginScreen.classList.remove("hidden");
    toast(e.message);
  });
}
