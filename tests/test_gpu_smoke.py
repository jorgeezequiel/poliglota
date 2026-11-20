from __future__ import annotations

import pytest

from poliglota.engines.pytorch_engine import PyTorchTranslationEngine

try:
    import torch
except (ImportError, OSError):
    torch = None

HAS_CUDA = torch is not None and torch.cuda.is_available()


@pytest.mark.gpu
@pytest.mark.skipif(not HAS_CUDA, reason="real CUDA device is not available")
def test_cuda_smoke_moves_real_model_and_runs_tensor_on_gpu() -> None:
    """Exercise a real torch module and tensor on CUDA without downloading models."""
    engine = PyTorchTranslationEngine("t5-small", device="cuda")
    assert engine.device == "cuda"
    model = torch.nn.Linear(2, 1)
    engine._move_model_to_device(model, engine.device)
    inputs = torch.ones((1, 2), device=engine.device)

    output = model(inputs)
    torch.cuda.synchronize()

    assert next(model.parameters()).device.type == "cuda"
    assert inputs.device.type == "cuda"
    assert output.device.type == "cuda"
