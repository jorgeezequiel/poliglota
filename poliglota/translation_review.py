"""Persistent, isolated and transactionally exported translation reviews."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml
from defusedxml import ElementTree

from poliglota.core.format import LocalizedDocument
from poliglota.core.locale import Locale
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry
from poliglota.language_detection import normalize_locale_code
from poliglota.quality.placeholders import ArbPlaceholderProtector

MANIFEST_NAME = "review_manifest.json"
SCHEMA_VERSION = 2


class ReviewSessionError(ValueError):
    """An expected problem opening, saving, validating, or exporting reviews."""


def _fail(message: str) -> NoReturn:
    raise ReviewSessionError(message)


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """One translation and its review freshness state."""

    file: str
    key: str
    source: str
    preliminary: str
    value: str
    context: str
    reviewed: bool
    stale: bool = False
    previous_review: str | None = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scope_key(root: Path, format_name: str, source: str, target: str) -> str:
    identity = json.dumps(
        [str(root.resolve()).casefold(), format_name.lower(), source, target],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _digest(identity)


def _flatten_string_values(value: Any, prefix: str = "") -> dict[str, str]:
    """Flatten only string leaves; other JSON/YAML values remain structural data."""
    result: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten_string_values(child, name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            name = f"{prefix}.{index}" if prefix else str(index)
            result.update(_flatten_string_values(child, name))
    elif isinstance(value, str):
        result[prefix] = value
    return result


def _translatable_entries(document: LocalizedDocument, format_name: str) -> dict[str, str]:
    """Return only actual string leaves for adapters that stringify scalars."""
    if format_name not in {"json", "yaml", "yml"}:
        return {key: value for key, value in document.entries.items() if isinstance(value, str)}
    metadata_key = "@@json_original" if format_name == "json" else "@@yaml_original"
    raw = document.metadata.get(metadata_key)
    if not isinstance(raw, str):
        return {}
    structure = json.loads(raw) if format_name == "json" else yaml.safe_load(raw)
    raw_strings = _flatten_string_values(structure)
    return {
        key: value
        for key, value in raw_strings.items()
        if key in document.entries and document.entries[key] == value
    }


def _set_path(value: Any, dotted: str, replacement: str) -> None:
    parts = dotted.split(".")
    current = value
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = replacement
    else:
        if not isinstance(current.get(final), str):
            _fail(f"Refusing to replace non-string field: {dotted}")
        current[final] = replacement


class TranslationReviewSession:
    """Load, persist, validate and safely export a local translation review."""

    def __init__(self, root: Path, format_name: str, source: str, target: str) -> None:
        """Create a locale-scoped session and load the existing local manifest."""
        self.root = Path(root).resolve()
        self.format_name = format_name.lower()
        self.source = normalize_locale_code(source) or source
        self.target = normalize_locale_code(target) or target
        self.translation_root = self.root / ".poliglota_translated"
        self.review_root = self.root / ".poliglota_reviewed"
        self.manifest_path = self.review_root / MANIFEST_NAME
        self.scope = _scope_key(self.root, self.format_name, self.source, self.target)
        self.adapter = get_registry().get(self.format_name)
        if self.adapter is None:
            _fail(f"Unsupported review format: {format_name}")
        self._documents: dict[str, tuple[Path, LocalizedDocument]] = {}
        self._items: dict[tuple[str, str], ReviewItem] = {}
        self._manifest = self._read_manifest()
        self._load_items()

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema": SCHEMA_VERSION, "sessions": {}, "legacy_v1": None}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            message = f"Review manifest is unreadable; existing review data was preserved: {exc}"
            raise ReviewSessionError(message) from exc
        if not isinstance(data, dict):
            _fail("Review manifest must contain a JSON object.")
        if data.get("schema") == 1 and isinstance(data.get("reviewed"), dict):
            # Legacy flags have no content fingerprints: retain them for recovery, never approve.
            return {"schema": SCHEMA_VERSION, "sessions": {}, "legacy_v1": data}
        if data.get("schema") != SCHEMA_VERSION or not isinstance(data.get("sessions"), dict):
            _fail("Unsupported or invalid review manifest schema.")
        data.setdefault("legacy_v1", None)
        return data

    def _target_path(self, resource: Any, output_root: Path) -> Path:
        builder = getattr(self.adapter, "target_path", None)
        if callable(builder):
            return builder(resource, self.root, output_root, self.source, self.target)
        relative = resource.path.relative_to(self.root)
        if self.format_name == "arb":
            module = str(resource.attributes.get("module", ""))
            if module:
                return output_root / f"app_{module}_{self.target}.arb"
        name = relative.name.replace(self.source, self.target)
        return output_root / relative.with_name(name)

    def _source_resources(self) -> list[Any]:
        """Discover project inputs without treating Poliglota's own outputs as sources."""
        internal_roots = {self.translation_root, self.review_root}
        return [
            resource
            for resource in discover_resources(self.adapter, self.root).get(self.source, [])
            if not any(internal in resource.path.parents for internal in internal_roots)
        ]

    def _scope_records(self) -> dict[str, Any]:
        return self._manifest["sessions"].setdefault(self.scope, {})

    @staticmethod
    def _entry_id(relative: str, key: str) -> str:
        return json.dumps([relative, key], ensure_ascii=False, separators=(",", ":"))

    def _load_items(self) -> None:
        resources = self._source_resources()
        records = self._scope_records()
        for resource in resources:
            translated_path = self._target_path(resource, self.translation_root)
            if not translated_path.is_file():
                continue
            source_doc = self.adapter.read(resource.path)
            translated_doc = self.adapter.read(translated_path)
            source_entries = _translatable_entries(source_doc, self.format_name)
            translated_entries = _translatable_entries(translated_doc, self.format_name)
            relative = translated_path.relative_to(self.translation_root).as_posix()
            self._documents[relative] = (translated_path, translated_doc)
            for key, preliminary in translated_entries.items():
                source = source_entries.get(key)
                if source is None:
                    continue
                entry_id = self._entry_id(relative, key)
                record = records.get(entry_id)
                fresh = bool(
                    isinstance(record, dict)
                    and record.get("source_hash") == _digest(source)
                    and record.get("preliminary_hash") == _digest(preliminary)
                )
                previous = record.get("value") if isinstance(record, dict) else None
                legacy_reviewed = self._manifest.get("legacy_v1") or {}
                legacy_keys = set(legacy_reviewed.get("reviewed", {}).get(relative, []))
                if record is None and key in legacy_keys:
                    legacy_path = self.review_root / relative
                    if legacy_path.is_file():
                        legacy_doc = self.adapter.read(legacy_path)
                        previous = legacy_doc.entries.get(key)
                current = previous if fresh and isinstance(previous, str) else preliminary
                reviewed = bool(fresh and record.get("reviewed"))
                metadata = source_doc.metadata.get(f"@{key}", {})
                context = metadata.get("description", "") if isinstance(metadata, dict) else ""
                self._items[(relative, key)] = ReviewItem(
                    file=relative,
                    key=key,
                    source=source,
                    preliminary=preliminary,
                    value=current,
                    context=str(context),
                    reviewed=reviewed,
                    stale=bool((record and not fresh) or (record is None and key in legacy_keys)),
                    previous_review=previous
                    if ((record and not fresh) or (record is None and key in legacy_keys))
                    and isinstance(previous, str)
                    else None,
                )

        # Retain records for removed resources/keys; they are not exported or approved.

    @property
    def items(self) -> tuple[ReviewItem, ...]:
        """Return current source/translation entries in project order."""
        return tuple(self._items.values())

    @property
    def pending_count(self) -> int:
        """Count current entries that have not been marked reviewed."""
        return sum(not item.reviewed for item in self._items.values())

    def save(self, file: str, key: str, value: str, *, reviewed: bool = False) -> None:
        """Persist a draft or reviewed value atomically in the local manifest."""
        item = self._items[(file, key)]
        current_source, current_preliminary = self._current_texts(file, key)
        if current_source != item.source or current_preliminary != item.preliminary:
            _fail("Source or preliminary translation changed; reopen the review before saving.")
        issues = ArbPlaceholderProtector().validate_preservation_for_format(
            self.format_name, item.source, value
        )
        if issues:
            raise ValueError("; ".join(issues))
        entry_id = self._entry_id(file, key)
        self.review_root.mkdir(parents=True, exist_ok=True)
        manifest = self._read_manifest()
        if manifest.get("legacy_v1") is None and self._manifest.get("legacy_v1") is not None:
            manifest["legacy_v1"] = self._manifest["legacy_v1"]
        records = manifest["sessions"].setdefault(self.scope, {})
        prior = records.get(entry_id)
        baseline = self._manifest.get("sessions", {}).get(self.scope, {}).get(entry_id)
        if prior != baseline:
            _fail("This translation changed in another review window; reopen it before saving.")
        history = list(prior.get("history", [])) if isinstance(prior, dict) else []
        if isinstance(prior, dict) and prior.get("value") != value:
            history.append({"value": prior.get("value"), "reviewed": prior.get("reviewed", False)})
        records[entry_id] = {
            "file": file,
            "key": key,
            "source_hash": _digest(item.source),
            "preliminary_hash": _digest(item.preliminary),
            "value": value,
            "reviewed": bool(reviewed),
            "history": history,
        }
        self._write_manifest(manifest)
        self._manifest = manifest
        self._items[(file, key)] = ReviewItem(
            file=item.file,
            key=item.key,
            source=item.source,
            preliminary=item.preliminary,
            value=value,
            context=item.context,
            reviewed=bool(reviewed),
        )

    def _current_texts(self, file: str, key: str) -> tuple[str, str]:
        """Read current disk content so a long-open session cannot approve stale text."""
        for resource in self._source_resources():
            target_path = self._target_path(resource, self.translation_root)
            if (
                target_path.is_file()
                and target_path.relative_to(self.translation_root).as_posix() == file
            ):
                source_doc = self.adapter.read(resource.path)
                target_doc = self.adapter.read(target_path)
                source_value = _translatable_entries(source_doc, self.format_name).get(key)
                target_value = _translatable_entries(target_doc, self.format_name).get(key)
                if source_value is not None and target_value is not None:
                    return source_value, target_value
        _fail(f"Localization entry no longer exists: {file}:{key}")

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self.review_root.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix="review-", suffix=".tmp", dir=self.review_root)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.manifest_path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            message = f"Could not safely save review manifest: {exc}"
            raise ReviewSessionError(message) from exc

    def _source_target_pairs(self) -> list[tuple[Path, Path]]:
        resources = self._source_resources()
        pairs = []
        for resource in resources:
            source_path = resource.path
            target_path = self._target_path(resource, self.translation_root)
            if source_path.is_symlink():
                _fail(f"Symlink source localization files are not safe to export: {source_path}")
            if not target_path.is_file():
                _fail(
                    "Translated localization file is missing for source resource: "
                    f"{source_path.relative_to(self.root).as_posix()}"
                )
            pairs.append((source_path, target_path))
        expected_targets = {target for _, target in pairs}
        translated_root = self.translation_root
        target_key = normalize_locale_code(self.target) or self.target
        translated_resources = discover_resources(self.adapter, translated_root).get(target_key, [])
        for resource in translated_resources:
            if resource.path not in expected_targets:
                _fail(
                    "Unexpected translated localization file would be omitted from export: "
                    f"{resource.path.relative_to(translated_root).as_posix()}"
                )
        return pairs

    def _materialize(self, source_path: Path, target_path: Path, output_path: Path) -> None:
        source_doc = self.adapter.read(source_path)
        target_doc = self.adapter.read(target_path)
        source_entries = _translatable_entries(source_doc, self.format_name)
        target_entries = _translatable_entries(target_doc, self.format_name)
        relative = target_path.relative_to(self.translation_root).as_posix()
        records = self._scope_records()
        expected = set(source_entries)
        actual = set(target_entries)
        if expected != actual:
            _fail(f"Localization keys differ for {relative}; regenerate/synchronize before export.")
        entries = dict(target_doc.entries)
        for key in expected:
            source_text = source_entries[key]
            preliminary = target_entries[key]
            record = records.get(self._entry_id(relative, key))
            if isinstance(record, dict):
                fresh = record.get("source_hash") == _digest(source_text) and record.get(
                    "preliminary_hash"
                ) == _digest(preliminary)
                if record.get("reviewed") and not fresh:
                    _fail(f"Stale review requires re-review: {relative}:{key}")
                if fresh:
                    entries[key] = record["value"]
            issues = ArbPlaceholderProtector().validate_preservation_for_format(
                self.format_name, source_text, str(entries[key])
            )
            if issues:
                _fail(f"{relative}:{key}: {'; '.join(issues)}")

        # JSON/YAML adapters flatten scalars to strings. Patch the original parsed
        # tree instead of rebuilding it, preserving numeric, boolean and list types.
        if self.format_name in {"json", "yaml", "yml"}:
            raw = target_doc.metadata.get(
                "@@json_original" if self.format_name == "json" else "@@yaml_original"
            )
            if not isinstance(raw, str):
                _fail(f"Original document metadata unavailable for {relative}.")
            structure = json.loads(raw) if self.format_name == "json" else yaml.safe_load(raw)
            for key in expected:
                replacement = str(entries[key])
                original_leaf = _flatten_string_values(structure).get(key)
                if original_leaf is None:
                    _fail(f"Cannot safely map translated field {relative}:{key}.")
                if replacement != original_leaf:
                    _set_path(structure, key, replacement)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if self.format_name == "json":
                output_path.write_text(
                    json.dumps(structure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            else:
                output_path.write_text(
                    yaml.safe_dump(structure, allow_unicode=True, sort_keys=False), encoding="utf-8"
                )
            # Parse back and check shape/types against source target except string values.
            parsed = (
                json.loads(output_path.read_text(encoding="utf-8"))
                if self.format_name == "json"
                else yaml.safe_load(output_path.read_text(encoding="utf-8"))
            )
            if _shape(parsed) != _shape(structure):
                _fail(f"Export changed document structure for {relative}.")
            return

        output_doc = LocalizedDocument(Locale(self.target), entries, dict(target_doc.metadata))
        if self.format_name == "arb":
            output_doc.metadata["@@locale"] = self.target
        self.adapter.write(output_doc, output_path)
        validated = self.adapter.read(output_path)
        if set(validated.entries) != set(target_doc.entries):
            _fail(f"Export changed resource keys for {relative}.")
        if self.format_name == "xml" and _xml_structure(source_path) != _xml_structure(output_path):
            _fail(f"Export changed Android/XML structure for {relative}.")

    def export(self, destination: Path) -> Path:
        """Validate into a same-volume staging directory, then publish without overwrite."""
        self._manifest = self._read_manifest()
        destination = Path(destination).absolute()
        parent = destination.parent
        if destination.exists():
            message = f"Export destination already exists: {destination}"
            raise FileExistsError(message)
        if not parent.is_dir():
            _fail(f"Export parent directory does not exist: {parent}")
        pairs = self._source_target_pairs()
        if not pairs:
            _fail("No translated localization files are available to export.")
        stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=parent))
        published = False
        try:
            for source_path, target_path in pairs:
                if target_path.is_symlink() or source_path.is_symlink():
                    _fail("Symlink localization files are not safe to export.")
                relative = target_path.relative_to(self.translation_root)
                self._materialize(source_path, target_path, stage / relative)
            # Ensure no file vanished and parse every staged output before publishing.
            staged = [path for path in stage.rglob("*") if path.is_file()]
            if len(staged) != len(pairs):
                _fail("Staged export inventory did not match the source inventory.")
            for path in staged:
                self.adapter.read(path)
            destination.mkdir()
            published = True
            marker = destination / ".poliglota-export-incomplete"
            marker.write_text("Incomplete export; do not use.\n", encoding="utf-8")
            for path in staged:
                relative = path.relative_to(stage)
                output = destination / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
            marker.unlink()
            return destination
        except Exception:
            if published:
                # The destination was created exclusively by this operation. Remove
                # only its marked/incomplete tree; never touch a pre-existing path.
                marker = destination / ".poliglota-export-incomplete"
                if marker.exists():
                    shutil.rmtree(destination)
                else:
                    # marker creation itself may have failed; rmdir is safe because
                    # it only removes the directory while it remains empty.
                    with suppress(OSError):
                        destination.rmdir()
            raise
        else:
            return destination
        finally:
            shutil.rmtree(stage, ignore_errors=True)


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return ("dict", tuple((key, _shape(child)) for key, child in value.items()))
    if isinstance(value, list):
        return ("list", tuple(_shape(child) for child in value))
    return type(value).__name__


def _xml_structure(path: Path) -> Any:
    root = ElementTree.parse(path).getroot()

    def visit(element: ElementTree.Element) -> Any:
        return (
            element.tag,
            tuple(sorted(element.attrib.items())),
            tuple(visit(child) for child in element),
        )

    return visit(root)
