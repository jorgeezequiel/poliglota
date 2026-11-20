from __future__ import annotations

import json
from pathlib import Path

import pytest

from poliglota.formats.arb import load_arb
from poliglota.translation_review import TranslationReviewSession


@pytest.mark.unit
def test_review_session_persists_edits_without_overwriting_source_and_exports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "app_home_en_US.arb"
    source.write_text(
        json.dumps(
            {
                "@@locale": "en_US",
                "hello": "Hello {name}",
                "@hello": {"description": "Greeting"},
            }
        ),
        encoding="utf-8",
    )
    translated = root / ".poliglota_translated" / "app_home_es_ES.arb"
    translated.parent.mkdir()
    translated.write_text(
        json.dumps(
            {
                "@@locale": "es_ES",
                "hello": "Hola {name}",
                "@hello": {"description": "Greeting"},
            }
        ),
        encoding="utf-8",
    )
    source_bytes = source.read_bytes()
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert session.pending_count == 1
    assert session.items[0].context == "Greeting"

    session.save(session.items[0].file, "hello", "Saludos {name}", reviewed=True)
    assert session.pending_count == 0
    assert source.read_bytes() == source_bytes

    resumed = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert resumed.items[0].value == "Saludos {name}"
    assert resumed.items[0].reviewed is True
    with pytest.raises(ValueError, match="Placeholder"):
        resumed.save(resumed.items[0].file, "hello", "Saludos", reviewed=True)

    exported = resumed.export(tmp_path / "exported")
    payload = load_arb(exported / "app_home_es_ES.arb")
    assert payload["hello"] == "Saludos {name}"
    assert payload["@hello"] == {"description": "Greeting"}
    with pytest.raises(FileExistsError):
        resumed.export(exported)


@pytest.mark.unit
def test_android_review_export_keeps_nontranslatable_resources_and_format_placeholders(
    tmp_path: Path,
) -> None:
    root = tmp_path / "android"
    source_dir = root / "app" / "src" / "main" / "res" / "values-pt-rBR"
    source_dir.mkdir(parents=True)
    source = source_dir / "strings.xml"
    source.write_text(
        '<resources><string name="count">%1$s itens</string>'
        '<string name="package" translatable="false">Poliglota</string></resources>',
        encoding="utf-8",
    )
    target = (
        root
        / ".poliglota_translated"
        / "app"
        / "src"
        / "main"
        / "res"
        / "values-es-rES"
        / "strings.xml"
    )
    target.parent.mkdir(parents=True)
    target.write_text(
        '<resources><string name="count">%1$s elementos</string>'
        '<string name="package" translatable="false">Poliglota</string></resources>',
        encoding="utf-8",
    )
    session = TranslationReviewSession(root, "xml", "pt_BR", "es_ES")
    assert [item.key for item in session.items] == ["count"]
    session.save(session.items[0].file, "count", "%1$s elementos", reviewed=True)
    exported = session.export(tmp_path / "android-export")
    xml = (exported / "app" / "src" / "main" / "res" / "values-es-rES" / "strings.xml").read_text(
        encoding="utf-8"
    )
    assert 'name="count"' in xml
    assert "%1$s elementos" in xml
    assert 'name="package" translatable="false"' in xml


@pytest.mark.unit
def test_android_export_preserves_format_tokens_escapes_and_nontranslatable_resource(
    tmp_path: Path,
) -> None:
    root = tmp_path / "android"
    source_dir = root / "res" / "values-pt-rBR"
    source_dir.mkdir(parents=True)
    source = source_dir / "strings.xml"
    source.write_text(
        r'<resources><string name="format">%1$s: %2$d %%\ntexto</string>'
        '<string name="fixed" translatable="false">literal</string></resources>',
        encoding="utf-8",
    )
    target = root / ".poliglota_translated" / "res" / "values-es-rES" / "strings.xml"
    target.parent.mkdir(parents=True)
    target.write_text(
        r'<resources><string name="format">%1$s: %2$d %%\ntexto</string>'
        '<string name="fixed" translatable="false">literal</string></resources>',
        encoding="utf-8",
    )
    session = TranslationReviewSession(root, "xml", "pt_BR", "es_ES")
    item = session.items[0]
    with pytest.raises(ValueError, match="Placeholder"):
        session.save(item.file, item.key, "%1$s: texto", reviewed=True)
    with pytest.raises(ValueError, match="Android escape"):
        session.save(item.file, item.key, r"%1$s: %2$d %%texto", reviewed=True)
    destination = session.export(tmp_path / "android-final")
    exported_xml = destination / "res" / "values-es-rES" / "strings.xml"
    assert "%1$s" in exported_xml.read_text(encoding="utf-8")
    assert r"\n" in exported_xml.read_text(encoding="utf-8")


@pytest.mark.unit
def test_export_preliminary_files_without_saved_review(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "app_home_en_US.arb"
    source.write_text('{"@@locale":"en_US","hello":"Hello"}', encoding="utf-8")
    generated = root / ".poliglota_translated" / "app_home_es_ES.arb"
    generated.parent.mkdir()
    generated.write_text('{"@@locale":"es_ES","hello":"Hola"}', encoding="utf-8")

    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    exported = session.export(tmp_path / "exported")

    assert load_arb(exported / generated.name) == load_arb(generated)
    assert source.read_text(encoding="utf-8") == '{"@@locale":"en_US","hello":"Hello"}'


def _arb_project(
    root: Path,
    *,
    key: str = "same",
    source_text: str = "Hello {name}",
    preliminary: str = "Hola {name}",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "app_home_en_US.arb").write_text(
        json.dumps({"@@locale": "en_US", key: source_text, f"@{key}": {"description": "Greeting"}}),
        encoding="utf-8",
    )
    translated = root / ".poliglota_translated" / "app_home_es_ES.arb"
    translated.parent.mkdir(parents=True, exist_ok=True)
    translated.write_text(
        json.dumps({"@@locale": "es_ES", key: preliminary, f"@{key}": {"description": "Greeting"}}),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_review_scope_isolated_by_locale_pair_and_project(tmp_path: Path) -> None:
    first = tmp_path / "project one"
    second = tmp_path / "project two"
    _arb_project(first)
    _arb_project(second)
    es = TranslationReviewSession(first, "arb", "en_US", "es_ES")
    es.save(es.items[0].file, "same", "Hola {name}", reviewed=True)

    fr_file = first / ".poliglota_translated" / "app_home_fr_FR.arb"
    fr_file.write_text(
        json.dumps({"@@locale": "fr_FR", "same": "Bonjour {name}"}), encoding="utf-8"
    )
    fr = TranslationReviewSession(first, "arb", "en_US", "fr_FR")
    assert fr.pending_count == 1
    assert fr.items[0].value == "Bonjour {name}"
    other = TranslationReviewSession(second, "arb", "en_US", "es_ES")
    assert other.pending_count == 1
    pt_source = first / "app_home_pt_BR.arb"
    pt_source.write_text(json.dumps({"@@locale": "pt_BR", "same": "Olá {name}"}), encoding="utf-8")
    pt_session = TranslationReviewSession(first, "arb", "pt_BR", "es_ES")
    assert pt_session.items[0].source == "Olá {name}"
    assert pt_session.pending_count == 1


@pytest.mark.unit
def test_same_key_in_different_files_and_open_sessions_do_not_collide(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    (root / "app_profile_en_US.arb").write_text(
        json.dumps({"@@locale": "en_US", "same": "Other source"}), encoding="utf-8"
    )
    (root / ".poliglota_translated" / "app_profile_es_ES.arb").write_text(
        json.dumps({"@@locale": "es_ES", "same": "Otra fuente"}), encoding="utf-8"
    )
    first = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    second = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    home = next(item for item in first.items if item.file == "app_home_es_ES.arb")
    profile = next(item for item in second.items if item.file == "app_profile_es_ES.arb")
    first.save(home.file, home.key, "Saludo {name}", reviewed=True)
    second.save(profile.file, profile.key, "Fuente distinta", reviewed=True)
    resumed = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    values = {(item.file, item.key): item.value for item in resumed.items}
    assert values[(home.file, home.key)] == "Saludo {name}"
    assert values[(profile.file, profile.key)] == "Fuente distinta"
    assert resumed.pending_count == 0


@pytest.mark.unit
def test_changed_source_or_preliminary_marks_review_stale_and_keeps_history(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    session.save(session.items[0].file, "same", "Revisado {name}", reviewed=True)
    _arb_project(root, source_text="Welcome {name}", preliminary="Bienvenido {name}")
    resumed = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    item = resumed.items[0]
    assert item.stale is True
    assert item.reviewed is False
    assert item.value == "Bienvenido {name}"
    assert item.previous_review == "Revisado {name}"
    with pytest.raises(ValueError, match="Placeholder"):
        resumed.save(item.file, item.key, "Revisado", reviewed=True)
    with pytest.raises(ValueError, match="Stale review"):
        resumed.export(tmp_path / "stale-export")


@pytest.mark.unit
def test_metadata_only_change_does_not_stale_review(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    item = session.items[0]
    session.save(item.file, item.key, "Hola {name}", reviewed=True)
    source = root / "app_home_en_US.arb"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["@same"]["description"] = "Updated description only"
    source.write_text(json.dumps(data), encoding="utf-8")
    reopened = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert reopened.items[0].reviewed is True


@pytest.mark.unit
def test_manifest_replace_failure_preserves_previous_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    item = session.items[0]
    session.save(item.file, item.key, "Hola {name}", reviewed=False)
    manifest = root / ".poliglota_reviewed" / "review_manifest.json"
    original = manifest.read_bytes()
    failure = OSError("replace failed")
    monkeypatch.setattr(Path, "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(failure))
    with pytest.raises(ValueError, match="safely save"):
        session.save(item.file, item.key, "Saludos {name}", reviewed=True)
    assert manifest.read_bytes() == original
    assert not list(manifest.parent.glob("review-*.tmp"))


@pytest.mark.unit
def test_json_export_translates_only_strings_and_preserves_types(tmp_path: Path) -> None:
    root = tmp_path / "json-project"
    source_dir = root / "locales"
    source_dir.mkdir(parents=True)
    (source_dir / "app_en_US.json").write_text(
        json.dumps({"menu": {"title": "Settings", "count": 3}, "enabled": True}),
        encoding="utf-8",
    )
    target = root / ".poliglota_translated" / "locales" / "app_es_ES.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"menu": {"title": "Ajustes", "count": 3}, "enabled": True}),
        encoding="utf-8",
    )
    session = TranslationReviewSession(root, "json", "en_US", "es_ES")
    assert [item.key for item in session.items] == ["menu.title"]
    session.save(session.items[0].file, "menu.title", "Preferencias", reviewed=True)
    exported = session.export(tmp_path / "json-export")
    document = json.loads((exported / "locales" / "app_es_ES.json").read_text(encoding="utf-8"))
    assert document == {"menu": {"title": "Preferencias", "count": 3}, "enabled": True}


@pytest.mark.unit
def test_save_detects_source_changed_while_window_is_open(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    source = root / "app_home_en_US.arb"
    source.write_text(json.dumps({"@@locale": "en_US", "same": "Changed {name}"}), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        session.save(session.items[0].file, "same", "Revised {name}", reviewed=True)


@pytest.mark.unit
def test_corrupt_manifest_fails_without_discarding_existing_data(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    manifest = root / ".poliglota_reviewed" / "review_manifest.json"
    manifest.parent.mkdir()
    manifest.write_text('{"schema":', encoding="utf-8")
    with pytest.raises(ValueError, match="preserved"):
        TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert manifest.read_text(encoding="utf-8") == '{"schema":'


@pytest.mark.unit
def test_export_is_transactional_and_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "projeto ü"
    _arb_project(root)
    second_source = root / "app_profile_en_US.arb"
    second_source.write_text(json.dumps({"@@locale": "en_US", "name": "Profile"}), encoding="utf-8")
    second_output = root / ".poliglota_translated" / "app_profile_es_ES.arb"
    second_output.write_text(json.dumps({"@@locale": "es_ES", "name": "Perfil"}), encoding="utf-8")
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    destination = tmp_path / "saída final"
    original_copy = __import__("poliglota.translation_review", fromlist=["shutil"]).shutil.copy2
    injected_error = OSError("injected second-stage copy failure")
    calls = 0

    def fail_copy(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise injected_error
        original_copy(source, target)

    monkeypatch.setattr("poliglota.translation_review.shutil.copy2", fail_copy)
    with pytest.raises(OSError, match="injected"):
        session.export(destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".saída final.staging-*"))
    monkeypatch.setattr("poliglota.translation_review.shutil.copy2", original_copy)
    session.export(destination)
    with pytest.raises(FileExistsError):
        session.export(destination)
    assert destination.exists()


@pytest.mark.parametrize("failure_point", ["destination", "marker"])
def test_export_publication_failure_removes_only_attempted_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    destination = tmp_path / "published"
    marker = destination / ".poliglota-export-incomplete"

    if failure_point == "destination":
        original_mkdir = Path.mkdir
        failure = PermissionError("injected destination permission failure")

        def fail_destination_mkdir(
            path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
        ) -> None:
            if path == destination:
                raise failure
            original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

        monkeypatch.setattr(Path, "mkdir", fail_destination_mkdir)
    else:
        original_write_text = Path.write_text
        failure = OSError("injected publication marker failure")

        def fail_marker_write(path: Path, data: str, *args: object, **kwargs: object) -> int:
            if path == marker:
                raise failure
            return original_write_text(path, data, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_marker_write)

    with pytest.raises((PermissionError, OSError)):
        session.export(destination)

    assert not destination.exists()
    assert not list(tmp_path.glob(".published.staging-*"))
    assert (root / "app_home_en_US.arb").is_file()


def test_export_staging_permission_failure_does_not_create_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    destination = tmp_path / "published"
    failure = PermissionError("injected staging permission failure")

    def fail_staging(*_args: object, **_kwargs: object) -> Path:
        raise failure

    monkeypatch.setattr("poliglota.translation_review.tempfile.mkdtemp", fail_staging)
    with pytest.raises(PermissionError):
        session.export(destination)

    assert not destination.exists()
    assert (root / "app_home_en_US.arb").is_file()


@pytest.mark.unit
def test_manifest_v1_is_preserved_but_never_auto_approves(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    manifest = root / ".poliglota_reviewed" / "review_manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps({"schema": 1, "reviewed": {"app_home_es_ES.arb": ["same"]}}), encoding="utf-8"
    )
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert session.pending_count == 1
    session.save(session.items[0].file, "same", "Hola {name}", reviewed=False)
    migrated = json.loads(manifest.read_text(encoding="utf-8"))
    assert migrated["schema"] == 2
    assert migrated["legacy_v1"]["reviewed"]["app_home_es_ES.arb"] == ["same"]


@pytest.mark.unit
def test_export_fails_when_any_source_file_has_no_translation(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _arb_project(root)
    (root / "app_profile_en_US.arb").write_text(
        json.dumps({"@@locale": "en_US", "name": "Profile"}), encoding="utf-8"
    )
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    destination = tmp_path / "export"

    with pytest.raises(ValueError, match="Translated localization file is missing"):
        session.export(destination)
    assert not destination.exists()
