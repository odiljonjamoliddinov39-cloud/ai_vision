from pathlib import Path

from starlette.requests import Request

from api import server


ROOT = Path(__file__).resolve().parents[1]


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
    assert "window.setInterval(reconcileLiveStreams, LIVE_FRAME_REFRESH_MS)" in source
    assert "const MAX_LIVE_STREAMS = 6;" in source
    assert "new IntersectionObserver(" in source
    assert 'image.dataset.liveVisible !== "false"' in source
    assert 'document.addEventListener("visibilitychange", syncLiveFrameRefresh)' in source


def test_dashboard_uses_first_free_camera_slot_for_new_nvr():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "for (let slot = 1; slot <= MAX_NVR_SLOTS; slot += 1)" in source
    assert "Math.max(...usedSlots) + 1" not in source
    assert "new MutationObserver((mutations) => {" in source
    # Native MJPEG stream: one long-lived connection per visible tile, no
    # per-frame fetch/objectURL polling.
    assert "image.src = url;" in source
    assert 'image.dataset.liveStreaming = "true";' in source
    assert "function stopLiveStream(image)" in source
    assert 'image.removeAttribute("src");' in source
    assert 'data-live-priming="true" src="${liveFrameUrl(channel.slot_number)}"' in source
    assert 'loading="lazy" decoding="async"' in source
    assert "image.complete && image.naturalWidth > 0" in source


def test_dashboard_caps_concurrent_live_streams_to_stay_under_connection_limit():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const LIVE_FRAME_REFRESH_MS = 150;" in source
    # Only the first MAX_LIVE_STREAMS visible tiles hold an MJPEG connection so
    # the browser's ~6-per-origin connection cap never starves API calls.
    assert "const streaming = visibleImages.slice(0, MAX_LIVE_STREAMS);" in source
    assert "streaming.forEach(startLiveStream);" in source
    assert "if (!streamingSet.has(image)) stopLiveStream(image);" in source


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


def test_dashboard_backs_off_a_failed_stream_instead_of_holding_the_connection():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const LIVE_STREAM_ERROR_BACKOFF_MS = 4000;" in source
    assert (
        "image.dataset.liveErrorUntil = String(Date.now() + LIVE_STREAM_ERROR_BACKOFF_MS);"
        in source
    )
    # On error we drop the connection (freeing a stream slot) and wait out the
    # backoff before reconnecting.
    assert "stopLiveStream(image);" in source
    assert (
        "if (backoffUntil && Date.now() < backoffUntil) return;" in source
    )


def test_camera_accounts_land_on_the_live_feed_without_removing_other_modules():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'if (!accountModule && role.access?.camera) accountModule = "feed"' in source
    assert 'menus.push({ id: "camera", label: "Camera Control"' in source
    assert 'menus.push({ id: "feed", label: "Camera Feed"' in source


def test_camera_control_rows_use_stream_health_for_live_slots():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'api("/api/v2/streams/health").catch(() => ({ streams: [] }))' in source
    assert "function streamStatusBySlot()" in source
    assert 'const isLive = stream?.status === "online";' in source
    assert 'const label = isLive' in source
    assert '? "Live"' in source


def test_backend_container_keeps_detector_autostart_and_watchdog_enabled():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'AUTO_START_DETECTION: "true"' in compose
    assert 'DETECTION_WATCHDOG_ENABLED: "true"' in compose
    assert 'AUTO_START_DETECTION: "${AUTO_START_DETECTION:-true}"' not in compose


def test_dashboard_asset_version_loads_the_continuous_feed_release():
    html = (ROOT / "dashboard-v2" / "index.html").read_text(encoding="utf-8")

    assert "/dashboard-v2/assets/app.js?v=51" in html
    assert "/dashboard-v2/assets/styles.css?v=39" in html


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
