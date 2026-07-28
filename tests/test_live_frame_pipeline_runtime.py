from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
NODE = Path(
    r"C:\Users\Porter\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\node\bin\node.exe"
)


def test_live_frame_pipeline_runtime_harness():
    result = subprocess.run(
        [str(NODE), str(ROOT / "tests" / "live_frame_pipeline_harness.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "live-frame pipeline harness: PASS" in result.stdout
