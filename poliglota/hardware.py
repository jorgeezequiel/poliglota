"""Friendly hardware discovery kept separate from translation backends."""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DeviceOption:
    """A user-facing device label paired with a stable runtime identifier."""

    identifier: str
    label: str
    available: bool = field(kw_only=True)


def cpu_name() -> str:
    """Return a friendly CPU model without importing PyTorch or spawning a process."""
    name = platform.processor().strip() or platform.uname().processor.strip()
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                name = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except (ImportError, OSError, ValueError):
            pass
    elif sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith(("model name", "hardware")):
                    name = line.split(":", 1)[-1].strip()
                    if name:
                        break
        except OSError:
            pass
    name = name or "Processador não identificado"
    name = re.sub(r"\s*\((?:R|TM)\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+CPU\s*@.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+CPU$", "", name, flags=re.IGNORECASE)
    return name.strip()


def discover_devices() -> list[DeviceOption]:
    """Discover CPU and accelerator choices; importing torch is intentionally lazy."""
    cpu = cpu_name()
    options = [
        DeviceOption("auto", "Automático (recomendado)", available=True),
        DeviceOption("cpu", f"CPU ({cpu})", available=True),
    ]
    physical_gpu_name: str | None = None
    compatible_gpu_found = False
    try:
        import torch
    except (ImportError, OSError, RuntimeError):
        torch = None

    if torch is not None:
        cuda = getattr(torch, "cuda", None)
        try:
            cuda_available = bool(cuda and cuda.is_available())
            count = int(cuda.device_count()) if cuda_available else 0
        except (AttributeError, RuntimeError, TypeError, ValueError):
            count = 0
        for index in range(count):
            try:
                name = str(cuda.get_device_name(index)).strip()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                name = f"GPU {index + 1}"
            options.append(DeviceOption(f"cuda:{index}", f"GPU ({name})", available=True))
            physical_gpu_name = physical_gpu_name or name
            compatible_gpu_found = True

        mps = getattr(torch, "mps", None)
        try:
            mps_available = bool(mps and mps.is_available())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            mps_available = False
        if mps_available and not count:
            options.append(DeviceOption("mps", "GPU (Apple silicon)", available=True))
            physical_gpu_name = "Apple silicon"
            compatible_gpu_found = True

    if not compatible_gpu_found:
        physical_gpu_name = _detected_incompatible_gpu_name()
        if physical_gpu_name:
            options.append(
                DeviceOption(
                    "gpu-unavailable",
                    f"GPU ({physical_gpu_name}) — indisponível",
                    available=False,
                ),
            )
    return options


def _detected_incompatible_gpu_name() -> str | None:
    """Best-effort physical GPU label using platform metadata, without subprocesses."""
    if sys.platform == "win32":
        try:
            import winreg

            base = r"SYSTEM\CurrentControlSet\Control\Video"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, index)
                    try:
                        with winreg.OpenKey(key, subkey_name) as video_key:
                            for child_index in range(winreg.QueryInfoKey(video_key)[0]):
                                child = winreg.EnumKey(video_key, child_index)
                                try:
                                    with winreg.OpenKey(video_key, child) as adapter:
                                        value, _ = winreg.QueryValueEx(adapter, "DriverDesc")
                                        cleaned = str(value).strip()
                                        if cleaned:
                                            return cleaned
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except (ImportError, OSError):
            return None
    elif sys.platform.startswith("linux"):
        try:
            for vendor_file in Path("/sys/class/drm").glob("card[0-9]/device/vendor"):
                vendor = vendor_file.read_text(encoding="ascii").strip().lower()
                names = {"0x10de": "NVIDIA GPU", "0x1002": "AMD GPU", "0x8086": "Intel GPU"}
                if vendor in names:
                    return names[vendor]
        except OSError:
            return None
    elif sys.platform == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        return "Apple GPU"
    return None


def is_cuda_device(identifier: str) -> bool:
    """Return whether an identifier is CUDA, optionally with a device index."""
    return bool(re.fullmatch(r"cuda(?::\d+)?", identifier.strip().lower()))
