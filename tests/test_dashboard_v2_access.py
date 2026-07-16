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


def test_user_password_is_hashed_and_authenticates(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Secure User", "secure@example.com")

    updated = db.set_user_password(user["id"], "StrongPass123")
    assert updated["has_password"] is True

    with db.db.connect() as conn:
        row = conn.execute(db._sql("SELECT password_hash FROM ac_users WHERE id = ?"), (user["id"],)).fetchone()
    assert row["password_hash"] != "StrongPass123"
    assert db.authenticate_user("secure@example.com", "StrongPass123")["email"] == "secure@example.com"
    assert db.authenticate_user("secure@example.com", "wrong") is None


def test_session_token_resolves_user(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Session User", "session@example.com")
    db.set_user_password(user["id"], "StrongPass123")

    authenticated = db.authenticate_user("session@example.com", "StrongPass123")
    token = db.create_session(authenticated["id"])

    assert db.get_user_by_session_token(token["token"])["email"] == "session@example.com"
    assert db.get_user_by_session_token("bad-token") is None


def test_auth_preference_can_be_selected(tmp_path):
    db = AccessControlDB(str(tmp_path / "access.db"))
    user = db.create_user("Biometric User", "bio@example.com")

    updated = db.set_user_auth_preference(user["id"], "password_and_biometric")

    assert updated["preferred_auth_method"] == "password_and_biometric"
