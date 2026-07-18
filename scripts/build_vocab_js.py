#!/usr/bin/env python3
"""
Build vocab.js from data/*.txt for offline play.

Reads top-level *.txt files in the data directory (same rules as db.seed_words_from_files).
Outputs a JavaScript file defining VOCAB (theme -> words) and THEMES (id, name, display, word_count).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_weekly_package import (
    ALLOWED_CATEGORIES,
    PackageError,
    load_package,
    normalize_term,
)
from scripts.validate_neurobiology_glossary import DEFAULT_PATH, THEME_BY_CATEGORY, validate


DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = ROOT / "vocab.js"
DEFAULT_WEEKLY_PACKAGE_DIR = ROOT / "data/source/weekly_packages"


def theme_display_name(theme_name: str) -> str:
    """Mirror db.theme_display_name: KET_ANIMALS -> Animals."""
    if not theme_name or not theme_name.strip():
        return "Vocabulary"
    parts = theme_name.strip().split("_")
    return parts[-1].title() if parts else theme_name


def collect_word_files(source_dirs: list[Path]) -> list[Path]:
    """Top-level *.txt only in each directory."""
    files = []
    for directory in source_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        files.extend(sorted(directory.glob("*.txt")))
    return files


def build_vocab_and_themes(data_dir: Path) -> tuple[dict[str, list[str]], list[dict]]:
    vocab = {}
    themes = []
    for file_path in collect_word_files([data_dir]):
        theme_name = file_path.stem.upper()
        words = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            word = line.strip().lower()
            if word:
                words.append(word)
        if theme_name:
            vocab[theme_name] = words
            themes.append({
                "id": theme_name,
                "name": theme_name,
                "display": theme_display_name(theme_name),
                "word_count": len(words),
            })
    return vocab, themes


def add_neurobiology_vocab(
    vocab: dict[str, list[str]], themes: list[dict], glossary_path: Path = DEFAULT_PATH
) -> None:
    """Merge approved glossary answers into the same generated offline vocabulary."""
    if not glossary_path.exists():
        return
    theme_by_id = {theme["id"]: theme for theme in themes}
    for row in validate(glossary_path):
        if row["status"].strip().lower() != "approved" or row["hangman_enabled"].strip().lower() != "yes":
            continue
        theme_key = THEME_BY_CATEGORY[row["category"].strip()]
        values = vocab.setdefault(theme_key, [])
        answer = row["answer"].strip().lower()
        if answer not in values:
            values.append(answer)
        if theme_key not in theme_by_id:
            theme = {
                "id": theme_key,
                "name": theme_key,
                "display": theme_display_name(theme_key),
                "word_count": 0,
            }
            themes.append(theme)
            theme_by_id[theme_key] = theme
        theme_by_id[theme_key]["word_count"] = len(values)


def collect_weekly_packages(package_dir: Path = DEFAULT_WEEKLY_PACKAGE_DIR) -> list[Path]:
    """Return repository-owned published packages in deterministic order."""
    if not package_dir.exists():
        return []
    return sorted(package_dir.rglob("*.json"))


def add_weekly_package_vocab(
    vocab: dict[str, list[str]],
    themes: list[dict],
    package_dir: Path = DEFAULT_WEEKLY_PACKAGE_DIR,
) -> dict[str, int]:
    """Validate and merge immutable published weekly packages into offline vocab."""
    theme_by_id = {theme["id"]: theme for theme in themes}
    terms_by_category = {
        category: {normalize_term(term) for term in terms}
        for category, terms in vocab.items()
    }
    term_categories: dict[str, set[str]] = {}
    for category, terms in terms_by_category.items():
        for term in terms:
            term_categories.setdefault(term, set()).add(category)
    source_identities: dict[str, tuple[str, str]] = {}
    summary = {"packages": 0, "items": 0, "deduplicated": 0, "added": 0}
    package_checksums: dict[str, str] = {}
    validated_packages = []

    for package_path in collect_weekly_packages(package_dir):
        try:
            package = load_package(package_path)
        except PackageError as exc:
            raise ValueError(
                f"Invalid weekly package {package_path.name}: {exc}"
            ) from exc
        package_id = package["package_id"]
        payload_sha256 = package["payload_sha256"]
        previous_checksum = package_checksums.get(package_id)
        if previous_checksum is not None and previous_checksum != payload_sha256:
            raise ValueError(
                "Weekly package identity has conflicting payload checksums."
            )
        if previous_checksum == payload_sha256:
            continue
        package_checksums[package_id] = payload_sha256
        validated_packages.append(package)

    for package in validated_packages:
        summary["packages"] += 1
        for item in sorted(
            package["items"],
            key=lambda value: (
                value["source_term_id"],
                normalize_term(value["canonical_term"]),
            ),
        ):
            summary["items"] += 1
            category = item["category"]
            normalized = normalize_term(item["canonical_term"])
            if category not in ALLOWED_CATEGORIES:
                raise ValueError("Weekly package contains an unsupported category.")
            identity = item["source_term_id"]
            previous = source_identities.get(identity)
            current = (normalized, category)
            if previous is not None and previous != current:
                raise ValueError(
                    "Weekly package reuses a source identity with conflicting term/category."
                )
            source_identities[identity] = current

            prior_categories = term_categories.get(normalized, set())
            if prior_categories and prior_categories != {category}:
                raise ValueError("Weekly package term conflicts with another category.")
            values = vocab.setdefault(category, [])
            category_terms = terms_by_category.setdefault(category, set())
            if normalized in category_terms:
                summary["deduplicated"] += 1
                continue
            values.append(normalized)
            category_terms.add(normalized)
            term_categories.setdefault(normalized, set()).add(category)
            summary["added"] += 1
            if category not in theme_by_id:
                theme = {
                    "id": category,
                    "name": category,
                    "display": theme_display_name(category),
                    "word_count": 0,
                }
                themes.append(theme)
                theme_by_id[category] = theme
            theme_by_id[category]["word_count"] = len(values)
    return summary


def build_vocab(
    data_dir: Path = DEFAULT_DATA_DIR,
    package_dir: Path = DEFAULT_WEEKLY_PACKAGE_DIR,
) -> tuple[dict[str, list[str]], list[dict], dict[str, int]]:
    """Build vocabulary in memory, failing before any output is written."""
    vocab, themes = build_vocab_and_themes(data_dir)
    add_neurobiology_vocab(vocab, themes)
    weekly_summary = add_weekly_package_vocab(vocab, themes, package_dir)
    return vocab, themes, weekly_summary


def emit_js(vocab: dict, themes: list[dict], out_path: Path) -> None:
    """Write vocab.js with VOCAB and THEMES."""
    vocab_json = json.dumps(vocab, ensure_ascii=False)
    themes_json = json.dumps(themes, ensure_ascii=False)
    content = f"""// Generated by scripts/build_vocab_js.py — do not edit by hand.
const VOCAB = {vocab_json};
const THEMES = {themes_json};
"""
    out_path.write_text(content, encoding="utf-8")


def main() -> int:
    data_dir = ROOT / "data" if len(sys.argv) < 2 else Path(sys.argv[1]).resolve()
    out_path = DEFAULT_OUTPUT if len(sys.argv) < 3 else Path(sys.argv[2]).resolve()

    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        return 1

    vocab, themes, weekly_summary = build_vocab(data_dir)
    if not vocab:
        print("Warning: no vocabulary files found.", file=sys.stderr)

    emit_js(vocab, themes, out_path)
    print(f"Wrote {out_path} ({len(themes)} themes, {sum(len(w) for w in vocab.values())} words).")
    print(
        "Weekly packages: "
        f"{weekly_summary['packages']} files, {weekly_summary['items']} items, "
        f"{weekly_summary['deduplicated']} deduplicated, {weekly_summary['added']} added."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
