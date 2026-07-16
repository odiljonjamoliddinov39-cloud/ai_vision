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
  els.scopeLine.textContent = formatScope(dashboard.scope || {});
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
  if (code === "home") {
    const user = dashboard.user || {};
    els.moduleView.innerHTML = `
      <div class="operator-dashboard">
        <section class="welcome-panel">
          <div>
            <p class="section-kicker">Shift workspace</p>
            <h2>Good morning, ${esc(user.name || "Operator")}</h2>
            <p>Here is today’s warehouse vision summary.</p>
          </div>
          <span class="status-pill">Morning shift</span>
        </section>
        <section class="metric-grid">
          ${metricCard("Current Shift", "Morning Shift", "08:00 - 16:00")}
          ${metricCard("Target", "5,000", "units")}
          ${metricCard("Counted", "3,740", "units")}
          ${metricCard("Progress", "74.8%", "on target")}
          ${metricCard("Current Rate", "420", "units/hr")}
          ${metricCard("Cameras Online", "4 / 4", "all cameras live")}
          ${metricCard("Boxes Counted", "320", "today")}
          ${metricCard("Last Sync", new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), "live")}
        </section>
        <section class="ops-grid">
          <article class="chart-card wide-chart">
            <div class="module-head"><div><p class="section-kicker">Production</p><h2>Production Overview</h2></div><span class="status-pill">Today</span></div>
            <div class="line-chart"><span style="height:28%"></span><span style="height:36%"></span><span style="height:42%"></span><span style="height:51%"></span><span style="height:57%"></span><span style="height:66%"></span><span style="height:72%"></span><span style="height:82%"></span></div>
          </article>
          <article class="chart-card">
            <div class="module-head"><div><p class="section-kicker">Products</p><h2>Top Products</h2></div></div>
            <div class="donut-card"><div class="donut">3,740<br><small>Total</small></div><ul><li>EPS Panel 50mm</li><li>EPS Panel 100mm</li><li>EPS Block</li></ul></div>
          </article>
        </section>
      </div>`;
    return;
  }
  if (code === "live_monitoring") {
    const cameras = data.cameras || [];
    els.moduleView.innerHTML = `<div class="module-head"><div><p class="section-kicker">Camera grid</p><h2>Live Monitoring</h2></div><span class="status-pill">${esc(cameras.length)} feed(s)</span></div><div class="live-grid">${cameras.map((cam) => `<figure><div class="feed-top"><span>Slot ${esc(cam.slot_number)}</span><strong>${esc(cam.name)}</strong></div><img src="${API_BASE}/api/live_frame?slot=${cam.slot_number}&t=${Date.now()}" /><figcaption><span class="badge good">Detection frame</span><small>${esc(cam.status || "active")}</small></figcaption></figure>`).join("") || "<p>No scoped cameras assigned.</p>"}</div>`;
    return;
  }
  if (code === "counting" || code === "products") {
    const stock = data.stock || [];
    els.moduleView.innerHTML = `<div class="module-head"><div><p class="section-kicker">Inventory</p><h2>${esc(module.name)}</h2></div><span class="status-pill">${esc(stock.length)} item(s)</span></div><table><tbody>${stock.map((item) => `<tr><td>${esc(item.name)}</td><td>${esc(item.current_stock)}</td></tr>`).join("") || "<tr><td>No stock yet.</td></tr>"}</tbody></table>`;
    return;
  }
  if (code === "reports" || code === "activity_history") {
    els.moduleView.innerHTML = `<div class="module-head"><div><p class="section-kicker">History</p><h2>${esc(module.name)}</h2></div></div><pre>${esc(JSON.stringify(data.movements || [], null, 2))}</pre>`;
    return;
  }
  els.moduleView.innerHTML = `<div class="module-head"><div><p class="section-kicker">Module</p><h2>${esc(module.name)}</h2></div><span class="status-pill">Assigned</span></div><p>${esc(data.message || "Module assigned and ready.")}</p><pre>${esc(JSON.stringify(data, null, 2))}</pre>`;
}
function metricCard(label, value, note) {
  return `<article class="metric-card"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
}
function formatScope(scope) {
  const cameraCount = (scope.camera_ids || []).length;
  const warehouseCount = (scope.warehouse_ids || []).length;
  if (!cameraCount && !warehouseCount) return "Warehouse scope: all assigned operations";
  return `Warehouse scope: ${warehouseCount || "all"} warehouse(s), ${cameraCount || "all"} camera(s)`;
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
