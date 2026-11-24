# BIG BANG Repository Instructions

## Source and change control

- All changes must be based on the existing BIG BANG source in this repository.
- Do not replace BIG BANG with a newly written substitute system without explicit user authorization.
- Do not remove existing product behavior, routes, workflows, database fields, or platform support during an upgrade. Document any approved removal and migration.
- Preserve the existing runtime paths and import relationships. Do not reorganize files solely to match a proposed directory diagram.
- Never replace a newer resource archive with an older one. Verify its SHA-256 against `data/ASSET_MANIFEST.json` before activation.
- Preserve all existing 300 template identities and product-to-template mappings. Never randomize or infer mappings while migrating resources.
- Shopify and SHOPLINE are separate platform adapters. Do not assume Liquid is compatible with SLINE or that one platform's CSV is valid for the other.
- Keep original resource archives immutable. Derived exports must be generated separately and include provenance.

## Quality and release requirements

- Record every code or resource change in `CHANGELOG.md`.
- Run the regression suite after each code or resource change. Add a regression test for each fixed defect.
- CI must pass before a release tag or GitHub Release is created. A mock or offline result must never be described as a live-platform test.
- Release notes must state version, source/resource inventory, SHA-256 hashes, change record, test results, and known limitations.
- Keep the clean seed database separate from runtime data. Never commit company documents, uploaded files, delivery history, runtime databases, or backups.
- Never put real API keys, passwords, license documents, bank details, or other sensitive data in source control. Use environment variables and `.env.example` placeholders.
- Do not invent product specifications, features, company facts, authorization, or test outcomes.

## Frontend and store-resource design

- All new website code and new resource filenames must use English. Preserve existing resource filenames when changing them would break the source archive or mappings; document the compatibility constraint.
- Use square corners. Do not add rounded cards, rounded buttons, pill labels, or circular icon backgrounds.
- Use high-contrast light text on dark backgrounds.
- Avoid repetitive AI-style layouts built from a large image followed by tiny feature cards or mechanical text strips. Prefer readable editorial layouts with clear hierarchy.
- Product rendering for SHOPLINE must use the verified native `all_products` path first and retain the tested fallback. Do not revert to an Ajax-only product loader.

## Required checks

- `python scripts/verify_release.py`
- `python -m pytest -q`
- `node --check` for each JavaScript file under `static/`
- Playwright responsive checks at 320, 375, 390, 430, 768, 1024, 1440, and 1920 CSS pixels.
- Live platform checks must be separately authorized and reported as live only after they run against an actual test store.
