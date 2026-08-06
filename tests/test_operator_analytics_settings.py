from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "dashboard-v2" / "app.js").read_text(encoding="utf-8")


def test_operator_analytics_uses_the_existing_live_camera_analytics():
    menus = SOURCE[SOURCE.index("function accountMenus"):SOURCE.index("function accountMenuLabel")]
    renderer = SOURCE[SOURCE.index("function renderAccountModule"):SOURCE.index("async function discoverySearch")]

    assert 'id: "analytics", label: "Analytics", sub: "Scan live cameras"' in menus
    assert 'menu.id === "analytics"' in renderer
    assert "renderTrainingAnalytics(els.moduleContent)" in renderer
    assert 'id: "ops_analytics"' not in menus


def test_operator_settings_rerenders_after_async_configuration_load():
    settings = SOURCE[SOURCE.index("function renderSettings"):SOURCE.index("function configPathValue")]

    assert 'accountState ? accountModule === "settings" : state.activeModule === "settings"' in settings
    assert "container.isConnected && settingsVisible" in settings
    assert "renderSettings(container)" in settings
