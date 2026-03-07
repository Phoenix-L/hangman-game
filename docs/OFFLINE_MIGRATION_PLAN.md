# Hangman: Offline Migration Plan

This document is a **design and migration plan only**. No code changes have been made. It describes how to add a fully offline, single-HTML mode while keeping the current Flask backend intact for development.

---

## Step 1 — Current Repository Analysis

### 1.1 Flask Backend Architecture

- **Entry:** `server.py` — Flask app with `static_folder='.'`, serves everything from repo root.
- **Database:** SQLite via `db.py`; default path `hangman.db`. Schema: `users`, `themes`, `words`, `games`, `word_progress`, `leaderboard_entries`.
- **Startup:** On import, `initialize_and_seed(DB_PATH)` runs: `init_db`, `clear_themes_and_words`, then `seed_words_from_files` from `data/` (top-level `*.txt` only).
- **Session:** Flask session stores `user_id` for auth; `SECRET_KEY` from env or default dev value.

### 1.2 API Endpoints Used by the Game

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves `index.html` |
| `/api/themes` | GET | List themes (id, name, description, word_count); used at startup to set `defaultThemeId` |
| `/api/word/next?theme=<id>` | GET | Next word for theme (auth: spaced-repetition engine; guest: random). Returns `word` (id, theme_id, value), `theme`, `theme_display`, `reason` |
| `/api/random_word` | GET | Fallback: single random word + theme + theme_display |
| `/api/game/result` | POST | Submit game outcome: word_id, theme_id, duration_ms, guesses, won → backend computes score, stores game, updates word_progress, creates leaderboard entry if logged in |
| `/api/me` | GET | Session: guest vs user (id, username) |
| `/api/auth/signup` | POST | Create user, set session |
| `/api/auth/login` | POST | Validate credentials, set session |
| `/api/auth/logout` | POST | Clear session |
| `/api/progress/summary` | GET | Words seen/mastered, accuracy_7d, streak_days, per-theme breakdown (requires auth) |

Static assets: `style.css`, `game.js`, `assets/correct.mp3`, `assets/wrong.mp3`, `assets/win.mp3`, `assets/lose.mp3`.

### 1.3 Word Selection Engine

- **Location:** `engine/word_selector.py`
- **Authenticated:** `select_next_word(conn, user_id, theme_id)` — excludes recent N games and “mastered today” words; then picks in order: due review → high mistake → new word → fallback random (all within theme).
- **Guest:** `select_guest_word(conn, theme_id)` — random word from theme.
- **Progress:** `update_word_progress(conn, user_id, word_id, was_correct=...)` — updates spaced-repetition fields (times_seen, times_correct, times_wrong, interval_days, next_review_at).

Engine depends on: DB connection, `words`/`word_progress`/`games` tables.

### 1.4 Database Logic

- **Schema:** `db.py` — `init_db()`, migrations for `password_hash`, games columns.
- **Vocabulary loading:** `seed_words_from_files()` uses `DEFAULT_WORD_DIRS = ("data",)`, `Path(directory).glob("*.txt")` (top-level only). Theme name = `file_path.stem.upper()` (e.g. `ket_animals.txt` → `KET_ANIMALS`). Each line (trimmed, lowercased) → one word row.
- **Helpers:** `list_themes`, `get_theme_name_by_id`, `theme_display_name(theme_name)` (e.g. `KET_ANIMALS` → `"Animals"`), `get_random_word`, `get_progress_summary`, etc.

### 1.5 Vocabulary Loading (Current)

- **Source:** `data/*.txt` (e.g. `ket_animals.txt`, `pet_travel.txt`). One word per line, lowercase.
- **Scripts:** `scripts/init_db.py` calls `initialize_and_seed(DEFAULT_DB_PATH)`; `scripts/seed_words.py` can seed from custom dirs. No existing “export to JS” step.

### 1.6 Frontend Gameplay Logic

- **Entry:** `game.js` — on load: `refreshAuth()` → `startGame()`.
- **startGame:** `GET /api/themes` → set `defaultThemeId` from first theme → `loadWord(updateDisplay)`.
- **loadWord:** `GET /api/word/next?theme=...` (cache-bust `?_=...`). On success: set `selectedWord`, `currentWordId`, `currentThemeId`, `currentThemeName`, `gameStartTime`, reset letters, callback. On failure: fallback `GET /api/random_word`.
- **Game loop:** Keyboard → update `correctLetters`/`wrongLetters` → `updateDisplay()` → `checkGameStatus()` (win/lose) → on end `submitGameResult(won)` (POST `/api/game/result`), play sound, show “Play Again”.
- **Progress tab:** `GET /api/progress/summary` → `renderProgress(summary)` (words seen/mastered, accuracy_7d, streak, per-theme). Share card uses canvas and download.
- **Auth:** Sign up / Log in / Log out call APIs above; UI toggles `auth-guest` / `auth-user` and forms.

### 1.7 Current Game Flow (Development Mode)

```
Browser
  → GET /api/themes
  ← themes (id, name, ...)
  → GET /api/word/next?theme=<id>
  ← Flask → get_connection → select_next_word (or select_guest_word) → DB
  ← { word: { id, theme_id, value }, theme, theme_display }
  → Frontend: selectedWord = value, currentWordId/currentThemeId/currentThemeName set, updateDisplay()
  … user plays …
  → POST /api/game/result { word_id, theme_id, duration_ms, guesses, won }
  ← Flask → _compute_accuracy_and_score, INSERT games, update_word_progress, leaderboard
  → Frontend: restart / load next word
```

---

## Step 2 — Backend Dependencies

### 2.1 What Requires Flask / Backend Today

| Concern | Backend dependency |
|--------|---------------------|
| **Fetching a new word** | `/api/word/next` and `/api/random_word` — DB + word selection engine. |
| **Themes list** | `/api/themes` — DB themes + word counts. |
| **Recording score / game** | `/api/game/result` — DB (games, word_progress, leaderboard_entries). |
| **Vocabulary source** | DB seeded from `data/*.txt` by Python at server start. |
| **Learning progress** | `/api/progress/summary` — DB (word_progress, games). |
| **Auth** | `/api/me`, signup, login, logout — Flask session + DB users. |
| **Leaderboard** | Backend has `/api/leaderboard/global`; frontend does not call it in current `game.js`. |

### 2.2 API Call Summary (from game.js)

- `GET /api/themes` — startGame
- `GET /api/word/next?theme=...` — loadWord (primary)
- `GET /api/random_word` — loadWord fallback
- `POST /api/game/result` — after win/lose
- `GET /api/progress/summary` — Progress tab
- `GET /api/me` — refreshAuth
- `POST /api/auth/signup` — signup
- `POST /api/auth/login` — login
- `POST /api/auth/logout` — logout

---

## Step 3 — Offline Architecture

### 3.1 Goal

- Run the game by **opening a single HTML file** in the browser (e.g. `index.html` or a dedicated `index-offline.html`), with **no server**.
- All logic runs in the browser.
- Vocabulary comes from a **pre-built JavaScript file** generated from `data/*.txt`.

### 3.2 Proposed File Layout for Offline

- **index-offline.html** (or reuse `index.html` with mode detection)  
  - Same UI as current (canvas, word, wrong letters, message, restart, theme hint, auth bar, Play/Progress, sounds).  
  - Loads: `style.css`, `vocab.js`, `game.js` (or an offline-specific bundle).  
  - No Flask; open from file or any static host.

- **vocab.js** (generated, not hand-edited)  
  - Single global object, e.g.:

  ```js
  const VOCAB = {
    KET_ANIMALS: ["animal", "ant", "bear", ...],
    KET_FOOD: ["apple", "bread", ...],
    PET_TRAVEL: ["plane", "train", ...]
  };
  const THEMES = [
    { id: "KET_ANIMALS", name: "KET_ANIMALS", display: "Animals", word_count: 28 },
    ...
  ];
  ```

  - Theme keys = file stems (uppercase) to mirror backend. `display` = `theme_display_name(theme_name)` (e.g. last segment title-cased).

- **game.js** (or **game-offline.js**)  
  - Same gameplay (keyboard, win/lose, draw hangman, sounds, restart).  
  - **Mode:** either a global flag (e.g. `const OFFLINE_MODE = true`) or **auto-detect**: e.g. try `fetch('/api/themes')` once; if it fails or not same-origin, use offline.  
  - When offline: no auth, no progress API, no game/result API; word selection and themes come from `VOCAB`/`THEMES`.

### 3.3 Data Flow (Offline)

- **Themes:** From `THEMES` (in vocab.js). No IDs from DB; use string theme key (e.g. `KET_ANIMALS`) as “theme id” for selection.
- **Word selection:** `selectWordOffline(themeKey)` in JS: pick random word from `VOCAB[themeKey]`, return `{ value, theme, theme_display }` (no word_id/theme_id needed for backend).
- **Score:** Optional: compute locally with same formula as server (`_compute_accuracy_and_score`) and show in UI only, or store in `localStorage` for a “local progress” view (no server).

### 3.4 What Stays Server-Only (Unchanged)

- All of `server.py`, `db.py`, `engine/word_selector.py`, `scripts/init_db.py`, `scripts/seed_words.py`.
- Development flow: run Flask, open `http://localhost:5000/` → current behavior (API, DB, auth, progress).

---

## Step 4 — Replacing API Calls with Local Functions (Offline Path)

### 4.1 Theme List

- **Dev:** `GET /api/themes` → `data.themes` (id, name, word_count, etc.).  
- **Offline:** Use `THEMES` from vocab.js. Map to same shape expected by existing UI where possible (e.g. `id` = theme key string or index).

### 4.2 Word Selection

- **Dev:** `GET /api/word/next?theme=<id>` → returns `word` object (id, theme_id, value), `theme`, `theme_display`.  
- **Offline:** Implement in JS, e.g.:

  ```js
  function selectWordOffline(themeKey) {
    const words = VOCAB[themeKey];
    if (!words || words.length === 0) return null;
    const value = words[Math.floor(Math.random() * words.length)];
    const themeDisplay = themeDisplayName(themeKey);
    return { word: { value }, theme: themeKey, theme_display: themeDisplay };
  }
  function themeDisplayName(themeName) {
    if (!themeName) return 'Vocabulary';
    const parts = themeName.trim().split('_');
    return parts.length ? parts[parts.length - 1].replace(/^\w/, c => c.toUpperCase()) : themeName;
  }
  ```

- **Game loop:** In offline mode, `loadWord()` calls `selectWordOffline(defaultThemeKey)` (or selected theme) and then sets `selectedWord`, `currentThemeName`; `currentWordId`/`currentThemeId` stay null so `submitGameResult` no-ops (or is skipped).

### 4.3 Game Result / Score

- **Dev:** `POST /api/game/result` with word_id, theme_id, duration_ms, guesses, won.  
- **Offline:** Do not call API. Optionally: compute score in JS (same formula as `_compute_accuracy_and_score`) and show “Your score: X” or store in localStorage for a simple “last score” or “today’s games” UI.

### 4.4 Auth and Progress

- **Offline:** No signup/login/logout; always “guest”. Hide or simplify auth bar (e.g. hide auth section when offline).  
- **Progress tab:** Either hide, or show a message “Progress is available when using the server,” or implement a minimal local summary from localStorage (e.g. words played today, last score) without backend.

---

## Step 5 — Preserving the Development Backend

- **Do not delete or replace** Flask, db, or engine code.
- **Two modes in the frontend:**
  - **Option A (explicit):** Build two entry points:  
    - Dev: `index.html` + `game.js` (current, uses API).  
    - Offline: `index-offline.html` + `vocab.js` + `game-offline.js` (or same `game.js` with `OFFLINE_MODE` set by that HTML).
  - **Option B (single codebase):** One `index.html`, one `game.js`. At startup, set `OFFLINE_MODE = true` if a query flag like `?offline=1`, or detect by `fetch('/api/themes').then(...).catch(() => { OFFLINE_MODE = true; ... })`. Then all fetch paths branch on `OFFLINE_MODE`.

- **Recommendation:** Single `game.js` with a **mode flag** (set by script tag or one detection fetch). If offline: use `VOCAB`/`THEMES` and local `selectWordOffline`; if online: keep current fetch logic. No duplication of draw/ keyboard/win/lose logic.

---

## Step 6 — Vocabulary Build Pipeline

### 6.1 Script Role

- **Input:** Same as backend: `data/*.txt` (top-level `.txt` only).  
- **Output:** Single JS file `vocab.js` (or `vocab-offline.js`) that defines:
  - `VOCAB`: object whose keys are theme names (e.g. `KET_ANIMALS`), values are arrays of lowercase words.
  - `THEMES`: array of `{ id, name, display, word_count }` for UI (id can be theme name string; display = last segment title-cased).

### 6.2 Implementation Outline

- **Language:** Python (fits repo; reuses path logic from db).
- **Location:** e.g. `scripts/build_vocab_js.py` or `scripts/export_vocab.py`.
- **Steps:**
  1. Use same file discovery as `db.py`: e.g. `Path("data").glob("*.txt")` (or take `data` as default, allow override).
  2. For each file: theme_name = stem.upper(); words = [line.strip().lower() for line in file if line.strip()].
  3. Build VOCAB dict and THEMES list (display name = last part of theme_name, title-cased).
  4. Write a single .js file: e.g. `const VOCAB = { ... }; const THEMES = [ ... ];` (or use a small template). Escape strings for JS if needed.
  5. Run as part of release/pre-package step; output path e.g. `vocab.js` in repo root or a dedicated `offline/` folder.

### 6.3 When to Run

- Manually before packaging offline bundle, or in CI when `data/*.txt` changes.  
- Optionally add to README: “To refresh offline vocabulary: `python scripts/build_vocab_js.py`.”

---

## Step 7 — UI Behavior (Offline)

- **Theme display:** Use `theme_display` from local selection (e.g. “Animals”) in the same `#theme-hint` element.
- **Score:** Show in message or a small “Score: X” area after game end (computed locally if desired); no server submit.
- **Restart:** Same “Play Again” button → call `loadWord(updateDisplay)`; in offline, that uses local selection.
- **Sound effects:** Keep `<audio>` tags pointing to `assets/correct.mp3`, etc.; paths relative to HTML file so they work when opened from file if assets sit next to HTML (or embed base64 if true single-file is required later).
- **Keyboard:** Unchanged; same keydown handler.
- **Auth:** In offline mode, hide auth bar or show “Offline mode — no sign in.” Progress tab: hide or show “Use the online version for progress.”

---

## Step 8 — Migration Plan (Implementation Order)

### Phase 1 — Vocabulary build and offline data

1. **Add `scripts/build_vocab_js.py`**
   - Read `data/*.txt` (same rules as db: top-level only, stem = theme name).
   - Build VOCAB object and THEMES array (with display names).
   - Write `vocab.js` (e.g. to repo root or `offline/vocab.js`).
   - Document in README.

2. **Generate and commit `vocab.js`** (or add to .gitignore and document “run script to generate”). Prefer generating in CI or at release so offline bundle is always in sync with `data/`.

### Phase 2 — Frontend mode and local word selection

3. **Introduce offline mode in frontend**
   - Add a way to set offline mode: e.g. `window.OFFLINE_MODE = true` from a script in a dedicated HTML, or one-time `fetch('/api/themes').catch(() => { window.OFFLINE_MODE = true; })` and then call `startGame()`.
   - In `game.js`, guard all API calls with `if (window.OFFLINE_MODE) { ... } else { fetch(...) }` (or extract “word loader”, “auth”, “progress” behind small adapters).

4. **Implement local word selection (offline only)**
   - Add `selectWordOffline(themeKey)` and `themeDisplayName(themeName)` in game.js (or a small `word-selector-offline.js`).
   - When offline: themes from `THEMES`; default theme = first theme’s id (string). `loadWord` uses `selectWordOffline` and sets `selectedWord`, `currentThemeName`; leave `currentWordId`/`currentThemeId` null so `submitGameResult` is effectively no-op.

5. **Optional: local score**
   - Port `_compute_accuracy_and_score` to JS; after win/lose in offline mode, compute and show score (and optionally save to localStorage).

### Phase 3 — Offline entry and UI tweaks

6. **Offline HTML entry**
   - Either add `index-offline.html` that loads `vocab.js` then `game.js` and sets `OFFLINE_MODE = true`, or keep single `index.html` and load `vocab.js` only when building for offline (or always load; harmless if unused) and set mode by query or detection.

7. **UI for offline**
   - When `OFFLINE_MODE`: hide auth section (or show “Offline” label). Progress tab: either hide or show “Progress is available in the online version.”
   - Ensure theme hint, restart, sounds, keyboard work without any server.

### Phase 4 — Preserve dev path and test

8. **Keep development path unchanged**
   - No removal of Flask routes or db/engine code. Dev: run `python server.py`, open `http://localhost:5000/` → current behavior.
   - Optional: `index-offline.html` only used when opening file directly or from a static server; main `index.html` stays the default for Flask.

9. **Testing**
   - **Dev:** Existing tests (pytest for server, db, engine) unchanged; manual test in browser with Flask.
   - **Offline:** Open `index-offline.html` (or index with `?offline=1`) in browser without starting Flask; verify: themes appear, word loads, play win/lose, theme hint, restart, sounds. No 404s for `/api/*` when offline path is used.
   - **Vocabulary:** Run `build_vocab_js.py` and diff against `data/*.txt` word lists to ensure consistency.

### Files to create

| File | Purpose |
|------|---------|
| `scripts/build_vocab_js.py` | Reads `data/*.txt`, writes `vocab.js` (VOCAB + THEMES). |
| `vocab.js` | Generated; consumed by offline HTML. |
| `index-offline.html` (optional) | Clone of index that sets OFFLINE_MODE and loads vocab.js. |

### Files to modify

| File | Change |
|------|--------|
| `game.js` | Mode flag; when offline use THEMES/VOCAB and selectWordOffline; skip or no-op fetch for word, game/result, themes, auth, progress. Optionally hide auth/progress UI when offline. |
| `index.html` (if single entry) | Optionally load vocab.js and set mode via query or detection. |
| `README.md` (or docs) | Describe offline build: run `python scripts/build_vocab_js.py`, then open `index-offline.html` (or equivalent). |

### What not to change

- `server.py`, `db.py`, `engine/word_selector.py`, `scripts/init_db.py`, `scripts/seed_words.py` — no deletions or behavior change for dev mode.

---

## Summary

- **Development mode:** Unchanged; Flask + DB + current API + current frontend when served from Flask.
- **Offline mode:** Open one HTML file (with optional separate `vocab.js` and same `game.js`); vocabulary from generated `vocab.js`; word selection and theme display in JS; no auth/progress/backend; optional local score and localStorage.
- **Bridge:** One codebase in `game.js` with an offline flag and local implementations for themes and word selection, plus a small build script to turn `data/*.txt` into `vocab.js`.

This plan is ready for implementation; no code has been modified yet.
