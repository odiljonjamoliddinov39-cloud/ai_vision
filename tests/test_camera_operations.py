import api.server as server
from database.camera_db import CameraDB
from database.vision_config_db import VisionConfigDB


class FakeStreamManager:
    def __init__(self, streams=None):
        self.streams = streams or []
        self.stopped = []

    def status(self):
        return {"streams": self.streams}

    def stop(self, camera_id):
        self.stopped.append(camera_id)


def test_camera_payload_exposes_operator_contract_and_persisted_block(tmp_path, monkeypatch):
    camera_db = CameraDB(str(tmp_path / "cameras.db"))
    camera = camera_db.add_camera("Camera 5", "rtsp://admin:secret@example.test/live")
    camera_db.assign_slot(camera["id"], 5)
    vision_path = str(tmp_path / "vision.db")
    config_db = VisionConfigDB(vision_path)
    block = config_db.create_block("Warehouse A")
    config_db.assign_camera_block(camera["id"], block["id"])
    stream_manager = FakeStreamManager([{
        "channel_id": str(camera["id"]), "status": "online", "fps": 24.5,
        "last_frame_at": "2026-08-06T00:00:00+00:00", "decode_errors": 3,
        "reconnect_count": 2,
    }])
    monkeypatch.setattr(server, "_get_camera_db", lambda: camera_db)
    monkeypatch.setattr(server, "_get_stream_manager", lambda: stream_manager)
    monkeypatch.setenv("VISION_DB_PATH", vision_path)

    row = server._camera_operations_payload()[0]

    assert row["camera_id"] == camera["id"]
    assert row["camera_name"] == "Camera 5"
    assert row["rtsp_url"] == "rtsp://admin:****@example.test/live"
    assert row["status"] == "live"
    assert row["fps"] == 24.5
    assert row["last_frame"] == "2026-08-06T00:00:00+00:00"
    assert row["decode_errors"] == 3
    assert row["reconnect_count"] == 2
    assert row["block_id"] == block["id"]
    assert row["block_name"] == "Warehouse A"


def test_reconnect_restarts_only_selected_camera(tmp_path, monkeypatch):
    camera_db = CameraDB(str(tmp_path / "cameras.db"))
    first = camera_db.add_camera("Camera 1", "rtsp://example.test/1")
    second = camera_db.add_camera("Camera 2", "rtsp://example.test/2")
    camera_db.assign_slot(first["id"], 1)
    camera_db.assign_slot(second["id"], 2)
    stream_manager = FakeStreamManager()
    started = []
    monkeypatch.setattr(server, "_get_camera_db", lambda: camera_db)
    monkeypatch.setattr(server, "_get_stream_manager", lambda: stream_manager)
    monkeypatch.setattr(server, "_start_stream_for_camera", lambda camera: started.append(camera["id"]) or {"status": "starting"})
    monkeypatch.setattr(server, "_camera_operations_payload", lambda: [{"id": first["id"]}, {"id": second["id"]}])
    monkeypatch.setattr(server, "stop_detection", lambda: (_ for _ in ()).throw(AssertionError("global detector restart")))

    server.reconnect_operator_camera(second["id"])

    assert stream_manager.stopped == [str(second["id"])]
    assert started == [second["id"]]


def test_blocks_endpoint_returns_persistent_assignment_choices(tmp_path, monkeypatch):
    vision_path = str(tmp_path / "vision.db")
    config_db = VisionConfigDB(vision_path)
    block = config_db.create_block("Packaging")
    monkeypatch.setenv("VISION_DB_PATH", vision_path)

    response = server.list_camera_assignment_blocks()

    assert response["meta"] == {"count": 1}
    assert response["data"] == [{**block, "camera_count": 0}]


def test_camera_management_ui_has_only_approved_controls():
    source = (server.ROOT / "dashboard-v2" / "app.js").read_text(encoding="utf-8")
    camera_section = source[source.index("async function renderOperatorCameraManagement"):source.index("async function applySearchRow")]
    assert 'api("/api/v1/cameras"' in camera_section
    assert 'data-camera-block-name' in camera_section
    assert 'JSON.stringify({ block_name: blockName })' in camera_section
    assert '<select data-camera-block' not in camera_section
    assert "data-camera-reconnect" in camera_section
    assert "data-camera-save" in camera_section
    assert "data-camera-test" not in camera_section
    assert "data-camera-refresh" not in camera_section
    assert "window.setInterval" in camera_section


def test_typed_block_name_is_created_and_assigned(tmp_path, monkeypatch):
    camera_db = CameraDB(str(tmp_path / "cameras.db"))
    camera = camera_db.add_camera("Camera 1", "rtsp://example.test/1")
    vision_path = str(tmp_path / "vision.db")
    monkeypatch.setattr(server, "_get_camera_db", lambda: camera_db)
    monkeypatch.setattr(server, "_camera_operations_payload", lambda: [{"id": camera["id"], "block_name": "Warehouse North"}])
    monkeypatch.setenv("VISION_DB_PATH", vision_path)

    response = server.update_operator_camera(
        camera["id"], server.CameraOperationsUpdate(block_name="  Warehouse North  ")
    )

    blocks = VisionConfigDB(vision_path).list_blocks()
    settings = VisionConfigDB(vision_path).get_camera_settings_map([camera["id"]])[str(camera["id"])]
    assert response["data"]["block_name"] == "Warehouse North"
    assert [block["name"] for block in blocks] == ["Warehouse North"]
    assert settings["block_id"] == blocks[0]["id"]


def test_typed_block_name_reuses_existing_block_case_insensitively(tmp_path, monkeypatch):
    camera_db = CameraDB(str(tmp_path / "cameras.db"))
    camera = camera_db.add_camera("Camera 1", "rtsp://example.test/1")
    vision_path = str(tmp_path / "vision.db")
    config_db = VisionConfigDB(vision_path)
    existing = config_db.create_block("Packaging")
    monkeypatch.setattr(server, "_get_camera_db", lambda: camera_db)
    monkeypatch.setattr(server, "_camera_operations_payload", lambda: [{"id": camera["id"]}])
    monkeypatch.setenv("VISION_DB_PATH", vision_path)

    server.update_operator_camera(camera["id"], server.CameraOperationsUpdate(block_name="packaging"))

    assert len(config_db.list_blocks()) == 1
    assert config_db.get_camera_settings_map([camera["id"]])[str(camera["id"])]["block_id"] == existing["id"]
