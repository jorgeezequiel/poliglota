"""Exercise a real PyTorch CPU operation without model downloads."""

from __future__ import annotations

import pytest

from poliglota.engines.pytorch_engine import PyTorchTranslationEngine


def test_real_pytorch_model_and_tensor_run_on_cpu() -> None:
    """Verify the installed CPU runtime can execute the engine's device path."""
    torch = pytest.importorskip("torch", reason="CPU integration profile requires PyTorch")

    engine = PyTorchTranslationEngine("t5-small", device="cpu")
    model = torch.nn.Linear(2, 1)
    engine._move_model_to_device(model, "cpu")
    inputs = torch.ones((1, 2), device="cpu")

    output = model(inputs)

    assert next(model.parameters()).device.type == "cpu"
    assert inputs.device.type == "cpu"
    assert output.device.type == "cpu"
    assert output.shape == (1, 1)
