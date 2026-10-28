"""Tests for interactive CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from poliglota import cli_interactive

if TYPE_CHECKING:
    import pytest


def test_interactive_cancel_on_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_input(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    result = cli_interactive.run_interactive()
    assert result == 0
