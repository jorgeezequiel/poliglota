"""PyTorch-backed multilingual translation engine for local Hugging Face models."""

from __future__ import annotations

import gc
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Protocol, Self, cast

if TYPE_CHECKING:
    import torch  # type: ignore[import-not-found]
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore[import-not-found]

try:
    import torch  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from transformers import (  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
    )
except ImportError as exc:  # pragma: no cover - runtime guard when ML deps are missing.
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from poliglota.engines.protocol import MariansNMTTranslationEngine
from poliglota.gpu import detect_device, validate_vram

logger = logging.getLogger(__name__)

_MODEL_ALIASES: dict[str, str] = {
    "t5-small": "t5-small",
    "google/flan-t5-small": "google/flan-t5-small",
    "mbart-50": "facebook/mbart-large-50-many-to-many-mmt",
    "mbart50": "facebook/mbart-large-50-many-to-many-mmt",
    "mBART-50": "facebook/mbart-large-50-many-to-many-mmt",
    "facebook/mbart-large-50-many-to-many-mmt": "facebook/mbart-large-50-many-to-many-mmt",
}

_SUPPORTED_PAIRS: list[tuple[str, str]] = [
    ("en", "pt"),
    ("pt", "en"),
    ("en", "es"),
    ("es", "en"),
    ("en", "fr"),
    ("fr", "en"),
    ("pt", "es"),
    ("es", "pt"),
    ("pt", "fr"),
    ("fr", "pt"),
]


class _ModelProtocol(Protocol):
    def to(self, device: str) -> object: ...
    def eval(self) -> None: ...
    def generate(self, **kwargs: object) -> object: ...


class _TokenizerProtocol(Protocol):
    def __call__(self, texts: list[str] | str, **kwargs: object) -> object: ...
    def batch_decode(self, tensors: object, skip_special_tokens: bool = True) -> list[str]: ...


class PyTorchTranslationEngine(MariansNMTTranslationEngine):
    """PyTorch translation engine backed by Hugging Face seq2seq models."""

    @staticmethod
    def _cuda_is_available() -> bool:
        """Return whether CUDA is available in the active torch runtime."""
        return torch is not None and bool(getattr(torch.cuda, "is_available", lambda: False)())

    def __init__(self, model_name: str, device: str = "auto") -> None:
        """Initialize the engine and decide the best available device."""
        if _IMPORT_ERROR is not None:
            err = _IMPORT_ERROR
            msg = (
                "Missing ML dependencies. Install torch>=2.7 and "
                "transformers>=4.35 before using PyTorchTranslationEngine."
            )
            raise RuntimeError(msg) from err

        self.model_name = self._normalize_model_name(model_name)
        self.requested_device = device or "auto"
        self.device = self._resolve_device(self.requested_device)
        self.batch_size = 8
        self._model: _ModelProtocol | None = None
        self._tokenizer: _TokenizerProtocol | None = None
        self._model_loaded = False
        self._last_inference_time_ms = 0.0
        self._model_info: dict[str, str | int | float] = {
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "last_inference_time_ms": 0,
        }
        logger.info(
            "Initialized PyTorchTranslationEngine for model=%s, device=%s",
            self.model_name,
            self.device,
        )

    @property
    def name(self) -> str:
        """Return the stable engine identifier."""
        return self.model_name

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Normalize the user-facing model alias to a Hugging Face model ID."""
        normal = (model_name or "t5-small").strip()
        if not normal:
            return "t5-small"
        model_ref = normal.lower()
        return _MODEL_ALIASES.get(model_ref, normal)

    @staticmethod
    def _normalize_lang_code(value: str) -> str:
        """Normalize the language code to a two-letter root token."""
        code = (value or "").strip().lower().replace("_", "-")
        if not code:
            msg = "Language code is required for translation."
            raise ValueError(msg)
        return code.split("-", 1)[0]

    def _resolve_device(self, preferred: str) -> str:
        """Select the device, validating VRAM before choosing GPU."""
        requested = (preferred or "auto").strip().lower()
        if requested not in {"auto", "cpu", "cuda", "mps"}:
            logger.warning(
                "Unsupported preferred device %r; using auto detection.",
                preferred,
            )
            requested = "auto"

        selected = detect_device(requested)
        logger.info(
            "GPU/device selection resolved to %s for model=%s.",
            selected,
            self.model_name,
        )

        if selected == "cpu":
            return "cpu"

        required_vram = 2.0 if "mbart" in self.model_name.lower() else 1.5
        if not validate_vram(min_gb=required_vram):
            logger.warning(
                "Insufficient VRAM for model %s on %s. Falling back to CPU.",
                self.model_name,
                selected,
            )
            return "cpu"
        return selected

    def engine_language(self, locale: object) -> str:
        """Return the engine language code for a locale-like input."""
        if isinstance(locale, str):
            return self._normalize_lang_code(locale)

        language_value = getattr(locale, "language", None)
        if isinstance(language_value, str):
            return self._normalize_lang_code(language_value)

        msg = f"Unsupported locale for PyTorch engine: {locale!r}"
        raise ValueError(msg)

    def supports(self, source: object, target: object) -> bool:
        """Return whether the given language pair is supported."""
        if source is None or target is None:
            return False
        source_code = self._normalize_lang_code(str(source))
        target_code = self._normalize_lang_code(str(target))
        return bool(source_code and target_code) and (
            source_code,
            target_code,
        ) in _SUPPORTED_PAIRS

    def get_supported_pairs(self) -> list[tuple[str, str]]:
        """Expose the language pairs supported by this engine."""
        return list(_SUPPORTED_PAIRS)

    def load_model(self, model_path: str | None = None, device: str = "cpu") -> None:
        """Load the model from the local cache or the Hugging Face Hub."""
        if AutoModelForSeq2SeqLM is None or AutoTokenizer is None or torch is None:
            msg = "Transformers and torch are required to load a PyTorch model."
            raise RuntimeError(msg)

        requested = (device or self.requested_device or "auto").strip().lower()
        if requested not in {"auto", "cpu", "cuda", "mps"}:
            logger.warning(
                "Unsupported device override %r; falling back to auto detection.",
                device,
            )
            requested = "auto"

        self.device = self._resolve_device(requested)
        logger.info(
            "Loading model %s onto %s.",
            model_path or self.model_name,
            self.device,
        )

        local_only = os.environ.get("HF_HUB_OFFLINE", "").lower() in {"1", "true", "yes"}
        model_id = model_path or self.model_name
        try:
            tokenizer = cast(
                "_TokenizerProtocol",
                AutoTokenizer.from_pretrained(model_id, local_files_only=local_only),
            )
            model = cast(
                "_ModelProtocol",
                AutoModelForSeq2SeqLM.from_pretrained(model_id, local_files_only=local_only),
            )
        except OSError as exc:
            if local_only:
                msg = (
                    "Model %s is not cached locally while Hugging Face offline mode "
                    "is enabled. Run a network-enabled load once or disable "
                    "HF_HUB_OFFLINE."
                )
                raise RuntimeError(msg % model_id) from exc
            msg = f"Could not load PyTorch model '{model_id}': {exc}"
            raise RuntimeError(msg) from exc

        self._move_model_to_device(model, self.device)
        model.eval()
        self._model = model
        self._tokenizer = tokenizer
        self._model_loaded = True
        self._model_info["device"] = self.device
        self._model_info["model_name"] = self.model_name
        logger.info("Model %s loaded successfully on %s.", self.model_name, self.device)

    @staticmethod
    def _is_cuda_oom_error(exc: BaseException) -> bool:
        """Return True when the exception is a CUDA out-of-memory condition."""
        if torch is None:
            return False
        cuda_module = getattr(torch, "cuda", None)
        if cuda_module is None:
            return False
        oom_exc = getattr(cuda_module, "OutOfMemoryError", None)
        if oom_exc is None:
            return False
        return isinstance(exc, oom_exc)

    def _move_model_to_device(self, model: _ModelProtocol, device: str) -> None:
        """Move the model to the target device with automatic CPU fallback."""
        try:
            model.to(device)
        except RuntimeError as exc:
            if self._is_cuda_oom_error(exc):
                logger.exception(
                    "Out-of-memory while moving model to %s. Falling back to CPU.",
                    device,
                )
                self.device = "cpu"
                model.to("cpu")
                return
            if "out of memory" in str(exc).lower():
                logger.exception(
                    "Out-of-memory while moving model to %s. Falling back to CPU.",
                    device,
                )
                self.device = "cpu"
                model.to("cpu")
                return
            raise

    def _is_mbart_model(self) -> bool:
        """Return True for mBART-based models."""
        return "mbart" in self.model_name.lower()

    def _prepare_texts(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Prepare the input strings for model generation."""
        normalized_source = self._normalize_lang_code(source_lang)
        normalized_target = self._normalize_lang_code(target_lang)
        prepared: list[str] = []
        for text in texts:
            value = str(text).strip()
            if not value:
                continue
            if self._is_mbart_model():
                prepared.append(value)
            else:
                prepared.append(
                    f"translate {normalized_source} to {normalized_target}: {value}"
                )
        return prepared

    def _generate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Generate translated outputs for a batch of texts."""
        if self._model is None or self._tokenizer is None:
            msg = "Model is not loaded. Call load_model() before translating."
            raise RuntimeError(msg)

        model = self._model
        tokenizer = self._tokenizer
        prepared = self._prepare_texts(texts, source_lang, target_lang)
        if not prepared:
            return []

        tokenized = cast(
            "dict[str, Any]",
            tokenizer(
                prepared,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ),
        )

        if self.device in {"cuda", "mps"}:
            tokenized = {
                key: value.to(self.device)
                for key, value in tokenized.items()
            }

        generation_kwargs: dict[str, Any] = {
            "num_beams": 4,
            "max_new_tokens": 512,
            "do_sample": False,
        }

        if self._is_mbart_model():
            lang_code = self._normalize_lang_code(target_lang)
            lang_to_id = getattr(tokenizer, "lang_code_to_id", None)
            if lang_to_id is not None and lang_code in lang_to_id:
                generation_kwargs["forced_bos_token_id"] = lang_to_id[lang_code]

        started_at = time.perf_counter()
        try:
            generated = model.generate(
                **cast("dict[str, Any]", tokenized),
                **generation_kwargs,
            )
        except RuntimeError as exc:
            if not self._is_cuda_oom_error(exc):
                raise
            logger.exception(
                "OOM during generation. Falling back to CPU for the current batch."
            )
            if self.device != "cpu":
                self.device = "cpu"
                model.to("cpu")
                tokenized = {
                    key: value.to("cpu")
                    for key, value in tokenized.items()
                }
                generated = model.generate(
                    **cast("dict[str, Any]", tokenized),
                    **generation_kwargs,
                )
            else:
                raise

        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        result = [str(value).strip() for value in decoded]
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self._last_inference_time_ms = elapsed_ms
        self._model_info["last_inference_time_ms"] = round(elapsed_ms)
        logger.info(
            "Inference batch of %d items completed in %.2f ms on %s.",
            len(prepared),
            elapsed_ms,
            self.device,
        )
        return result

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text payload using the active model."""
        if not text:
            return ""
        if not self._model_loaded:
            self.load_model(device=self.requested_device)
        start = time.perf_counter()
        batch_result = self.translate_batch([text], source_lang, target_lang)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Single translation completed in %.2f ms for %s->%s.",
            elapsed_ms,
            source_lang,
            target_lang,
        )
        return batch_result[0] if batch_result else ""

    def _translate_batch_chunk(
        self,
        filtered: list[str],
        start_index: int,
        batch_size: int,
        source_lang: str,
        target_lang: str,
    ) -> tuple[int, int, list[str]]:
        """Translate one chunk and return the next index and updated batch size."""
        chunk = filtered[start_index : start_index + batch_size]
        while True:
            try:
                translated = self._generate_batch(chunk, source_lang, target_lang)
                return start_index + len(chunk), batch_size, translated
            except RuntimeError as exc:
                is_oom = self._is_cuda_oom_error(exc) or "out of memory" in str(exc).lower()
                if not is_oom:
                    raise
                next_batch_size = max(1, batch_size // 2)
                logger.warning(
                    "OOM detected for model=%s. Reducing batch size from %d to %d.",
                    self.model_name,
                    batch_size,
                    next_batch_size,
                )
                batch_size = next_batch_size
                if batch_size == 1 and len(chunk) > 1:
                    logger.warning(
                        "Single-item fallback activated; switching to CPU for safety."
                    )
                    self.device = "cpu"
                    if self._model is not None:
                        self._model.to("cpu")
                    chunk = filtered[start_index : start_index + 1]
                    continue
                chunk = filtered[start_index : start_index + batch_size]
                if not chunk:
                    chunk = filtered[start_index : start_index + 1]

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate multiple strings with adaptive batching and OOM recovery."""
        if not texts:
            return []

        filtered = [str(item).strip() for item in texts if str(item).strip()]
        if not filtered:
            return []

        if not self._model_loaded:
            self.load_model(device=self.requested_device)

        results: list[str] = []
        batch_size = max(1, min(self.batch_size, len(filtered)))
        index = 0

        while index < len(filtered):
            next_index, batch_size, translated = self._translate_batch_chunk(
                filtered,
                index,
                batch_size,
                source_lang,
                target_lang,
            )
            results.extend(translated)
            index = next_index

        self._model_info["batch_size"] = batch_size
        return results

    def get_model_info(self) -> dict[str, str | int | float]:
        """Return metadata about the selected model and current runtime state."""
        return dict(self._model_info)

    def close(self) -> None:
        """Free model weights and empty the CUDA/MPS caches."""
        logger.info("Closing PyTorchTranslationEngine for %s.", self.model_name)
        self._model_loaded = False

        if self._model is not None:
            try:
                self._model.to("cpu")
            except (AttributeError, RuntimeError, TypeError):
                logger.warning("Unable to move model to CPU during close().")
            self._model = None

        self._tokenizer = None

        if torch is not None:
            if hasattr(torch.cuda, "empty_cache"):
                torch.cuda.empty_cache()
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()

        gc.collect()
        self.device = "cpu"
        logger.info(
            "PyTorchTranslationEngine for %s has been closed and caches cleared.",
            self.model_name,
        )

    def __enter__(self) -> Self:
        """Support context-manager usage."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release resources on context-manager exit."""
        self.close()


__all__ = ["PyTorchTranslationEngine"]
