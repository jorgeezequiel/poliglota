from __future__ import annotations

import logging

import pytest

from poliglota import cli as cli_module


@pytest.fixture
def mock_hf_cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path):
    cache_root = tmp_path / "hf-cache"
    (cache_root / "hub").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HF_HOME", str(cache_root))
    return cache_root


@pytest.fixture
def mock_environ(monkeypatch: pytest.MonkeyPatch):
    def _set(value: str | None) -> None:
        if value is None:
            monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
            return
        monkeypatch.setenv("HF_HUB_OFFLINE", str(value))

    return _set


@pytest.mark.unit
def test_select_default_motor_m2m_supported() -> None:
    assert cli_module._select_default_motor("pt_BR", "en_US") == "facebook/m2m100_418M"


@pytest.mark.unit
def test_select_default_motor_mbart_fallback(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("1")
    cache_dir = mock_hf_cache_path / "hub" / "facebook--mbart-50-many-to-many-mmt"
    cache_dir.mkdir(parents=True, exist_ok=True)

    assert cli_module._select_default_motor("pt_BR", "de") == "facebook/mbart-50-many-to-many-mmt"


@pytest.mark.unit
def test_select_default_motor_unsupported_pair() -> None:
    with pytest.raises(ValueError, match="Unsupported default motor pair"):
        cli_module._select_default_motor("xx", "yy")


@pytest.mark.unit
def test_select_default_motor_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLIGLOTA_DEFAULT_MOTOR", "facebook/mbart-50-many-to-many-mmt")

    assert cli_module._select_default_motor("pt_BR", "en_US") == "facebook/mbart-50-many-to-many-mmt"


@pytest.mark.unit
def test_select_default_motor_offline_mode_skips_missing_m2m_cache(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("1")
    (mock_hf_cache_path / "hub" / "facebook--mbart-50-many-to-many-mmt").mkdir(parents=True, exist_ok=True)

    assert cli_module._select_default_motor("pt_BR", "de") == "facebook/mbart-50-many-to-many-mmt"


@pytest.mark.unit
def test_verify_offline_with_cache_present(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("1")
    cache_dir = mock_hf_cache_path / "hub" / "facebook--m2m100_418M"
    cache_dir.mkdir(parents=True, exist_ok=True)

    assert cli_module._verify_offline_capability("facebook/m2m100_418M") is True


@pytest.mark.unit
def test_verify_offline_with_cache_missing(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("1")

    with pytest.raises(RuntimeError, match="Model cache not available for offline mode"):
        cli_module._verify_offline_capability("facebook/m2m100_418M")


@pytest.mark.unit
def test_verify_offline_mode_disabled(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("0")

    assert cli_module._verify_offline_capability("facebook/m2m100_418M") is False


@pytest.mark.unit
def test_verify_offline_with_cache_present_when_offline_disabled(mock_environ, mock_hf_cache_path) -> None:
    mock_environ("0")
    (mock_hf_cache_path / "hub" / "facebook--m2m100_418M").mkdir(parents=True, exist_ok=True)

    assert cli_module._verify_offline_capability("facebook/m2m100_418M") is True


@pytest.mark.unit
def test_validate_m2m_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="poliglota.cli"):
        cli_module._validate_resource_footprint("M2M-100-418M")

    assert not any("requires" in record.message.lower() for record in caplog.records)


@pytest.mark.unit
def test_validate_mbart_ram_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="poliglota.cli"):
        cli_module._validate_resource_footprint("mBART-50")

    assert any("2GB+ may cause OOM" in record.message for record in caplog.records)


@pytest.mark.unit
def test_validate_nllb_both_warnings(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="poliglota.cli"):
        cli_module._validate_resource_footprint("NLLB-200")

    messages = [record.message for record in caplog.records]
    assert any("2GB+ may impact install" in message for message in messages)
    assert any("2GB+ may cause OOM" in message for message in messages)


@pytest.mark.unit
def test_validate_unknown_model_graceful(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="poliglota.cli"):
        cli_module._validate_resource_footprint("unknown-model")

    assert any("No Phase D resource footprint benchmark available" in record.message for record in caplog.records)

