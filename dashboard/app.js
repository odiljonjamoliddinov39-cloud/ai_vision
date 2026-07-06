const els = {
  pageTitle: document.querySelector("#pageTitle"),
  statusPill: document.querySelector("#statusPill"),
  refreshBtn: document.querySelector("#refreshBtn"),
  btnStartDetection: document.querySelector("#btnStartDetection"),
  btnStopDetection: document.querySelector("#btnStopDetection"),
  btnRestartDetection: document.querySelector("#btnRestartDetection"),
  navButtons: Array.from(document.querySelectorAll(".nav-btn")),
  pages: Array.from(document.querySelectorAll(".page")),
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
  warehouseVideo: document.querySelector("#warehouseVideo"),
  warehouseFallback: document.querySelector("#warehouseFallback"),
  warehouseHint: document.querySelector("#warehouseHint"),
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

const api = async (path, options = {}) => {
  const url = `${window.location.origin}${path}`;
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
      : tab === "checkIn"
      ? "Check In"
      : tab === "recognitions"
      ? "Recognitions"
      : tab === "occupancy"
      ? "Occupancy"
      : "Ready List";
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
        return `<tr><td>${movement.created_at}</td><td>${movement.direction}</td><td>${movement.product_name}</td><td>${movement.camera_id || "—"}</td><td>#${movement.tracking_id}</td><td>${confidence}</td></tr>`;
      })
      .join("") || `<tr><td colspan="6">No automatic camera check-ins yet.</td></tr>`;

  els.visionStockTable.innerHTML =
    stock
      .map(
        (item) =>
          `<tr><td>${item.name}</td><td>${item.current_stock}</td><td>${item.created_at}</td></tr>`
      )
      .join("") || `<tr><td colspan="3">No camera-counted stock yet.</td></tr>`;
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
    const status = await api("/api/status");
    setStatus(status.running);
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

const startLiveFeed = async () => {
  if (navigator.mediaDevices?.getUserMedia) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      els.warehouseVideo.srcObject = stream;
      els.warehouseVideo.classList.remove("hidden");
      els.warehouseFallback.classList.add("hidden");
      els.warehouseHint.textContent = "Using browser webcam";
      return;
    } catch (err) {
      console.warn("Browser camera unavailable", err);
    }
  }

  els.warehouseVideo.classList.add("hidden");
  els.warehouseFallback.classList.remove("hidden");
  els.warehouseHint.textContent = "Using backend live feed";
  const refreshImage = () => {
    els.warehouseFallback.src = "/api/live_mjpeg?t=" + Date.now();
  };
  refreshImage();
  window.setInterval(refreshImage, 800);
};

els.navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tab);
  });
});

els.refreshBtn.addEventListener("click", refreshDashboard);
els.btnStartDetection.addEventListener("click", () =>
  handleDetectionAction("start", els.btnStartDetection)
);
els.btnStopDetection.addEventListener("click", () =>
  handleDetectionAction("stop", els.btnStopDetection)
);
els.btnRestartDetection.addEventListener("click", () =>
  handleDetectionAction("restart", els.btnRestartDetection)
);
els.itemForm.addEventListener("submit", handleAddItem);
els.btnCheckIn.addEventListener("click", () => handleCheckAction("checkin"));
els.btnCheckOut.addEventListener("click", () => handleCheckAction("checkout"));

setActiveTab("itemEntry");
await refreshDashboard();
startLiveFeed();
window.setInterval(refreshDashboard, 6000);
