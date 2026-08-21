from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.version import Version

from detection.detector import Detection
from tracking.bytetrack_adapter import ByteTrackAdapter


pytest.importorskip("ultralytics")


def _config():
    return str(
        Path(__file__).resolve().parents[1] / "config" / "warehouse_bytetrack.yaml"
    )


def _detection():
    return Detection("baget box", 0.92, (10, 20, 100, 80), class_id=0)


def test_real_ultralytics_84115_uses_isolated_camera_track_classes():
    # requirements.txt allows ultralytics>=8.4.115,<8.5 - match that range
    # instead of pinning an exact patch version the installed one will drift
    # past on every routine dependency update.
    installed = Version(version("ultralytics"))
    assert Version("8.4.115") <= installed < Version("8.5")

    first = ByteTrackAdapter("camera-one", _config())
    second = ByteTrackAdapter("camera-two", _config())

    first_track = first.update([_detection()], (720, 1280, 3), 1, 10.0)[0]
    second_track = second.update([_detection()], (720, 1280, 3), 1, 10.0)[0]

    assert first._tracker.track_class is not second._tracker.track_class
    assert isinstance(first._tracker.tracked_stracks[0], first._tracker.track_class)
    assert isinstance(second._tracker.tracked_stracks[0], second._tracker.track_class)
    assert first_track.track_id == 1
    assert second_track.track_id == 1
