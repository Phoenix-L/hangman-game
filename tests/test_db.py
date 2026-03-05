from pathlib import Path

from db import init_db, list_themes, seed_words_from_files


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
    inserted = seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])

    assert inserted == 4

    themes = list_themes(str(db_path))
    names = [theme['name'] for theme in themes]
    assert names == ['KET', 'PET']

    word_counts = {theme['name']: theme['word_count'] for theme in themes}
    assert word_counts['KET'] == 2
    assert word_counts['PET'] == 2

    inserted_again = seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])
    assert inserted_again == 0
