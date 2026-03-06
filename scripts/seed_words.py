import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import DEFAULT_DB_PATH, get_connection, init_db


def _resolve_word_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob('*.txt'))


def seed_words(db_path: str, data_dir: str = 'data') -> tuple[int, int]:
    data_path = Path(data_dir)
    if not data_path.exists() or not data_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    files = _resolve_word_files(data_path)
    if not files:
        raise FileNotFoundError(f"No .txt files found in {data_path}/")

    init_db(db_path)
    conn = get_connection(db_path)

    total_inserted = 0
    total_duplicates = 0

    try:
        for file_path in files:
            theme_name = file_path.stem
            print(f"Loading theme: {theme_name}")

            conn.execute(
                "INSERT OR IGNORE INTO themes (name, description) VALUES (?, ?)",
                (theme_name, f"Seeded from {file_path}"),
            )
            theme_row = conn.execute(
                "SELECT id FROM themes WHERE name = ?",
                (theme_name,),
            ).fetchone()
            if not theme_row:
                print("Inserted 0 words")
                print("Skipped 0 duplicates")
                continue

            theme_id = theme_row['id']
            inserted = 0
            duplicates = 0
            non_blank_seen = 0

            with file_path.open('r', encoding='utf-8') as handle:
                for raw in handle:
                    word = raw.strip().lower()
                    if not word:
                        continue
                    non_blank_seen += 1
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO words (theme_id, value) VALUES (?, ?)",
                        (theme_id, word),
                    )
                    if cursor.rowcount == 1:
                        inserted += 1
                    else:
                        duplicates += 1

            if non_blank_seen == 0:
                print(f"File is empty (no words): {file_path.name}")

            print(f"Inserted {inserted} words")
            print(f"Skipped {duplicates} duplicates")

            total_inserted += inserted
            total_duplicates += duplicates

        conn.commit()
        print(f"Done. Inserted {total_inserted} words, skipped {total_duplicates} duplicates.")
        return total_inserted, total_duplicates
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed vocabulary words into SQLite database.')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Path to SQLite database file')
    parser.add_argument('--data-dir', default='data', help='Directory containing vocabulary .txt files')
    args = parser.parse_args()

    try:
        seed_words(db_path=args.db_path, data_dir=args.data_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
