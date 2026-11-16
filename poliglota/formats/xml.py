"""XML format adapter implementation for Poliglota."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any

from defusedxml.ElementTree import fromstring as defused_fromstring

if TYPE_CHECKING:
    from pathlib import Path
    from xml.etree.ElementTree import Element

    from poliglota.core import LocalizedDocument, LocalizedResource

ElementLike = Any


class XMLFormatAdapter:
    """XML implementation of :class:`poliglota.core.format.FormatAdapter`."""

    name = "xml"

    def discover(self, root: Path) -> list[LocalizedResource]:
        """Discover XML files under ``root`` as generic localized resources.

        Searches for files matching patterns:
        - *.xml
        - {locale_code}.xml
        - {name}_{locale_code}.xml

        Locale is inferred from filename or directory structure.
        """
        from poliglota.core.format import LocalizedResource
        from poliglota.core.locale import Locale

        resources: list[LocalizedResource] = []

        if not root.exists():
            return resources

        # Recurse all directories for *.xml files
        for xml_file in root.rglob("*.xml"):
            locale = self._infer_locale_from_path(xml_file)
            if locale:
                resources.append(
                    LocalizedResource(
                        path=xml_file,
                        locale=Locale(locale),
                        format=self.name,
                        attributes={
                            "directory": str(xml_file.parent.relative_to(root)),
                            "android_values": self._android_values_directory(xml_file) or "",
                        },
                    )
                )

        return resources

    def read(self, path: Path) -> LocalizedDocument:
        """Parse an XML file into translatable entries and preserved metadata.

        Extracts text nodes from XML elements and stores structural info.
        Metadata preserves the original XML tree for write-back.
        """
        from poliglota.core.format import LocalizedDocument
        from poliglota.core.locale import Locale

        xml_content = path.read_text(encoding="utf-8")

        try:
            root = defused_fromstring(xml_content)
        except ET.ParseError as exc:
            msg = f"Failed to parse XML file {path}: {exc}"
            raise ValueError(msg) from exc

        locale_code = self._infer_locale_from_path(path)

        # Extract translatable text from all elements
        if self._android_values_directory(path):
            entries = self._extract_android_string_entries(root)
        else:
            entries = self._extract_text_entries(root)

        # Preserve original XML tree and structure for write-back
        metadata = {
            "@@xml_original": xml_content,
            "@@xml_root_tag": root.tag,
            "@@xml_root_attrib": dict(root.attrib),
        }

        return LocalizedDocument(
            locale=Locale(locale_code) if locale_code else None,
            entries=entries,
            metadata=metadata,
        )

    def write(self, document: LocalizedDocument, path: Path) -> None:
        """Write ``document`` back as XML, reconstructing the tree structure.

        Uses original XML structure from metadata if available.
        Updates text nodes with translated values while preserving attributes.
        """
        # Get original XML structure from metadata
        original_xml = document.metadata.get("@@xml_original")

        if original_xml:
            # Parse original and update text nodes
            root = defused_fromstring(original_xml)
            if self._android_values_directory(path) or self._android_values_directory_from_xml(
                root
            ):
                self._update_android_string_entries(root, dict(document.entries))
            else:
                self._update_text_entries(root, dict(document.entries))
        else:
            # Fallback: create minimal XML structure
            root = ET.Element("root")
            for key, value in document.entries.items():
                elem = ET.SubElement(root, "entry")
                elem.set("key", key)
                elem.text = str(value)

        path.parent.mkdir(parents=True, exist_ok=True)

        # Write XML with pretty printing
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def target_path(
        resource: LocalizedResource,
        root: Path,
        output_dir: Path,
        source_locale: str,
        target_locale: str,
    ) -> Path:
        """Build an output path, translating Android values qualifiers when present."""
        relative = resource.path.relative_to(root)
        values_dir = resource.attributes.get("android_values")
        if values_dir:
            parts = list(relative.parts)
            index = len(parts) - 2
            target = target_locale.replace("-", "_").split("_")
            qualifier = target[0].lower()
            if len(target) > 1:
                qualifier += f"-r{target[1].upper()}"
            parts[index] = f"values-{qualifier}"
            return output_dir.joinpath(*parts)
        output = output_dir / relative
        return output.with_name(output.name.replace(source_locale, target_locale))

    @staticmethod
    def _android_values_directory(path: Path) -> str | None:
        """Return an Android ``values`` directory name for standard resource paths."""
        candidate = path.parent.name
        if re.fullmatch(r"values(?:-[a-z]{2,3}(?:-r[A-Za-z]{2,3})?)?", candidate):
            return candidate
        return None

    @staticmethod
    def _android_values_directory_from_xml(root: ET.Element) -> bool:
        """Identify Android resource XML by its standard root and named string nodes."""
        return root.tag == "resources" and any(
            child.tag == "string" and "name" in child.attrib for child in root
        )

    @staticmethod
    def _extract_android_string_entries(root: ET.Element) -> dict[str, str]:
        """Extract only translatable Android string resources, keyed by resource name."""
        return {
            child.attrib["name"]: child.text or ""
            for child in root
            if child.tag == "string"
            and child.attrib.get("name")
            and child.attrib.get("translatable", "true").lower() != "false"
            and (child.text or "").strip()
        }

    @staticmethod
    def _update_android_string_entries(root: ET.Element, entries: dict[str, Any]) -> None:
        """Update only named Android string resources, preserving other XML nodes."""
        for child in root:
            name = child.attrib.get("name")
            if (
                child.tag == "string"
                and name in entries
                and child.attrib.get("translatable", "true").lower() != "false"
            ):
                child.text = str(entries[name])

    @staticmethod
    def _extract_text_entries(element: ET.Element, prefix: str = "") -> dict[str, Any]:
        """Extract translatable text from XML elements recursively.

        Returns a dict mapping element paths to their text content.
        Example: <strings><app><title>Hello</title></app></strings>
                -> {"app.title": "Hello"}
        """
        result = {}

        # Get the tag name, handling namespace prefixes
        tag = element.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]  # Remove namespace

        current_path = f"{prefix}{tag}" if not prefix else f"{prefix}.{tag}"

        # Extract text from this element if present and non-empty
        if element.text and element.text.strip():
            result[current_path] = element.text.strip()

        # Recursively process child elements
        for child in element:
            result.update(XMLFormatAdapter._extract_text_entries(child, current_path))

        return result

    @staticmethod
    def _update_text_entries(element: Element, entries: dict[str, Any], prefix: str = "") -> None:
        """Update XML element text nodes with translated values.

        Recursively traverses the tree and updates text content based on path keys.
        """
        # Get the tag name, handling namespace prefixes
        tag = element.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]  # Remove namespace

        current_path = f"{prefix}{tag}" if not prefix else f"{prefix}.{tag}"

        # Update text if entry exists for this path
        if current_path in entries:
            element.text = str(entries[current_path])

        # Recursively process child elements
        for child in element:
            XMLFormatAdapter._update_text_entries(child, entries, current_path)

    @staticmethod
    def _document_structure(element: ET.Element) -> dict[str, Any]:
        """Capture structural information about the XML document."""
        tag = element.tag.split("}", 1)[1] if "}" in element.tag else element.tag
        return {
            "root_tag": tag,
            "depth": XMLFormatAdapter._max_depth(element),
        }

    @staticmethod
    def _max_depth(element: ET.Element, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of the XML tree."""
        if not list(element):
            return current_depth

        return max(XMLFormatAdapter._max_depth(child, current_depth + 1) for child in element)

    @staticmethod
    def _infer_locale_from_path(path: Path) -> str | None:
        """Infer locale code from file path.

        Patterns supported:
        - {locale_code}.xml (e.g., en.xml, pt_BR.xml)
        - {name}_{locale_code}.xml (e.g., strings_en.xml, app_pt_BR.xml)
        - Filename only if matches locale pattern (e.g., en, pt-BR, pt_BR)

        Returns None if no valid locale pattern found.
        """
        values_dir = XMLFormatAdapter._android_values_directory(path)
        if values_dir and values_dir != "values":
            match = re.fullmatch(r"values-([a-z]{2,3})(?:-r([A-Za-z]{2,3}))?", values_dir)
            if match:
                language, region = match.groups()
                return f"{language}_{region}" if region else language
        stem = path.stem

        # Pattern: {name}_{locale_code}.xml
        # Match: word_word, word_word_word (e.g., strings_en, app_pt_BR)
        match = re.match(r"^(.+?)_([a-z]{2}(?:[_\-][a-zA-Z]{2})?)$", stem)
        if match:
            locale = match.group(2)
            # Normalize: replace - with _ for consistency
            return locale.replace("-", "_").lower()

        # Pattern: {locale_code}.xml (e.g., en.xml, pt_BR.xml, pt-BR.xml)
        if re.match(r"^[a-z]{2}(?:[_\-][a-zA-Z]{2})?$", stem):
            return stem.replace("-", "_").lower()

        return None
