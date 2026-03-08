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
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Open your browser and go to `http://localhost:5000`.

## Offline mode

You can run the game without the Flask server by opening a single HTML file in your browser.

1. Generate the vocabulary file from `data/*.txt` (run whenever you change the word lists):

   ```bash
   python scripts/build_vocab_js.py
   ```

2. Open **index-offline.html** in your browser (e.g. double-click the file or drag it into the browser). No server is required.

   - Vocabulary and themes come from **vocab.js** (generated in step 1).
   - Word selection is random within the first theme; theme hint and score are shown locally.
   - Sign-in and the Progress dashboard are disabled (they require the server).

**To run from another folder** (e.g. a USB stick or shared folder), copy these files into one folder and open `index-offline.html`:

- `index-offline.html`
- `vocab.js` (exact filename)
- `game.js`
- `style.css`
- `assets/` (folder with `correct.mp3`, `wrong.mp3`, `win.mp3`, `lose.mp3`)

Development mode (Flask + database) is unchanged: use `index.html` at `http://localhost:5000` for full features (auth, progress, leaderboard).

## Vocabulary workflow

- Store vocabulary only in `data/*.txt` (one word per line, one theme per file).
- Use the filename (without extension) as the theme identifier.
- Load/update words in SQLite with:

```bash
python scripts/seed_words.py
```

## Run tests

```bash
pytest -q
```

## API endpoints

- `GET /api/random_word` - random word from the SQLite `words` table.
- `GET /api/themes` - returns seeded themes and word counts from SQLite.


## Auth endpoints (MVP)

- `POST /api/auth/signup` with JSON `{ "username": "...", "password": "..." }`
- `POST /api/auth/login` with JSON `{ "username": "...", "password": "..." }`
- `GET /api/me` returns guest/user session info
- `POST /api/leaderboard_entries` requires login (guests receive `401`)
- `POST /api/game/result` stores completed game results and computes score server-side
- `GET /api/leaderboard/global?theme=<theme_id>&limit=50` returns ranked global scores

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
├── data/                # Vocabulary files (*.txt), one theme per file
├── index.html           # Main HTML file
├── style.css            # Styling
├── game.js              # Game logic
├── server.py            # Flask backend
├── requirements.txt     # Python dependencies
├── tests/               # Pytest test files
├── assets/              # Sounds
└── README.md            # Project docs
```


## Word Selection Engine v1

The backend now includes `engine/word_selector.py` with the interface:

- `select_next_word(user_id, theme_id)` (implemented as `select_next_word(conn, user_id, theme_id, ...)`)

Selection order for authenticated users:

1. due review words (`next_review <= now`)
2. difficult words (high wrong count / fail-rate)
3. unseen/new words
4. fallback random word in theme

Recent history is considered via the latest games and recently used words are avoided when possible.

Guest mode behavior:

- Guests use random selection within the requested theme (`guest_random` reason).
- Guests still cannot submit leaderboard entries.

### New API endpoint

- `GET /api/word/next?theme=<theme_id>`
  - Auth user: learning-priority selection (review -> difficult -> new -> fallback)
  - Guest: random in theme
  - Response includes `review_status` in `{ "review", "difficult", "new", "random_fallback", "guest_random" }`
- `POST /api/word/progress` (auth only) with `{ "word_id": <int>, "was_correct": <bool> }`
  - updates `user_word_progress` using a simplified SM-2-like rule

## Manual game-result + leaderboard flow

1. Start server: `python server.py`
2. Fetch available themes:
   ```bash
   curl -s http://localhost:5000/api/themes
   ```
3. Login or sign up and keep session cookies (example with signup):
   ```bash
   curl -i -c cookies.txt -X POST http://localhost:5000/api/auth/signup \
     -H "Content-Type: application/json" \
     -d '{"username":"score_user","password":"secret123"}'
   ```
4. Submit game result (replace `word_id`/`theme_id` with real values):
   ```bash
   curl -i -b cookies.txt -X POST http://localhost:5000/api/game/result \
     -H "Content-Type: application/json" \
     -d '{"word_id":1,"theme_id":1,"duration_ms":12000,"guesses":{"correct":5,"wrong":1},"won":true}'
   ```
5. Read the global leaderboard:
   ```bash
   curl -s "http://localhost:5000/api/leaderboard/global?theme=1&limit=50"
   ```

### Extension points

- Swap scoring logic in `engine/word_selector.py` for alternate models.
- Tune `recent_games_limit` and interval growth/reset behavior without changing API contracts.


## Progress dashboard + share card (MVP)

- Open **Progress** tab in the app to see:
  - words seen
  - words mastered
  - 7-day accuracy
  - per-theme breakdown
  - streak days
- Use **Share Progress Card** to generate a PNG card in-browser (Canvas) and download it for social sharing.
- Mastery rule used by backend summary: `times_correct >= 3` and `interval_days >= 7`.


## Learning engine scheduling model

For authenticated users, the engine stores per-user/per-word state in `user_word_progress` and applies:

- **Correct outcome**: `correct_count += 1`, `ease_factor += 0.05` (max 3.0), `interval = round(interval * ease_factor)`, `next_review = now + interval days`
- **Incorrect outcome**: `wrong_count += 1`, `ease_factor -= 0.2` (min 1.3), `interval = 1`, `next_review = now + 1 day`

This enables due-review prioritization and difficult-word resurfacing without changing frontend gameplay flow.
