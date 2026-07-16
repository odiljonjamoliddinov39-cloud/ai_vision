const els = {
  loginScreen: document.querySelector("#loginScreen"),
  loginForm: document.querySelector("#loginForm"),
  loginEmail: document.querySelector("#loginEmail"),
  loginPassword: document.querySelector("#loginPassword"),
  biometricLoginBtn: document.querySelector("#biometricLoginBtn"),
  setupPasswordBtn: document.querySelector("#setupPasswordBtn"),
  loginHint: document.querySelector("#loginHint"),
  userLine: document.querySelector("#userLine"),
  moduleNav: document.querySelector("#moduleNav"),
  pageTitle: document.querySelector("#pageTitle"),
  scopeLine: document.querySelector("#scopeLine"),
  emptyState: document.querySelector("#emptyState"),
  moduleView: document.querySelector("#moduleView"),
  refreshBtn: document.querySelector("#refreshBtn"),
  toast: document.querySelector("#toast"),
};
const API_BASE = (() => {
  const params = new URLSearchParams(location.search);
  if (params.get("api")) localStorage.setItem("ai_v2_api", params.get("api").replace(/\/+$/, ""));
  if (params.get("user_email")) localStorage.setItem("ai_v2_user_email", params.get("user_email"));
  return localStorage.getItem("ai_v2_api") || (location.hostname.endsWith("vercel.app") ? "https://ai-vision-backend-nasoe.ondigitalocean.app" : location.origin);
})();
let USER_EMAIL = localStorage.getItem("ai_v2_user_email") || "blank@ai-vision.local";
let AUTH_TOKEN = localStorage.getItem("ai_v2_token") || "";
let dashboard = null;
let activeModule = null;
const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const toast = (message) => { els.toast.textContent = message; els.toast.classList.add("show"); setTimeout(() => els.toast.classList.remove("show"), 2200); };
async function api(path) {
  const headers = AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : { "X-AI-User-Email": USER_EMAIL };
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
async function apiPost(path, body) {
  const headers = { "Content-Type": "application/json", ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}) };
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: JSON.stringify(body || {}) });
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
function credentialForServer(credential) {
  return {
    id: credential.id,
    rawId: bufferToBase64Url(credential.rawId),
    type: credential.type,
    response: {
      authenticatorData: bufferToBase64Url(credential.response.authenticatorData),
      clientDataJSON: bufferToBase64Url(credential.response.clientDataJSON),
      signature: bufferToBase64Url(credential.response.signature),
      userHandle: credential.response.userHandle ? bufferToBase64Url(credential.response.userHandle) : null,
    },
  };
}
function saveAuth(result) {
  AUTH_TOKEN = result.token;
  USER_EMAIL = result.user?.email || USER_EMAIL;
  localStorage.setItem("ai_v2_token", AUTH_TOKEN);
  localStorage.setItem("ai_v2_user_email", USER_EMAIL);
  els.loginScreen.classList.add("hidden");
}
async function load() {
  dashboard = await api(`/api/v2/me/dashboard?user_email=${encodeURIComponent(USER_EMAIL)}`);
  if (!activeModule || !(dashboard.modules || []).some((m) => m.code === activeModule)) {
    activeModule = dashboard.modules?.[0]?.code || null;
  }
  render();
  if (activeModule) await renderModule(activeModule);
}
function render() {
  const user = dashboard.user || {};
  els.userLine.textContent = `${user.name || "Unassigned"} • ${user.email || USER_EMAIL}`;
  els.scopeLine.textContent = `Scope: ${JSON.stringify(dashboard.scope || {})}`;
  const modules = dashboard.modules || [];
  els.emptyState.classList.toggle("hidden", modules.length > 0);
  els.moduleView.classList.toggle("hidden", modules.length === 0);
  els.moduleNav.innerHTML = modules.map((m) => `<button class="${m.code === activeModule ? "active" : ""}" data-module="${m.code}"><span>${esc(m.name)}</span><small>${esc(m.required_permission)}</small></button>`).join("");
  if (!modules.length) {
    els.pageTitle.textContent = "Empty dashboard";
    els.moduleView.innerHTML = "";
  }
}
async function loginWithPassword(event) {
  event.preventDefault();
  const result = await apiPost("/api/v2/auth/login", { email: els.loginEmail.value, password: els.loginPassword.value });
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
  const email = els.loginEmail.value || USER_EMAIL;
  els.loginEmail.value = email;
  const options = await apiPost("/api/v2/auth/login/passkey/options", { email });
  await finishPasskeyLogin(options, email);
}
async function finishPasskeyLogin(options, email) {
  const credential = await navigator.credentials.get({ publicKey: publicKeyForGet(options) });
  const result = await apiPost("/api/v2/auth/login/passkey", {
    email,
    challenge_id: options.challenge_id,
    credential: credentialForServer(credential),
  });
  saveAuth(result);
  await load();
  toast("Biometric login complete");
}
async function renderModule(code) {
  const module = dashboard.modules.find((m) => m.code === code);
  els.pageTitle.textContent = module?.name || "Access denied";
  els.moduleNav.querySelectorAll("button").forEach((btn) => btn.classList.toggle("active", btn.dataset.module === code));
  let data;
  try {
    data = await api(`/api/v2/me/module/${encodeURIComponent(code)}?user_email=${encodeURIComponent(USER_EMAIL)}`);
  } catch (error) {
    els.moduleView.innerHTML = `<h2>Access denied</h2><p>${esc(error.message)}</p>`;
    return;
  }
  if (code === "live_monitoring") {
    const cameras = data.cameras || [];
    els.moduleView.innerHTML = `<h2>Live Monitoring</h2><div class="live-grid">${cameras.map((cam) => `<figure><img src="${API_BASE}/api/live_frame?slot=${cam.slot_number}&t=${Date.now()}" /><figcaption>Slot ${esc(cam.slot_number)} — ${esc(cam.name)}</figcaption></figure>`).join("") || "<p>No scoped cameras assigned.</p>"}</div>`;
    return;
  }
  if (code === "counting" || code === "products") {
    const stock = data.stock || [];
    els.moduleView.innerHTML = `<h2>${esc(module.name)}</h2><table><tbody>${stock.map((item) => `<tr><td>${esc(item.name)}</td><td>${esc(item.current_stock)}</td></tr>`).join("") || "<tr><td>No stock yet.</td></tr>"}</tbody></table>`;
    return;
  }
  if (code === "reports" || code === "activity_history") {
    els.moduleView.innerHTML = `<h2>${esc(module.name)}</h2><pre>${esc(JSON.stringify(data.movements || [], null, 2))}</pre>`;
    return;
  }
  els.moduleView.innerHTML = `<h2>${esc(module.name)}</h2><p>${esc(data.message || "Module assigned and ready.")}</p><pre>${esc(JSON.stringify(data, null, 2))}</pre>`;
}
els.moduleNav.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-module]");
  if (!button) return;
  activeModule = button.dataset.module;
  await renderModule(activeModule);
});
els.refreshBtn.addEventListener("click", () => load().then(() => toast("Refreshed")).catch((e) => toast(e.message)));
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
  const result = await apiPost("/api/v2/auth/setup-password", { email: els.loginEmail.value, password: els.loginPassword.value });
  saveAuth(result);
  await load();
  toast("First password set");
}
els.loginEmail.value = USER_EMAIL;
if (AUTH_TOKEN) {
  els.loginScreen.classList.add("hidden");
  load().catch((e) => {
    localStorage.removeItem("ai_v2_token");
    AUTH_TOKEN = "";
    els.loginScreen.classList.remove("hidden");
    toast(e.message);
  });
}
