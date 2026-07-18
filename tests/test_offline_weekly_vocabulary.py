import json
from pathlib import Path

import pytest

from scripts.build_vocab_js import (
    add_neurobiology_vocab,
    add_weekly_package_vocab,
    build_vocab_and_themes,
    emit_js,
)
from scripts.import_weekly_package import checksum, normalize_term, stable_source_term_id


ROOT = Path(__file__).resolve().parents[1]
WEEKLY_PACKAGE = ROOT / "data/source/weekly_packages/neuroscience-90/week-1.json"


def make_package(term="test offline term", category="NEURO_ANATOMY", package_id=None):
    normalized = " ".join(term.casefold().split())
    item = {
        "source_term_id": stable_source_term_id("neuroscience-90", normalized),
        "canonical_term": term,
        "display_term": term,
        "pronunciation_text": term,
        "definition": "A test vocabulary definition.",
        "part_of_speech": "noun",
        "category": category,
        "aliases": [term],
        "source_days": [1],
    }
    package = {
        "format": "hangman-weekly-v1",
        "package_id": package_id or "hangman-weekly-v1:neuroscience-90:week-1",
        "program_slug": "neuroscience-90",
        "week_number": 1,
        "items": [item],
    }
    package["payload_sha256"] = checksum(package)
    return package


def write_package(directory: Path, package, name="package.json"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(package, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def vocab_with_glossary():
    vocab, themes = build_vocab_and_themes(ROOT / "data")
    add_neurobiology_vocab(vocab, themes)
    return vocab, themes


def test_valid_package_contributes_canonical_terms(tmp_path):
    package = make_package()
    write_package(tmp_path, package)
    vocab, themes = vocab_with_glossary()

    summary = add_weekly_package_vocab(vocab, themes, tmp_path)

    assert vocab["NEURO_ANATOMY"][-1] == "test offline term"
    assert summary == {"packages": 1, "items": 1, "deduplicated": 0, "added": 1}


def test_exact_same_category_term_is_deduplicated(tmp_path):
    package = make_package("axon", "NEURO_FOUNDATIONS")
    write_package(tmp_path, package)
    vocab, themes = vocab_with_glossary()
    before = list(vocab["NEURO_FOUNDATIONS"])

    summary = add_weekly_package_vocab(vocab, themes, tmp_path)

    assert vocab["NEURO_FOUNDATIONS"] == before
    assert summary["deduplicated"] == 1
    assert summary["added"] == 0


def test_repeated_identical_source_identity_is_idempotent(tmp_path):
    package = make_package()
    write_package(tmp_path, package, "a.json")
    write_package(tmp_path, package, "b.json")
    vocab, themes = vocab_with_glossary()

    summary = add_weekly_package_vocab(vocab, themes, tmp_path)

    assert vocab["NEURO_ANATOMY"].count("test offline term") == 1
    assert summary["added"] == 1
    assert summary["deduplicated"] == 1


def test_invalid_package_checksum_fails_closed(tmp_path):
    package = make_package()
    package["payload_sha256"] = "0" * 64
    write_package(tmp_path, package)
    vocab, themes = vocab_with_glossary()

    with pytest.raises(ValueError, match="Invalid weekly package"):
        add_weekly_package_vocab(vocab, themes, tmp_path)


@pytest.mark.parametrize(
    "field, value",
    [
        ("source_term_id", "learning:neuroscience-90:term:" + "0" * 24),
        ("category", "NOT_A_THEME"),
    ],
)
def test_invalid_package_identity_or_category_fails_closed(tmp_path, field, value):
    package = make_package()
    package["items"][0][field] = value
    package["payload_sha256"] = checksum({k: v for k, v in package.items() if k != "payload_sha256"})
    write_package(tmp_path, package)
    vocab, themes = vocab_with_glossary()

    with pytest.raises(ValueError, match="Invalid weekly package"):
        add_weekly_package_vocab(vocab, themes, tmp_path)


def test_same_term_in_different_category_fails_closed(tmp_path):
    package = make_package("axon", "NEURO_FUNCTION")
    write_package(tmp_path, package)
    vocab, themes = vocab_with_glossary()

    with pytest.raises(ValueError, match="another category"):
        add_weekly_package_vocab(vocab, themes, tmp_path)


def test_same_source_identity_with_conflicting_category_fails_closed(tmp_path):
    first = make_package("shared offline term", "NEURO_ANATOMY")
    second = make_package("shared offline term", "NEURO_FUNCTION")
    write_package(tmp_path, first, "a.json")
    write_package(tmp_path, second, "b.json")
    vocab, themes = vocab_with_glossary()

    with pytest.raises(ValueError, match="source identity"):
        add_weekly_package_vocab(vocab, themes, tmp_path)


def test_real_week_one_package_has_expected_counts_and_terms():
    package = json.loads(WEEKLY_PACKAGE.read_text(encoding="utf-8"))
    assert len(package["items"]) == 54
    assert package["payload_sha256"] == "a188ab4181488af94ea041e448081621966ff1825c4d66cd556c1ba8c01d189a"

    before, themes = vocab_with_glossary()
    before_sets = {category: set(values) for category, values in before.items()}
    summary = add_weekly_package_vocab(before, themes, WEEKLY_PACKAGE.parent.parent)

    assert summary == {"packages": 1, "items": 54, "deduplicated": 5, "added": 49}
    assert sum(len(values) for values in before.values()) == 1501
    for item in package["items"]:
        assert normalize_term(item["canonical_term"]) in {
            normalize_term(value) for value in before[item["category"]]
        }


def test_existing_vocab_is_preserved_and_generation_is_deterministic(tmp_path):
    before, before_themes = vocab_with_glossary()
    before_copy = {category: list(values) for category, values in before.items()}
    first, first_themes = vocab_with_glossary()
    second, second_themes = vocab_with_glossary()
    add_weekly_package_vocab(first, first_themes, WEEKLY_PACKAGE.parent.parent)
    add_weekly_package_vocab(second, second_themes, WEEKLY_PACKAGE.parent.parent)
    first_output = tmp_path / "first.js"
    second_output = tmp_path / "second.js"
    emit_js(first, first_themes, first_output)
    emit_js(second, second_themes, second_output)

    assert all(first[category][: len(values)] == values for category, values in before_copy.items())
    assert first_output.read_bytes() == second_output.read_bytes()
