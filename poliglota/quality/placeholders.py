"""Placeholder protection for translation integrity.

Identifies, masks, and restores format-specific placeholders (e.g., {placeholder}
in ARB) to prevent translation engines from corrupting variable references.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class ArbPlaceholderProtector:
    """Protects and restores ARB-style placeholders: {placeholder}."""

    # ARB placeholder syntax: {identifier}
    _PLACEHOLDER_PATTERN = r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
    # Android/printf formatting tokens such as %s, %d and %1$s.
    _PRINTF_PLACEHOLDER_PATTERN = (
        # A space is technically a printf flag, but accepting it here makes
        # ordinary prose such as "% of the budget" look like the token "% o".
        # Android's resource placeholders use compact specifiers, so whitespace
        # is intentionally excluded to avoid false positives in localized text.
        r"%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diuoxXfFeEgGaAcspn]"
    )

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
            while True:
                nonce = uuid.uuid4().hex
                token = f"{self.token_prefix}{nonce}"
                marker_pattern = rf"_*PH_{re.escape(nonce)}"
                if (
                    token not in placeholders_map
                    and token not in text
                    and re.search(marker_pattern, text, flags=re.IGNORECASE) is None
                ):
                    break
            placeholders_map[token] = full_placeholder
            return token

        combined_pattern = rf"{self._PLACEHOLDER_PATTERN}|{self._PRINTF_PLACEHOLDER_PATTERN}"
        masked_text = re.sub(combined_pattern, replace_placeholder, text)
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
            # Multilingual tokenizers may remove leading underscores while
            # preserving the per-placeholder nonce. Recover that marker too.
            nonce = token.rsplit("_", 1)[-1]
            damaged_marker = re.compile(rf"(?i)_*PH_{re.escape(nonce)}")
            result = damaged_marker.sub(token, result)
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
        remaining_printf = re.findall(self._PRINTF_PLACEHOLDER_PATTERN, masked)
        if remaining_printf:
            issues.append(f"Printf placeholders still present in masked text: {remaining_printf}")

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

    def validate_preservation(
        self,
        original: str,
        translated: str,
        placeholders_map: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Check placeholder multiplicity while allowing translated prose to differ."""
        original_counts: dict[str, int] = {}
        translated_counts: dict[str, int] = {}
        original_placeholders = re.findall(self._PRINTF_PLACEHOLDER_PATTERN, original)
        translated_placeholders = re.findall(self._PRINTF_PLACEHOLDER_PATTERN, translated)
        original_placeholders.extend(
            "{" + value + "}" for value in re.findall(self._PLACEHOLDER_PATTERN, original)
        )
        translated_placeholders.extend(
            "{" + value + "}" for value in re.findall(self._PLACEHOLDER_PATTERN, translated)
        )
        for placeholder in original_placeholders:
            original_counts[placeholder] = original_counts.get(placeholder, 0) + 1
        for placeholder in translated_placeholders:
            translated_counts[placeholder] = translated_counts.get(placeholder, 0) + 1

        issues = [
            f"Placeholder {placeholder} count changed from {count} to "
            f"{translated_counts.get(placeholder, 0)}"
            for placeholder, count in original_counts.items()
            if translated_counts.get(placeholder, 0) != count
        ]
        unexpected = translated_counts.keys() - original_counts.keys()
        if unexpected:
            issues.append(f"Unexpected placeholders in translated text: {sorted(unexpected)}")
        if any(token in translated for token in (placeholders_map or {})):
            issues.append("Placeholder tokens still present in translated text")
        for token in placeholders_map or {}:
            nonce = token.rsplit("_", 1)[-1]
            damaged_marker = re.compile(rf"(?i)_*PH_{re.escape(nonce)}")
            if damaged_marker.search(translated):
                issues.append(f"Placeholder token remains in translated text: {token}")
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
