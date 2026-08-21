import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_locustfile_imports_in_isolation():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from loadtests.locustfile import CaptureApiUser, CaptureChatUser, CaptureFileUser",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
