import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.access_control_db import AccessControlDB


def test_new_user_dashboard_starts_empty(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Blank User", "blank@example.com")

    dashboard = db.resolve_dashboard(user_id=user["id"])

    assert dashboard["modules"] == []
    assert dashboard["permissions"] == []


def test_role_assignment_adds_modules_and_permissions(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Operator", "operator@example.com")

    db.assign_role(user["id"], "operator")
    dashboard = db.resolve_dashboard(user_id=user["id"])

    module_codes = {module["code"] for module in dashboard["modules"]}
    assert "live_monitoring" in module_codes
    assert "camera.live_view" in dashboard["permissions"]


def test_user_deny_module_overrides_role_allow(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Operator", "operator@example.com")
    db.assign_role(user["id"], "operator")

    db.set_user_module(user["id"], "live_monitoring", "deny")
    dashboard = db.resolve_dashboard(user_id=user["id"])

    module_codes = {module["code"] for module in dashboard["modules"]}
    assert "live_monitoring" not in module_codes


def test_user_scope_assignment_is_resolved(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Scoped", "scoped@example.com")

    db.set_user_scope(user["id"], "camera", ["12", "13"])
    dashboard = db.resolve_dashboard(user_id=user["id"])

    assert dashboard["scope"]["camera_ids"] == ["12", "13"]
