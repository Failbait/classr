import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sys as _sys
import types

# capture.py imports the Pi-only camera module at import time; stub it for this unit test.
_sys.modules.setdefault("camera", types.SimpleNamespace(
    read_frame=None, start_camera=None, stop_camera=None))

from capture import frame_path


def test_frame_path_is_timestamped_and_indexed():
    path = frame_path("captures", datetime(2026, 10, 9, 14, 5, 7), 3)
    assert path == Path("captures/frame_20261009_140507_03.png")
