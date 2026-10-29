#!/usr/bin/env python3
"""
Phase A — Complete corpus inventory audit.

Inventories a local corpus without modifying any source files.
Identifies ARB files, locales, anomalies, and file metrics in a portable way.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from ._portable import add_common_audit_arguments, resolve_paths


def audit_corpus(root: Path) -> dict[str, Any]:
    """Audit the corpus and return a comprehensive inventory."""
    if not root.exists():
        return {"error": f"Root path does not exist: {root}"}

    all_arb_files = sorted(root.rglob("*.arb"))
    if not all_arb_files:
        return {"error": f"No .arb files found under {root}"}

    by_locale_from_name: dict[str, list[Path]] = defaultdict(list)
    by_locale_from_meta: dict[str, list[Path]] = defaultdict(list)
    by_dir: dict[str, list[Path]] = defaultdict(list)

    file_details: list[dict[str, Any]] = []
    anomalies: list[str] = []
    all_locales_from_names: set[str] = set()
    all_locales_from_meta: set[str] = set()
    all_lang_codes: set[str] = set()

    for fpath in all_arb_files:
        by_dir[str(fpath.parent)] = by_dir.get(str(fpath.parent), []) + [fpath]

        locale_from_name: str | None = None
        name = fpath.stem
        if "_pt_BR" in name:
            locale_from_name = "pt_BR"
            all_lang_codes.add("pt")
        elif "_en_US" in name:
            locale_from_name = "en_US"
            all_lang_codes.add("en")
        elif "_es_ES" in name:
            locale_from_name = "es_ES"
            all_lang_codes.add("es")
        elif "_fr_FR" in name:
            locale_from_name = "fr_FR"
            all_lang_codes.add("fr")
        elif "_de_DE" in name:
            locale_from_name = "de_DE"
            all_lang_codes.add("de")
        elif "_it_IT" in name:
            locale_from_name = "it_IT"
            all_lang_codes.add("it")
        elif "_zh_CN" in name:
            locale_from_name = "zh_CN"
            all_lang_codes.add("zh")
        elif "_ja_JP" in name:
            locale_from_name = "ja_JP"
            all_lang_codes.add("ja")
        elif "_ko_KR" in name:
            locale_from_name = "ko_KR"
            all_lang_codes.add("ko")
        else:
            parts = name.split("_")
            if len(parts) >= 2:
                potential = f"{parts[-2]}_{parts[-1]}"
                if len(parts[-2]) == 2 and len(parts[-1]) == 2:
                    locale_from_name = potential
                    all_lang_codes.add(parts[-2])

        if locale_from_name:
            all_locales_from_names.add(locale_from_name)
            by_locale_from_name[locale_from_name].append(fpath)

        try:
            content = fpath.read_text(encoding="utf-8")
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                anomalies.append(f"INVALID_JSON: {fpath.relative_to(root)} - {exc}")
                file_details.append(
                    {
                        "path": str(fpath.relative_to(root)),
                        "size_bytes": fpath.stat().st_size,
                        "is_valid_json": False,
                        "is_empty": len(content.strip()) == 0,
                        "locale_from_name": locale_from_name,
                        "locale_from_meta": None,
                        "entry_count": 0,
                        "key_count": 0,
                        "issues": ["INVALID_JSON"],
                    }
                )
                continue

            locale_from_meta = data.get("@@locale")
            if locale_from_meta:
                all_locales_from_meta.add(str(locale_from_meta))
                by_locale_from_meta[str(locale_from_meta)].append(fpath)

            is_empty = len(data) == 0 or (len(data) == 1 and "@@locale" in data)
            if is_empty:
                anomalies.append(f"EMPTY_OR_NO_ENTRIES: {fpath.relative_to(root)}")

            entry_count = len(data)
            key_count = sum(1 for key in data if not str(key).startswith("@"))

            issues: list[str] = []
            if locale_from_name and locale_from_meta and locale_from_name != locale_from_meta:
                issues.append("LOCALE_MISMATCH")
                anomalies.append(
                    f"LOCALE_MISMATCH: {fpath.relative_to(root)} - filename={locale_from_name}, metadata={locale_from_meta}"
                )

            placeholder_count = 0
            for value in data.values():
                if isinstance(value, str) and "{" in value and "}" in value:
                    placeholder_count += value.count("{")

            file_details.append(
                {
                    "path": str(fpath.relative_to(root)),
                    "size_bytes": fpath.stat().st_size,
                    "is_valid_json": True,
                    "is_empty": is_empty,
                    "locale_from_name": locale_from_name,
                    "locale_from_meta": locale_from_meta,
                    "entry_count": entry_count,
                    "key_count": key_count,
                    "placeholder_count": placeholder_count,
                    "issues": issues or [],
                }
            )

        except OSError as exc:
            anomalies.append(f"READ_ERROR: {fpath.relative_to(root)} - {exc}")
            file_details.append(
                {
                    "path": str(fpath.relative_to(root)),
                    "size_bytes": 0,
                    "is_valid_json": False,
                    "is_empty": False,
                    "locale_from_name": locale_from_name,
                    "locale_from_meta": None,
                    "entry_count": 0,
                    "key_count": 0,
                    "issues": ["READ_ERROR"],
                }
            )

    all_locales = all_locales_from_names | all_locales_from_meta
    by_locale_combined = {
        locale: sorted(set(by_locale_from_name.get(locale, []) + by_locale_from_meta.get(locale, [])))
        for locale in all_locales
    }

    return {
        "corpus_root": str(root),
        "total_arb_files": len(all_arb_files),
        "total_distinct_locales": len(all_locales),
        "all_locales": sorted(all_locales),
        "locales_from_filename": sorted(all_locales_from_names),
        "locales_from_metadata": sorted(all_locales_from_meta),
        "total_lang_codes": len(all_lang_codes),
        "lang_codes": sorted(all_lang_codes),
        "by_directory": {directory: len(files) for directory, files in sorted(by_dir.items())},
        "by_locale": {
            locale: {
                "count": len(files),
                "files": [str(f.relative_to(root)) for f in sorted(files)],
            }
            for locale, files in sorted(by_locale_combined.items())
        },
        "file_details": file_details,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the inventory audit from command-line arguments."""
    parser = argparse.ArgumentParser(description="Audit localized corpus files without modifying them.")
    add_common_audit_arguments(parser)
    args = parser.parse_args(argv)

    paths = resolve_paths(
        repo_root=args.repo_root,
        corpus_root=args.corpus_root,
        report_dir=args.report_dir,
        python_executable=args.python_executable,
    )
    repo_root = paths["repo_root"]
    corpus_root = paths["corpus_root"] or repo_root
    report_dir = paths["report_dir"]

    print("=" * 80)
    print("PHASE A — CORPUS INVENTORY AUDIT")
    print("=" * 80)

    if not corpus_root.exists():
        print(f"ERROR: corpus_root does not exist: {corpus_root}", file=sys.stderr)
        return 1

    result = audit_corpus(corpus_root)
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1

    print(f"\n[SUMMARY]")
    print("-" * 80)
    print(f"Corpus root:             {result['corpus_root']}")
    print(f"Total ARB files:         {result['total_arb_files']}")
    print(f"Distinct locales:        {result['total_distinct_locales']}")
    print(f"Language codes:          {result['total_lang_codes']}")
    print(f"Anomalies found:         {result['anomaly_count']}")

    print(f"\n[LOCALES FOUND]")
    print("-" * 80)
    for locale in result["all_locales"]:
        info = result["by_locale"][locale]
        print(f"{locale:15s} {info['count']:3d} file(s)")
        for fname in info["files"]:
            print(f"  -> {fname}")

    print(f"\n[LANGUAGE CODES]")
    print("-" * 80)
    print(f"Codes: {', '.join(result['lang_codes'])}")

    print(f"\n[DISTRIBUTION BY DIRECTORY]")
    print("-" * 80)
    for directory, count in sorted(result["by_directory"].items()):
        print(f"{count:3d} file(s) in {directory}")

    if result["anomalies"]:
        print(f"\n[ANOMALIES ({result['anomaly_count']})]")
        print("-" * 80)
        for anomaly in result["anomalies"]:
            print(f"  ! {anomaly}")

    report_path = report_dir / "phase_a_inventory.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Full inventory saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
