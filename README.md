# Hangman Game

A classic Hangman word guessing game built with HTML, CSS, JavaScript, and a Python Flask backend.

## Features

- Classic hangman gameplay
- Word guessing mechanics
- Visual hangman drawing
- Score tracking
- Web interface with sound effects
- SQLite schema + seed loader for themes and words

## Setup

1. Create a virtual environment (recommended):

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

## Run the application

1. Start the Flask server:

   ```bash
   python server.py
   ```

2. Open your browser and go to `http://localhost:5000`.

## Run tests

```bash
pytest -q
```

## API endpoints

- `GET /api/random_word` - existing random word endpoint used by the game.
- `GET /api/themes` - returns seeded themes and word counts from SQLite.


## Auth endpoints (MVP)

- `POST /api/auth/signup` with JSON `{ "username": "...", "password": "..." }`
- `POST /api/auth/login` with JSON `{ "username": "...", "password": "..." }`
- `GET /api/me` returns guest/user session info
- `POST /api/leaderboard_entries` requires login (guests receive `401`)

## Manual auth test steps

1. Start server: `python server.py`
2. Sign up:
   ```bash
   curl -i -X POST http://localhost:5000/api/auth/signup \
     -H "Content-Type: application/json" \
     -d '{"username":"demo_user","password":"secret123"}'
   ```
3. Login:
   ```bash
   curl -i -X POST http://localhost:5000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"demo_user","password":"secret123"}'
   ```
4. Verify current session user:
   ```bash
   curl -i http://localhost:5000/api/me
   ```
5. Confirm guest restriction on leaderboard:
   ```bash
   curl -i -X POST http://localhost:5000/api/leaderboard_entries \
     -H "Content-Type: application/json" \
     -d '{"score":10}'
   ```

## How to Play

1. Guess letters to reveal the hidden word.
2. You have 6 incorrect attempts before the hangman is complete.
3. Win by guessing all letters in the word.

## Project Structure

```text
hangman-game/
├── AGENTS.md            # Instructions for Codex agents
├── db.py                # SQLite schema + seed/query utilities
├── scripts/init_db.py   # DB initialization entrypoint
├── data/words/          # Seed word lists grouped by theme
├── index.html           # Main HTML file
├── style.css            # Styling
├── game.js              # Game logic
├── server.py            # Flask backend
├── requirements.txt     # Python dependencies
├── tests/               # Pytest test files
├── word/                # Legacy word lists used by current gameplay
├── assets/              # Sounds
└── README.md            # Project docs
```


## Word Selection Engine v1

The backend now includes `engine/word_selector.py` with the interface:

- `select_next_word(user_id, theme_id)` (implemented as `select_next_word(conn, user_id, theme_id, ...)`)

Selection order for authenticated users:

1. due review words (`next_review_at <= now`)
2. high-mistake words (`times_wrong` descending)
3. unseen/new words
4. fallback random word in theme

Recent history is considered via the latest games and recently used words are avoided when possible.

Guest mode behavior:

- Guests use random selection within the requested theme (`guest_random` reason).
- Guests still cannot submit leaderboard entries.

### New API endpoint

- `GET /api/word/next?theme=<theme_id>`
  - Auth user: history/spaced-repetition aware selection
  - Guest: random in theme
- `POST /api/word/progress` (auth only) with `{ "word_id": <int>, "was_correct": <bool> }`
  - updates `times_seen`, `times_correct`, `times_wrong`, `last_seen_at`, `interval_days`, `next_review_at`

### Extension points

- Swap scoring logic in `engine/word_selector.py` for alternate models.
- Tune `recent_games_limit` and interval growth/reset behavior without changing API contracts.
