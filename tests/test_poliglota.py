from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from poliglota.cli import _verify_offline_capability, main
from poliglota.syncer import sync_locale_files
from poliglota.validator import validate_root

if TYPE_CHECKING:
    from pathlib import Path


def write_arb(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_validate_root_detects_missing_keys_and_placeholder_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"

    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {
            "@@locale": "pt_BR",
            "welcome": "Olá, {name}!",
            "count": "Você tem {count} itens",
            "settings": "Configurações",
        },
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {
            "@@locale": "es_ES",
            "welcome": "Hola, {user}!",
            "count": "Tienes {quantity} artículos",
        },
    )

    issues = validate_root(tmp_path, "pt_BR")

    assert any("missing keys" in issue for issue in issues)
    assert any("placeholder mismatch" in issue for issue in issues)


def test_sync_locale_files_copies_missing_keys(tmp_path: Path) -> None:
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"

    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {
            "@@locale": "pt_BR",
            "welcome": "Olá, {name}!",
            "settings": "Configurações",
        },
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {
            "@@locale": "es_ES",
            "welcome": "Hola, {name}!",
        },
    )

    changed = sync_locale_files(tmp_path, "pt_BR")

    assert changed == 1
    target_data = json.loads((target_dir / "app_core_es_ES.arb").read_text(encoding="utf-8"))
    assert target_data["settings"] == "Configurações"


def test_main_validate_command_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"

    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {"@@locale": "pt_BR", "welcome": "Olá, {name}!"},
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {"@@locale": "es_ES", "welcome": "Hola, {user}!"},
    )

    exit_code = main(["validate", "--root", str(tmp_path), "--source", "pt_BR"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "placeholder mismatch" in captured.out or "missing keys" in captured.out


def test_main_sync_missing_source_reports_error_without_touching_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_file = tmp_path / "lib" / "l10n" / "europa" / "es_ES" / "app_core_es_ES.arb"
    write_arb(target_file, {"@@locale": "es_ES", "welcome": "Hola, {name}!"})
    bytes_before = target_file.read_bytes()
    files_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*.arb"))

    exit_code = main(["sync", "--root", str(tmp_path), "--source", "pt_BR"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Source locale 'pt_BR' not found" in captured.out
    assert "Traceback" not in captured.err
    assert target_file.read_bytes() == bytes_before
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*.arb")) == files_before


def test_main_translate_uses_auto_selected_default_motor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = {
        "selected": False,
        "verified": False,
        "validated": False,
        "translated": False,
        "engine": False,
        "detect_device": False,
    }

    def fake_select_default_motor(source: str, target: str) -> str:
        calls["selected"] = True
        assert source == "pt_BR"
        assert target == "en_US"
        return "facebook/m2m100_418M"

    def fake_verify(model_name: str) -> bool:
        calls["verified"] = True
        assert model_name == "facebook/m2m100_418M"
        return True

    def fake_validate(model_name: str) -> None:
        calls["validated"] = True
        assert model_name == "facebook/m2m100_418M"

    def fake_translate(
        text: str,
        source_locale: str,
        target_locale: str,
        *,
        preserve_placeholders: bool,
        model_name: str,
        device: str,
        batch_size: int,
    ) -> tuple[str, dict[str, int], float]:
        calls["translated"] = True
        assert text == "Olá mundo"
        assert source_locale == "pt_BR"
        assert target_locale == "en_US"
        assert model_name == "facebook/m2m100_418M"
        return "Hello world", {"preserved": 0, "substituted": 0, "missing": 0}, 12.5

    def fake_detect_device(device: str, strict: bool = False) -> str:
        calls["detect_device"] = True
        return "cpu"

    class FakeAdapter:
        def __init__(self, model_name: str, device: str) -> None:
            self.model_name = model_name
            self.device = device
            self.batch_size = 1

    def fake_get_engine(
        engine_name: str,
        model_name: str,
        device: str,
        batch_size: int,
    ) -> object:
        calls["engine"] = True
        assert engine_name == "marian"
        assert model_name == "facebook/m2m100_418M"
        adapter = FakeAdapter(model_name, device)
        adapter.batch_size = batch_size
        return adapter

    monkeypatch.setattr("poliglota.cli._select_default_motor", fake_select_default_motor)
    monkeypatch.setattr("poliglota.cli._verify_offline_capability", fake_verify)
    monkeypatch.setattr("poliglota.cli._validate_resource_footprint", fake_validate)
    monkeypatch.setattr("poliglota.cli._translate_with_placeholders", fake_translate)
    monkeypatch.setattr("poliglota.cli._get_engine", fake_get_engine)
    monkeypatch.setattr("poliglota.gpu.detect_device", fake_detect_device)

    exit_code = main(["translate", "--source", "pt_BR", "--target", "en_US", "Olá mundo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == {
        "selected": True,
        "verified": True,
        "validated": True,
        "translated": True,
        "engine": True,
        "detect_device": True,
    }
    assert "Using default motor: facebook/m2m100_418M" in captured.out


def test_main_translate_uses_explicit_model_without_auto_select(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = {
        "selected": False,
        "verified": False,
        "validated": False,
        "translated": False,
        "engine": False,
        "detect_device": False,
    }

    def fake_select_default_motor(source: str, target: str) -> str:
        calls["selected"] = True
        msg = "auto-select should not run when --model is provided"
        raise AssertionError(msg)

    def fake_verify(model_name: str) -> bool:
        calls["verified"] = True
        assert model_name == "facebook/m2m100_418M"
        return True

    def fake_validate(model_name: str) -> None:
        calls["validated"] = True
        assert model_name == "facebook/m2m100_418M"

    def fake_translate(
        text: str,
        source_locale: str,
        target_locale: str,
        *,
        preserve_placeholders: bool,
        model_name: str,
        device: str,
        batch_size: int,
    ) -> tuple[str, dict[str, int], float]:
        calls["translated"] = True
        assert model_name == "facebook/m2m100_418M"
        return "Hello world", {"preserved": 0, "substituted": 0, "missing": 0}, 12.5

    def fake_detect_device(device: str, strict: bool = False) -> str:
        calls["detect_device"] = True
        return "cpu"

    class FakeAdapter:
        def __init__(self, model_name: str, device: str) -> None:
            self.model_name = model_name
            self.device = device
            self.batch_size = 1

    def fake_get_engine(
        engine_name: str,
        model_name: str,
        device: str,
        batch_size: int,
    ) -> object:
        calls["engine"] = True
        assert engine_name == "marian"
        assert model_name == "facebook/m2m100_418M"
        adapter = FakeAdapter(model_name, device)
        adapter.batch_size = batch_size
        return adapter

    monkeypatch.setattr("poliglota.cli._select_default_motor", fake_select_default_motor)
    monkeypatch.setattr("poliglota.cli._verify_offline_capability", fake_verify)
    monkeypatch.setattr("poliglota.cli._validate_resource_footprint", fake_validate)
    monkeypatch.setattr("poliglota.cli._translate_with_placeholders", fake_translate)
    monkeypatch.setattr("poliglota.cli._get_engine", fake_get_engine)
    monkeypatch.setattr("poliglota.gpu.detect_device", fake_detect_device)

    exit_code = main(
        [
            "translate",
            "--source",
            "pt_BR",
            "--target",
            "en_US",
            "--model",
            "facebook/m2m100_418M",
            "Olá mundo",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == {
        "selected": False,
        "verified": True,
        "validated": True,
        "translated": True,
        "engine": True,
        "detect_device": True,
    }
    assert "Using default motor" not in captured.out


def test_verify_offline_capability_returns_true_when_model_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_root = tmp_path / ".cache" / "huggingface"
    cached_model = cache_root / "hub" / "facebook--m2m100_418M"
    cached_model.mkdir(parents=True)
    monkeypatch.setenv("HF_HOME", str(cache_root))
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)

    assert _verify_offline_capability("facebook/m2m100_418M") is True


def test_verify_offline_capability_raises_when_offline_mode_and_cache_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_root = tmp_path / ".cache" / "huggingface"
    monkeypatch.setenv("HF_HOME", str(cache_root))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    with pytest.raises(RuntimeError, match="Model cache not available for offline mode"):
        _verify_offline_capability("facebook/m2m100_418M")


def test_verify_offline_capability_returns_false_when_model_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_root = tmp_path / ".cache" / "huggingface"
    cache_root.mkdir(parents=True)
    monkeypatch.setenv("HF_HOME", str(cache_root))
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)

    assert _verify_offline_capability("facebook/m2m100_418M") is False
