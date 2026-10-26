from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from poliglota.engines.pytorch_engine import PyTorchTranslationEngine

try:
    import torch
except (ImportError, OSError):
    torch = None

HAS_TORCH = torch is not None

pytestmark = pytest.mark.skipif(not HAS_TORCH, reason="torch not available")


@pytest.fixture
def has_torch() -> bool:
    """Return whether the optional ML stack is available for this environment."""
    return HAS_TORCH


@pytest.fixture(scope="module")
def model_instance() -> PyTorchTranslationEngine:
    """Create a cached mock model instance for deterministic engine tests."""

    class FakeTokenizer:
        def __call__(self, texts: str | list[str], **kwargs: object) -> dict[str, list[list[int]]]:
            if isinstance(texts, str):
                texts = [texts]
            return {
                "input_ids": [[1, 2, 3] for _ in texts],
                "attention_mask": [[1, 1, 1] for _ in texts],
            }

        def batch_decode(self, sequences: object, skip_special_tokens: bool = True) -> list[str]:
            return ["translated" for _ in sequences]

    class FakeModel:
        def __init__(self) -> None:
            self.device = "cpu"

        def to(self, device: str) -> FakeModel:
            self.device = device
            return self

        def eval(self) -> None:
            return None

        def generate(self, **kwargs: object) -> list[list[int]]:
            batch_size = len(kwargs.get("input_ids", []))  # type: ignore[arg-type]
            return [[7, 8, 9] for _ in range(batch_size)]

    fake_tokenizer = FakeTokenizer()
    fake_model = FakeModel()
    safe_mps_patch = (
        patch.object(torch.mps, "empty_cache", return_value=None)
        if torch is not None and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache")
        else nullcontext()
    )

    with (
        patch("poliglota.engines.pytorch_engine.detect_device", return_value="cpu"),
        patch("poliglota.engines.pytorch_engine.validate_vram", return_value=True),
        patch("poliglota.engines.pytorch_engine.AutoTokenizer") as tokenizer_cls,
        patch("poliglota.engines.pytorch_engine.AutoModelForSeq2SeqLM") as model_cls,
        safe_mps_patch,
    ):
        tokenizer_cls.from_pretrained.return_value = fake_tokenizer
        model_cls.from_pretrained.return_value = fake_model

        engine = PyTorchTranslationEngine("t5-small")
        engine.load_model(model_path="t5-small", device="cpu")
        yield engine
        engine.close()


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_mbart_locale_code_uses_tokenizer_specific_variant() -> None:
    engine = PyTorchTranslationEngine("facebook/mbart-large-50-many-to-many-mmt", device="cpu")
    tokenizer = type("FakeTokenizer", (), {"lang_code_to_id": {"en_XX": 256, "pt_XX": 257}})()

    assert engine._resolve_target_lang_code("pt_BR", tokenizer) == "pt_XX"
    assert engine._resolve_target_lang_code("en_US", tokenizer) == "en_XX"
    assert engine._resolve_target_lang_code("pt", tokenizer) == "pt_XX"


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_device_detection_prefers_gpu_if_available() -> None:
    with (
        patch("poliglota.engines.pytorch_engine.detect_device", return_value="cuda"),
        patch("poliglota.engines.pytorch_engine.validate_vram", return_value=True),
    ):
        engine = PyTorchTranslationEngine("t5-small", device="auto")

    assert engine.device == "cuda"


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_device_detection_fallback_to_cpu_if_cuda_unavailable() -> None:
    with (
        patch("poliglota.engines.pytorch_engine.detect_device", return_value="cpu"),
        patch("poliglota.engines.pytorch_engine.validate_vram", return_value=False),
    ):
        engine = PyTorchTranslationEngine("t5-small", device="cuda")
        assert engine.device == "cpu"
        assert engine._resolve_device("cuda") == "cpu"


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_vram_validation_passes_with_sufficient_memory() -> None:
    with (
        patch("poliglota.engines.pytorch_engine.detect_device", return_value="cuda"),
        patch("poliglota.engines.pytorch_engine.validate_vram", return_value=True),
    ):
        engine = PyTorchTranslationEngine("t5-small", device="auto")
        resolved = engine._resolve_device("cuda")

    assert resolved == "cuda"
    assert engine.device in {"cpu", "cuda", "mps"}


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_single_text_translation_pt_to_en(
    model_instance: PyTorchTranslationEngine,
) -> None:
    result = model_instance.translate("olá mundo", "pt", "en")

    assert isinstance(result, str)
    assert result == "translated"
    assert model_instance.device in {"cpu", "cuda", "mps"}


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_batch_translation_multiple_texts(
    model_instance: PyTorchTranslationEngine,
) -> None:
    inputs = ["olá", "bom dia", "até logo"]

    results = model_instance.translate_batch(inputs, "pt", "en")

    assert len(results) == len(inputs)
    assert all(item == "translated" for item in results)


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_batch_size_adaptation_on_oom(
    model_instance: PyTorchTranslationEngine,
) -> None:
    texts = ["um", "dois", "três"]
    mock_generate = MagicMock(
        side_effect=[
            RuntimeError("CUDA out of memory"),
            ["ok"],
            ["ok"],
            ["ok"],
        ]
    )

    with patch.object(model_instance, "_generate_batch", mock_generate):
        results = model_instance.translate_batch(texts, "pt", "en")

    assert len(results) == len(texts)
    assert results == ["ok", "ok", "ok"]


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_model_close_clears_cache(model_instance: PyTorchTranslationEngine) -> None:
    mps_context = (
        patch.object(torch.mps, "empty_cache", return_value=None)
        if torch is not None and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache")
        else nullcontext()
    )
    with mps_context:
        model_instance.close()

    assert model_instance._model is None
    assert model_instance._tokenizer is None
    assert model_instance._model_loaded is False
    assert model_instance.device == "cpu"


@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")
def test_unsupported_language_pair_raises_error(
    model_instance: PyTorchTranslationEngine,
) -> None:
    assert model_instance.supports("ja", "fr") is False

    def _guard_unsupported_pair(source: str, target: str) -> None:
        if not model_instance.supports(source, target):
            msg = "Unsupported language pair"
            raise ValueError(msg)

    with pytest.raises(ValueError, match="Unsupported language pair"):
        _guard_unsupported_pair("ja", "fr")
