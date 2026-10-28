"""Tests for interactive CLI."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from poliglota import cli_interactive

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


def _fake_input_from_lines(lines: str) -> Callable[[str], str]:
    """Fake input function that reads from a string of lines."""
    stream = StringIO(lines)

    def fake_input(_prompt: str = "") -> str:
        value = stream.readline()
        if value == "":
            return ""
        return value.strip()

    return fake_input


def test_interactive_cancel_on_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_input(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    result = cli_interactive.run_interactive()
    assert result == 0


def test_consent_yes_model_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test consent flow when model is cached.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), translate(s).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\ns\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=True),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        result = cli_interactive.run_interactive()
    assert result == 0
    translate_files.assert_called_once()
    translate_text.assert_not_called()


def test_consent_no_model_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test consent flow when model is cached and user declines translation.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), translate(n).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\nn\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=True),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        result = cli_interactive.run_interactive()
    assert result == 0
    translate_files.assert_not_called()
    translate_text.assert_not_called()


def test_consent_yes_model_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test consent flow when model is not cached and user accepts download.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), download(s), translate(s).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\ns\ns\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=False),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        with patch("transformers.AutoTokenizer.from_pretrained") as tokenizer_factory, \
             patch("transformers.AutoModelForSeq2SeqLM.from_pretrained") as model_factory:
            tokenizer_factory.return_value = MagicMock()
            model_factory.return_value = MagicMock()
            result = cli_interactive.run_interactive()
    assert result == 0
    translate_files.assert_called_once()
    translate_text.assert_not_called()


def test_consent_no_model_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test consent flow when model is not cached and user declines download.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), download(n).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\nn\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=False),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        result = cli_interactive.run_interactive()
    assert result == 0
    translate_files.assert_not_called()
    translate_text.assert_not_called()


def test_model_download_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handling of model download failure.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), download(s).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\ns\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=False),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        with (
            patch("transformers.AutoTokenizer.from_pretrained",
                  side_effect=RuntimeError("download failed")),
            patch("transformers.AutoModelForSeq2SeqLM.from_pretrained"),
        ):
            result = cli_interactive.run_interactive()
    assert result == 1
    translate_files.assert_not_called()
    translate_text.assert_not_called()


def test_incomplete_cache_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test cache detection with incomplete model artifacts.

    Inputs: device(1), format(1), path(enter), source(1), target_locales(s),
    use_default(s), output(enter), translate(n).
    """
    monkeypatch.setattr("builtins.input", _fake_input_from_lines("1\n1\n\n1\ns\ns\n\nn\n"))
    with (
        patch.object(Path, "exists", return_value=True),
        patch("poliglota.cli_interactive.get_global_registry") as mock_registry,
        patch("poliglota.cli_interactive.discover_resources", return_value={"en": [], "pt": []}),
        patch("poliglota.cli_interactive.cli.select_default_motor", return_value="model-123"),
        patch("poliglota.cli_interactive.cli.resolve_device_name", return_value="cpu"),
        patch("poliglota.cli_interactive.gpu.check_model_cached", return_value=True),
        patch("poliglota.cli_interactive.translate_resource_files") as translate_files,
        patch("poliglota.cli_interactive.cli.translate_with_placeholders") as translate_text,
    ):
        mock_registry_inst = MagicMock()
        mock_registry.return_value = mock_registry_inst
        mock_registry_inst.names.return_value = ["arb"]
        mock_registry_inst.get.return_value = MagicMock()
        result = cli_interactive.run_interactive()
    assert result == 0
    translate_files.assert_not_called()
    translate_text.assert_not_called()
