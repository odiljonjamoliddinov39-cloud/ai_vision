import json
from pathlib import Path

from starlette.requests import Request

from api import server


ROOT = Path(__file__).resolve().parents[1]


def test_backend_supports_one_hundred_active_camera_slots():
    assert server.MAX_CAMERA_SLOTS == 100


def _live_frame_request(slot: int) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/api/live_frame",
            "query_string": f"slot={slot}".encode(),
            "headers": [],
            "client": ("127.0.0.1", 5000),
            "server": ("testserver", 443),
        }
    )


def test_dashboard_continuously_refreshes_mounted_live_frames():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert source.count("data-live-frame data-live-slot") == 3
    assert "new WebSocket(liveWebSocketUrl(slots))" in source
    assert 'socket.binaryType = "arraybuffer";' in source
    assert 'socket.addEventListener("message"' in source
    assert "new IntersectionObserver(" not in source
    assert "window.setInterval(reconcileLiveStreams" not in source
    assert source.count("<canvas data-live-frame") == 2
    assert '<canvas class="feed-stale" data-live-frame' in source
    assert 'document.addEventListener("visibilitychange"' not in source


def test_dashboard_uses_first_free_camera_slot_for_new_nvr():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const MAX_NVR_SLOTS = 100;" in source
    assert "for (let slot = 1; slot <= MAX_NVR_SLOTS; slot += 1)" in source
    assert "Math.max(...usedSlots) + 1" not in source
    assert "new MutationObserver((mutations) => {" in source
    # Every mounted tile receives frames from one multiplexed WebSocket.
    assert "renderLiveSocketFrame(slot, payload.slice(2));" in source
    assert "createImageBitmap(new Blob([jpegBytes]" in source
    assert '.drawImage(bitmap, 0, 0);' in source
    assert "function stopLiveFrameRefresh()" in source
    assert 'data-live-priming="true" role="img"' in source
    assert "/api/live_frame?slot=${slot}" not in source
    assert "image.complete && image.naturalWidth > 0" not in source


def test_dashboard_streams_offscreen_cameras_without_viewport_gating():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "MAX_LIVE_STREAMS" not in source
    assert "liveVisible" not in source
    assert "document.hidden" not in source
    assert "url.searchParams.set(\"slots\", slots);" in source
    assert ".join(\",\");" in source


def test_dashboard_live_frame_observer_ignores_badge_text_mutations():
    # setFeedBadgeLive() sets badge.textContent, which is itself a childList
    # mutation - without filtering it out, the observer retriggers a refresh
    # on every completed request (success or failure), forming a tight loop
    # that ignores LIVE_FRAME_REFRESH_MS. Only structural mutations (feed
    # elements actually added/removed) should call syncLiveFrameRefresh.
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert (
        "return !(target instanceof Element && target.closest(\".feed-transmitting\"));"
        in source
    )
    assert "if (structuralChange) syncLiveFrameRefresh();" in source


def test_dashboard_reconnects_the_continuous_socket_after_failure():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const LIVE_STREAM_RECONNECT_MS = 1500;" in source
    assert "function scheduleLiveSocketReconnect()" in source
    assert "scheduleLiveSocketReconnect();" in source
    assert 'socket.addEventListener("error", () => socket.close());' in source


def test_backend_multiplexes_slots_on_one_websocket():
    source = (ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert '@app.websocket("/api/live_ws")' in source
    assert 'raw_slots = websocket.query_params.get("slots", "")' in source
    assert 'await websocket.send_bytes(struct.pack("!H", slot) + data)' in source
    assert 'os.getenv("LIVE_WEBSOCKET_FPS", "10")' in source


def test_camera_accounts_land_on_the_live_feed_without_removing_other_modules():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'if (!accountModule && role.access?.camera) accountModule = "feed"' in source
    assert 'menus.push({ id: "camera", label: "Camera Control"' in source
    assert 'menus.push({ id: "camera_info", label: "Camera Info"' in source
    assert 'menus.push({ id: "feed", label: "Camera Feed"' in source


def test_camera_feed_groups_rooms_and_allows_renaming():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")

    assert "company.cameraConfig.feedGroups" in source
    assert "const FEED_GROUP_SIZE = 8;" in source
    assert "function inferFeedGroup(nvr, nvrIndex, channel, channelIndex, nvrCount)" in source
    assert "function feedGroupsHtml(config)" in source
    assert 'data-acc-form="feed-group"' in source
    assert 'data-feed-group-id="${escapeAttr(group.id)}"' in source
    assert 't("feed.group_saved")' in source
    assert ".feed-group-head" in styles
    assert ".feed-group-form" in styles


def test_camera_info_page_lists_connected_camera_models():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'if (menu.id === "camera_info")' in source
    assert 'accountsApi("/api/v2/devices", { force })' in source
    assert "function renderCameraInfo(container, force = false)" in source
    assert 't("table.camera")' in source
    assert 't("table.model")' in source
    assert 't("table.ai_slot")' in source
    assert "Waiting for slot" in source
    assert "Not assigned" in source
    assert "response.device?.model" in source
    assert "function cameraInfoDiagnosticsText(row)" in source
    assert "stream?.last_error" in source
    assert "stream?.frame_age_ms" in source
    assert "stream?.reconnect_count" in source
    assert "stream?.decode_errors" in source


def test_dashboard_has_ru_eng_language_toggle():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "dashboard-v2" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")

    assert 'id="languageToggle"' in html
    assert "LANGUAGE_KEY" in source
    assert "function setLanguageToggleChrome()" in source
    assert "function rerenderCurrentViewForLanguage()" in source
    assert '"menu.camera_info": "Инфо камер"' in source
    assert ".language-toggle" in styles


def test_camera_control_rows_use_stream_health_for_live_slots():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'api("/api/v2/streams/health").catch(() => ({ streams: [] }))' in source
    assert "function streamStatusBySlot()" in source
    assert 'const isLive = stream?.status === "online";' in source
    assert 'const label = isLive' in source
    assert '? t("status.live")' in source
    assert "nvr-channel-detail" in source
    assert "stream?.decode_errors" in source


def test_backend_container_keeps_detector_autostart_and_watchdog_enabled():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'AUTO_START_DETECTION: "true"' in compose
    assert 'DETECTION_WATCHDOG_ENABLED: "true"' in compose
    assert 'AUTO_START_DETECTION: "${AUTO_START_DETECTION:-true}"' not in compose


def test_dashboard_asset_version_loads_the_continuous_feed_release():
    html = (ROOT / "dashboard-v2" / "index.html").read_text(encoding="utf-8")

    assert "/dashboard-v2/assets/app.js?v=70" in html
    assert "/dashboard-v2/assets/styles.css?v=50" in html


def test_latest_detections_endpoint_exposes_camera_slots_for_feed_overlay(tmp_path, monkeypatch):
    health_path = tmp_path / "detection_health.json"
    health_path.write_text(
        json.dumps(
            {
                "state": "running",
                "updated_at": "2026-07-31T10:00:00",
                "cameras": [{"name": "NVR Camera 5", "slot_number": 5}],
                "last_detections_by_camera": {
                    "NVR Camera 5": [
                        {
                            "class_name": "baget box",
                            "confidence": 0.91,
                            "frame_width": 1280,
                            "frame_height": 720,
                            "bbox": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "DETECTION_HEALTH_PATH", health_path)

    payload = server.v2_latest_detections()

    assert payload["cameras"] == [{"name": "NVR Camera 5", "slot_number": 5}]
    assert payload["detections"]["NVR Camera 5"][0]["bbox"]["x2"] == 110


def test_camera_feed_draws_detection_boxes_and_labels_on_live_canvas():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")

    assert 'api("/api/v2/detections/latest", { force: true })' in source
    assert "function liveDetectionOverlayForCanvas(canvas)" in source
    assert "function drawLiveDetectionOverlay(canvas, detections)" in source
    assert "function liveDetectionLabel(detection)" in source
    assert "ctx.strokeRect(x, y, boxWidth, boxHeight);" in source
    assert "ctx.fillText(label, labelX + 7, labelY + 4, labelWidth - 14);" in source
    assert 'data-live-camera-aliases="${escapeAttr(aliases)}"' in source
    assert 'data-live-detection-overlay data-live-slot="${channel.slot_number}"' in source
    assert "function redrawVisibleDetectionOverlays()" in source
    assert "function redrawVisibleLiveFramesWithDetections()" not in source
    assert ".live-preview canvas" in styles
    assert ".feed-detection-layer" in styles


def test_dashboard_navigation_uses_cached_data_until_refresh():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const readCache = new Map();" in source
    assert "function cachedRead(key, loader, force = false)" in source
    assert 'return cachedRead(readCacheKey("api", path)' in source
    assert 'return cachedRead(readCacheKey("accounts", path)' in source
    assert 'return cachedRead(readCacheKey("catalog", path)' in source
    assert "invalidateDashboardReads();" in source
    assert "if (accountModule === accButton.dataset.accModule) return;" in source
    assert "if (state.activeModule === button.dataset.module) return;" in source


def test_dashboard_settings_page_edits_system_config_dynamically():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")

    assert 'api("/api/config", { force })' in source
    assert 'data-settings-form="system-config"' in source
    assert "function systemSettingsHtml(config)" in source
    assert "function readSystemSettingsForm(form)" in source
    assert 'method: "PATCH"' in source
    assert "confidence_threshold" in source
    assert "recognition_similarity_threshold" in source
    assert "live_frame_jpeg_quality" in source
    assert "spatial_enabled" in source
    assert "warehouse_confidence_threshold" in source
    assert ".settings-config-form" in styles
    assert ".settings-field-grid" in styles


def test_dashboard_has_ai_modules_page_from_video_analytics_spec():
    import json

    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")
    catalog = json.loads((ROOT / "dashboard-v2" / "video-analytics-functions.json").read_text(encoding="utf-8"))

    assert 'menus.push({ id: "ai_modules", label: "AI Modules"' in source
    assert 'FEATURE_CATALOG_PATH = "/dashboard-v2/assets/video-analytics-functions.json"' in source
    assert "function renderAiModules(container" in source
    assert "data-ai-modules-filters" in source
    assert "aiModulesSummaryHtml(catalog, rows)" in source
    assert "aiModuleSectionCardsHtml(catalog)" in source
    assert "aiModulesTableHtml(visibleRows)" in source
    assert ".ai-modules-filters" in styles
    assert ".ai-module-section-grid" in styles
    assert ".ai-modules-table" in styles
    assert catalog["meta"]["sections_total"] == 18
    assert catalog["meta"]["features_total"] == 270
    assert len(catalog["sections"]) == 18
    assert sum(len(section["features"]) for section in catalog["sections"]) == 270


def test_dashboard_exposes_operator_platform_pages_from_spec():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard-v2" / "styles.css").read_text(encoding="utf-8")

    for module_id in ["enterprise", "events", "zones", "ai_models", "integrations"]:
        assert f'id: "{module_id}"' in source
        assert f'menu.{module_id}' in source

    assert "function renderEnterprisePage(container)" in source
    assert "function renderEventsPage(container, force = false)" in source
    assert "function renderSafetyZonesPage(container)" in source
    assert "function renderAiModelsPage(container, force = false)" in source
    assert "function renderIntegrationsPage(container, force = false)" in source
    assert "feedGroupRecords(config)" in source
    assert "eventRowsFromPayloads(enginePayload, auditPayload, logPayload)" in source
    assert ".platform-summary" in styles
    assert ".platform-card-grid" in styles
    assert ".platform-status" in styles


def test_dashboard_startup_retries_and_exposes_a_visible_failure_state():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "LOAD_RETRY_DELAYS_MS = [500, 1000, 2000]" in source
    assert "async function loadDashboard(attempt = 0)" in source
    assert "Dashboard data could not be loaded" in source
    assert "data-retry-dashboard" in source


def test_live_frame_rate_limits_are_isolated_per_camera_slot(monkeypatch):
    monkeypatch.setenv("SECURITY_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("LIVE_FRAME_RATE_LIMIT_PER_MINUTE", "1")
    server._rate_limits.clear()

    assert server._rate_limit(_live_frame_request(1)) is None
    assert server._rate_limit(_live_frame_request(2)) is None
    assert server._rate_limit(_live_frame_request(1)).status_code == 429

    server._rate_limits.clear()


def test_live_frames_have_a_dedicated_higher_rate_limit(monkeypatch):
    monkeypatch.setenv("SECURITY_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("LIVE_FRAME_RATE_LIMIT_PER_MINUTE", "2")
    server._rate_limits.clear()

    assert server._rate_limit(_live_frame_request(1)) is None
    assert server._rate_limit(_live_frame_request(1)) is None
    assert server._rate_limit(_live_frame_request(1)).status_code == 429

    server._rate_limits.clear()


def test_analytics_movements_chart_is_wired_to_ai_check_in_ledger():
    # The AI Check-ins chart should use the YOLO warehouse ledger, not the
    # older occupancy check-in/check-out activity tracker.
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'accountsApi("/api/warehouse/movements?limit=200")' in source
    assert "function aggregateMovements(movements)" in source
    assert 'movementsSpec.points = aggregateMovements(movements);' in source
    assert "points: emptyMovements()," in source
    assert 'title: "AI Check-ins"' in source


def test_analytics_shows_a_recent_activity_card_from_real_events():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "data-recent-activity" in source
    assert "function recentActivityHtml(movements)" in source
    assert "function timeAgo(timestamp)" in source
    assert "AI Check in:" in source
    assert "Checked out" not in source
