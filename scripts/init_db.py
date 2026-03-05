import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import DEFAULT_DB_PATH, initialize_and_seed


def main() -> None:
    inserted = initialize_and_seed(DEFAULT_DB_PATH)
    print(f"Database initialized and seeded. New words inserted: {inserted}")


if __name__ == "__main__":
    main()
