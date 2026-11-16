"""Project translation orchestration regressions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from poliglota.translation_workflow import translate_resource_files


def test_project_translation_reuses_engine_and_uses_android_target_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from poliglota import cli

    root = tmp_path / "res"
    source_dir = root / "values-pt-rBR"
    source_dir.mkdir(parents=True)
    for filename, message in (("strings_a.xml", "Olá %1$s"), ("strings_b.xml", "Bloquear")):
        (source_dir / filename).write_text(
            f'<resources><string name="message">{message}</string></resources>',
            encoding="utf-8",
        )

    created: list[object] = []
    calls: list[object] = []
    adapter = object()

    def create_engine(*args: object) -> object:
        created.append(args)
        return adapter

    def translate(
        text: str, *_args: object, adapter: object | None = None, **_kwargs: object
    ) -> tuple[str, dict[str, int], float]:
        calls.append(adapter)
        return text.replace("Olá", "Hola").replace("Bloquear", "Bloquear"), {}, 1.0

    monkeypatch.setattr(cli, "create_translation_engine", create_engine)
    monkeypatch.setattr(cli, "translate_with_placeholders", translate)
    output = tmp_path / "translated"
    report = translate_resource_files(
        root,
        "pt_BR",
        ["es_ES"],
        format_name="xml",
        output_dir=output,
        engine="pytorch",
        model="facebook/nllb-200-distilled-600M",
        device="cpu",
    )

    assert len(created) == 1
    assert calls == [adapter, adapter]
    assert report.failed == 0
    assert report.processed == 2
    assert report.translated == 2
    result = sorted((output / "values-es-rES").glob("*.xml"))
    assert len(result) == 2
    assert all(
        "%1$s" in path.read_text(encoding="utf-8") or "Bloquear" in path.read_text(encoding="utf-8")
        for path in result
    )
