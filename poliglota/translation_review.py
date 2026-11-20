"""Local, format-preserving review sessions for machine translations."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poliglota.core.format import LocalizedDocument
from poliglota.core.locale import Locale
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry
from poliglota.language_detection import normalize_locale_code
from poliglota.quality.placeholders import ArbPlaceholderProtector

MANIFEST_NAME = "review_manifest.json"


class ReviewSessionError(ValueError):
    """An expected problem opening, saving, or exporting a review session."""


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """One translatable string and its current review state."""

    file: str
    key: str
    source: str
    preliminary: str
    value: str
    context: str
    reviewed: bool


class TranslationReviewSession:
    """Load, persist, validate and export a local translation review."""

    def __init__(self, root: Path, format_name: str, source: str, target: str) -> None:
        """Initialize a review session for the selected project and locale pair."""
        self.root = Path(root).resolve()
        self.format_name = format_name
        self.source = normalize_locale_code(source) or source
        self.target = normalize_locale_code(target) or target
        self.translation_root = self.root / ".poliglota_translated"
        self.review_root = self.root / ".poliglota_reviewed"
        self.manifest_path = self.review_root / MANIFEST_NAME
        self.adapter = get_registry().get(format_name)
        self._documents: dict[str, tuple[Path, LocalizedDocument]] = {}
        self._items: dict[tuple[str, str], ReviewItem] = {}
        self._manifest = self._read_manifest()
        self._load_items()

    def _read_manifest(self) -> dict[str, Any]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema": 1, "reviewed": {}}
        if data.get("schema") != 1 or not isinstance(data.get("reviewed"), dict):
            return {"schema": 1, "reviewed": {}}
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
        return output_root / relative

    def _load_items(self) -> None:
        resources = discover_resources(self.adapter, self.root).get(self.source, [])
        for resource in resources:
            translated_path = self._target_path(resource, self.translation_root)
            if not translated_path.is_file():
                continue
            source_doc = self.adapter.read(resource.path)
            translated_doc = self.adapter.read(translated_path)
            relative = translated_path.relative_to(self.translation_root).as_posix()
            reviewed_path = self.review_root / relative
            active_doc = (
                self.adapter.read(reviewed_path) if reviewed_path.is_file() else translated_doc
            )
            self._documents[relative] = (translated_path, active_doc)
            reviewed_keys = set(self._manifest["reviewed"].get(relative, []))
            for key, translated in translated_doc.entries.items():
                source = source_doc.entries.get(key)
                if not isinstance(source, str) or not isinstance(translated, str):
                    continue
                value = active_doc.entries.get(key, translated)
                if not isinstance(value, str):
                    value = translated
                metadata = source_doc.metadata.get(f"@{key}", {})
                context = metadata.get("description", "") if isinstance(metadata, dict) else ""
                self._items[(relative, key)] = ReviewItem(
                    file=relative,
                    key=key,
                    source=source,
                    preliminary=translated,
                    value=value,
                    context=str(context),
                    reviewed=key in reviewed_keys,
                )

    @property
    def items(self) -> tuple[ReviewItem, ...]:
        """Return the translation entries in project file order."""
        return tuple(self._items.values())

    @property
    def pending_count(self) -> int:
        """Return the number of entries not marked as reviewed."""
        return sum(not item.reviewed for item in self._items.values())

    def save(self, file: str, key: str, value: str, *, reviewed: bool = False) -> None:
        """Persist an edit to a separate output tree after structural checks."""
        item = self._items[(file, key)]
        issues = ArbPlaceholderProtector().validate_preservation(item.source, value)
        if issues:
            raise ValueError("; ".join(issues))
        translated_path, document = self._documents[file]
        entries = dict(document.entries)
        entries[key] = value
        metadata = dict(document.metadata)
        if self.format_name == "arb":
            metadata["@@locale"] = self.target
        updated = LocalizedDocument(Locale(self.target), entries, metadata)
        destination = self.review_root / file
        self.adapter.write(updated, destination)
        self._documents[file] = (translated_path, updated)
        self._items[(file, key)] = ReviewItem(
            file=item.file,
            key=item.key,
            source=item.source,
            preliminary=item.preliminary,
            value=value,
            context=item.context,
            reviewed=reviewed,
        )
        reviewed_keys = set(self._manifest["reviewed"].get(file, []))
        if reviewed:
            reviewed_keys.add(key)
        else:
            reviewed_keys.discard(key)
        self._manifest["reviewed"][file] = sorted(reviewed_keys)
        self._write_manifest()

    def _write_manifest(self) -> None:
        self.review_root.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.manifest_path)

    def export(self, destination: Path) -> Path:
        """Copy generated localization files and overlay saved review edits."""
        destination = Path(destination).resolve()
        if destination.exists():
            msg = f"Export destination already exists: {destination}"
            raise FileExistsError(msg)
        files = [
            path
            for path in self.translation_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".arb", ".json", ".yaml", ".yml", ".xml"}
        ]
        if not files:
            msg = "No reviewed localization files are available to export."
            raise ReviewSessionError(msg)
        for source in files:
            relative = source.relative_to(self.translation_root)
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            reviewed_file = self.review_root / relative
            shutil.copy2(reviewed_file if reviewed_file.is_file() else source, output)
        return destination
