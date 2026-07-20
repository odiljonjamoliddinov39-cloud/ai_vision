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
    assert "window.setInterval(refreshLiveFrames, LIVE_FRAME_REFRESH_MS)" in source
    assert 'document.addEventListener("visibilitychange", syncLiveFrameRefresh)' in source
    assert "new MutationObserver(syncLiveFrameRefresh)" in source
    assert 'fetch(liveFrameUrl(slot), { cache: "no-store" })' in source
    assert "URL.revokeObjectURL(previousObjectUrl)" in source


def test_dashboard_targets_two_live_frame_updates_per_second():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert "const LIVE_FRAME_REFRESH_MS = 500;" in source
    assert 'if (image.dataset.liveLoading === "true") return;' in source


def test_camera_accounts_land_on_the_live_feed_without_removing_other_modules():
    source = (ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")

    assert 'if (!accountModule && role.access?.camera) accountModule = "feed"' in source
    assert 'menus.push({ id: "camera", label: "Camera Control"' in source
    assert 'menus.push({ id: "feed", label: "Camera Feed"' in source


def test_backend_container_keeps_detector_autostart_and_watchdog_enabled():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'AUTO_START_DETECTION: "true"' in compose
    assert 'DETECTION_WATCHDOG_ENABLED: "true"' in compose
    assert 'AUTO_START_DETECTION: "${AUTO_START_DETECTION:-true}"' not in compose


def test_dashboard_asset_version_loads_the_continuous_feed_release():
    html = (ROOT / "dashboard-v2" / "index.html").read_text(encoding="utf-8")

    assert "/dashboard-v2/assets/app.js?v=27" in html
    assert "/dashboard-v2/assets/styles.css?v=27" in html


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
