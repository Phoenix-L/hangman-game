# Weekly vocabulary package contract

## Format and checksum

The learning application emits a UTF-8 JSON document using format hangman-weekly-v1. Canonical JSON is UTF-8, sorted object keys, no insignificant whitespace, and ensure_ascii=false. The package payload checksum is SHA-256 of the canonical JSON object without payload_sha256; the exported file includes that checksum as a transport field.

Each package contains format, stable package_id, program_slug, week_number, and items. Each item contains source_term_id, canonical_term, display_term, pronunciation_text, definition, part_of_speech, category, aliases, and source_days. Only approved items are included.

## Identity and categories

source_term_id is learning:{program_slug}:term:{sha256(normalized_term)[:24]}, where normalization trims and case-folds whitespace. The only accepted Hangman categories are NEURO_FOUNDATIONS, NEURO_ANATOMY, NEURO_FUNCTION, and NEURO_CLINICAL.

## Receipt

Hangman emits hangman-weekly-receipt-v1 with package_id, payload_sha256, imported_at, secret-free database_id, inserted/updated/unchanged counts, mappings of source-term IDs to word IDs and categories, and receipt_sha256. The receipt checksum covers the canonical receipt object without receipt_sha256.

## State and retry rules

Learning batches move draft -> finalized -> exported -> published. Approval is per item and finalization is explicit. Finalized payloads are immutable. Hangman validates before one transaction, is additive, and requires explicit confirmation for writes. Identical package/receipt replay is a no-op; identity conflicts and malformed multi-item packages fail closed and roll back. Learning records only mappings belonging to approved exported items; partial receipts do not claim publication completion.

## Privacy and recovery

Packages and receipts contain vocabulary metadata and safe day provenance only. They contain no API keys, prompts, raw learning-log bodies, private evidence, emails, or secret paths. Back up the Hangman database, dry-run the package, import with explicit confirmation, return the receipt, and record it in Learning. If import fails, restore nothing automatically: inspect the validation error and retry only after correcting the package or environment.
+\n## Durable provenance and complete receipts\n\nHangman keeps weekly provenance in an additive external source-mapping table;\nit never replaces glossary word_metadata.source_term_id. A package audit row is\nunique by package_id and stores the canonical receipt, checksum, status, and\ncounts. A receipt must contain exactly one positive word mapping for every\npackage item, with matching category and operation counts. Partial receipts,\nduplicate mappings, conflicting package hashes, invalid week/day/alias types,\nand checksum or identity conflicts fail closed. Replaying the same package\nreturns the original receipt byte-for-byte and replaying that receipt in\nLearning is a no-op.\n
