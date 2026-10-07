import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import detector


def fake_model(patch_size=16, num_windows=2):
    return SimpleNamespace(model_config=SimpleNamespace(patch_size=patch_size,
                                                        num_windows=num_windows))


def test_rfdetr_shape_native_when_size_is_zero(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_IMAGE_SIZE", 0)
    assert detector._rfdetr_shape(fake_model()) is None


def test_rfdetr_shape_rounds_to_valid_multiple(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_IMAGE_SIZE", 1000)
    side, _ = detector._rfdetr_shape(fake_model())
    assert side % 32 == 0 and abs(side - 1000) <= 16


def test_unknown_rfdetr_size_fails_clearly(monkeypatch):
    monkeypatch.setattr(config, "MODEL_NAME", "rfdetr-huge")
    try:
        detector.load_model()
    except ValueError as exc:
        assert "huge" in str(exc)
    else:
        raise AssertionError("expected ValueError")
