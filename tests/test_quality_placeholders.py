"""Tests for placeholder protection and restoration."""

from __future__ import annotations

from poliglota.quality.placeholders import ArbPlaceholderProtector, PlaceholderProtectorRegistry


def test_arb_protector_detect_single_placeholder() -> None:
    """Protector detects a single ARB placeholder."""
    protector = ArbPlaceholderProtector()

    placeholders = protector.detect("Hello {name}")

    assert placeholders == {"name"}


def test_arb_protector_detect_multiple_placeholders() -> None:
    """Protector detects multiple ARB placeholders."""
    protector = ArbPlaceholderProtector()

    placeholders = protector.detect("Hello {first} {last}, you have {count} items")

    assert placeholders == {"first", "last", "count"}


def test_arb_protector_detect_duplicate_placeholders() -> None:
    """Protector returns unique placeholder names."""
    protector = ArbPlaceholderProtector()

    placeholders = protector.detect("{name} says hello to {name}")

    assert placeholders == {"name"}


def test_arb_protector_detect_no_placeholders() -> None:
    """Protector returns empty set when no placeholders."""
    protector = ArbPlaceholderProtector()

    placeholders = protector.detect("Hello world")

    assert placeholders == set()


def test_arb_protector_detect_empty_string() -> None:
    """Protector handles empty strings."""
    protector = ArbPlaceholderProtector()

    placeholders = protector.detect("")

    assert placeholders == set()


def test_arb_protector_mask_single_placeholder() -> None:
    """Protector masks a single placeholder with a unique token."""
    protector = ArbPlaceholderProtector()

    masked, placeholders_map = protector.mask("Hello {name}")

    assert "{name}" in placeholders_map.values()
    assert "{name}" not in masked
    assert any(token in masked for token in placeholders_map)


def test_arb_protector_mask_multiple_placeholders() -> None:
    """Protector masks multiple placeholders independently."""
    protector = ArbPlaceholderProtector()

    masked, placeholders_map = protector.mask("Hello {first} {last}")

    assert len(placeholders_map) == 2
    assert set(placeholders_map.values()) == {"{first}", "{last}"}
    assert "{first}" not in masked
    assert "{last}" not in masked


def test_arb_protector_mask_empty_string() -> None:
    """Protector handles masking empty strings."""
    protector = ArbPlaceholderProtector()

    masked, placeholders_map = protector.mask("")

    assert masked == ""
    assert placeholders_map == {}


def test_arb_protector_mask_no_placeholders() -> None:
    """Protector returns original text and empty map if no placeholders."""
    protector = ArbPlaceholderProtector()

    masked, placeholders_map = protector.mask("Hello world")

    assert masked == "Hello world"
    assert placeholders_map == {}


def test_arb_protector_restore_single_placeholder() -> None:
    """Protector restores a masked placeholder."""
    protector = ArbPlaceholderProtector()

    original = "Hello {name}"
    masked, placeholders_map = protector.mask(original)
    restored = protector.restore(masked, placeholders_map)

    assert restored == original


def test_arb_protector_restore_multiple_placeholders() -> None:
    """Protector restores multiple masked placeholders."""
    protector = ArbPlaceholderProtector()

    original = "Hello {first} {last}, you are {age} years old"
    masked, placeholders_map = protector.mask(original)
    restored = protector.restore(masked, placeholders_map)

    assert restored == original


def test_arb_protector_restore_empty_map() -> None:
    """Protector handles restoration with empty map."""
    protector = ArbPlaceholderProtector()

    text = "Hello world"
    restored = protector.restore(text, {})

    assert restored == text


def test_arb_protector_roundtrip_preserves_content() -> None:
    """Protector mask-restore roundtrip preserves original content."""
    protector = ArbPlaceholderProtector()
    texts = [
        "Hello {name}",
        "You have {count} messages",
        "{greeting}, {name}!",
        "No placeholders here",
        "",
    ]

    for text in texts:
        masked, placeholders_map = protector.mask(text)
        restored = protector.restore(masked, placeholders_map)
        assert restored == text, f"Roundtrip failed for: {text}"


def test_arb_protector_validate_mask_success() -> None:
    """Protector validates successful mask."""
    protector = ArbPlaceholderProtector()

    original = "Hello {name} {last}"
    masked, placeholders_map = protector.mask(original)

    issues = protector.validate_mask(original, masked, placeholders_map)

    assert issues == []


def test_arb_protector_validate_mask_missing_placeholders() -> None:
    """Protector detects missing placeholders in mask."""
    protector = ArbPlaceholderProtector()

    original = "Hello {name} {last}"
    # Simulate incomplete masking (missing {last})
    incomplete_map = {"__PH_token1": "{name}"}

    issues = protector.validate_mask(original, "Hello __PH_token1 {last}", incomplete_map)

    assert any("not captured" in issue for issue in issues)


def test_arb_protector_validate_mask_remaining_placeholders() -> None:
    """Protector detects placeholders still in masked text."""
    protector = ArbPlaceholderProtector()

    original = "Hello {name}"
    masked = "Hello {name}"  # Not actually masked
    placeholders_map = {}

    issues = protector.validate_mask(original, masked, placeholders_map)

    assert any("still present" in issue for issue in issues)


def test_arb_protector_validate_restore_success() -> None:
    """Protector validates successful restore."""
    protector = ArbPlaceholderProtector()

    original = "Hello {name}"
    masked, placeholders_map = protector.mask(original)
    restored = protector.restore(masked, placeholders_map)

    issues = protector.validate_restore(masked, restored, original)

    assert issues == []


def test_arb_protector_validate_restore_mismatch() -> None:
    """Protector detects restored text not matching original."""
    protector = ArbPlaceholderProtector()

    restored = "Hello {wrong}"
    original = "Hello {name}"

    issues = protector.validate_restore("masked", restored, original)

    assert any("does not match" in issue for issue in issues)


def test_arb_protector_validate_restore_remaining_tokens() -> None:
    """Protector detects placeholder tokens in restored text."""
    protector = ArbPlaceholderProtector()

    original = "Hello world"
    restored = "Hello __PH_abc123"

    issues = protector.validate_restore("masked", restored, original)

    assert any("tokens still present" in issue for issue in issues)


def test_placeholder_protector_registry_get_arb() -> None:
    """Registry retrieves ARB protector."""
    registry = PlaceholderProtectorRegistry()

    protector = registry.get("arb")

    assert protector is not None
    assert isinstance(protector, ArbPlaceholderProtector)


def test_placeholder_protector_registry_get_unknown() -> None:
    """Registry returns None for unknown format."""
    registry = PlaceholderProtectorRegistry()

    protector = registry.get("unknown_format")

    assert protector is None


def test_placeholder_protector_registry_register_custom() -> None:
    """Registry can register custom protectors."""
    registry = PlaceholderProtectorRegistry()
    custom_prefix = "__CUSTOM_"
    custom_protector = ArbPlaceholderProtector(token_prefix=custom_prefix)

    registry.register("custom", custom_protector)
    retrieved = registry.get("custom")

    assert retrieved is custom_protector


def test_arb_protector_complex_placeholders() -> None:
    """Protector handles complex placeholder patterns (valid ARB identifiers)."""
    protector = ArbPlaceholderProtector()

    # ARB allows: letters, digits, underscores; must start with letter/underscore
    text = "Hello {_name1} and {User_2} and {greeting_message}"
    placeholders = protector.detect(text)

    assert placeholders == {"_name1", "User_2", "greeting_message"}

    masked, placeholders_map = protector.mask(text)
    restored = protector.restore(masked, placeholders_map)

    assert restored == text


def test_arb_protector_invalid_placeholder_names_ignored() -> None:
    """Protector ignores invalid ARB placeholder names."""
    protector = ArbPlaceholderProtector()

    # These should NOT match ARB placeholder syntax
    text = "Price is {$100} and {-value} and {2name}"

    placeholders = protector.detect(text)

    # Should be empty (invalid identifiers)
    assert placeholders == set()
