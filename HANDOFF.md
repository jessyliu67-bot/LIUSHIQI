# BIG BANG V35 — recovered source handoff

This archive contains the existing V35 Python application source, static frontend, tests, documentation, clean template seed database and byte-identical V35 dual-platform resource ZIP. It is not a replacement application. Preserve relative paths.

## Current verified facts
- The seed database contains 300 template rows and 300 mapped store rows, zero entities, zero domain rows and zero company document rows. SQLite integrity check passed.
- The original V35 resource ZIP has 6,900 members and passes ZIP CRC validation. SHA-256 matches the existing V35 resource manifest.
- The derived Shopify compatibility ZIP in data/uploads is intentionally omitted; bootstrap_v16.py regenerates it from the canonical resources ZIP.
- No live SHOPLINE rendering or Windows executable startup test is claimed here. Existing QA JSON files are historical artifacts, not tests performed during this handoff.
- The original compiled Windows launcher build source was not found in the recovered directory. The Python launcher.py and desktop_start.py are included; the prior compiled executable is available separately. Do not invent missing native launcher source or claim a reproducible EXE build until verified.
- Older README/PROJECT_SCOPE descriptions are retained for provenance and may be stale. Treat code, resource manifest and this handoff as the current baseline, and update documentation after verification.

## Before publishing
Use a private repository. Review all contents for sensitive or proprietary data. Never commit live databases, company documents, credentials, uploads, historical deployments or backups. The provided seed database must remain a clean seed, not the runtime database. Keep the resource archive intact and preserve its mapping. Use GitHub Releases for the separately delivered EXE ZIP, not ordinary Git blobs. Verify actual write permissions with a commit. If permission is denied, report the error without claiming success.

## Local development
Create an isolated Python environment, install requirements.txt, copy the clean data directory into an isolated runtime location, and set BIGBANG_DATA_DIR to that location for backend development. Inspect app.py startup configuration and the launcher before running. Run bootstrap_v16.py to verify the resource archive and regenerate the derived archive, then run tests against disposable data. Verify platform behavior on an authorized test store before any production deployment.
