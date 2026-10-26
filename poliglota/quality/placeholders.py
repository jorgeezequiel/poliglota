"""Placeholder protection for translation integrity.

Identifies, masks, and restores format-specific placeholders (e.g., {placeholder}
in ARB) to prevent translation engines from corrupting variable references.
"""

from __future__ import annotations

import re
import uuid


class ArbPlaceholderProtector:
    """Protects and restores ARB-style placeholders: {placeholder}."""

    # ARB placeholder syntax: {identifier}
    _PLACEHOLDER_PATTERN = r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}"

    def __init__(self, token_prefix: str | None = None) -> None:
        """Initialize the protector.

        Args:
            token_prefix: Prefix for placeholder tokens (should be unique to avoid collisions).

        """
        # This placeholder token is a non-secret internal marker and is intentionally
        # safe to keep in plain text because it is never used as an auth secret.
        self.token_prefix = token_prefix or "__PH_"

    def detect(self, text: str) -> set[str]:
        """Return all ARB placeholders found in text.

        Returns:
            Set of placeholder names (e.g., {"name", "age"} for "{name} is {age}").

        """
        matches = re.findall(self._PLACEHOLDER_PATTERN, text)
        return set(matches)

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        """Replace ARB placeholders with unique tokens.

        Args:
            text: Text containing placeholders.

        Returns:
            (masked_text, placeholders_map) where placeholders_map is
            {token: original_placeholder} (e.g., {"__PH_uuid1": "{name}"}).

        """
        placeholders_map: dict[str, str] = {}

        def replace_placeholder(match: re.Match[str]) -> str:
            full_placeholder = match.group(0)  # e.g., "{name}"
            token = f"{self.token_prefix}{uuid.uuid4().hex[:8]}"
            placeholders_map[token] = full_placeholder
            return token

        masked_text = re.sub(self._PLACEHOLDER_PATTERN, replace_placeholder, text)
        return masked_text, placeholders_map

    def restore(self, text: str, placeholders_map: dict[str, str]) -> str:
        """Restore placeholders from tokens.

        Args:
            text: Text with placeholder tokens.
            placeholders_map: Map from tokens to original placeholders.

        Returns:
            Text with placeholders restored.

        """
        result = text
        for token, placeholder in placeholders_map.items():
            # Escape token for regex (tokens have uuid format, unlikely to have special chars)
            result = result.replace(token, placeholder)
        return result

    def validate_mask(
        self,
        original: str,
        masked: str,
        placeholders_map: dict[str, str],
    ) -> list[str]:
        """Validate that masking was correct.

        Checks:
        - All original placeholders are in the map.
        - No original placeholders remain in masked text.

        Args:
            original: Original text before masking.
            masked: Masked text.
            placeholders_map: Map from tokens to placeholders.

        Returns:
            List of validation issues, empty if all checks pass.

        """
        issues: list[str] = []
        original_placeholders = self.detect(original)
        mapped_placeholders = {ph.strip("{}") for ph in placeholders_map.values()}

        missing_from_map = original_placeholders - mapped_placeholders
        if missing_from_map:
            issues.append(f"Placeholders not captured in mask: {sorted(missing_from_map)}")

        remaining = self.detect(masked)
        if remaining:
            issues.append(f"Placeholders still present in masked text: {sorted(remaining)}")

        return issues

    def validate_restore(
        self,
        _masked: str,
        restored: str,
        original: str,
    ) -> list[str]:
        """Validate that restoration was correct.

        Checks:
        - Restored text matches original exactly.
        - No placeholder tokens remain.

        Args:
            masked: Masked text before restoration.
            restored: Restored text.
            original: Original text (ground truth).

        Returns:
            List of validation issues, empty if all checks pass.

        """
        issues: list[str] = []

        if restored != original:
            issues.append(
                f"Restored text does not match original. "
                f"Diff: original={len(original)} chars, restored={len(restored)} chars"
            )

        if self.token_prefix in restored:
            issues.append("Placeholder tokens still present in restored text")

        return issues


class PlaceholderProtectorRegistry:
    """Registry for placeholder protectors by format."""

    def __init__(self) -> None:
        """Initialize with built-in protectors."""
        self._protectors: dict[str, ArbPlaceholderProtector] = {
            "arb": ArbPlaceholderProtector(),
        }

    def get(self, format_name: str) -> ArbPlaceholderProtector | None:
        """Get protector for a format, or None if not registered."""
        return self._protectors.get(format_name)

    def register(self, format_name: str, protector: ArbPlaceholderProtector) -> None:
        """Register a custom protector for a format."""
        self._protectors[format_name] = protector
