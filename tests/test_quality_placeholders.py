"""Tests for placeholder protection and restoration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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


def test_arb_protector_restores_marker_after_tokenizer_drops_prefix_underscores() -> None:
    protector = ArbPlaceholderProtector()
    _, placeholders_map = protector.mask("Hello {name}")
    token = next(iter(placeholders_map))
    damaged = "Hola, " + token.lstrip("_")

    assert protector.restore(damaged, placeholders_map) == "Hola, {name}"


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


def test_android_printf_placeholders_are_masked_and_preserved() -> None:
    protector = ArbPlaceholderProtector()
    source = "Version %1$s; count %d; %% literal; user {user_id}."
    masked, placeholders = protector.mask(source)
    assert "%1$s" not in masked
    assert "%d" not in masked
    assert "{user_id}" not in masked
    translated = masked.replace("Version", "Versión").replace("count", "cantidad")
    restored = protector.restore(translated, placeholders)
    assert restored == "Versión %1$s; cantidad %d; %% literal; user {user_id}."
    assert protector.validate_preservation(source, restored, placeholders) == []


def test_printf_placeholder_removal_or_duplication_is_rejected() -> None:
    protector = ArbPlaceholderProtector()
    source = "Value %1$s and %d"
    assert protector.validate_preservation(source, "Valor %1$s y texto")
    assert protector.validate_preservation(source, "Valor %1$s %1$s y %d")


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


def test_arb_protector_validates_placeholders_without_comparing_translated_prose() -> None:
    protector = ArbPlaceholderProtector()

    assert protector.validate_preservation("Hello {name} {count}", "Hola {name} {count}") == []
    assert protector.validate_preservation("Hello {name} {name}", "Hola {name}")


def test_arb_protector_preserves_repeated_and_unicode_placeholders() -> None:
    protector = ArbPlaceholderProtector()
    original = "Olá, {user_name2}! Olá novamente, {user_name2}: {item_7}."
    masked, placeholders_map = protector.mask(original)
    translated = masked.replace("Olá", "こんにちは")

    restored = protector.restore(translated, placeholders_map)

    assert restored == "こんにちは, {user_name2}! こんにちは novamente, {user_name2}: {item_7}."
    assert protector.validate_preservation(original, restored, placeholders_map) == []


def test_arb_protector_restores_marker_with_removed_prefix_underscores() -> None:
    protector = ArbPlaceholderProtector()
    _, placeholders_map = protector.mask("Hello {name}")
    token = next(iter(placeholders_map))

    restored = protector.restore(token.replace("__PH_", "PH_"), placeholders_map)

    assert restored == "{name}"
    assert protector.validate_preservation("Hello {name}", restored, placeholders_map) == []


def test_arb_protector_rejects_missing_duplicate_and_incomplete_placeholders() -> None:
    protector = ArbPlaceholderProtector()
    _, placeholders_map = protector.mask("{first} and {second}")
    first, _second = placeholders_map

    assert protector.validate_preservation("{first} and {second}", "solo {first}", placeholders_map)
    assert protector.validate_preservation(
        "{first} and {second}", "{first} {first} {second}", placeholders_map
    )
    damaged = f"{placeholders_map[first]} and PH_invalid_marker"
    assert protector.validate_preservation("{first} and {second}", damaged, placeholders_map)


def test_arb_protector_reports_internal_marker_left_after_restore() -> None:
    protector = ArbPlaceholderProtector()
    _, placeholders_map = protector.mask("Hello {name}")
    token = next(iter(placeholders_map))
    nonce = token.rsplit("_", 1)[-1]
    translated = f"Hola PH_{nonce} {placeholders_map[token]}"

    issues = protector.validate_preservation("Hello {name}", translated, placeholders_map)

    assert any("token remains" in issue for issue in issues)


def test_arb_protector_avoids_collision_with_marker_like_source_text() -> None:
    protector = ArbPlaceholderProtector()
    colliding_nonce = "0" * 31 + "1"
    unique_nonce = "0" * 31 + "2"
    original = f"Literal __PH_{colliding_nonce} plus {{name}}"
    uuids = iter(
        [
            SimpleNamespace(hex=colliding_nonce),
            SimpleNamespace(hex=unique_nonce),
        ]
    )

    with patch("poliglota.quality.placeholders.uuid.uuid4", side_effect=lambda: next(uuids)):
        masked, placeholders_map = protector.mask(original)

    assert f"__PH_{colliding_nonce}" in masked
    assert list(placeholders_map) == [f"__PH_{unique_nonce}"]
    restored = protector.restore(masked, placeholders_map)
    assert restored == original
    assert protector.validate_preservation(original, restored, placeholders_map) == []


def test_arb_protector_rejects_unexpected_placeholder() -> None:
    protector = ArbPlaceholderProtector()

    assert protector.validate_preservation("Hello", "Hola {unexpected}")


def test_arb_protector_does_not_treat_percent_prose_as_printf_placeholders() -> None:
    protector = ArbPlaceholderProtector()
    source = "You spent {percent}% of your budget. % change from last month."
    translated = "Gastaste {percent}% de tu presupuesto. Variación respecto del mes pasado."

    assert protector.validate_preservation(source, translated) == []
    assert protector.detect(source) == {"percent"}


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
