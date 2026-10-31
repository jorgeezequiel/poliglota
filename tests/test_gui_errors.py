from __future__ import annotations

import pytest

from poliglota.gui_errors import UNKNOWN_ERROR, build_error_report, categorize_error


@pytest.mark.unit
@pytest.mark.parametrize(
    ("output", "expected_code"),
    [
        ("PermissionError: [Errno 13] Permission denied", "permission_denied"),
        ("Command 'x' timed out after 300 seconds", "timeout"),
        ("ModuleNotFoundError: No module named 'torch'", "missing_dependency"),
        ("torch.cuda.OutOfMemoryError: CUDA out of memory", "out_of_memory"),
        ("Torch not compiled with CUDA enabled", "cuda_unavailable"),
        ("Error: Unsupported engine 'foo'. Use one of: marian, pytorch.", "invalid_option"),
        ("Unsupported device 'tpu'. Supported: auto, cpu, cuda, mps, gpu", "invalid_option"),
        ("Glossary file not found: glossary.json", "glossary_error"),
        ("No ARB files found under C:/project.", "no_files"),
        ("No locale files found under C:/project.", "no_files"),
        ("FileNotFoundError: [Errno 2] No such file or directory", "file_not_found"),
        ("Validation issues found:", "validation_issues"),
        ("json.decoder.JSONDecodeError: Expecting value", "format_error"),
    ],
)
def test_categorize_error_matches_real_cli_messages(output: str, expected_code: str) -> None:
    assert categorize_error(output).code == expected_code


@pytest.mark.unit
def test_categorize_error_falls_back_to_unknown() -> None:
    assert categorize_error("algo inesperado aconteceu") is UNKNOWN_ERROR


@pytest.mark.unit
def test_categorize_error_handles_empty_output() -> None:
    assert categorize_error("") is UNKNOWN_ERROR


@pytest.mark.unit
def test_build_error_report_contains_title_suggestion_and_details() -> None:
    report = build_error_report("No ARB files found under C:/project.", exit_code=1)

    assert "Nenhum arquivo de tradução encontrado" in report
    assert "Sugestão" in report
    assert "código de saída 1" in report
    assert "No ARB files found under C:/project." in report


@pytest.mark.unit
def test_build_error_report_keeps_generic_details_when_output_is_empty() -> None:
    report = build_error_report("", exit_code=2)

    assert "Sem detalhes adicionais" in report
    assert "código de saída 2" in report
