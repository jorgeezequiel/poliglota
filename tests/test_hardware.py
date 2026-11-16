"""Unit tests for friendly hardware discovery without touching real devices."""

from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

import pytest

from poliglota import hardware
from poliglota.cli import _build_parser


@pytest.mark.unit
def test_cpu_name_is_available_without_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "cpu_name", lambda: "Example CPU")
    monkeypatch.setattr(hardware, "_detected_incompatible_gpu_name", lambda: None)
    original_import = builtins.__import__

    def no_torch(name: str, *args: object, **kwargs: object) -> object:
        if name == "torch":
            message = "not installed"
            raise ImportError(message)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_torch)
    options = hardware.discover_devices()
    assert [(item.identifier, item.label, item.available) for item in options] == [
        ("auto", "Automático (recomendado)", True),
        ("cpu", "CPU (Example CPU)", True),
    ]


@pytest.mark.unit
def test_discovery_lists_each_compatible_cuda_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "cpu_name", lambda: "Test CPU")
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 2,
            get_device_name=lambda index: ["GPU One", "GPU Two"][index],
        ),
        mps=SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    options = hardware.discover_devices()
    assert [(item.identifier, item.label, item.available) for item in options] == [
        ("auto", "Automático (recomendado)", True),
        ("cpu", "CPU (Test CPU)", True),
        ("cuda:0", "GPU (GPU One)", True),
        ("cuda:1", "GPU (GPU Two)", True),
    ]


@pytest.mark.unit
def test_detected_cuda_without_runtime_is_shown_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hardware, "cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(hardware, "_detected_incompatible_gpu_name", lambda: "Example GPU")
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    options = hardware.discover_devices()
    assert options[-1] == hardware.DeviceOption(
        "gpu-unavailable",
        "GPU (Example GPU) — indisponível",
        available=False,
    )


@pytest.mark.unit
def test_mps_device_is_listed_only_when_runtime_reports_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hardware, "cpu_name", lambda: "Apple CPU")
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        mps=SimpleNamespace(is_available=lambda: True),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    options = hardware.discover_devices()
    assert options[-1] == hardware.DeviceOption("mps", "GPU (Apple silicon)", available=True)


@pytest.mark.unit
@pytest.mark.parametrize("identifier", ["cuda", "cuda:0", "cuda:12"])
def test_cuda_identifier_compatibility(identifier: str) -> None:
    assert hardware.is_cuda_device(identifier)


@pytest.mark.unit
def test_gui_state_keeps_indexed_device_identifier() -> None:
    from poliglota.gui_config import GuiState

    assert GuiState.from_mapping({"device": "cuda:1"}).device == "cuda:1"


@pytest.mark.unit
def test_devices_command_prints_friendly_labels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    options = [
        hardware.DeviceOption("auto", "Automático (recomendado)", available=True),
        hardware.DeviceOption("cpu", "CPU (Test CPU)", available=True),
        hardware.DeviceOption("cuda:0", "GPU (Test GPU)", available=True),
    ]
    monkeypatch.setattr("poliglota.cli.discover_devices", lambda: options)
    args = _build_parser().parse_args(["devices"])
    assert args.func(args) == 0
    assert capsys.readouterr().out.splitlines() == [
        "CPU (Test CPU) — disponível",
        "GPU (Test GPU) — disponível",
    ]


@pytest.mark.unit
def test_translate_help_prioritizes_simple_device_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["translate", "Hello", "--help"])
    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "auto (recommended), cpu, or gpu" in help_text
    assert "cuda[:index], mps" in help_text
