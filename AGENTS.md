# AGENTS.md

## Project quickstart

1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Initialize and seed SQLite database:
   ```bash
   python scripts/init_db.py
   ```
4. Run the web server:
   ```bash
   python server.py
   ```
5. Open the app at `http://localhost:5000`.

## Test commands

Run the test suite with:

```bash
pytest -q
```

## Scope and constraints

- Do not change gameplay logic unless explicitly requested.
- Keep backend changes minimal and focused on server/runtime reliability.


## Auth endpoints (MVP)

- `POST /api/auth/signup` for account creation.
- `POST /api/auth/login` for session login.
- `GET /api/me` for guest/user session info.
- Guests can play and request words, but cannot post leaderboard entries (`POST /api/leaderboard_entries` returns `401`).


## Word selection engine notes

- Use `GET /api/word/next?theme=<id>` for next-word selection.
- For authenticated users, selection is due-review first, then high-mistake, then new words.
- For guests, selection is random within theme.
- Use `POST /api/word/progress` to update spaced-repetition fields after each outcome.
