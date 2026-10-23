from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from poliglota import cli as cli_module
from poliglota.engines import marian as marian_module
from poliglota.engines.protocol import (
    MariansNMTTranslationEngine,
    TranslationRequest,
    TranslationResult,
)


class TestTranslationRequest:
    def test_translation_request_dataclass_includes_expected_fields(self) -> None:
        request = TranslationRequest(
            text="Hello world",
            source_lang="en",
            target_lang="pt",
            preserve_placeholders=True,
        )

        assert request.text == "Hello world"
        assert request.source_lang == "en"
        assert request.target_lang == "pt"
        assert request.preserve_placeholders is True

    def test_translation_request_defaults_preserve_placeholders_to_true(self) -> None:
        request = TranslationRequest("Bonjour", "fr", "es")

        assert request.preserve_placeholders is True

    def test_translation_request_is_frozen(self) -> None:
        request = TranslationRequest("Hello", "en", "pt")

        with pytest.raises(FrozenInstanceError):
            request.text = "Bonjour"

    def test_translation_request_equality_and_repr_are_stable(self) -> None:
        left = TranslationRequest("Hi", "en", "fr")
        right = TranslationRequest("Hi", "en", "fr")

        assert left == right
        assert "TranslationRequest" in repr(left)


class TestTranslationResult:
    def test_translation_result_stores_output_and_metadata(self) -> None:
        result = TranslationResult(
            translated_text="Olá",
            source_lang="en",
            target_lang="pt",
            confidence=0.91,
            metadata={"model_name": "Helsinki-NLP/opus-mt-en-pt"},
        )

        assert result.translated_text == "Olá"
        assert result.source_lang == "en"
        assert result.target_lang == "pt"
        assert result.confidence == 0.91
        assert result.metadata["model_name"] == "Helsinki-NLP/opus-mt-en-pt"

    def test_translation_result_default_metadata_is_empty_dict(self) -> None:
        result = TranslationResult("Olá", "en", "pt", 0.99)

        assert result.metadata == {}

    def test_translation_result_is_frozen(self) -> None:
        result = TranslationResult("Olá", "en", "pt", 0.98)

        with pytest.raises(FrozenInstanceError):
            result.translated_text = "Hello"

    def test_translation_result_equality_uses_all_fields(self) -> None:
        left = TranslationResult("Olá", "en", "pt", 0.89)
        right = TranslationResult("Olá", "en", "pt", 0.89)

        assert left == right


class TestMariansNMTAdapter:
    @staticmethod
    def _mock_torch() -> SimpleNamespace:
        return SimpleNamespace(
            cuda=SimpleNamespace(
                is_available=lambda: True,
                OutOfMemoryError=RuntimeError,
                empty_cache=lambda: None,
            ),
            mps=SimpleNamespace(empty_cache=lambda: None),
        )

    def test_adapter_protocol_requires_required_methods(self) -> None:
        assert hasattr(MariansNMTTranslationEngine, "supports")
        assert hasattr(MariansNMTTranslationEngine, "load_model")
        assert hasattr(MariansNMTTranslationEngine, "translate")
        assert hasattr(MariansNMTTranslationEngine, "translate_batch")
        assert hasattr(MariansNMTTranslationEngine, "close")

    def test_adapter_raises_runtime_error_when_ml_dependencies_missing(self) -> None:
        with (
            patch.object(marian_module, "_IMPORT_ERROR", RuntimeError("missing dep")),
            pytest.raises(RuntimeError, match="Missing Marian offline dependency stack"),
        ):
            marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

    def test_adapter_load_model_with_mock(self) -> None:
        mock_tokenizer = Mock()
        mock_model = Mock()
        mock_model.to.return_value = mock_model
        mock_tokenizer.return_value = {"input_ids": [[1, 2]], "attention_mask": [[1, 1]]}
        mock_tokenizer.batch_decode.return_value = ["Olá mundo"]
        mock_model.generate.return_value = [[7, 8, 9]]

        with (
            patch.object(marian_module, "_IMPORT_ERROR", None),
            patch.object(marian_module, "torch", self._mock_torch()),
            patch.object(
                marian_module,
                "AutoTokenizer",
                Mock(from_pretrained=Mock(return_value=mock_tokenizer)),
            ),
            patch.object(
                marian_module,
                "AutoModelForSeq2SeqLM",
                Mock(from_pretrained=Mock(return_value=mock_model)),
            ),
        ):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter.load_model(device="cpu")

        assert adapter.model_name == "Helsinki-NLP/opus-mt-en-es"
        assert adapter.device == "cpu"
        assert adapter._model is mock_model
        assert adapter._tokenizer is mock_tokenizer

    def test_adapter_load_model_falls_back_to_cpu_when_cuda_unavailable(self) -> None:
        mock_tokenizer = Mock()
        mock_model = Mock()
        mock_model.to.return_value = mock_model
        mock_tokenizer.return_value = {"input_ids": [[1, 2]], "attention_mask": [[1, 1]]}
        mock_tokenizer.batch_decode.return_value = ["Hola"]
        mock_model.generate.return_value = [[7, 8, 9]]

        cuda_torch = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None),
            mps=SimpleNamespace(empty_cache=lambda: None),
        )

        with (
            patch.object(marian_module, "_IMPORT_ERROR", None),
            patch.object(marian_module, "torch", cuda_torch),
            patch.object(
                marian_module,
                "AutoTokenizer",
                Mock(from_pretrained=Mock(return_value=mock_tokenizer)),
            ),
            patch.object(
                marian_module,
                "AutoModelForSeq2SeqLM",
                Mock(from_pretrained=Mock(return_value=mock_model)),
            ),
        ):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter.load_model(device="cuda")

        assert adapter.device == "cpu"

    def test_adapter_raises_value_error_for_unsupported_model(self) -> None:
        with (
            patch.object(marian_module, "_IMPORT_ERROR", None),
            pytest.raises(ValueError, match="Unsupported Marian model"),
        ):
            marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-unsupported")

    def test_adapter_rejects_invalid_device(self) -> None:
        with (
            patch.object(marian_module, "_IMPORT_ERROR", None),
            pytest.raises(ValueError, match="Unsupported device"),
        ):
            marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es", device="tpu")

    def test_adapter_normalizes_supported_devices(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es", device="CUDA")

        assert adapter.device == "cuda"

    def test_adapter_supports_known_language_pairs(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        assert adapter.supports("en", "es") is True
        assert adapter.supports("es", "en") is True
        assert adapter.supports("en", "de") is False
        assert ("en", "pt") in adapter.get_supported_pairs()

    def test_adapter_engine_language_accepts_known_locale(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        assert adapter.engine_language("pt") == "pt"
        assert adapter.engine_language("fr") == "fr"

    def test_adapter_engine_language_rejects_unknown_locale(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        with pytest.raises(ValueError, match="Unsupported locale"):
            adapter.engine_language("ja_JP")

    def test_adapter_check_local_model_path_raises_for_missing_directory(
        self,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "does-not-exist"

        with pytest.raises(FileNotFoundError, match="Local Marian model not found"):
            marian_module.MariansNMTAdapter._check_local_model_path(str(missing))

    def test_adapter_strip_known_placeholders_records_positions(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        stripped, positions = adapter._strip_known_placeholders("<en>Hello <pt>friend")

        assert stripped == "Hello friend"
        assert positions == [(0, "<en>"), (10, "<pt>")]

    def test_adapter_restore_placeholders_at_positions_reinserts_tags(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        result = adapter._restore_placeholders_at_positions(
            "Hola amigo",
            [(0, "<en>"), (6, "<pt>")],
        )

        assert result == "<<en>>Hola a<<pt>>migo"

    def test_adapter_translate_preserves_known_placeholders(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter._translate_with_model = Mock(return_value=["Hola"])

            translated = adapter.translate("<en>Hello</en>", "en", "es")

        assert translated == "<<en>><<en>>Hola"

    def test_adapter_translate_batch_handles_multiple_inputs(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter.batch_size = 2
            adapter._translate_with_model = Mock(return_value=["Hola", "Buenas"])

            result = adapter.translate_batch(["Hello", "Good morning"], "en", "es")

        assert result == ["Hola", "Buenas"]

    def test_adapter_translate_batch_returns_empty_list_for_empty_input(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")

        assert adapter.translate_batch([], "en", "es") == []

    def test_adapter_translate_batch_raises_runtime_error_on_model_failure(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter.batch_size = 2
            adapter._translate_with_model = Mock(side_effect=RuntimeError("translate exploded"))

            with pytest.raises(RuntimeError, match="Marian batch inference failed"):
                adapter.translate_batch(["Hello", "Good morning"], "en", "es")

    def test_adapter_translate_request_returns_translation_result(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter.translate = Mock(return_value="Hola")

            result = adapter.translate_request(TranslationRequest("Hello", "en", "es"))

        assert result.translated_text == "Hola"
        assert result.source_lang == "en"
        assert result.target_lang == "es"
        assert result.confidence == 1.0

    def test_adapter_close_clears_loaded_model_and_cache(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter._model = Mock()
            adapter._tokenizer = Mock()
            mock_torch = self._mock_torch()
            with patch.object(marian_module, "torch", mock_torch):
                adapter.close()

        assert adapter._model is None
        assert adapter._tokenizer is None
        assert adapter._last_placeholder_positions == []

    def test_adapter_get_model_info_reports_runtime_metadata(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter._last_inference_time_ms = 125.4

            info = adapter.get_model_info()

        assert info["model_name"] == "Helsinki-NLP/opus-mt-en-es"
        assert info["device"] == "cpu"
        assert info["pairs_count"] == len(adapter.get_supported_pairs())
        assert info["last_inference_time_ms"] == 125

    def test_adapter_translate_raises_value_error_for_unsupported_pair(self) -> None:
        with patch.object(marian_module, "_IMPORT_ERROR", None):
            adapter = marian_module.MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
            adapter._translate_with_model = Mock(return_value=["Hola"])  # not reached

            with pytest.raises(ValueError, match="Unsupported translation pair"):
                adapter.translate("Hello", "en", "de")


class TestTranslateCommand:
    def test_translate_command_parser_includes_translate_subcommand(self) -> None:
        parser = cli_module._build_parser()
        args = parser.parse_args([
            "translate",
            "Hello",
            "--source",
            "en_US",
            "--target",
            "pt_BR",
        ])

        assert args.command == "translate"
        assert args.text == "Hello"
        assert args.source == "en_US"
        assert args.target == "pt_BR"

    def test_locale_to_engine_code_converts_poliglota_locale(self) -> None:
        assert cli_module._locale_to_engine_code("pt_BR") == "pt"
        assert cli_module._locale_to_engine_code("en_US") == "en"
        assert cli_module._locale_to_engine_code("fr") == "fr"

    def test_translate_with_placeholders_preserves_structured_tokens(self) -> None:
        adapter = Mock()
        adapter.translate.return_value = "Olá {name}!"

        with patch.object(cli_module, "_get_marian_adapter", return_value=adapter):
            translated, placeholder_stats, elapsed = cli_module._translate_with_placeholders(
                "Hello {name}",
                "en_US",
                "pt_BR",
                preserve_placeholders=True,
                model_name="Helsinki-NLP/opus-mt-en-pt",
                device="cpu",
                batch_size=8,
            )

        assert translated == "Olá {name}!"
        assert placeholder_stats["preserved"] == 1
        assert elapsed >= 0

    def test_translate_no_placeholder_preserves_raw_text(self) -> None:
        adapter = Mock()
        adapter.translate.return_value = "Olá {name}!"

        with patch.object(cli_module, "_get_marian_adapter", return_value=adapter):
            translated, placeholder_stats, elapsed = cli_module._translate_with_placeholders(
                "Hello {name}",
                "en_US",
                "pt_BR",
                preserve_placeholders=False,
                model_name="Helsinki-NLP/opus-mt-en-pt",
                device="cpu",
                batch_size=8,
            )

        assert translated == "Olá {name}!"
        assert placeholder_stats == {"preserved": 0, "substituted": 0, "missing": 0}
        assert elapsed >= 0

    def test_translate_command_success_for_plain_text(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch.object(
            cli_module,
            "_translate_with_placeholders",
            return_value=("Olá", {"preserved": 0, "substituted": 0, "missing": 0}, 12.5),
        ):
            exit_code = cli_module.main([
                "translate",
                "Hello",
                "--source",
                "en_US",
                "--target",
                "pt_BR",
            ])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Olá" in captured.out

    def test_translate_command_outputs_json_when_requested(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch.object(
            cli_module,
            "_translate_with_placeholders",
            return_value=("Olá", {"preserved": 1, "substituted": 0, "missing": 0}, 42.0),
        ):
            exit_code = cli_module.main([
                "translate",
                "Hello",
                "--source",
                "en_US",
                "--target",
                "pt_BR",
                "--json-output",
            ])

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exit_code == 0
        assert payload["translated"] == "Olá"
        assert payload["source"] == "en_US"
        assert payload["target"] == "pt_BR"
        assert payload["preserved_placeholders"] == 1

    def test_translate_command_unsupported_engine(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = cli_module.main(["translate", "Hello", "--engine", "google"])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Unsupported engine 'google'" in captured.out

    def test_translate_command_invalid_device(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = cli_module.main(["translate", "Hello", "--device", "npu"])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Unsupported device 'npu'" in captured.out

    def test_translate_command_value_error(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch.object(
            cli_module,
            "_translate_with_placeholders",
            side_effect=ValueError("bad input"),
        ):
            exit_code = cli_module.main(["translate", "Hello"])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Error: bad input" in captured.out

    def test_translate_command_runtime_error(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch.object(
            cli_module,
            "_translate_with_placeholders",
            side_effect=RuntimeError("model failed"),
        ):
            exit_code = cli_module.main(["translate", "Hello"])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Error: model failed" in captured.out
        assert "Hint: try --device cpu" in captured.out

    def test_translate_command_missing_model_file(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch.object(
            cli_module,
            "_translate_with_placeholders",
            side_effect=FileNotFoundError("model missing"),
        ):
            exit_code = cli_module.main(["translate", "Hello"])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Error: model missing" in captured.out

    def test_get_marian_adapter_raises_runtime_error_for_missing_module(self) -> None:
        with (
            patch.object(
                cli_module.importlib,
                "import_module",
                side_effect=ModuleNotFoundError("missing"),
            ),
            pytest.raises(RuntimeError, match="Marian engine is not available"),
        ):
            cli_module._get_marian_adapter("Helsinki-NLP/opus-mt-en-pt", "cpu")
