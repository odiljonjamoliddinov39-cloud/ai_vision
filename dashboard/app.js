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
// falls back to same-origin when served directly by FastAPI.
const API_BASE = (() => {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    localStorage.setItem("api_base", param.replace(/\/+$/, ""));
  }
  return localStorage.getItem("api_base") || window.location.origin;
})();

const api = async (path, options = {}) => {
  const url = `${API_BASE}${path}`;
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  try {
    const response = await fetch(url, {
      headers,
      credentials: "same-origin",
      ...options,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || response.statusText);
    }

    return response.json();
  } catch (error) {
    console.error("API fetch failed", path, error);
    throw new Error(error?.message || "Network request failed");
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
  els.statusPill.textContent = running ? "Detection running" : "Detection stopped";
  els.statusPill.dataset.state = running ? "running" : "stopped";
  els.btnStartDetection.disabled = running;
  els.btnStopDetection.disabled = !running;
  els.btnRestartDetection.disabled = !running;
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
      ? "Item Entry"
      : tab === "cameraSettings"
      ? "Camera Settings"
      : tab === "checkIn"
      ? "Check In"
      : tab === "recognitions"
      ? "Recognitions"
      : tab === "occupancy"
      ? "Occupancy"
      : "Ready List";
};

const cameraState = {
  cameras: [],
  activeCamera: null,
  activeCameras: [],
};
const MAX_CAMERA_SLOTS = 50;

const setCameraConnectionStatus = (status, message) => {
  const labels = {
    connected: "Connected",
    failed: "Failed",
    loading: "Loading",
    unknown: "Not tested",
  };
  const label = labels[status] || labels.unknown;
  els.cameraConnectionStatus.textContent = label;
  els.cameraConnectionStatus.dataset.state = status;
  els.cameraConnectionDetail.textContent = message && message !== label ? message : "";
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
      .join("") || `<option value="">No saved cameras</option>`;

  els.activeSlotList.innerHTML =
    cameraState.activeCameras
      .map(
        (camera) =>
          `<div class="slot-chip"><span>Slot ${escapeHtml(camera.slot_number || "-")}</span><strong>${escapeHtml(camera.name)}</strong><em>${escapeHtml(camera.status)}</em></div>`
      )
      .join("") || `<p class="panel-sub">No active camera slots yet.</p>`;

  els.savedCameraTable.innerHTML =
    cameras
      .map(
        (camera) =>
          `<tr><td>${escapeHtml(camera.name)}</td><td>${escapeHtml(camera.slot_number || "-")}</td><td>${escapeHtml(camera.masked_stream_url)}</td><td>${escapeHtml(camera.status)}</td><td>${camera.is_active ? "Active" : "-"}</td></tr>`
      )
      .join("") || `<tr><td colspan="5">No saved cameras yet.</td></tr>`;
};

const handleTestCamera = async () => {
  const streamUrl = els.cameraStreamUrl.value.trim();
  if (!streamUrl) {
    toast("Enter a camera stream URL first.");
    return;
  }

  els.btnTestCamera.disabled = true;
  setCameraConnectionStatus("loading", "Loading");
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

const handleConnectCamera = async (event) => {
  event.preventDefault();
  const name = els.cameraName.value.trim();
  const streamUrl = els.cameraStreamUrl.value.trim();
  const slotNumber = Number(els.cameraSlot.value || 1);
  if (!name || !streamUrl) {
    toast("Camera name and stream URL are required.");
    return;
  }
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Camera slot must be between 1 and ${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnConnectCamera.disabled = true;
  setCameraConnectionStatus("loading", "Loading");
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
    toast(connected ? "Camera connected and set active." : result.test?.message || "Camera saved but connection failed.");
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
    toast("Select a saved camera first.");
    return;
  }
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Slot must be between 1 and ${MAX_CAMERA_SLOTS}.`);
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
    toast(result.restarted ? "Camera slot assigned and detection restarted." : "Camera slot assigned.");
  } catch (error) {
    toast(error.message);
  } finally {
    els.btnSetActiveCamera.disabled = false;
  }
};

const handleClearCameraSlot = async () => {
  const slotNumber = Number(els.activeSlotNumber.value || 1);
  if (!Number.isInteger(slotNumber) || slotNumber < 1 || slotNumber > MAX_CAMERA_SLOTS) {
    toast(`Slot must be between 1 and ${MAX_CAMERA_SLOTS}.`);
    return;
  }

  els.btnClearCameraSlot.disabled = true;
  try {
    const result = await api(`/api/camera-slots/${slotNumber}`, { method: "DELETE" });
    cameraState.cameras = result.cameras || [];
    cameraState.activeCameras = result.active_cameras || [];
    renderCameras();
    renderLiveScreens();
    toast(result.restarted ? "Camera slot cleared and detection restarted." : "Camera slot cleared.");
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
  const types = [...new Set(items.map((item) => item.item_type || "unknown"))];

  els.totalItems.textContent = items.length;
  els.itemTypes.textContent = types.length;
  els.totalQuantity.textContent = totalQuantity;

  const itemRows = items
    .map(
      (item) =>
        `<tr><td>${item.item_id}</td><td>${item.name}</td><td>${item.item_type || "unknown"}</td><td>${item.quantity}</td></tr>`
    )
    .join("");
  els.itemList.innerHTML = itemRows || `<tr><td colspan="4">No items yet.</td></tr>`;
  els.checkItemTable.innerHTML = itemRows || `<tr><td colspan="4">No items yet.</td></tr>`;
  els.readyListTable.innerHTML =
    itemRows || `<tr><td colspan="5">No items yet.</td></tr>`;

  const options = items
    .map((item) => `<option value="${item.item_id}">${item.item_id} — ${item.name}</option>`)
    .join("");
  els.checkItemId.innerHTML = options || `<option value="">No items</option>`;

  els.historyTable.innerHTML =
    inventoryState.history
      .map(
        (entry) =>
          `<tr><td>${entry.timestamp}</td><td>${entry.action}</td><td>${entry.item_id}</td><td>${entry.quantity}</td><td>${entry.note || "—"}</td></tr>`
      )
      .join("") || `<tr><td colspan="5">No activity yet.</td></tr>`;
};

const loadRecognitions = async () => {
  return api("/api/recognitions");
};

const renderRecognitions = (data, running = false) => {
  const entries = data.entries || [];
  const counts = data.counts || [];
  const movements = data.movements || [];
  const movementCounts = data.movement_counts || {};
  const stock = data.stock || [];
  const classCount = counts.length;
  const entryCount = entries.length;

  const detectionText = running
    ? entryCount > 0
      ? `Active — ${entryCount} recent detections`
      : "Running — no recent detections"
    : "Detection stopped";

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
      .join("") || `<tr><td colspan="3">No recent detections.</td></tr>`;

  els.recognitionEntries.innerHTML =
    entries
      .map(
        (entry) =>
          `<tr><td>${entry.timestamp}</td><td>${entry.class_name}</td><td>${entry.camera}</td><td>${entry.confidence}</td></tr>`
      )
      .join("") || `<tr><td colspan="4">No recent detections.</td></tr>`;

  els.recognitionCounts.innerHTML =
    counts
      .map(
        (count) => `<tr><td>${count.class_name}</td><td>${count.count}</td></tr>`
      )
      .join("") || `<tr><td colspan="2">No recognized classes yet.</td></tr>`;

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
        return `<tr><td>${movement.created_at}</td><td>${movement.direction}</td><td>${escapeHtml(movement.product_name)}</td><td>${quantity}</td><td>${escapeHtml(movement.object_type || "—")}</td><td>${size}</td><td>${escapeHtml(movement.camera_id || "—")}</td><td>#${movement.tracking_id}</td><td>${confidence}</td></tr>`;
      })
      .join("") || `<tr><td colspan="9">No automatic camera check-ins yet.</td></tr>`;

  els.visionStockTable.innerHTML =
    stock
      .map(
        (item) =>
          `<tr><td>${item.name}</td><td>${item.current_stock}</td><td>${item.created_at}</td></tr>`
      )
      .join("") || `<tr><td colspan="3">No camera-counted stock yet.</td></tr>`;
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
      : "Off";

  const parts = [];
  parts.push(status.running ? "Detector process is running." : "Detector process is stopped.");
  if (health.last_frame_at) parts.push(`Last frame: ${health.last_frame_at}.`);
  if (health.error) parts.push(`Error: ${health.error}`);
  if (!health.last_frame_at && status.running) {
    parts.push("No processed frame has been reported yet.");
  }
  if (health.spatial_analysis_enabled) {
    parts.push("Monocular 3D estimation is active.");
  }
  els.healthMessage.textContent = parts.join(" ");

  els.spatialEstimateTable.innerHTML =
    spatialObjects
      .map((item) => {
        const grid = (item.quantity_grid || [1, 1, 1]).join(" x ");
        const size = `~${Number(item.width_m).toFixed(2)} x ${Number(item.height_m).toFixed(2)} x ${Number(item.depth_m).toFixed(2)} m`;
        return `<tr><td>${escapeHtml(item.inventory_name)}</td><td>${escapeHtml(item.object_type)}</td><td>${item.quantity}</td><td>${grid}</td><td>${size}</td><td>~${Number(item.distance_m).toFixed(1)} m</td></tr>`;
      })
      .join("") || `<tr><td colspan="6">No current 3D estimates.</td></tr>`;
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
      .join("") || `<tr><td colspan="2">Nothing checked in right now.</td></tr>`;

  els.occupancyCurrentTable.innerHTML =
    current
      .map(
        (row) =>
          `<tr><td>#${row.track_id}</td><td>${row.class_name}</td><td>${row.camera_name}</td><td>${row.since}</td></tr>`
      )
      .join("") || `<tr><td colspan="4">Nothing checked in right now.</td></tr>`;

  els.occupancyEventsTable.innerHTML =
    events
      .map((event) => {
        const dwell =
          event.event_type === "check_out" && event.duration_seconds != null
            ? `${Math.round(event.duration_seconds)}s`
            : "—";
        const label = event.event_type === "check_in" ? "Check-in" : "Check-out";
        return `<tr><td>${event.timestamp}</td><td>${label}</td><td>#${event.track_id}</td><td>${event.class_name}</td><td>${event.camera_name}</td><td>${dwell}</td></tr>`;
      })
      .join("") || `<tr><td colspan="6">No occupancy events yet.</td></tr>`;
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
    toast("Item ID and name are required.");
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
    toast("Item added successfully.");
  } catch (error) {
    toast(error.message);
  }
};

const handleCheckAction = async (action) => {
  const itemId = els.checkItemId.value;
  const quantity = Number(els.checkQuantity.value);
  const note = els.checkNote.value.trim();

  if (!itemId || quantity < 1) {
    toast("Select an item and quantity.");
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
    toast(`Item ${action.replace("check", "checked ")} successfully.`);
  } catch (error) {
    toast(error.message);
  }
};

const handleDetectionAction = async (action, button) => {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Working...";
  try {
    const result = await api(`/api/${action}`, { method: "POST" });
    setStatus(result.running);
    toast(
      action === "start"
        ? "Detection started."
        : action === "stop"
        ? "Detection stopped."
        : "Detection restarted."
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
      `<div class="camera-screen empty"><div><strong>No active camera slots</strong><span>Assign saved cameras to slots in Camera Settings.</span></div></div>`;
    return;
  }

  els.cameraLiveGrid.innerHTML = activeCameras
    .map((camera) => {
      const slot = camera.slot_number || 1;
      return `
        <div class="camera-screen">
          <div class="screen-head">
            <span>Slot ${escapeHtml(slot)}</span>
            <strong>${escapeHtml(camera.name)}</strong>
            <em>${escapeHtml(camera.status)}</em>
          </div>
          <div class="screen-body">
            <img data-live-slot="${escapeHtml(slot)}" alt="${escapeHtml(camera.name)} live view" />
            <span class="screen-placeholder" data-live-placeholder>Waiting for frames</span>
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
        image.closest(".screen-body")?.classList.add("has-frame");
      });
      image.addEventListener("error", () => {
        image.closest(".screen-body")?.classList.remove("has-frame");
      });
    }

    if (!image.getAttribute("src")) {
      image.src = `${API_BASE}/api/live_mjpeg?slot=${encodeURIComponent(image.dataset.liveSlot)}`;
    }
  });
};

const startLiveFeed = async () => {
  renderLiveScreens();
  refreshLiveScreens();
  window.setInterval(refreshLiveScreens, 800);
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
els.itemForm.addEventListener("submit", handleAddItem);
els.btnCheckIn.addEventListener("click", () => handleCheckAction("checkin"));
els.btnCheckOut.addEventListener("click", () => handleCheckAction("checkout"));

setActiveTab("itemEntry");
await refreshDashboard();
startLiveFeed();
window.setInterval(refreshDashboard, 6000);
