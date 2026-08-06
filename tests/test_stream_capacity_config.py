import api.server as server
from streams.manager import StreamManager, _rtsp_source_for_attempt
from database.camera_db import CameraDB


def test_camera_fanout_uses_bounded_low_cost_preview_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("STREAM_FRAME_WIDTH", "640")
    monkeypatch.setenv("STREAM_PREVIEW_FPS", "6")
    monkeypatch.setenv("STREAM_JPEG_QUALITY", "70")
    manager = StreamManager(snapshot_dir=tmp_path)
    captured = []

    monkeypatch.setattr(manager, "start", lambda config: captured.append(config) or {"status": "starting"})
    cameras = [
        {
            "id": index,
            "name": f"Camera {index}",
            "stream_url": f"rtsp://nvr/Streaming/Channels/{index}02",
            "slot_number": index,
            "is_active": True,
        }
        for index in range(1, 27)
    ]

    result = manager.ensure_from_cameras(cameras)

    assert len(result["streams"]) == 26
    assert len(captured) == 26
    assert {config.width for config in captured} == {640}
    assert {config.preview_fps for config in captured} == {6.0}
    assert {config.jpeg_quality for config in captured} == {70}


def test_individual_camera_start_uses_same_low_cost_settings(monkeypatch):
    monkeypatch.setenv("STREAM_FRAME_WIDTH", "640")
    monkeypatch.setenv("STREAM_PREVIEW_FPS", "6")
    monkeypatch.setenv("STREAM_JPEG_QUALITY", "70")
    captured = []

    class Manager:
        def start(self, config):
            captured.append(config)
            return {"status": "starting"}

    monkeypatch.setattr(server, "_get_stream_manager", lambda: Manager())
    server._start_stream_for_camera(
        {"id": 26, "name": "Camera 26", "stream_url": "rtsp://nvr/2602", "slot_number": 26}
    )

    assert captured[0].width == 640
    assert captured[0].preview_fps == 6.0
    assert captured[0].jpeg_quality == 70


def test_legacy_seven_camera_seed_expands_to_all_26_substreams(tmp_path, monkeypatch):
    db = CameraDB(str(tmp_path / "cameras.db"))
    for slot, channel in enumerate((2, 5, 6, 16, 20, 23, 25), start=1):
        camera = db.add_camera(
            f"Zavod NVR Camera {channel}",
            f"rtsp://admin:secret@nvr.test/Streaming/Channels/{channel}01",
            status="connected",
        )
        db.assign_slot(camera["id"], slot)
    monkeypatch.setenv("CAMERA_CONTROLLER_HOST", "nvr.test")
    monkeypatch.setenv("CAMERA_CONTROLLER_CHANNELS", "2,5,6,16,20,23,25")
    monkeypatch.setenv("CAMERA_CONTROLLER_STREAM_TEMPLATE", "/Streaming/Channels/{channel}01")
    captured = {}

    def register(controller, camera_db):
        captured["controller"] = controller
        for slot, channel in enumerate(controller.channels, start=1):
            camera = camera_db.add_camera(
                f"Zavod NVR Camera {channel}",
                f"rtsp://nvr.test/Streaming/Channels/{channel}02",
                status="connected",
            )
            camera_db.assign_slot(camera["id"], slot)
        return {}

    monkeypatch.setattr(server, "_register_controller_channels", register)
    monkeypatch.setattr(server, "_sync_config_active_cameras", lambda camera_db: {})

    server._seed_cameras_from_environment(db)

    assert captured["controller"].channels == list(range(1, 27))
    assert captured["controller"].stream_path_template.endswith("{channel}02")
    assert len(db.list_active_cameras(include_secret=False)) == 26
    assert all(row["masked_stream_url"].endswith("02") for row in db.list_active_cameras(include_secret=False))


def test_hikvision_profile_fallback_works_in_both_directions():
    assert _rtsp_source_for_attempt("rtsp://nvr/Streaming/Channels/1102", 1).endswith("1102")
    assert _rtsp_source_for_attempt("rtsp://nvr/Streaming/Channels/1102", 2).endswith("1101")
    assert _rtsp_source_for_attempt("rtsp://nvr/Streaming/Channels/1101", 2).endswith("1102")
    assert server._alternate_hikvision_stream_profile("rtsp://nvr/Streaming/Channels/1102").endswith("1101")
    assert server._alternate_hikvision_stream_profile("rtsp://nvr/Streaming/Channels/2601").endswith("2602")
