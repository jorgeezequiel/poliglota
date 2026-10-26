"""Garante que a versão do pacote seja declarada de forma consistente.

As fontes verificadas são:

- ``pyproject.toml`` (metadado oficial do pacote);
- ``poliglota/__init__.py`` (introspecção em tempo de execução);
- ``VERSION`` (arquivo de versionamento na raiz do repositório);
- metadados da instalação atual, quando o pacote estiver instalado.
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def _pyproject_version() -> str:
    """Lê a versão declarada em ``[project].version`` no ``pyproject.toml``."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _module_version() -> str:
    """Lê ``__version__`` diretamente do módulo ``poliglota/__init__.py``."""
    source = (ROOT / "poliglota" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', source, flags=re.MULTILINE)
    assert match is not None, "__version__ não encontrado em poliglota/__init__.py"
    return match.group(1)


def _version_file() -> str:
    """Lê o conteúdo normalizado do arquivo ``VERSION``."""
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_version_sources_match() -> None:
    """``pyproject.toml``, ``__init__.py`` e ``VERSION`` devem ser idênticos."""
    versions = {
        "pyproject.toml": _pyproject_version(),
        "poliglota/__init__.py": _module_version(),
        "VERSION": _version_file(),
    }
    assert len(set(versions.values())) == 1, f"Versões divergentes: {versions}"


def test_version_is_valid_semver() -> None:
    """A versão compartilhada precisa respeitar o formato SemVer."""
    version = _pyproject_version()
    assert SEMVER_PATTERN.match(version), f"Versão fora do padrão SemVer: {version!r}"


def test_installed_metadata_matches_version_sources() -> None:
    """Os metadados da instalação atual devem refletir as fontes versionadas."""
    try:
        installed = importlib.metadata.version("poliglota")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("poliglota não está instalado neste ambiente")

    assert installed == _pyproject_version(), (
        "Metadados da instalação divergem do pyproject.toml; "
        "reinstale com `python -m pip install -e .`"
    )
