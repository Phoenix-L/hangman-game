import sqlite3
from pathlib import Path

from db import get_connection, init_db
from scripts.import_neurobiology_glossary import import_glossary
from scripts.validate_neurobiology_glossary import validate, validate_rows


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/source/neurobiology_glossary.csv"


def test_master_glossary_has_all_normalized_source_concepts():
    rows = validate(CSV_PATH)
    assert len(rows) == 17
    stimulus = next(row for row in rows if row["term_id"] == "stimulus")
    assert stimulus["term"] == "stimulus"
    assert stimulus["answer"] == "stimulus"
    assert stimulus["singular"] == "stimulus"
    assert stimulus["plural"] == "stimuli"
    assert all(row["status"] == "approved" for row in rows)


def test_validator_rejects_duplicate_and_unsafe_rows():
    rows = validate(CSV_PATH)
    bad = dict(rows[0])
    bad["term_id"] = rows[1]["term_id"]
    bad["category"] = "Unsupported category"
    bad["hangman_enabled"] = "maybe"
    bad["status"] = "pending"
    bad["answer"] = "stimulus / stimuli"
    errors = validate_rows(rows + [bad])
    assert any("duplicate term_id" in error for error in errors)
    assert any("unsupported category" in error for error in errors)
    assert any("invalid hangman_enabled" in error for error in errors)
    assert any("invalid status" in error for error in errors)
    assert any("combined answer" in error for error in errors)


def test_import_is_additive_and_idempotent(tmp_path):
    db_path = str(tmp_path / "neurobiology.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('existing', 'hash')")
        conn.commit()
    finally:
        conn.close()

    first = import_glossary(db_path, CSV_PATH)
    assert first["inserted"] == 17
    assert first["updated"] == 0
    assert first["unchanged"] == 0

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM word_metadata").fetchone()[0] == 17
        assert conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 17
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        themes = dict(conn.execute("SELECT name, (SELECT COUNT(*) FROM words w WHERE w.theme_id=t.id) FROM themes t").fetchall())
        assert themes == {
            "NEURO_FOUNDATIONS": 2,
            "NEURO_ANATOMY": 11,
            "NEURO_FUNCTION": 2,
            "NEURO_CLINICAL": 2,
        }
    finally:
        conn.close()

    second = import_glossary(db_path, CSV_PATH)
    assert second["inserted"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 17


def test_import_preserves_existing_game_rows(tmp_path):
    db_path = str(tmp_path / "preserve.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO themes (name, description) VALUES ('OLD', 'old')")
        theme_id = conn.execute("SELECT id FROM themes WHERE name='OLD'").fetchone()["id"]
        conn.execute("INSERT INTO words (theme_id, value) VALUES (?, 'legacy')", (theme_id,))
        word_id = conn.execute("SELECT id FROM words WHERE value='legacy'").fetchone()["id"]
        conn.execute("INSERT INTO games (word_id, theme_id, status) VALUES (?, ?, 'won')", (word_id, theme_id))
        conn.commit()
    finally:
        conn.close()
    import_glossary(db_path, CSV_PATH)
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
        assert conn.execute("SELECT value FROM words WHERE id=?", (word_id,)).fetchone()[0] == "legacy"
    finally:
        conn.close()


def test_offline_vocab_builder_includes_four_neurobiology_themes():
    from scripts.build_vocab_js import add_neurobiology_vocab, build_vocab_and_themes

    vocab, themes = build_vocab_and_themes(ROOT / "data")
    add_neurobiology_vocab(vocab, themes, CSV_PATH)
    assert {"NEURO_FOUNDATIONS", "NEURO_ANATOMY", "NEURO_FUNCTION", "NEURO_CLINICAL"}.issubset(vocab)
    assert sum(len(vocab[key]) for key in ("NEURO_FOUNDATIONS", "NEURO_ANATOMY", "NEURO_FUNCTION", "NEURO_CLINICAL")) == 17
    assert "stimulus" in vocab["NEURO_FUNCTION"]
    assert "stimuli" not in vocab["NEURO_FUNCTION"]


def test_word_api_exposes_safe_pronunciation_metadata(tmp_path, monkeypatch):
    import importlib

    db_path = str(tmp_path / "api.db")
    init_db(db_path)
    import_glossary(db_path, CSV_PATH)
    server = importlib.import_module("server")
    monkeypatch.setattr(server, "DB_PATH", db_path)
    server.app.config["TESTING"] = True
    client = server.app.test_client()

    response = client.get("/api/word/next")
    assert response.status_code == 200
    word = response.get_json()["word"]
    assert word["answer"] == word["value"]
    assert word["display_term"]
    assert word["pronunciation_text"]
    assert "Chinese" not in word
    assert "definition_simple" not in word
