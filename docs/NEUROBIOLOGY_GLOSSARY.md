# Neurobiology glossary integration

The repository-owned master glossary is `data/source/neurobiology_glossary.csv`.
It contains the 17 supplied concepts, including the normalized canonical answer
`stimulus` with `stimuli` retained as plural metadata.

## Theme mapping

The importer uses this deterministic mapping:

| Glossary category | Hangman theme |
| --- | --- |
| Cellular neuroscience | `NEURO_FOUNDATIONS` |
| Neuroanatomy | `NEURO_ANATOMY` |
| General anatomy and physiology | `NEURO_ANATOMY` |
| Sensory systems | `NEURO_FUNCTION` |
| Motor systems | `NEURO_FUNCTION` |
| Neurological disorders | `NEURO_CLINICAL` |

The initial row counts are 2 foundations, 11 anatomy, 2 function, and 2
clinical terms.

## Database safety

`word_metadata` is created additively by `db.init_db()`. Application startup
and `scripts/init_db.py` use the additive path. The importer inserts
missing themes, words, and metadata and updates only the matching glossary
metadata. It never clears vocabulary, deletes words, or rewrites games,
progress, users, or leaderboard rows. Re-running the importer is idempotent.

The destructive development-only path is named `reset_and_seed_database()` and
is reachable from `scripts/init_db.py` only with both
`--reset-destructive --confirm-destructive-reset`. It is never called by
`server.py` or normal bootstrap.

If an old database contains the pre-migration `word_progress` shape, normal
initialization renames that legacy table to `word_progress_legacy` before
creating the current additive table; it does not drop the legacy rows.

## Validation and offline mode

Run `python scripts/validate_neurobiology_glossary.py` before importing and
`python scripts/import_neurobiology_glossary.py --db-path PATH` to import. The
existing `scripts/build_vocab_js.py` includes approved glossary answers and
validated immutable published weekly packages in the generated offline
`vocab.js` using the same four theme keys. Weekly package files are stored
under `data/source/weekly_packages/`; their checksums and item contracts are
verified without opening SQLite. Exact terms already present in the same
category are deduplicated, while category or source-identity conflicts fail
closed.

Online package import updates SQLite but intentionally does not rewrite
offline assets. The committed Week 1 package has 54 items, 5 same-category
deduplications, and 49 net additions, producing 1501 offline words to match
the published online vocabulary.

Only ASCII letters are guessable in glossary answers. Spaces and punctuation
are revealed automatically, and the original display term is used for the
answer and browser pronunciation.
