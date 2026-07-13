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

`word_metadata` is created additively by `db.init_db()`. The importer inserts
missing themes, words, and metadata and updates only the matching glossary
metadata. It never clears vocabulary, deletes words, or rewrites games,
progress, users, or leaderboard rows. Re-running the importer is idempotent.

## Validation and offline mode

Run `python scripts/validate_neurobiology_glossary.py` before importing and
`python scripts/import_neurobiology_glossary.py --db-path PATH` to import. The
existing `scripts/build_vocab_js.py` includes approved glossary answers in the
generated offline `vocab.js` using the same four theme keys.

Only ASCII letters are guessable in glossary answers. Spaces and punctuation
are revealed automatically, and the original display term is used for the
answer and browser pronunciation.
