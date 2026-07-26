from pathlib import Path

from tracking.tracker import ObjectTracker


class Values:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values

    def __getitem__(self, index):
        value = self.values[index]
        return Values(value) if isinstance(value, list) else value


class FakeBoxes:
    id = None
    cls = Values([0])
    conf = Values([0.9])
    xyxy = Values([[10, 10, 50, 50]])


class FakeModel:
    def predict(self, **_kwargs):
        return [
            type(
                "Result",
                (),
                {"names": {0: "box"}, "boxes": FakeBoxes()},
            )()
        ]


def test_track_ids_are_isolated_per_camera_tracker():
    model = FakeModel()
    first_camera = ObjectTracker(model)
    second_camera = ObjectTracker(model)

    assert first_camera.update(object())[0].track_id == 1
    assert second_camera.update(object())[0].track_id == 1
    assert first_camera.update(object())[0].track_id == 1

    first_camera.reset()
    assert first_camera.update(object())[0].track_id == 1
    assert second_camera.update(object())[0].track_id == 1


def test_main_never_reuses_old_detections_on_new_frames():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8"
    )

    assert "object_trackers = {" in source
    assert "LatestFrameInferenceScheduler(processors)" in source
    assert "last_detections.get" not in source
    assert '"stale": True' in source
    assert "last_detections_by_camera[cam.name] = []" in source
