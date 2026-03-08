# System Architecture Document

## Scope

This document reflects the architecture currently implemented in code and excludes future roadmap assumptions.

---

## 1. System Overview

This repository implements a browser-based Hangman learning game using a client-server architecture:

- **Frontend**: static HTML/CSS/JavaScript served by Flask
- **Backend**: Flask API server (`server.py`) providing auth, game, selection, leaderboard, and progress endpoints
- **Domain logic**: word selection and spaced repetition in `engine/word_selector.py`
- **Persistence**: SQLite schema and data access utilities in `db.py`
- **Vocabulary source**: plain text files under `data/*.txt`, loaded into DB through seeding logic

The runtime word source is the database (`words` table); text files are used for seeding, not request-time gameplay reads.

---

## 2. Major Components and Responsibilities

## 2.1 Frontend UI (Presentation)

**Files**: `index.html`, `game.js`, `style.css`

Responsibilities:

- Render gameplay screen (canvas hangman, masked word, wrong letters, status message)
- Handle keyboard input (`a-z`) and local game loop state
- Call backend APIs for next word, game result submission, auth, and progress
- Toggle between Play and Progress views
- Generate a shareable progress PNG from canvas
- Play sound effects for correct/wrong/win/lose events

## 2.2 Flask API Server (Application)

**File**: `server.py`

Responsibilities:

- Serve static frontend files and REST JSON APIs
- Initialize DB + seed vocabulary at startup
- Manage session-based authentication (`session['user_id']`)
- Route requests to domain/data logic:
  - word selection
  - progress updates
  - score computation and game persistence
  - leaderboard and progress summary

## 2.3 Word Selection Engine (Domain)

**File**: `engine/word_selector.py`

Responsibilities:

- Select next word for authenticated users with priority:
  1. due review
  2. high mistake
  3. new word
  4. random fallback
- Select random themed word for guests
- Update spaced repetition state after outcomes
- Avoid recently used word IDs for users

## 2.4 Database Layer (Data Access)

**File**: `db.py`

Responsibilities:

- Define SQLite schema (`users`, `themes`, `words`, `games`, `word_progress`, `user_word_progress`, `leaderboard_entries`)
- Initialize and migrate schema-compatible changes
- Seed themes/words from `data/*.txt`
- Provide utility functions for users, themes, leaderboard, and progress summary queries

## 2.5 Seed / Initialization Scripts

**Files**: `scripts/init_db.py`, `scripts/seed_words.py`

Responsibilities:

- `init_db.py`: initialize schema and seed vocabulary
- `seed_words.py`: explicit vocabulary reload/seed flow from `data/*.txt` with duplicate-safe inserts and console logs

---

## 3. Component Interaction Map

At runtime, the browser communicates only with Flask via HTTP; Flask uses domain logic and SQLite.

```text
Browser (index.html + game.js)
        |
        | HTTP (JSON)
        v
Flask API Server (server.py)
        |
        | function calls
        +--> Word Selection Engine (engine/word_selector.py)
        |
        +--> DB Access Utilities (db.py)
                        |
                        v
                   SQLite DB
```

Vocabulary ingestion path is separate from gameplay path:

```text
data/*.txt
   |
   v
scripts/seed_words.py or db.initialize_and_seed()
   |
   v
SQLite: themes + words tables
   |
   v
Runtime selection APIs (/api/word/next, /api/random_word)
```

---

## 4. Architecture Diagrams (ASCII)

## 4.1 System Architecture

```text
+---------------------------+
|       Browser Client      |
|  index.html / game.js UI  |
+-------------+-------------+
              |
              | HTTP/JSON
              v
+---------------------------+
|      Flask Web Server     |
|         server.py         |
|---------------------------|
| Auth Endpoints            |
| Game / Word APIs          |
| Leaderboard / Progress    |
+------+--------------------+
       |
       | calls
       +--------------------+
       |                    |
       v                    v
+---------------+   +----------------+
| Word Selector |   |   DB Utilities |
|   (engine/)   |   |     (db.py)    |
+-------+-------+   +--------+-------+
        \                  /
         \                /
          v              v
           +----------------+
           |   SQLite DB    |
           +----------------+
```

## 4.2 Data Flow (Vocabulary to Gameplay)

```text
+------------------+
|  data/*.txt      |
|  theme wordlists |
+--------+---------+
         |
         v
+------------------+
| Seed Process     |
| init_db.py /     |
| seed_words.py    |
+--------+---------+
         |
         v
+------------------+
| SQLite words     |
| + themes tables  |
+--------+---------+
         |
         v
+------------------+
| Selection Engine |
| (DB queries)     |
+--------+---------+
         |
         v
+------------------+
| /api/word/next   |
| JSON response    |
+--------+---------+
         |
         v
+------------------+
| Frontend renders |
| gameplay state   |
+------------------+
```

## 4.3 Gameplay Request Flow

```text
Browser
  |
  | GET /api/word/next?theme=<id>
  v
Flask route: get_next_word()
  |
  | if logged in -> select_next_word(...)
  | else         -> select_guest_word(...)
  v
SQLite (words/games/user_word_progress)
  |
  v
Selected word + review status
  |
  v
JSON response to browser
  |
  v
Browser updates selectedWord and renders masked letters
```

---

## 5. API-Centric Runtime Flows

## 5.1 Word Retrieval and Play Loop

1. Frontend fetches themes (`/api/themes`) at startup and stores first theme ID.
2. Frontend requests next word (`/api/word/next?theme=<id>`).
3. Backend selects word via engine (auth) or guest random strategy.
4. Frontend runs local keyboard gameplay.
5. On win/loss, frontend posts `/api/game/result` with duration and guess counts.
6. Backend computes score and persists game; for authenticated users it also updates progress and leaderboard.

## 5.2 Authentication Flow

1. User signs up/logs in (`/api/auth/signup`, `/api/auth/login`).
2. Flask writes `session['user_id']`.
3. Frontend calls `/api/me` to render guest vs logged-in UI.
4. Logout clears session via `/api/auth/logout`.

## 5.3 Progress Flow

The learning scheduler persists per-user state in `user_word_progress` and updates it with a simplified SM-2-like rule after each completed game.


1. Frontend opens Progress tab.
2. Calls `/api/progress/summary`.
3. Backend aggregates words seen/mastered, 7-day accuracy, streak, and per-theme stats.
4. Frontend renders summary and can export share card PNG.

---

## 6. System Layers

## 6.1 Presentation Layer

- Browser-rendered UI (`index.html`, `style.css`)
- Interaction and state management in `game.js`
- Handles view toggles, keyboard input, and rendering feedback

## 6.2 Application Layer

- Flask route handlers in `server.py`
- Session/auth guard checks
- Request validation and response shaping
- Score computation and endpoint orchestration

## 6.3 Domain Layer

- Selection policy and repetition behavior in `engine/word_selector.py`
- Encapsulates learning strategy independent of HTTP specifics

## 6.4 Data Layer

- SQLite schema and query helpers in `db.py`
- Vocabulary files (`data/*.txt`) + seeding scripts as ingestion source

---

## 7. Data Model Summary

Core tables and meaning:

- `users`: account identity and password hash
- `themes`: vocabulary themes
- `words`: words scoped by theme (`UNIQUE(theme_id, value)`)
- `games`: per-game outcomes, guess metrics, duration, computed score
- `word_progress`: spaced repetition state per (user, word)
- `leaderboard_entries`: per-game score records linked to game/user (legacy; still written for each completed game).
- `user_stats`: one row per user for aggregated leaderboard (total_games, total_score, current_streak_days, last_played_date, lifetime_xp). Updated on each game result; used for ranking.

**Leaderboard ranking (user-aggregated):** Each user appears once. Rank is by `leaderboard_score`:

- **Formula:** `leaderboard_score = SUM(score * POWER(decay_factor, age_in_days)) + streak_bonus + daily_activity_bonus + challenge_bonus_hook`
- **Defaults (db.py):** decay_factor=0.94, streak_bonus = min(current_streak_days, 30)*8, daily_activity_bonus=50 if played today, challenge_bonus_hook=0 (future daily challenge).
- **Streak rules:** First play or gap > 1 day → 1; played yesterday → +1; already played today → unchanged.
- **Periods:** `today` (games today), `week` (last 7 days), `all` (lifetime_xp from user_stats).
- **Extension:** Set `LEADERBOARD_CHALLENGE_BONUS_HOOK` or add daily challenge logic for extra bonus.

---

## 8. Architectural Characteristics

1. **Client-server architecture** with browser UI and Flask JSON APIs.
2. **Database-driven runtime**: words selected from SQLite, not directly from files at request time.
3. **Modular domain logic**: selection/repetition isolated in `engine/word_selector.py`.
4. **Session-based authentication**: simple cookie-backed login state.
5. **Synchronous request processing**: direct DB operations in request lifecycle.
6. **File-to-DB vocabulary pipeline**: `data/*.txt` is canonical source, seed process loads DB.
7. **Single-process simplicity**: minimal deployment complexity suitable for MVP/small workloads.

---

## 9. Architectural Limitations (Current Implementation)

1. **Single-process Flask app** (`app.run(debug=True)` in module entry): no built-in horizontal scaling strategy.
2. **SQLite as primary store**: simple and reliable for small scale, but limited write concurrency for larger multi-user loads.
3. **No caching layer**: repeated reads (themes, leaderboard, random word) always hit DB.
4. **No async/background jobs**: all score/progress updates happen inline during request handling.
5. **Session model is basic**: no advanced features like refresh tokens, MFA, role model, or device management.
6. **Frontend theme selection is implicit**: startup uses first theme ID from `/api/themes`; no explicit theme picker control in UI.
7. **No API rate limiting / observability stack** in current code (e.g., centralized metrics/tracing).

---

## 10. Evidence Pointers (Implementation Anchors)

- API routes, auth/session, score flow: `server.py`
- Selection/repetition logic: `engine/word_selector.py`
- DB schema, seed and query helpers: `db.py`
- Seeding scripts: `scripts/init_db.py`, `scripts/seed_words.py`
- Frontend gameplay/progress/auth logic: `index.html`, `game.js`, `style.css`
- Vocabulary source files: `data/*.txt`
- Behavioral verification examples: tests in `tests/`

