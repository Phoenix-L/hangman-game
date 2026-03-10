# Release v0.3.0 — Professional leaderboard & engagement features

**Release date:** (set when publishing)

## Highlights

- **User-aggregated leaderboard:** One row per player; ranking uses a combined score instead of raw per-game scores.
- **Time-decayed scoring:** Older game scores count less over time so active players can climb and inactive ones drift down.
- **Streaks & daily bonus:** Consecutive-day play increases rank; playing today adds a fixed bonus.
- **Leaderboard periods:** View **Today**, **This Week**, or **All Time** from the Progress page.
- **Game-over feedback:** After each game, see score, accuracy, your rank, and current streak (when logged in).
- **Word selector fixes:** Lower repetition and no re-selection of words you’ve already answered correctly.

---

## Leaderboard system

- **Ranking formula:**  
  `leaderboard_score = time-decayed game scores + streak bonus + daily activity bonus`  
  (plus a reserved hook for future daily challenges.)
- **Decay:** Each game score is multiplied by `0.94^age_in_days` so recent play matters more.
- **Streak:** Consecutive days played add up to 30×8 points; gap of more than one day resets streak to 1.
- **Daily bonus:** 50 points if the user played on the reference date (today for “today” view).

---

## API changes

- **`GET /api/leaderboard/global`**  
  - Query: `period=today|week|all` (default `all`), `limit=N`.  
  - Response: one entry per user with `rank`, `username`, `leaderboard_score`, `current_streak_days`, `last_active`, `is_current_user`.
- **`POST /api/game/result`**  
  - Response now includes `rank`, `leaderboard_score`, and `current_streak_days` for authenticated users when applicable.

---

## UI changes

- **Play page:** Mini leaderboard “This Week’s Top Players” (top 5) with rank, player, leaderboard score, and streak; current user highlighted.
- **Progress page:**  
  - Leaderboard tabs: **Today** | **This Week** | **All Time**.  
  - Full table: rank, player, score, streak, last active.  
  - Self-summary card: your rank, leaderboard score, streak; placeholder for “Daily challenge”.
- **Game over:** Message shows score, accuracy, “Your Rank: #N”, and “Streak: N day(s)” when available.

---

## Database

- New table **`user_stats`**: one row per user (`total_games`, `total_score`, `current_streak_days`, `last_played_date`, `lifetime_xp`).  
- Filled on each completed game and backfilled for existing users with completed games.  
- Existing tables (`games`, `leaderboard_entries`) and game recording are unchanged.

---

## Testing

- New tests in `tests/test_leaderboard_aggregated.py` (streak, decay, bonuses, one-row-per-user, period filter).
- `tests/test_game_result_and_leaderboard.py` updated for the new leaderboard API and response shape.
- Full test suite: 35 tests passing.

---

## Documentation

- **docs/system_architecture.md:** `user_stats`, leaderboard formula, streak rules, periods, extension point.
- **docs/product_features_report.md:** Leaderboard API and UI (Play mini, Progress full, game-over rank/streak).
- **README.md:** Note on user-aggregated leaderboard and period support.

---

## Upgrade notes

- Run the app or `scripts/init_db.py` as usual; `user_stats` is created and backfilled automatically.
- No breaking changes to gameplay or to raw game/leaderboard storage; guest mode and existing flows are preserved.
