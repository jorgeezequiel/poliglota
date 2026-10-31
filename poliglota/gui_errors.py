"""Translate raw CLI failures into actionable messages for GUI users.

The CLI prints technical diagnostics on stderr. Users of the desktop window
should not have to decode them, so every failure is classified into a small
category with a plain-language title and a concrete next step, while the raw
output is kept below for anyone who wants the details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorCategory:
    """User-facing description of a failed command."""

    code: str
    title: str
    suggestion: str


UNKNOWN_ERROR = ErrorCategory(
    code="unknown",
    title="Não foi possível concluir o comando",
    suggestion="Confira os detalhes técnicos abaixo e tente novamente.",
)

_RULES: tuple[tuple[re.Pattern[str], ErrorCategory], ...] = (
    (
        re.compile(r"permission denied|permissionerror", re.IGNORECASE),
        ErrorCategory(
            code="permission_denied",
            title="Sem permissão para acessar os arquivos",
            suggestion=(
                "Feche o arquivo em outros programas ou escolha uma pasta "
                "onde você tenha permissão de escrita."
            ),
        ),
    ),
    (
        re.compile(r"timed out|timeoutexpired|timeout", re.IGNORECASE),
        ErrorCategory(
            code="timeout",
            title="O comando demorou demais e foi interrompido",
            suggestion=(
                "Tente novamente com um projeto menor ou use um modelo já "
                "baixado para reduzir o tempo de execução."
            ),
        ),
    ),
    (
        re.compile(r"no module named|modulenotfounderror|importerror", re.IGNORECASE),
        ErrorCategory(
            code="missing_dependency",
            title="Dependência opcional não instalada",
            suggestion=(
                "Instale as dependências de tradução com: "
                "pip install poliglota[gpu] (ou escolha o motor marian)."
            ),
        ),
    ),
    (
        re.compile(
            r"cuda out of memory|outofmemoryerror|out of memory|not enough vram",
            re.IGNORECASE,
        ),
        ErrorCategory(
            code="out_of_memory",
            title="Memória da GPU insuficiente",
            suggestion=(
                "Troque o dispositivo para 'cpu', reduza o tamanho do lote "
                "ou feche outros programas que usam a GPU."
            ),
        ),
    ),
    (
        re.compile(
            r"not compiled with cuda|cuda.*not available|no cuda-capable device",
            re.IGNORECASE,
        ),
        ErrorCategory(
            code="cuda_unavailable",
            title="CUDA não está disponível neste ambiente",
            suggestion="Selecione o dispositivo 'cpu' ou 'auto' e execute novamente.",
        ),
    ),
    (
        re.compile(r"unsupported engine|unsupported device|invalid device", re.IGNORECASE),
        ErrorCategory(
            code="invalid_option",
            title="Opção de motor ou dispositivo inválida",
            suggestion="Escolha um motor (marian, pytorch) e um dispositivo válido na lista.",
        ),
    ),
    (
        re.compile(r"glossary", re.IGNORECASE),
        ErrorCategory(
            code="glossary_error",
            title="Problema no glossário informado",
            suggestion="Verifique o caminho do glossário e use um arquivo .json ou .csv válido.",
        ),
    ),
    (
        re.compile(r"no .{0,20}files found under|no locale files found", re.IGNORECASE),
        ErrorCategory(
            code="no_files",
            title="Nenhum arquivo de tradução encontrado",
            suggestion=(
                "Confirme a pasta do projeto e o formato selecionado "
                "(arb, json, yaml ou xml) antes de tentar novamente."
            ),
        ),
    ),
    (
        re.compile(r"no such file or directory|filenotfounderror", re.IGNORECASE),
        ErrorCategory(
            code="file_not_found",
            title="Arquivo ou pasta não encontrado",
            suggestion="Use o botão 'Selecionar' para escolher uma pasta de projeto existente.",
        ),
    ),
    (
        re.compile(r"validation issues found|placeholder", re.IGNORECASE),
        ErrorCategory(
            code="validation_issues",
            title="Foram encontrados problemas nos recursos",
            suggestion=(
                "Corrija as chaves listadas abaixo (placeholders e estrutura) "
                "e execute a validação novamente."
            ),
        ),
    ),
    (
        re.compile(r"json\.decoder|yaml|xml|parse|malformed", re.IGNORECASE),
        ErrorCategory(
            code="format_error",
            title="Arquivo de tradução malformado",
            suggestion="Abra o arquivo indicado abaixo e confira a sintaxe do formato escolhido.",
        ),
    ),
)


def categorize_error(output: str) -> ErrorCategory:
    """Classify a failed command output into a user-facing category."""
    text = output or ""
    for pattern, category in _RULES:
        if pattern.search(text):
            return category

    return UNKNOWN_ERROR


def build_error_report(output: str, *, exit_code: int) -> str:
    """Return a friendly report that keeps the technical details below it."""
    category = categorize_error(output)
    details = (output or "").strip() or "Sem detalhes adicionais."

    return "\n".join(
        (
            f"[ERRO] {category.title}",
            "",
            f"Sugestão: {category.suggestion}",
            "",
            f"Detalhes técnicos (código de saída {exit_code}):",
            details,
        ),
    )
