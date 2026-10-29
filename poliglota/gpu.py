"""Utilities for GPU device detection and VRAM validation."""

from __future__ import annotations

import logging
import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)

__all__ = ["check_model_cached", "detect_device", "get_device_info", "validate_vram"]

_TORCH_MIN_VERSION = (2, 7, 0)
_TORCH_VERSION_PARTS = 3


def _parse_torch_version(version: str) -> tuple[int, int, int]:
    """Parse a torch version string into a comparable tuple."""
    numbers = re.findall(r"\d+", version.split("+", 1)[0])
    if not numbers:
        return (0, 0, 0)
    while len(numbers) < _TORCH_VERSION_PARTS:
        numbers.append("0")

    version_tuple: tuple[int, int, int] = (
        int(numbers[0]),
        int(numbers[1]),
        int(numbers[2]),
    )
    return version_tuple


def _coerce_float(value: object) -> float:
    """Convert a value from a torch API into a float, tolerating common object types."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _require_torch() -> ModuleType:
    """Import torch lazily and enforce the project minimum version."""
    try:
        import torch
    except ImportError as exc:
        msg = "GPU support requires torch >= 2.7.0"
        raise RuntimeError(msg) from exc

    if _parse_torch_version(getattr(torch, "__version__", "0.0.0")) < _TORCH_MIN_VERSION:
        msg = "GPU support requires torch >= 2.7.0"
        raise RuntimeError(msg)

    return torch


def _is_mps_available(torch: ModuleType) -> bool:
    """Return True when Apple MPS is present and available.

    Some macOS virtualized runners emit a UserWarning when the underlying device
    does not support Metal 2.0; treat that as an unavailable backend instead of a
    hard failure in the runtime/device-selection layer.
    """
    mps = getattr(torch, "mps", None)
    if mps is None:
        return False
    is_available = getattr(mps, "is_available", None)
    if not callable(is_available):
        return False

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*Skipping device.*does not support Metal 2\.0.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r".*Metal 2\.0.*",
            category=UserWarning,
        )
        try:
            return bool(is_available())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False


def _bytes_to_gb(value_bytes: float) -> float:
    """Convert bytes to GiB for reporting."""
    return float(value_bytes) / (1024**3)


def _cuda_vram_stats(torch: ModuleType) -> tuple[float, float]:
    """Return total and free CUDA memory in GiB."""
    if not bool(getattr(torch.cuda, "is_available", lambda: False)()):
        return 0.0, 0.0

    total_bytes = 0.0
    free_bytes = 0.0

    try:
        total_bytes, free_bytes = torch.cuda.mem_get_info()
    except (AttributeError, RuntimeError, ValueError):
        properties = torch.cuda.get_device_properties(0)
        total_bytes = float(getattr(properties, "total_memory", 0.0))
        free_bytes = total_bytes

    return _bytes_to_gb(total_bytes), _bytes_to_gb(free_bytes)


def _mps_vram_stats(torch: ModuleType) -> tuple[float, float]:
    """Return total and free MPS memory in GiB when available."""
    if not _is_mps_available(torch):
        return 0.0, 0.0

    mps = torch.mps
    total_bytes = 0.0
    used_bytes = 0.0

    recommended_max = getattr(mps, "recommended_max_memory", None)
    if callable(recommended_max):
        try:
            total_bytes = _coerce_float(recommended_max())
        except (TypeError, ValueError):
            total_bytes = 0.0

    current_allocated = getattr(mps, "current_allocated_memory", None)
    if callable(current_allocated):
        try:
            used_bytes = _coerce_float(current_allocated())
        except (TypeError, ValueError):
            used_bytes = 0.0

    free_bytes = max(total_bytes - used_bytes, 0.0)
    return _bytes_to_gb(total_bytes), _bytes_to_gb(free_bytes)


def detect_device(preferred: str = "auto", strict: bool = False) -> str:
    """Return the active device string for torch operations.

    Args:
        preferred: Requested device ('auto', 'cpu', 'cuda', 'mps', or 'gpu').
                   Default is 'auto'.
        strict: If True, raises ValueError when an explicit device is unavailable.
                If False (default), silently falls back to CPU for unavailable devices.

    Returns:
        Selected device string ('cpu', 'cuda', or 'mps').

    Raises:
        ValueError: If strict=True and an explicit device is unavailable or invalid.

    """
    torch = _require_torch()
    requested = (preferred or "auto").strip().lower()
    selected = "cpu"

    cuda_available = bool(getattr(torch.cuda, "is_available", lambda: False)())
    mps_available = _is_mps_available(torch)

    # Validate device name; reject invalid devices
    if requested not in {"auto", "cuda", "mps", "cpu", "gpu"}:
        msg = f"Invalid device '{requested}'. Supported: auto, cpu, cuda, mps, gpu"
        if strict:
            raise ValueError(msg)
        logger.warning("%s; defaulting to auto.", msg)
        requested = "auto"

    # Handle explicit CPU request (never fallback from CPU)
    if requested == "cpu":
        selected = "cpu"
        logger.info("CPU selected as requested.")
        return selected

    # Handle explicit CUDA request
    if requested == "cuda":
        if cuda_available:
            selected = "cuda"
            logger.info("CUDA selected as preferred device.")
            return selected
        msg = "CUDA requested but not available on this system."
        if strict:
            logger.error(msg)
            raise ValueError(msg)
        logger.warning("%s Falling back to CPU.", msg)
        return "cpu"

    # Handle explicit MPS request
    if requested == "mps":
        if mps_available:
            selected = "mps"
            logger.info("MPS selected as preferred device.")
            return selected
        msg = "MPS (Apple Metal) requested but not available on this system."
        if strict:
            logger.error(msg)
            raise ValueError(msg)
        logger.warning("%s Falling back to CPU.", msg)
        return "cpu"

    # Handle 'gpu' alias: prefer CUDA, then MPS
    if requested == "gpu":
        if cuda_available:
            logger.info("GPU alias: CUDA device available; selecting CUDA.")
            return "cuda"
        if mps_available:
            logger.info("GPU alias: CUDA unavailable; selecting MPS.")
            return "mps"
        msg = "GPU requested but no CUDA or MPS device available."
        if strict:
            logger.error(msg)
            raise ValueError(msg)
        logger.warning("%s Falling back to CPU.", msg)
        return "cpu"

    # Handle 'auto': CUDA > MPS > CPU
    if requested == "auto":
        if cuda_available:
            logger.info("Auto-selected CUDA device.")
            return "cuda"
        if mps_available:
            logger.info("Auto-selected MPS device.")
            return "mps"
        logger.warning("No CUDA or MPS device detected; using CPU.")
        return "cpu"

    # Fallback (should not reach here due to earlier validation)
    logger.warning("Unexpected device state for %r; defaulting to CPU.", requested)
    return "cpu"


def validate_vram(min_gb: float = 1.0) -> bool:
    """Check whether the current device has enough free VRAM for the target minimum."""
    torch = _require_torch()
    device = detect_device("auto")

    if device == "cpu":
        logger.debug("Skipping VRAM validation on CPU because no dedicated VRAM is available.")
        return True

    min_gb = max(float(min_gb), 0.0)
    required_gb = min_gb * 1.08

    if device == "cuda":
        total_gb, free_gb = _cuda_vram_stats(torch)
        logger.debug(
            "Checking CUDA VRAM: total=%.2f GiB, free=%.2f GiB, required=%.2f GiB.",
            total_gb,
            free_gb,
            required_gb,
        )
        is_valid = free_gb >= required_gb
        if is_valid:
            logger.info(
                "CUDA VRAM validation passed: %.2f GiB free >= %.2f GiB required.",
                free_gb,
                required_gb,
            )
        else:
            logger.warning(
                "CUDA VRAM validation failed: %.2f GiB free < %.2f GiB required.",
                free_gb,
                required_gb,
            )
        return is_valid

    if device == "mps":
        total_gb, free_gb = _mps_vram_stats(torch)
        logger.debug(
            "Checking MPS VRAM: total=%.2f GiB, free=%.2f GiB, required=%.2f GiB.",
            total_gb,
            free_gb,
            required_gb,
        )
        is_valid = free_gb >= required_gb if total_gb > 0 else False
        if is_valid:
            logger.info(
                "MPS VRAM validation passed: %.2f GiB free >= %.2f GiB required.",
                free_gb,
                required_gb,
            )
        else:
            logger.warning(
                "MPS VRAM validation failed or memory metadata was unavailable: "
                "%.2f GiB free < %.2f GiB required.",
                free_gb,
                required_gb,
            )
        return is_valid

    logger.warning(
        "Unknown device %r encountered during VRAM validation; returning False.",
        device,
    )
    return False


def get_device_info() -> dict[str, object]:
    """Return a summary describing the selected device and current memory state."""
    torch = _require_torch()
    device = detect_device("auto")
    info: dict[str, object] = {
        "device": device,
        "name": "CPU",
        "total_vram_gb": 0.0,
        "free_vram_gb": 0.0,
        "compute_capability": None,
    }

    if device == "cuda":
        try:
            info["name"] = torch.cuda.get_device_name(0)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Unable to read CUDA device name: %s", exc)
            info["name"] = "CUDA"

        total_gb, free_gb = _cuda_vram_stats(torch)
        info["total_vram_gb"] = total_gb
        info["free_vram_gb"] = free_gb

        try:
            info["compute_capability"] = torch.cuda.get_device_capability(0)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Unable to read CUDA compute capability: %s", exc)
            info["compute_capability"] = None

        logger.debug(
            "Detected CUDA device info: name=%s, total_vram_gb=%.2f, "
            "free_vram_gb=%.2f, capability=%s",
            info["name"],
            info["total_vram_gb"],
            info["free_vram_gb"],
            info["compute_capability"],
        )
        return info

    if device == "mps":
        info["name"] = "Apple Metal Performance Shaders"
        total_gb, free_gb = _mps_vram_stats(torch)
        info["total_vram_gb"] = total_gb
        info["free_vram_gb"] = free_gb
        info["compute_capability"] = None
        logger.debug(
            "Detected MPS device info: name=%s, total_vram_gb=%.2f, free_vram_gb=%.2f",
            info["name"],
            info["total_vram_gb"],
            info["free_vram_gb"],
        )
        return info

    logger.debug("Detected CPU device info: name=%s", info["name"])
    return info


def _is_nonempty_file(path: Path) -> bool:
    """Return True when a path resolves to a readable non-empty regular file."""
    try:
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.exists() or not target.is_file():
                return False
            return target.stat().st_size > 0

        if not path.exists() or not path.is_file():
            return False
        return path.stat().st_size > 0
    except (OSError, RuntimeError, ValueError):
        return False


def check_model_cached(model_name: str) -> bool:
    """Return True when a Hugging Face model is already cached locally and complete.

    Validates that the model snapshot contains essential artifacts:
    - config.json (required for all models)
    - At least one weights file or safetensors archive
    - Tokenizer artifacts (at least one of: tokenizer.json, tokenizer.model, etc.)

    Returns False for incomplete, empty, or inaccessible caches.
    Does not make network calls or download anything.
    """
    if not model_name or not isinstance(model_name, str):
        return False

    normalized_name = model_name.strip()
    if not normalized_name:
        return False

    result = False
    try:
        cache_dir = os.environ.get("HF_HOME")
        if not cache_dir:
            cache_dir = str(Path.home() / ".cache" / "huggingface")

        model_key = normalized_name.replace("/", "--")
        dir_candidates = [
            Path(cache_dir),
            Path(cache_dir) / "hub",
        ]
        snapshot_roots = []
        for root in dir_candidates:
            if not root.exists():
                continue
            snapshot_roots.extend(
                [
                    root / f"models--{model_key}",
                    root / model_key,
                    root / "hub" / f"models--{model_key}",
                    root / "hub" / model_key,
                ]
            )

        snapshot_roots = list(dict.fromkeys(snapshot_roots))
        snapshots = None
        for root in snapshot_roots:
            candidate = root / "snapshots"
            if candidate.exists() and candidate.is_dir():
                snapshots = candidate
                break

        if snapshots is None or not snapshots.exists() or not snapshots.is_dir():
            result = False
        else:
            for snapshot_dir in snapshots.iterdir():
                try:
                    if not snapshot_dir.exists() or not snapshot_dir.is_dir():
                        continue

                    config_path = snapshot_dir / "config.json"
                    if not _is_nonempty_file(config_path):
                        continue

                    weight_patterns = [
                        "pytorch_model.bin",
                        "model.safetensors",
                        "model.pth",
                        "flax_model.msgpack",
                    ]
                    has_weights = any(
                        _is_nonempty_file(snapshot_dir / pattern) for pattern in weight_patterns
                    )
                    if not has_weights:
                        for candidate in sorted(snapshot_dir.glob("*.bin")):
                            if _is_nonempty_file(candidate):
                                has_weights = True
                                break
                        if not has_weights:
                            for candidate in sorted(snapshot_dir.glob("*.safetensors")):
                                if _is_nonempty_file(candidate):
                                    has_weights = True
                                    break

                    if not has_weights:
                        continue

                    tokenizer_patterns = [
                        "tokenizer.json",
                        "tokenizer.model",
                        "spiece.model",
                        "sentencepiece.model",
                        "vocab.txt",
                        "vocab.json",
                        "tokenizer_config.json",
                    ]
                    has_tokenizer = any(
                        _is_nonempty_file(snapshot_dir / pattern) for pattern in tokenizer_patterns
                    )
                    if not has_tokenizer:
                        for candidate in sorted(snapshot_dir.glob("*tokenizer*")):
                            if _is_nonempty_file(candidate):
                                has_tokenizer = True
                                break

                    if has_tokenizer:
                        result = True
                        break

                except (OSError, TypeError, ValueError):
                    continue
    except (OSError, ValueError, TypeError):
        result = False

    logger.debug(
        "Checking model cache for %s: %s",
        model_name,
        "found" if result else "not found",
    )
    return result
