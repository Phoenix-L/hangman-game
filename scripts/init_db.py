import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import DEFAULT_DB_PATH, initialize_and_seed, reset_and_seed_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Hangman database safely.")
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument(
        '--reset-destructive',
        action='store_true',
        help='DESTRUCTIVE: delete vocabulary and dependent game history before reseeding',
    )
    parser.add_argument(
        '--confirm-destructive-reset',
        action='store_true',
        help='Explicitly confirm the destructive reset for automation',
    )
    args = parser.parse_args()
    source_dirs = [args.data_dir]
    if args.reset_destructive:
        if not args.confirm_destructive_reset:
            parser.error('--reset-destructive requires --confirm-destructive-reset')
        print('WARNING: destructive reset will delete vocabulary and dependent game history.')
        inserted = reset_and_seed_database(args.db_path, source_dirs=source_dirs)
    else:
        inserted = initialize_and_seed(args.db_path, source_dirs=source_dirs)
    print(f"Database initialized and seeded safely. New words inserted: {inserted}")


if __name__ == "__main__":
    main()
