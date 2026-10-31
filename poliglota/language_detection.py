"""Content-based source language detection for localization resources.

The detection layer is intentionally format-agnostic: adapters remain responsible
for parsing the file and exposing translatable strings; this module only scores
text evidence and exposes the user-facing candidates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from langdetect import DetectorFactory, detect_langs
except ImportError:  # pragma: no cover - optional runtime dependency
    DetectorFactory = None  # type: ignore[assignment]
    detect_langs = None  # type: ignore[assignment]

from .formats.registry_init import get_registry

_TEXT_WEIGHTS = {
    "default": 1.0,
    "short": 0.45,
    "mixed": 0.8,
}

_LOCALE_DISPLAY_NAMES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "ja": "日本語",
    "ko": "한국어",
    "pt": "Português",
    "pt_BR": "Português (Brasil)",
    "pt_PT": "Português (Portugal)",
    "zh": "中文",
}

_LANGUAGE_ALIASES = {
    "pt-br": "pt_BR",
    "pt_br": "pt_BR",
    "pt-pt": "pt_PT",
    "pt_pt": "pt_PT",
    "en-us": "en_US",
    "en_us": "en_US",
    "es-es": "es_ES",
    "es_es": "es_ES",
    "fr-fr": "fr_FR",
    "fr_fr": "fr_FR",
    "de-de": "de_DE",
    "de_de": "de_DE",
    "ja-jp": "ja_JP",
    "ja_jp": "ja_JP",
    "ko-kr": "ko_KR",
    "ko_kr": "ko_KR",
    "zh-cn": "zh_CN",
    "zh_cn": "zh_CN",
    "zh-tw": "zh_TW",
    "zh_tw": "zh_TW",
}


@dataclass(frozen=True, slots=True)
class DetectionCandidate:
    """One likely source language with aggregated evidence."""

    locale_code: str
    display_name: str
    confidence: float
    evidence_count: int
    source: str = "content"

    @property
    def confidence_percent(self) -> int:
        """Return the rounded confidence as a percentage."""
        return max(0, min(100, round(self.confidence * 100)))

    @property
    def label(self) -> str:
        """Return the user-facing label for this candidate."""
        return f"{self.display_name} — {self.locale_code} — {self.confidence_percent}%"


@dataclass(slots=True)
class LanguageDetectionResult:
    """The detection result for one resource tree."""

    candidates: list[DetectionCandidate] = field(default_factory=list)
    files_analyzed: int = 0
    strings_analyzed: int = 0
    metadata_conflicts: list[str] = field(default_factory=list)
    inconclusive: bool = False

    @property
    def top_locale(self) -> str | None:
        """Return the top locale candidate, if any."""
        if not self.candidates:
            return None
        return self.candidates[0].locale_code


_XML_SUFFIXES = {
    "yaml": (".yaml", ".yml"),
    "yml": (".yaml", ".yml"),
    "json": (".json",),
    "xml": (".xml",),
    "arb": (".arb",),
}


def normalize_locale_code(locale: str | None) -> str | None:
    """Canonicalize locale strings while preserving region information.

    Examples:
      "pt-BR" -> "pt_BR"
      "pt_BR" -> "pt_BR"
      "en-US" -> "en_US"
      "pt" -> "pt"

    """
    if locale is None:
        return None

    value = str(locale).strip()
    if not value:
        return None

    normalized = value.replace("-", "_")
    normalized = normalized.replace(" ", "")
    lowered = normalized.lower()
    alias = _LANGUAGE_ALIASES.get(lowered)
    if alias is not None:
        return alias

    if "_" in normalized:
        language, region = normalized.split("_", 1)
        return f"{language.lower()}_{region.upper()}"

    return normalized.lower()


def _display_name_for_locale(locale_code: str) -> str:
    canonical = normalize_locale_code(locale_code) or locale_code
    if canonical in _LOCALE_DISPLAY_NAMES:
        return _LOCALE_DISPLAY_NAMES[canonical]

    language_code = canonical.split("_", 1)[0].lower()
    return _LOCALE_DISPLAY_NAMES.get(language_code, canonical)


def _iter_resource_files(root: Path, format_name: str) -> list[Path]:
    """Return all files pertaining to a given format in the project tree."""
    if not root.exists():
        return []

    suffixes = _XML_SUFFIXES.get(format_name.lower(), (f".{format_name.lower()}",))
    files: list[Path] = []
    for suffix in suffixes:
        files.extend(sorted(root.rglob(f"*{suffix}")))

    if format_name.lower() == "json":
        files = [
            path
            for path in files
            if path.name not in {"package.json", "tsconfig.json", "package-lock.json"}
        ]

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _extract_metadata_locale(document: Any, path: Path) -> str | None:
    """Inspect secondary locale metadata when present."""
    metadata = getattr(document, "metadata", {}) or {}
    candidates: list[str] = []
    for key in ("@@locale", "locale", "language", "base_language"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
    if not candidates:
        stem = path.stem.lower()
        for match in re.finditer(r"(?:^|[_-])([a-z]{2,3})(?:[_-]([a-z]{2}))?", stem):
            if match.group(1):
                language = match.group(1).lower()
                region = match.group(2)
                if region:
                    candidates.append(f"{language}_{region.upper()}")
                else:
                    candidates.append(language)
    return normalize_locale_code(candidates[0]) if candidates else None


def _is_placeholder_like(value: str) -> bool:
    """Identify strings that are not useful linguistic evidence."""
    value = value.strip()
    if not value or len(value) <= 1:
        return True
    if re.fullmatch(r"[\d\s.,:;!?/\\|@#%\-_=+()\[\]{}<>]+", value):
        return True
    if re.match(
        r"^(https?://|www\.|mailto:|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$",
        value,
    ):
        return True
    if "{name}" in value or "{0}" in value or "%s" in value or "${" in value:
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", value) and len(value) < 4)


def _string_values(document: Any) -> list[str]:
    """Collect user-facing string values from a parsed localization document."""
    entries = getattr(document, "entries", {}) or {}
    values: list[str] = []
    for value in entries.values():
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned or _is_placeholder_like(cleaned):
            continue
        values.append(cleaned)
    return values


def _langdetect_scores(text: str) -> dict[str, float]:
    """Ask langdetect for probabilities when available."""
    if detect_langs is None or DetectorFactory is None:
        return {}

    try:
        lang_scores = detect_langs(text)
    except (TypeError, ValueError):
        return {}

    scores: dict[str, float] = {}
    for item in lang_scores:
        code = str(item).split(":", 1)[0]
        if not code:
            continue
        normalized_code = normalize_locale_code(code)
        if normalized_code is None:
            continue
        curve = float(item.prob)
        if curve <= 0:
            continue
        scores[normalized_code] = max(scores.get(normalized_code, 0.0), curve)
    return scores


def _fallback_scores(text: str) -> dict[str, float]:
    """Provide lightweight heuristic fallback for common supported languages."""
    text_lower = text.lower()
    hints: dict[str, float] = {}

    if any(
        token in text_lower
        for token in ("olá", "você", "não", "obrigado", "bom dia", "tudo bem")
    ):
        hints["pt"] = 0.7
    if any(token in text_lower for token in ("hello", "world", "welcome", "please", "thanks")):
        hints["en"] = 0.7
    if any(token in text_lower for token in ("hola", "gracias", "buenos", "adiós", "por favor")):
        hints["es"] = 0.7
    if any(token in text_lower for token in ("bonjour", "merci", "s'il", "salut", "français")):
        hints["fr"] = 0.7
    if any(token in text_lower for token in ("hallo", "danke", "guten", "morgen")):
        hints["de"] = 0.7
    if any(token in text_lower for token in ("こんにちは", "ありがとう", "です", "ます")):
        hints["ja"] = 0.9
    return hints


def _aggregate_score_map(texts: list[str]) -> dict[str, float]:
    """Aggregate evidence across the strings extracted from one file."""
    vote_map: dict[str, float] = {}
    for text in texts:
        scores = _langdetect_scores(text)
        if not scores:
            scores = _fallback_scores(text)
        if not scores:
            continue

        total = sum(scores.values()) if scores else 0.0
        if total == 0:
            continue

        if len(text) <= 18:
            weight = _TEXT_WEIGHTS["short"]
        elif len(text) > 120:
            weight = _TEXT_WEIGHTS["default"]
        else:
            weight = _TEXT_WEIGHTS["mixed"]

        for code, value in scores.items():
            normalized = normalize_locale_code(code) or code
            vote_map[normalized] = vote_map.get(normalized, 0.0) + (value / total) * weight
    return vote_map


def detect_source_locale(
    root: str | Path,
    format_name: str,
    *,
    adapter: Any | None = None,
) -> LanguageDetectionResult:
    """Detect the likely source language from the text content in a resource tree."""
    root_path = Path(root)
    if adapter is None:
        registry = get_registry()
        adapter = registry.get(format_name)

    files = _iter_resource_files(root_path, format_name)
    aggregated: dict[str, float] = {}
    metadata_conflicts: list[str] = []
    strings_analyzed = 0
    valid_texts: list[str] = []

    for path in files:
        try:
            document = adapter.read(path)
        except (TypeError, ValueError, OSError):
            continue

        metadata_locale = _extract_metadata_locale(document, path)
        texts = _string_values(document)
        if not texts:
            continue

        strings_analyzed += len(texts)
        valid_texts.extend(texts)

        score_map = _aggregate_score_map(texts)
        for code, value in score_map.items():
            aggregated[code] = aggregated.get(code, 0.0) + value

        if metadata_locale is not None:
            best_match = sorted(score_map, key=score_map.get, reverse=True)[:1]
            if best_match and normalize_locale_code(best_match[0]) != normalize_locale_code(
                metadata_locale
            ):
                conflict_msg = (
                    f"{path.name}: metadata says {metadata_locale}, "
                    f"content suggests {best_match[0]}"
                )
                metadata_conflicts.append(conflict_msg)

    if not valid_texts:
        return LanguageDetectionResult(
            files_analyzed=len(files),
            strings_analyzed=0,
            metadata_conflicts=metadata_conflicts,
            inconclusive=True,
        )

    candidates: list[DetectionCandidate] = []
    total_votes = sum(aggregated.values())
    if total_votes <= 0:
        return LanguageDetectionResult(
            files_analyzed=len(files),
            strings_analyzed=strings_analyzed,
            metadata_conflicts=metadata_conflicts,
            inconclusive=True,
        )

    for locale_code, score in sorted(aggregated.items(), key=lambda item: item[1], reverse=True):
        confidence = score / total_votes
        candidates.append(
            DetectionCandidate(
                locale_code=locale_code,
                display_name=_display_name_for_locale(locale_code),
                confidence=confidence,
                evidence_count=max(1, round(score * 10)),
                source="content",
            )
        )

    top_candidate = candidates[0].confidence if candidates else 0.0
    second_candidate = candidates[1].confidence if len(candidates) > 1 else 0.0
    inconclusive = top_candidate < 0.35 or (top_candidate - second_candidate) < 0.12

    return LanguageDetectionResult(
        candidates=candidates,
        files_analyzed=len(files),
        strings_analyzed=strings_analyzed,
        metadata_conflicts=metadata_conflicts,
        inconclusive=inconclusive,
    )


def detect_source_locale_code(
    root: str | Path,
    format_name: str,
    *,
    adapter: Any | None = None,
) -> str | None:
    """Return the best locale candidate, or ``None`` when the text is inconclusive."""
    result = detect_source_locale(root, format_name, adapter=adapter)
    if not result.candidates:
        return None
    if result.inconclusive:
        return None
    return result.candidates[0].locale_code
