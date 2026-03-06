from pathlib import Path

from db import (
    clear_themes_and_words,
    get_random_word,
    get_theme_name_by_id,
    init_db,
    list_themes,
    seed_words_from_files,
)


def test_init_db_creates_expected_tables(tmp_path):
    db_path = tmp_path / 'test.db'

    init_db(str(db_path))

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()

    expected = {
        'users',
        'themes',
        'words',
        'games',
        'word_progress',
        'leaderboard_entries',
    }
    assert expected.issubset(tables)


def test_seed_loading_and_theme_queries(tmp_path):
    db_path = tmp_path / 'seed.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'ket.txt').write_text('cat\ndog\n', encoding='utf-8')
    (words_dir / 'pet.txt').write_text('planet\ntravel\n', encoding='utf-8')

    init_db(str(db_path))
    inserted = seed_words_from_files(str(db_path), data_dir=str(words_dir))

    assert inserted == 4

    themes = list_themes(str(db_path))
    names = [theme['name'] for theme in themes]
    assert names == ['ket', 'pet']

    word_counts = {theme['name']: theme['word_count'] for theme in themes}
    assert word_counts['ket'] == 2
    assert word_counts['pet'] == 2

    inserted_again = seed_words_from_files(str(db_path), data_dir=str(words_dir))
    assert inserted_again == 0


def test_get_theme_name_by_id(tmp_path):
    db_path = tmp_path / 'themes.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'ket.txt').write_text('cat\ndog\n', encoding='utf-8')

    init_db(str(db_path))
    seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])

    conn = __import__('sqlite3').connect(db_path)
    theme_id = conn.execute("SELECT id FROM themes WHERE name='KET'").fetchone()[0]
    conn.close()

    assert get_theme_name_by_id(str(db_path), theme_id) == 'KET'
    assert get_theme_name_by_id(str(db_path), 99999) is None


def test_get_random_word_returns_value_and_theme(tmp_path):
    db_path = tmp_path / 'rand.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'food.txt').write_text('apple\nbread\n', encoding='utf-8')

    init_db(str(db_path))
    seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])

    result = get_random_word(str(db_path))
    assert result is not None
    assert 'value' in result
    assert 'theme' in result
    assert result['value'] in ('apple', 'bread')
    assert result['theme'] == 'FOOD'

    # Empty DB returns None
    clear_themes_and_words(str(db_path))
    assert get_random_word(str(db_path)) is None
