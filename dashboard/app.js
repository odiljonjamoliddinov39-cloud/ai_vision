const els = {
  pageTitle: document.querySelector("#pageTitle"),
  statusPill: document.querySelector("#statusPill"),
  refreshBtn: document.querySelector("#refreshBtn"),
  btnStartDetection: document.querySelector("#btnStartDetection"),
  btnStopDetection: document.querySelector("#btnStopDetection"),
  btnRestartDetection: document.querySelector("#btnRestartDetection"),
  navButtons: Array.from(document.querySelectorAll(".nav-btn")),
  pages: Array.from(document.querySelectorAll(".page")),
  cameraForm: document.querySelector("#cameraForm"),
  cameraName: document.querySelector("#cameraName"),
  cameraStreamUrl: document.querySelector("#cameraStreamUrl"),
  cameraSlot: document.querySelector("#cameraSlot"),
  cameraConnectionDetail: document.querySelector("#cameraConnectionDetail"),
  controllerForm: document.querySelector("#controllerForm"),
  controllerName: document.querySelector("#controllerName"),
  controllerHost: document.querySelector("#controllerHost"),
  controllerProtocol: document.querySelector("#controllerProtocol"),
  controllerPort: document.querySelector("#controllerPort"),
  controllerUsername: document.querySelector("#controllerUsername"),
  controllerPassword: document.querySelector("#controllerPassword"),
  controllerChannelCount: document.querySelector("#controllerChannelCount"),
  controllerChannelStart: document.querySelector("#controllerChannelStart"),
  controllerStartSlot: document.querySelector("#controllerStartSlot"),
  controllerStreamTemplate: document.querySelector("#controllerStreamTemplate"),
  controllerCameraNameTemplate: document.querySelector("#controllerCameraNameTemplate"),
  controllerConnectionStatus: document.querySelector("#controllerConnectionStatus"),
  controllerConnectionDetail: document.querySelector("#controllerConnectionDetail"),
  btnConnectController: document.querySelector("#btnConnectController"),
  btnTestCamera: document.querySelector("#btnTestCamera"),
  btnConnectCamera: document.querySelector("#btnConnectCamera"),
  btnRefreshCameras: document.querySelector("#btnRefreshCameras"),
  btnSetActiveCamera: document.querySelector("#btnSetActiveCamera"),
  btnClearCameraSlot: document.querySelector("#btnClearCameraSlot"),
  activeSlotNumber: document.querySelector("#activeSlotNumber"),
  slotCameraSelect: document.querySelector("#slotCameraSelect"),
  activeSlotList: document.querySelector("#activeSlotList"),
  savedCameraTable: document.querySelector("#savedCameraTable"),
  cameraConnectionStatus: document.querySelector("#cameraConnectionStatus"),
  itemForm: document.querySelector("#itemForm"),
  itemId: document.querySelector("#itemId"),
  itemName: document.querySelector("#itemName"),
  itemType: document.querySelector("#itemType"),
  itemImage: document.querySelector("#itemImage"),
  itemNote: document.querySelector("#itemNote"),
  itemList: document.querySelector("#itemList"),
  totalItems: document.querySelector("#totalItems"),
  itemTypes: document.querySelector("#itemTypes"),
  totalQuantity: document.querySelector("#totalQuantity"),
  healthFrames: document.querySelector("#healthFrames"),
  healthDetections: document.querySelector("#healthDetections"),
  healthTracking: document.querySelector("#healthTracking"),
  healthStockMode: document.querySelector("#healthStockMode"),
  healthMessage: document.querySelector("#healthMessage"),
  ai3dScene: document.querySelector("#ai3dScene"),
  spatialEstimateTable: document.querySelector("#spatialEstimateTable"),
  cameraLiveGrid: document.querySelector("#cameraLiveGrid"),
  checkItemId: document.querySelector("#checkItemId"),
  checkQuantity: document.querySelector("#checkQuantity"),
  checkNote: document.querySelector("#checkNote"),
  btnCheckIn: document.querySelector("#btnCheckIn"),
  btnCheckOut: document.querySelector("#btnCheckOut"),
  checkItemTable: document.querySelector("#checkItemTable"),
  readyListTable: document.querySelector("#readyListTable"),
  historyTable: document.querySelector("#historyTable"),
  videoRecognitionStatus: document.querySelector("#videoRecognitionStatus"),
  videoRecognitionClassCount: document.querySelector("#videoRecognitionClassCount"),
  videoRecognitionEntryCount: document.querySelector("#videoRecognitionEntryCount"),
  videoRecognitionEntries: document.querySelector("#videoRecognitionEntries"),
  recognitionStatus: document.querySelector("#recognitionStatus"),
  recognitionClassCount: document.querySelector("#recognitionClassCount"),
  recognitionEntryCount: document.querySelector("#recognitionEntryCount"),
  recognitionEntries: document.querySelector("#recognitionEntries"),
  recognitionCounts: document.querySelector("#recognitionCounts"),
  visionCheckInTotal: document.querySelector("#visionCheckInTotal"),
  visionCheckOutTotal: document.querySelector("#visionCheckOutTotal"),
  visionCurrentStockTotal: document.querySelector("#visionCurrentStockTotal"),
  visionMovementEntries: document.querySelector("#visionMovementEntries"),
  visionStockTable: document.querySelector("#visionStockTable"),
  occupancyTotal: document.querySelector("#occupancyTotal"),
  occupancyClassCount: document.querySelector("#occupancyClassCount"),
  occupancyCounts: document.querySelector("#occupancyCounts"),
  occupancyCurrentTable: document.querySelector("#occupancyCurrentTable"),
  occupancyEventsTable: document.querySelector("#occupancyEventsTable"),
  toast: document.querySelector("#toast"),
};

// API base: use ?api=https://your-backend.example.com once to save it,
// falls back to the deployed backend for static hosts and same-origin when
// served directly by FastAPI.
const API_BASE = (() => {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    localStorage.setItem("api_base", param.replace(/\/+$/, ""));
  }
  const saved = localStorage.getItem("api_base");
  if (window.location.hostname.endsWith("vercel.app")) {
    const deployedBackend = "https://67-205-160-8.sslip.io";
    const staleSavedBackend =
      saved &&
      (saved.includes("github.dev") ||
        saved.includes("localhost") ||
        saved.includes("127.0.0.1"));
    if (!saved || staleSavedBackend) {
      localStorage.setItem("api_base", deployedBackend);
      return deployedBackend;
    }
  }
  if (saved) {
    return saved;
  }
  return window.location.origin;
})();
const LIVE_FRAME_REFRESH_MS = 120;
const LIVE_FRAME_RETRY_MS = 750;
const liveState = {
  detectionRunning: false,
};

const API_KEY = (() => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || params.get("api_key");
  if (token) {
    localStorage.setItem("admin_api_key", token);
    params.delete("token");
    params.delete("api_key");
    const query = params.toString();
    const cleanedUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", cleanedUrl);
    return token;
  }
  return localStorage.getItem("admin_api_key") || "";
})();

const api = async (path, options = {}) => {
  const url = `${API_BASE}${path}`;
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  try {
    const response = await fetch(url, {
      headers,
      credentials: "same-origin",
      ...options,
    });

    if (!response.ok) {
      const message = await response.text();
      if (response.status === 401) {
        throw new Error(
          "Backend требует admin API key. Откройте dashboard один раз с ?token=YOUR_ADMIN_API_KEY."
        );
      }
      throw new Error(message || response.statusText);
    }

    return response.json();
  } catch (error) {
    console.error("Ошибка API-запроса", path, error);
    throw new Error(error?.message || "Сетевой запрос не выполнен");
  }
};

const toast = (message) => {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.setTimeout(() => els.toast.classList.remove("show"), 2400);
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const setStatus = (running) => {
  liveState.detectionRunning = Boolean(running);
  els.statusPill.textContent = running ? "Детекция запущена" : "Детекция остановлена";
  els.statusPill.dataset.state = running ? "running" : "stopped";
  els.btnStartDetection.disabled = running;
  els.btnStopDetection.disabled = !running;
  els.btnRestartDetection.disabled = !running;
  updateLivePlaceholders();
};

const inventoryState = {
  items: [],
  history: [],
};

const setActiveTab = (tab) => {
  els.navButtons.forEach((button) => {
    const isActive = button.dataset.tab === tab;
    button.classList.toggle("active", isActive);
  });

  els.pages.forEach((page) => {
    page.classList.toggle("hidden", page.id !== tab);
  });

  els.pageTitle.textContent =
    tab === "itemEntry"
      ? "Добавить товар"
      : tab === "cameraSettings"
      ? "Настройки камер"
      : tab === "checkIn"
      ? "Приём / выдача"
      : tab === "recognitions"
      ? "Распознавание"
      : tab === "occupancy"
      ? "Наличие"
      : tab === "warehouse"
      ? "События склада"
      : "Готовый список";
};

const cameraState = {
  cameras: [],
  activeCamera: null,
  activeCameras: [],
};
const MAX_CAMERA_SLOTS = 50;

const setCameraConnectionStatus = (status, message) => {
  const labels = {
    connected: "Подключено",
    failed: "Ошибка",
    loading: "Загрузка",
    unknown: "Не проверено",
  };
  const label = labels[status] || labels.unknown;
  els.cameraConnectionStatus.textContent = label;
  els.cameraConnectionStatus.dataset.state = status;
  els.cameraConnectionDetail.textContent = message && message !== label ? message : "";
};

const setControllerConnectionStatus = (status, message) => {
  const labels = {
    connected: "Подключено",
    failed: "Ошибка",
    loading: "Загрузка",
    unknown: "Не проверено",
  };
  const label = labels[status] || labels.unknown;
  els.controllerConnectionStatus.textContent = label;
  els.controllerConnectionStatus.dataset.state = status;
  els.controllerConnectionDetail.textContent = message && message !== label ? message : "";
};

const loadCameras = async () => {
  const data = await api("/api/cameras");
  cameraState.cameras = data.cameras || [];
  cameraState.activeCamera = data.active_camera || null;
  cameraState.activeCameras = data.active_cameras || [];
  renderCameras();
  renderLiveScreens();
};

const renderCameras = () => {
  const cameras = cameraState.cameras;
  els.slotCameraSelect.innerHTML =
    cameras
      .map(
        (camera) =>
          `<option value="${camera.id}" ${camera.is_active ? "selected" : ""}>${escapeHtml(camera.name)} — ${escapeHtml(camera.status)}</option>`
      )
      .join("") || `<option value="">Нет сохранённых камер</option>`;

  els.activeSlotList.innerHTML =
    cameraState.activeCameras
      .map(
        (camera) =>
          `<div class="slot-chip"><span>Слот ${escapeHtml(camera.slot_number || "-")}</span><strong>${escapeHtml(camera.name)}</strong><em>${escapeHtml(camera.status)}</em></div>`
      )
      .join("") || `<p class="panel-sub">Активных слотов камер пока нет.</p>`;

  els.savedCameraTable.innerHTML =
    cameras
      .map(
        (camera) =>
          `<tr><td>${escapeHtml(camera.name)}</td><td>${escapeHtml(camera.slot_number || "-")}</td><td>${escapeHtml(camera.masked_stream_url)}</td><td>${escapeHtml(camera.status)}</td><td>${camera.is_active ? "Активна" : "-"}</td></tr>`
      )
      .join("") || `<tr><td colspan="5">Сохранённых камер пока нет.</td></tr>`;
};

const numberFromInput = (input, fallback = null) => {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
};

const isPrivateControllerHost = (host) => {
  const value = host.trim().replace(/^https?:\/\//, "").replace(/^rtsp:\/\//, "").split(/[/:]/)[0];
  return (
    value === "localhost" ||
    value.startsWith("127.") ||
    value.startsWith("10.") ||
    value.startsWith("192.168.") ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(value)
  );
};

const handleTestCamera = async () => {
  const streamUrl = els.cameraStreamUrl.value.trim();
  if (!streamUrl) {
    toast("Сначала введите URL потока камеры.");
    return;
  }

  els.btnTestCamera.disabled = true;
  setCameraConnectionStatus("loading", "Загрузка");
  try {
    const result = await api("/api/cameras/test", {
      method: "POST",
      body: JSON.stringify({ stream_url: streamUrl }),
    });
    const connected = result.status === "connected";
    setCameraConnectionStatus(connected ? "connected" : "failed", result.message);
    toast(result.message);
  } catch (error) {
    setCameraConnectionStatus("failed", error.message);
    toast(error.message);
  } finally {
    els.btnTestCamera.disabled = false;
  }
};

const handleConnectController = async (event) => {
  event.preventDefault();

  const channelCount = numberFromInput(els.controllerChannelCount);
  const channelStart = numberFromInput(els.controllerChannelStart);
  const startSlot = numberFromInput(els.controllerStartSlot);
  const port = numberFromInput(els.controllerPort, null);
  const lastSlot = startSlot + channelCount - 1;

  if (!els.controllerHost.value.trim()) {
    toast("IP/host контроллера обязателен.");
    return;
  }
  if (isPrivateControllerHost(els.controllerHost.value)) {
    const message =
      "Используйте публичный IP или DNS/DDNS. Частные Wi‑Fi/LAN IP недоступны для облачного backend.";
    setControllerConnectionStatus("failed", message);
    toast(message);
    return;
  }
  if (!Number.isInteger(channelCount) || channelCount < 1 || channelCount > MAX_CAMERA_SLOTS) {
    toast(`Количество камер должно быть от 1 до ${MAX_CAMERA_SLOTS}.`);
    return;
  }
  if (!Number.isInteger(channelStart) || channelStart < 1) {
    toast("Первый канал контроллера должен быть 1 или выше.");
    return;
  }
  if (!Number.isInteger(startSlot) || startSlot < 1 || lastSlot > MAX_CAMERA_SLOTS) {
    toast(`Слоты контроллера должны помещаться в диапазон 1–${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnConnectController.disabled = true;
  setControllerConnectionStatus("loading", "Проверка контроллера и создание слотов камер...");
  try {
    const result = await api("/api/camera-controller", {
      method: "POST",
      body: JSON.stringify({
        name: els.controllerName.value.trim() || "Контроллер камер",
        host: els.controllerHost.value.trim(),
        protocol: els.controllerProtocol.value,
        port,
        username: els.controllerUsername.value.trim() || undefined,
        password: els.controllerPassword.value || undefined,
        channel_count: channelCount,
        channel_start: channelStart,
        start_slot: startSlot,
        stream_path_template: els.controllerStreamTemplate.value.trim(),
        camera_name_template: els.controllerCameraNameTemplate.value.trim(),
        make_active: true,
        test_controller: true,
        test_streams: false,
        require_public: true,
      }),
    });

    cameraState.cameras = result.cameras || [];
    cameraState.activeCameras = result.active_cameras || [];
    renderCameras();
    renderLiveScreens();

    const createdCount = (result.created || []).length;
    const activeCount = (result.results || []).filter((row) => row.active).length;
    const connected = result.controller?.reachable;
    const message = connected
      ? `Контроллер подключён. Добавлено камер: ${createdCount}, назначено слотов: ${activeCount}.`
      : result.controller?.message || "Контроллер недоступен.";
    setControllerConnectionStatus(connected ? "connected" : "failed", message);
    toast(message);
  } catch (error) {
    setControllerConnectionStatus("failed", error.message);
    toast(error.message);
  } finally {
    els.btnConnectController.disabled = false;
  }
};

const handleConnectCamera = async (event) => {
  event.preventDefault();
  const name = els.cameraName.value.trim();
  const streamUrl = els.cameraStreamUrl.value.trim();
  const slotNumber = Number(els.cameraSlot.value || 1);
  if (!name || !streamUrl) {
    toast("Название камеры и URL потока обязательны.");
    return;
  }
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Слот камеры должен быть от 1 до ${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnConnectCamera.disabled = true;
  setCameraConnectionStatus("loading", "Загрузка");
  try {
    const result = await api("/api/cameras", {
      method: "POST",
      body: JSON.stringify({
        name,
        stream_url: streamUrl,
        make_active: true,
        test_connection: true,
        slot_number: slotNumber,
      }),
    });
    cameraState.cameras = result.cameras || [];
    cameraState.activeCameras = result.active_cameras || [];
    renderCameras();
    renderLiveScreens();
    const connected = result.test?.status === "connected";
    setCameraConnectionStatus(connected ? "connected" : "failed", result.test?.message);
    toast(connected ? "Камера подключена и активирована." : result.test?.message || "Камера сохранена, но соединение не удалось.");
  } catch (error) {
    setCameraConnectionStatus("failed", error.message);
    toast(error.message);
  } finally {
    els.btnConnectCamera.disabled = false;
  }
};

const handleSetActiveCamera = async () => {
  const cameraId = els.slotCameraSelect.value;
  const slotNumber = Number(els.activeSlotNumber.value || 1);
  if (!cameraId) {
    toast("Сначала выберите сохранённую камеру.");
    return;
  }
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Слот должен быть от 1 до ${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnSetActiveCamera.disabled = true;
  try {
    const result = await api(`/api/cameras/${cameraId}/activate`, {
      method: "POST",
      body: JSON.stringify({ slot_number: slotNumber }),
    });
    cameraState.cameras = result.cameras || [];
    cameraState.activeCameras = result.active_cameras || [];
    renderCameras();
    renderLiveScreens();
    toast(result.restarted ? "Слот камеры назначен, детекция перезапущена." : "Слот камеры назначен.");
  } catch (error) {
    toast(error.message);
  } finally {
    els.btnSetActiveCamera.disabled = false;
  }
};

const handleClearCameraSlot = async () => {
  const slotNumber = Number(els.activeSlotNumber.value || 1);
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Слот должен быть от 1 до ${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnClearCameraSlot.disabled = true;
  try {
    const result = await api(`/api/camera-slots/${slotNumber}`, { method: "DELETE" });
    cameraState.cameras = result.cameras || [];
    cameraState.activeCameras = result.active_cameras || [];
    renderCameras();
    renderLiveScreens();
    toast(result.restarted ? "Слот камеры очищен, детекция перезапущена." : "Слот камеры очищен.");
  } catch (error) {
    toast(error.message);
  } finally {
    els.btnClearCameraSlot.disabled = false;
  }
};

const loadInventory = async () => {
  const data = await api("/api/inventory");
  inventoryState.items = data.items || [];
  inventoryState.history = data.history || [];
  renderInventory();
};

const renderInventory = () => {
  const items = inventoryState.items;
  const totalQuantity = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  const types = [...new Set(items.map((item) => item.item_type || "неизвестно"))];

  els.totalItems.textContent = items.length;
  els.itemTypes.textContent = types.length;
  els.totalQuantity.textContent = totalQuantity;

  const itemRows = items
    .map(
      (item) =>
        `<tr><td>${item.item_id}</td><td>${item.name}</td><td>${item.item_type || "неизвестно"}</td><td>${item.quantity}</td></tr>`
    )
    .join("");
  els.itemList.innerHTML = itemRows || `<tr><td colspan="4">Товаров пока нет.</td></tr>`;
  els.checkItemTable.innerHTML = itemRows || `<tr><td colspan="4">Товаров пока нет.</td></tr>`;
  els.readyListTable.innerHTML =
    itemRows || `<tr><td colspan="5">Товаров пока нет.</td></tr>`;

  const options = items
    .map((item) => `<option value="${item.item_id}">${item.item_id} — ${item.name}</option>`)
    .join("");
  els.checkItemId.innerHTML = options || `<option value="">Нет товаров</option>`;

  els.historyTable.innerHTML =
    inventoryState.history
      .map(
        (entry) =>
          `<tr><td>${entry.timestamp}</td><td>${entry.action}</td><td>${entry.item_id}</td><td>${entry.quantity}</td><td>${entry.note || "—"}</td></tr>`
      )
      .join("") || `<tr><td colspan="5">Действий пока нет.</td></tr>`;
};

const loadRecognitions = async () => {
  return api("/api/recognitions");
};

const renderRecognitions = (data, running = false) => {
  const entries = data.entries || [];
  const counts = data.counts || [];
  const visionItems = data.vision_items || [];
  const movements = data.movements || [];
  const movementCounts = data.movement_counts || {};
  const stock = data.stock || [];
  const classCount = counts.length;
  const entryCount = entries.length;

  const detectionText = running
    ? entryCount > 0
      ? `Активно — последних детекций: ${entryCount}`
      : "Работает — последних детекций нет"
    : "Детекция остановлена";

  els.videoRecognitionStatus.textContent = detectionText;
  els.recognitionStatus.textContent = detectionText;
  els.videoRecognitionClassCount.textContent = classCount;
  els.recognitionClassCount.textContent = classCount;
  els.videoRecognitionEntryCount.textContent = entryCount;
  els.recognitionEntryCount.textContent = entryCount;

  els.videoRecognitionEntries.innerHTML =
    entries
      .slice(-5)
      .reverse()
      .map(
        (entry) =>
          `<tr><td>${entry.timestamp}</td><td>${entry.class_name}</td><td>${entry.confidence}</td></tr>`
      )
      .join("") || `<tr><td colspan="3">Последних детекций нет.</td></tr>`;

  els.recognitionEntries.innerHTML =
    entries
      .map(
        (entry) =>
          `<tr><td>${entry.timestamp}</td><td>${entry.class_name}</td><td>${entry.camera}</td><td>${entry.confidence}</td></tr>`
      )
      .join("") || `<tr><td colspan="4">Последних детекций нет.</td></tr>`;

  els.recognitionCounts.innerHTML =
    visionItems
      .map((item) => {
        const stateLabel = item.state === "check-out" ? "Выдача" : "Приём";
        return `<tr><td>${escapeHtml(item.product_name)}</td><td>${stateLabel}</td><td>${item.quantity}</td><td>${item.current_stock}</td></tr>`;
      })
      .join("") ||
    counts
      .map((count) => `<tr><td>${escapeHtml(count.class_name)}</td><td>Обнаружено</td><td>${count.count}</td><td>—</td></tr>`)
      .join("") ||
    `<tr><td colspan="4">Распознанных коробок пока нет.</td></tr>`;

  els.visionCheckInTotal.textContent = movementCounts.IN || 0;
  els.visionCheckOutTotal.textContent = movementCounts.OUT || 0;
  els.visionCurrentStockTotal.textContent = stock.length;

  els.visionMovementEntries.innerHTML =
    movements
      .map((movement) => {
        const confidence =
          movement.confidence == null
            ? "—"
            : `${Math.round(Number(movement.confidence) * 100)}%`;
        const quantity = movement.quantity_grid
          ? `${movement.quantity} (${movement.quantity_grid})`
          : movement.quantity || 1;
        const size =
          movement.estimated_width_m == null
            ? "—"
            : `~${Number(movement.estimated_width_m).toFixed(2)} x ${Number(movement.estimated_height_m).toFixed(2)} x ${Number(movement.estimated_depth_m).toFixed(2)} m`;
        const direction = movement.direction === "OUT" ? "Выход" : "Вход";
        return `<tr><td>${movement.created_at}</td><td>${direction}</td><td>${escapeHtml(movement.product_name)}</td><td>${quantity}</td><td>${escapeHtml(movement.object_type || "—")}</td><td>${size}</td><td>${escapeHtml(movement.camera_id || "—")}</td><td>#${movement.tracking_id}</td><td>${confidence}</td></tr>`;
      })
      .join("") || `<tr><td colspan="9">Автоматических событий с камер пока нет.</td></tr>`;

  els.visionStockTable.innerHTML =
    stock
      .map(
        (item) =>
          `<tr><td>${item.name}</td><td>${item.current_stock}</td><td>${item.created_at}</td></tr>`
      )
      .join("") || `<tr><td colspan="3">Остатков, посчитанных камерой, пока нет.</td></tr>`;
};

const renderAi3dScene = (spatialObjects) => {
  if (!els.ai3dScene) return;

  if (!spatialObjects.length) {
    els.ai3dScene.innerHTML = `
      <div class="ai-3d-empty">
        <strong>Текущих 3D-объектов нет</strong>
        <span>Запустите детекцию и дождитесь кадров камеры, чтобы построить сцену распознавания.</span>
      </div>
    `;
    return;
  }

  const maxДистанция = Math.max(
    1,
    ...spatialObjects.map((item) => Number(item.distance_m || 0))
  );

  els.ai3dScene.innerHTML = spatialObjects
    .map((item, index) => {
      const width = Math.max(0.15, Number(item.width_m || 0.2));
      const height = Math.max(0.15, Number(item.height_m || 0.2));
      const depth = Math.max(0.15, Number(item.depth_m || 0.2));
      const distance = Math.max(0, Number(item.distance_m || 0));
      const distancePct = Math.min(100, Math.round((distance / maxДистанция) * 100));
      const scale = Math.max(0.7, Math.min(1.35, 1.3 - distance / Math.max(maxДистанция * 1.4, 1)));
      const grid = (item.quantity_grid || [1, 1, 1]).join(" x ");
      const label = item.inventory_name || item.class_name || "Обнаружено item";
      const hue = (index * 54) % 360;
      const sizeLabel = `${width.toFixed(2)} x ${height.toFixed(2)} x ${depth.toFixed(2)} m`;

      return `
        <article class="ai-3d-object" style="--hue:${hue}; --scale:${scale}; --distance:${distancePct}%;">
          <div class="object-cube" aria-hidden="true">
            <span class="cube-face cube-front"></span>
            <span class="cube-face cube-top"></span>
            <span class="cube-face cube-side"></span>
          </div>
          <div class="object-meta">
            <strong>${escapeHtml(label)}</strong>
            <span>${escapeHtml(item.object_type || "объект")} · ${item.quantity || 1} ед.</span>
            <em>Сетка ${escapeHtml(grid)} · ~${sizeLabel}</em>
            <div class="distance-track"><span></span></div>
            <small>Дистанция ~${distance.toFixed(1)} m</small>
          </div>
        </article>
      `;
    })
    .join("");
};

const renderFunctionHealth = (status) => {
  const health = status.health || {};
  const spatialObjects = health.last_spatial_objects || [];
  els.healthFrames.textContent = health.frames_read ?? 0;
  els.healthDetections.textContent = health.last_detection_count ?? 0;
  els.healthTracking.textContent = health.last_tracked_count ?? 0;
  els.healthStockMode.textContent =
    health.warehouse_counting_enabled
      ? health.warehouse_counting_mode || "on"
      : "Выкл";

  const parts = [];
  parts.push(status.running ? "Процесс детекции запущен." : "Процесс детекции остановлен.");
  if (health.last_frame_at) parts.push(`Последний кадр: ${health.last_frame_at}.`);
  if (health.error) parts.push(`Ошибка: ${health.error}`);
  if (!health.last_frame_at && status.running) {
    parts.push("Обработанный кадр пока не получен.");
  }
  if (health.spatial_analysis_enabled) {
    parts.push("Монокулярная 3D-оценка активна.");
  }
  els.healthMessage.textContent = parts.join(" ");

  els.spatialEstimateTable.innerHTML =
    spatialObjects
      .map((item) => {
        const grid = (item.quantity_grid || [1, 1, 1]).join(" x ");
        const size = `~${Number(item.width_m).toFixed(2)} x ${Number(item.height_m).toFixed(2)} x ${Number(item.depth_m).toFixed(2)} m`;
        return `<tr><td>${escapeHtml(item.inventory_name)}</td><td>${escapeHtml(item.object_type)}</td><td>${item.quantity}</td><td>${grid}</td><td>${size}</td><td>~${Number(item.distance_m).toFixed(1)} m</td></tr>`;
      })
      .join("") || `<tr><td colspan="6">Текущих 3D-оценок нет.</td></tr>`;

  renderAi3dScene(spatialObjects);
};

const loadOccupancy = async () => {
  const [occupancy, events] = await Promise.all([
    api("/api/occupancy"),
    api("/api/occupancy/events?limit=50"),
  ]);
  return { occupancy, events: events.events || [] };
};

const renderOccupancy = ({ occupancy, events }) => {
  const current = occupancy.current || [];
  const counts = occupancy.counts || [];

  els.occupancyTotal.textContent = current.length;
  els.occupancyClassCount.textContent = counts.length;

  els.occupancyCounts.innerHTML =
    counts
      .map((count) => `<tr><td>${count.class_name}</td><td>${count.count}</td></tr>`)
      .join("") || `<tr><td colspan="2">Сейчас внутри ничего нет.</td></tr>`;

  els.occupancyCurrentTable.innerHTML =
    current
      .map(
        (row) =>
          `<tr><td>#${row.track_id}</td><td>${row.class_name}</td><td>${row.camera_name}</td><td>${row.since}</td></tr>`
      )
      .join("") || `<tr><td colspan="4">Сейчас внутри ничего нет.</td></tr>`;

  els.occupancyEventsTable.innerHTML =
    events
      .map((event) => {
        const dwell =
          event.event_type === "check_out" && event.duration_seconds != null
            ? `${Math.round(event.duration_seconds)}s`
            : "—";
        const label = event.event_type === "check_in" ? "Приём" : "Выдача";
        return `<tr><td>${event.timestamp}</td><td>${label}</td><td>#${event.track_id}</td><td>${event.class_name}</td><td>${event.camera_name}</td><td>${dwell}</td></tr>`;
      })
      .join("") || `<tr><td colspan="6">Событий наличия пока нет.</td></tr>`;
};

const refreshDashboard = async () => {
  try {
    await loadInventory();
    await loadCameras();
    const status = await api("/api/status");
    setStatus(status.running);
    renderFunctionHealth(status);
    const recognitions = await loadRecognitions();
    renderRecognitions(recognitions, status.running || recognitions.running);
    const occupancyData = await loadOccupancy();
    renderOccupancy(occupancyData);
  } catch (error) {
    toast(error.message);
  }
};

const uploadItemImage = async (itemId, file) => {
  const form = new FormData();
  form.append("item_id", itemId);
  form.append("file", file);
  return api("/api/inventory/upload-image", {
    method: "POST",
    body: form,
  });
};

const handleAddItem = async (event) => {
  event.preventDefault();
  const itemId = els.itemId.value.trim();
  const name = els.itemName.value.trim();
  const itemType = els.itemType.value.trim();
  const note = els.itemNote.value.trim();
  const imageFile = els.itemImage.files[0];

  if (!itemId || !name) {
    toast("ID товара и название обязательны.");
    return;
  }

  try {
    await api("/api/inventory/item", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, name, item_type: itemType || undefined }),
    });

    if (imageFile) {
      await uploadItemImage(itemId, imageFile);
    }

    els.itemForm.reset();
    await loadInventory();
    toast("Товар успешно добавлен.");
  } catch (error) {
    toast(error.message);
  }
};

const handleCheckAction = async (action) => {
  const itemId = els.checkItemId.value;
  const quantity = Number(els.checkQuantity.value);
  const note = els.checkNote.value.trim();

  if (!itemId || quantity < 1) {
    toast("Выберите товар и количество.");
    return;
  }

  try {
    await api(`/api/inventory/${action}`, {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, quantity, note: note || undefined }),
    });
    els.checkQuantity.value = 1;
    els.checkNote.value = "";
    await loadInventory();
    toast(action === "checkin" ? "Товар успешно принят." : "Товар успешно выдан.");
  } catch (error) {
    toast(error.message);
  }
};

const handleDetectionAction = async (action, button) => {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Выполняется...";
  try {
    const result = await api(`/api/${action}`, { method: "POST" });
    setStatus(result.running);
    toast(
      action === "start"
        ? "Детекция запущена."
        : action === "stop"
        ? "Детекция остановлена."
        : "Детекция перезапущена."
    );
  } catch (error) {
    toast(error.message);
  } finally {
    button.textContent = originalText;
    // setStatus() above already sets the correct disabled state; this
    // guards the case where the request failed and status didn't change.
    const status = await api("/api/status").catch(() => null);
    if (status) setStatus(status.running);
  }
};

const renderLiveScreens = () => {
  if (!els.cameraLiveGrid) return;

  const activeCameras = cameraState.activeCameras || [];
  if (!activeCameras.length) {
    els.cameraLiveGrid.innerHTML =
      `<div class="camera-screen empty"><div><strong>Нет активных слотов камер</strong><span>Назначьте сохранённые камеры на слоты в настройках камер.</span></div></div>`;
    return;
  }

  els.cameraLiveGrid.innerHTML = activeCameras
    .map((camera) => {
      const slot = camera.slot_number || 1;
      return `
        <div class="camera-screen">
          <div class="screen-head">
            <span>Слот ${escapeHtml(slot)}</span>
            <strong>${escapeHtml(camera.name)}</strong>
            <em>${escapeHtml(camera.status)}</em>
          </div>
          <div class="screen-body">
            <img data-live-slot="${escapeHtml(slot)}" alt="${escapeHtml(camera.name)} видео" />
            <span class="screen-placeholder" data-live-placeholder>Ожидание кадров</span>
          </div>
        </div>
      `;
    })
    .join("");
  refreshLiveScreens();
};

const refreshLiveScreens = () => {
  document.querySelectorAll("[data-live-slot]").forEach((image) => {
    if (!image.dataset.bound) {
      image.dataset.bound = "true";
      image.addEventListener("load", () => {
        image.dataset.loading = "false";
        image.dataset.failures = "0";
        setLivePlaceholder(image, "Кадры детекции");
        image.closest(".screen-body")?.classList.add("has-frame");
        window.setTimeout(() => refreshLiveImage(image), LIVE_FRAME_REFRESH_MS);
      });
      image.addEventListener("error", () => {
        image.dataset.loading = "false";
        const failures = Number(image.dataset.failures || 0) + 1;
        image.dataset.failures = String(failures);
        image.closest(".screen-body")?.classList.remove("has-frame");
        setLivePlaceholder(
          image,
          liveState.detectionRunning
            ? "Кадра из этого слота пока нет. Поток камеры может быть недоступен."
            : "Детекция остановлена. Запустите детекцию после доступности потоков камер."
        );
        window.setTimeout(() => refreshLiveImage(image), LIVE_FRAME_RETRY_MS);
      });
    }

    if (!image.getAttribute("src") && image.dataset.loading !== "true") {
      refreshLiveImage(image);
    }
  });
};

const refreshLiveImage = (image) => {
  if (!image?.dataset?.liveСлот || image.dataset.loading === "true") {
    return;
  }
  const now = Date.now();
  image.dataset.loading = "true";
  const params = new URLSearchParams({
    slot: image.dataset.liveSlot,
    t: String(now),
  });
  if (API_KEY) {
    params.set("api_key", API_KEY);
  }
  image.src = `${API_BASE}/api/live_frame?${params.toString()}`;
};

const setLivePlaceholder = (image, message) => {
  const placeholder = image?.closest(".screen-body")?.querySelector("[data-live-placeholder]");
  if (placeholder) {
    placeholder.textContent = message;
  }
};

const updateLivePlaceholders = () => {
  document.querySelectorAll("[data-live-slot]").forEach((image) => {
    if (image.closest(".screen-body")?.classList.contains("has-frame")) {
      return;
    }
    setLivePlaceholder(
      image,
      liveState.detectionRunning
        ? "Ожидание первого обработанного кадра..."
        : "Детекция остановлена. Запустите детекцию после доступности потоков камер."
    );
  });
};

const startLiveFeed = async () => {
  renderLiveScreens();
  refreshLiveScreens();
  window.setInterval(refreshLiveScreens, 2500);
};

els.navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tab);
  });
});

els.refreshBtn.addEventListener("click", refreshDashboard);
els.btnRefreshCameras.addEventListener("click", loadCameras);
els.btnTestCamera.addEventListener("click", handleTestCamera);
els.btnSetActiveCamera.addEventListener("click", handleSetActiveCamera);
els.btnClearCameraSlot.addEventListener("click", handleClearCameraSlot);
els.btnStartDetection.addEventListener("click", () =>
  handleDetectionAction("start", els.btnStartDetection)
);
els.btnStopDetection.addEventListener("click", () =>
  handleDetectionAction("stop", els.btnStopDetection)
);
els.btnRestartDetection.addEventListener("click", () =>
  handleDetectionAction("restart", els.btnRestartDetection)
);
els.cameraForm.addEventListener("submit", handleConnectCamera);
els.controllerForm.addEventListener("submit", handleConnectController);
els.itemForm.addEventListener("submit", handleAddItem);
els.btnCheckIn.addEventListener("click", () => handleCheckAction("checkin"));
els.btnCheckOut.addEventListener("click", () => handleCheckAction("checkout"));

setActiveTab("itemEntry");
await refreshDashboard();
startLiveFeed();
window.setInterval(refreshDashboard, 6000);

