"""Offline Marian-NMT adapter backed by Hugging Face Transformers."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
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
except (
    ImportError,
    OSError,
) as exc:  # pragma: no cover - runtime guard when ML deps are missing or DLLs unavailable.
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from poliglota.engines.protocol import (
    MariansNMTTranslationEngine,
    TranslationRequest,
    TranslationResult,
)

logger = logging.getLogger(__name__)

_INFERENCE_WARNING_MS = 5000
_PLACEHOLDER_TAG_RE = re.compile(r"</?(en|pt|es|fr)>", flags=re.IGNORECASE)
_SUPPORTED_PAIRS: list[tuple[str, str]] = [
    # Existing OPUS-MT pairs
    ("en", "pt"),
    ("pt", "en"),
    ("en", "es"),
    ("es", "en"),
    ("en", "fr"),
    ("fr", "en"),
    ("pt", "es"),
    ("es", "pt"),
    # M2M100 pairs (pt source to 6 missing targets)
    ("pt", "de"),
    ("pt", "ja"),
    ("pt", "ko"),
    ("pt", "pl"),
    ("pt", "ru"),
    ("pt", "it"),
]
_SUPPORTED_MODELS: dict[str, tuple[str, str]] = {
    # Helsinki-NLP OPUS-MT models (existing)
    "Helsinki-NLP/opus-mt-tc-big-en-pt": ("en", "pt"),
    "Helsinki-NLP/opus-mt-en-es": ("en", "es"),
    "Helsinki-NLP/opus-mt-en-fr": ("en", "fr"),
    # Facebook M2M100 (multilingual, covers all 6 missing target languages)
    "facebook/m2m100_418M": ("pt", "multi"),  # Marker: multilingual model for pt source
}


class _ModelProtocol(Protocol):
    def to(self, device: str) -> object: ...
    def eval(self) -> None: ...
    def generate(self, **kwargs: object) -> object: ...


class _TokenizerProtocol(Protocol):
    def __call__(self, texts: list[str], **kwargs: object) -> object: ...
    def batch_decode(self, tensors: object, skip_special_tokens: bool = True) -> list[str]: ...


class MariansNMTAdapter(MariansNMTTranslationEngine):
    """Concrete Marian-NMT adapter for local and cached Hugging Face models."""

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        """Initialize the adapter and validate the requested runtime configuration."""
        self.model_name = model_name
        self.device = self._normalize_device(device)
        self.batch_size = 8
        self._model: _ModelProtocol | None = None
        self._tokenizer: _TokenizerProtocol | None = None
        self._last_placeholder_positions: list[tuple[int, str]] = []
        self._last_inference_time_ms = 0.0
        self._model_info: dict[str, str | int | float] = {
            "model_name": model_name,
            "model_size_mb": 0,
            "device": self.device,
            "pairs_count": len(_SUPPORTED_PAIRS),
            "last_inference_time_ms": 0,
        }

        if _IMPORT_ERROR is not None:
            msg = (
                "Missing Marian offline dependency stack. "
                "Install transformers>=4.35, torch>=2.0 and huggingface_hub>=0.20."
            )
            raise RuntimeError(msg) from _IMPORT_ERROR

        if model_name not in _SUPPORTED_MODELS:
            supported = ", ".join(sorted(_SUPPORTED_MODELS))
            msg = f"Unsupported Marian model '{model_name}'. Supported models: {supported}."
            raise ValueError(msg)

    @property
    def name(self) -> str:
        """Stable engine identifier."""
        return self.model_name

    @staticmethod
    def _normalize_device(device: str) -> str:
        """Validate the requested device value."""
        normalized = device.lower()
        if normalized in {"cpu", "cuda", "mps"}:
            return normalized
        msg = "Unsupported device. Use 'cpu', 'cuda', or 'mps'."
        raise ValueError(msg)

    @staticmethod
    def _check_local_model_path(model_path: str | None) -> str | None:
        """Resolve a local model directory if provided."""
        if model_path is None:
            return None
        resolved = Path(model_path).expanduser()
        if not resolved.exists():
            msg = f"Local Marian model not found: {resolved}"
            raise FileNotFoundError(msg)
        return str(resolved)

    def __enter__(self) -> Self:
        """Return the adapter for context-manager usage."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release the model when the context manager exits."""
        self.close()

    def engine_language(self, locale: object) -> str:
        """Return the engine language code for the locale in a best-effort manner."""
        if isinstance(locale, str):
            code = locale.strip().lower()
            if code in {"en", "pt", "es", "fr"}:
                return code
        msg = f"Unsupported locale for Marian adapter: {locale!r}"
        raise ValueError(msg)

    def supports(self, source: object, target: object) -> bool:
        """Return whether a language pair is supported."""
        source_code = str(source).lower() if source is not None else ""
        target_code = str(target).lower() if target is not None else ""
        return (source_code, target_code) in _SUPPORTED_PAIRS

    def load_model(
        self,
        model_path: str | None = None,
        device: str = "cpu",
    ) -> None:
        """Load a model from a local directory or configured Hugging Face model."""
        if AutoModelForSeq2SeqLM is None or AutoTokenizer is None or torch is None:
            msg = (
                "Missing Marian offline dependency stack. "
                "Install transformers>=4.35, torch>=2.0 and huggingface_hub>=0.20."
            )
            raise RuntimeError(msg)

        if device:
            self.device = self._normalize_device(device)
        if self.device == "cuda" and (torch is None or not torch.cuda.is_available()):
            logger.warning("CUDA requested but unavailable; falling back to CPU.")
            self.device = "cpu"
        elif self.device == "mps" and (torch is None or not hasattr(torch, "mps")):
            logger.warning("MPS requested but unavailable; falling back to CPU.")
            self.device = "cpu"

        model_ref = self._check_local_model_path(model_path) or self.model_name

        try:
            tokenizer = cast("_TokenizerProtocol", AutoTokenizer.from_pretrained(model_ref))
            model = cast("_ModelProtocol", AutoModelForSeq2SeqLM.from_pretrained(model_ref))
            model.to(self.device)
            model.eval()
            self._tokenizer = tokenizer
            self._model = model
            self._model_info["device"] = self.device
            self._model_info["model_name"] = self.model_name
        except Exception as exc:  # pragma: no cover - runtime fallback path.
            if torch is not None and isinstance(exc, torch.cuda.OutOfMemoryError):
                logger.exception("CUDA memory error while loading Marian model; retrying on CPU.")
                self.device = "cpu"
                try:
                    tokenizer = cast(
                        "_TokenizerProtocol",
                        AutoTokenizer.from_pretrained(model_ref),
                    )
                    model = cast(
                        "_ModelProtocol",
                        AutoModelForSeq2SeqLM.from_pretrained(model_ref),
                    )
                    model.to(self.device)
                    model.eval()
                    self._tokenizer = tokenizer
                    self._model = model
                    self._model_info["device"] = self.device
                except Exception as retry_exc:  # pragma: no cover - runtime fallback path.
                    msg = (
                        "Failed to load Marian model after falling back to CPU. "
                        f"Original error: {retry_exc}"
                    )
                    raise RuntimeError(msg) from retry_exc
            else:
                msg = f"Could not load Marian model '{model_ref}': {exc}"
                raise RuntimeError(msg) from exc

    def _validate_pair(self, source_lang: str, target_lang: str) -> None:
        """Validate a requested translation pair against the known supported matrix."""
        pair = (source_lang.lower(), target_lang.lower())
        if pair not in _SUPPORTED_PAIRS:
            supported = ", ".join(f"{src}->{dst}" for src, dst in _SUPPORTED_PAIRS)
            msg = (
                f"Unsupported translation pair '{source_lang}->{target_lang}'. "
                f"Supported pairs: {supported}"
            )
            raise ValueError(msg)

    def get_supported_pairs(self) -> list[tuple[str, str]]:
        """Return the hardcoded set of supported translation pairs."""
        return list(_SUPPORTED_PAIRS)

    def _strip_known_placeholders(self, text: str) -> tuple[str, list[tuple[int, str]]]:
        """Remove known language tags while recording their original positions."""
        positions: list[tuple[int, str]] = []

        def replace(match: re.Match[str]) -> str:
            tag = match.group(0)
            normalized = tag.lower()
            if normalized not in {"<en>", "<pt>", "<es>", "<fr>"}:
                return tag
            positions.append((match.start(), normalized))
            return ""

        stripped = _PLACEHOLDER_TAG_RE.sub(replace, text)
        self._last_placeholder_positions = positions
        return stripped, positions

    def _restore_known_placeholders(self, text: str) -> str:
        """Reinsert preserved placeholder tags at their original offsets."""
        return self._restore_placeholders_at_positions(
            text,
            self._last_placeholder_positions,
        )

    def _restore_placeholders_at_positions(
        self,
        text: str,
        positions: list[tuple[int, str]],
    ) -> str:
        """Reinsert placeholder tags at the original offsets described by positions."""
        restored = text
        for position, tag in reversed(positions):
            insertion_index = max(0, min(len(restored), position))
            restored = restored[:insertion_index] + f"<{tag}>" + restored[insertion_index:]
        return restored

    def _translate_with_model(self, texts: list[str]) -> list[str]:
        """Perform model.generate() for a list of prepared inputs."""
        if self._model is None or self._tokenizer is None:
            msg = "Model is not loaded. Call load_model() before translating."
            raise RuntimeError(msg)

        model = self._model
        tokenizer = self._tokenizer
        prepared_texts = [text.strip() for text in texts if text]
        if not prepared_texts:
            return []

        tokenized = cast(
            "dict[str, Any]",
            tokenizer(
                prepared_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ),
        )

        if self.device in {"cuda", "mps"}:
            tokenized = {key: value.to(self.device) for key, value in tokenized.items()}

        generated = model.generate(
            **cast("dict[str, Any]", tokenized),
            num_beams=4,
            max_new_tokens=512,
            do_sample=False,
        )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [str(value).strip() for value in decoded]

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate one string while preserving known placeholder tags."""
        self._validate_pair(source_lang, target_lang)
        stripped_text, positions = self._strip_known_placeholders(text)
        start = time.perf_counter()
        translated = self._translate_with_model([stripped_text])[0]
        restored = self._restore_known_placeholders(translated)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._last_inference_time_ms = elapsed_ms
        self._model_info["last_inference_time_ms"] = round(elapsed_ms)

        if positions:
            for position, tag in reversed(positions):
                insertion_index = max(0, min(len(restored), position))
                restored = restored[:insertion_index] + f"<{tag}>" + restored[insertion_index:]

        if elapsed_ms > _INFERENCE_WARNING_MS:
            logger.warning(
                "Marian inference exceeded 5s for %s->%s: %.2fms",
                source_lang,
                target_lang,
                elapsed_ms,
            )
        return restored

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        """Translate a list of strings in batches using an adaptive OOM-aware batch size.

        The instance batch_size is kept unchanged; each chunk retries with a locally
        reduced batch size when the model hits a device memory limit.
        """
        self._validate_pair(source_lang, target_lang)
        if not texts:
            return []

        start = time.perf_counter()
        translated: list[str] = []
        index = 0
        while index < len(texts):
            current_batch_size = min(self.batch_size, len(texts) - index)

            while True:
                chunk = texts[index : index + current_batch_size]
                stripped_chunk: list[str] = []
                for value in chunk:
                    cleaned, positions = self._strip_known_placeholders(value)
                    self._last_placeholder_positions = positions
                    stripped_chunk.append(cleaned)

                try:
                    results = self._translate_with_model(stripped_chunk)
                    break
                except Exception as exc:  # pragma: no cover - runtime engine failure.
                    is_oom = "out of memory" in str(exc).lower()
                    if torch is not None:
                        cuda_oom = getattr(getattr(torch, "cuda", None), "OutOfMemoryError", None)
                        mps_oom = getattr(getattr(torch, "mps", None), "OutOfMemoryError", None)
                        is_oom = is_oom or (
                            (cuda_oom is not None and isinstance(exc, cuda_oom))
                            or (mps_oom is not None and isinstance(exc, mps_oom))
                        )

                    if not is_oom:
                        msg = f"Marian batch inference failed: {exc}"
                        raise RuntimeError(msg) from exc

                    if current_batch_size == 1:
                        if self.device != "cpu" and torch is not None:
                            cuda_oom = getattr(
                                getattr(torch, "cuda", None), "OutOfMemoryError", None
                            )
                            if cuda_oom is not None and isinstance(exc, cuda_oom):
                                logger.exception(
                                    "CUDA out-of-memory during batch translation; "
                                    "falling back to CPU."
                                )
                                self.device = "cpu"
                                if self._model is not None:
                                    self._model.to(self.device)
                                try:
                                    results = self._translate_with_model(stripped_chunk)
                                    break
                                except (
                                    Exception
                                ) as retry_exc:  # pragma: no cover - runtime engine failure.
                                    msg = f"Marian batch inference failed: {retry_exc}"
                                    raise RuntimeError(msg) from retry_exc
                        msg = f"Marian batch inference failed: {exc}"
                        raise RuntimeError(msg) from exc

                    new_batch_size = max(1, current_batch_size // 2)
                    warning_message = f"OOM detected; reducing batch_size to {new_batch_size}"
                    logger.warning(warning_message)
                    current_batch_size = new_batch_size
                    continue

            for original_text, result in zip(chunk, results, strict=True):
                _, positions = self._strip_known_placeholders(original_text)
                self._last_placeholder_positions = positions
                restored = self._restore_placeholders_at_positions(result, positions)
                translated.append(restored)
            index += current_batch_size

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._last_inference_time_ms = elapsed_ms
        self._model_info["last_inference_time_ms"] = round(elapsed_ms)
        if elapsed_ms > _INFERENCE_WARNING_MS:
            logger.warning(
                "Marian batch inference exceeded 5s for %s->%s: %.2fms",
                source_lang,
                target_lang,
                elapsed_ms,
            )
        return translated

    def get_model_info(self) -> dict[str, str | int | float]:
        """Return metadata describing the currently loaded model state."""
        info = dict(self._model_info)
        info["pairs_count"] = len(self.get_supported_pairs())
        info["last_inference_time_ms"] = round(self._last_inference_time_ms)
        return info

    def close(self) -> None:
        """Release the model and explicitly clear GPU cache if available."""
        self._model = None
        self._tokenizer = None
        self._last_placeholder_positions = []
        if torch is not None:
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                torch.cuda.empty_cache()
            mps_module = getattr(torch, "mps", None)
            empty_cache = getattr(mps_module, "empty_cache", None)
            if callable(empty_cache):
                empty_cache()

    def translate_request(self, request: TranslationRequest) -> TranslationResult:
        """Translate a structured request object using the string API."""
        translated = self.translate(request.text, request.source_lang, request.target_lang)
        return TranslationResult(
            translated_text=translated,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            confidence=1.0,
            metadata={"model_name": self.model_name, "device": self.device},
        )

    def __repr__(self) -> str:
        """Render a concise debug representation of the adapter state."""
        return f"MariansNMTAdapter(model_name={self.model_name!r}, device={self.device!r})"
