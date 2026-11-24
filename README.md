# BIG BANG

BIG BANG is the existing local application for managing store entities, reviewing and editing assigned store resources, preparing policy files, and exporting Shopify or SHOPLINE packages. This repository preserves the V35 source handoff and the canonical resource archive at the paths expected by the application.

## Baseline and provenance

- Project version: V35 (app.py reports 11.4.3-V35).
- Source: BIG_BANG_V35_GITHUB_SOURCE_HANDOFF.zip, recovered from the existing BIG BANG project handoff.
- Resources: resources/BIG_BANG_V35_DUAL_600.zip, SHA-256 b5686ae01ffdcfee0746ed7e1d34fc3acb291ab5d0d02d98a3bfdb2f13af7aac.
- Mappings: 300 existing store/template identities, each with Shopify and SHOPLINE resources; mapping identities are retained in data/bigbang.sqlite3 and resource paths.
- Original compiled package: BIG_BANG_ORIGINAL_V35_COMPLETE.zip contains only BIG_BANG.exe. The original native launcher build source and reproducible build project were not included.

The source uses its existing root-level Python modules and static frontend. These paths are runtime dependencies; do not move them solely to match a proposed directory layout. The exact V35 ZIP bytes are stored as `resources/BIG_BANG_V35_DUAL_600.zip.xz` to fit the repository upload transport. `python scripts/materialize_resources.py` restores the original `resources/BIG_BANG_V35_DUAL_600.zip` path and verifies its SHA-256 before use; application startup also restores it automatically when needed. This does not alter the archive contents or the 300 fixed mappings.

## Platform behavior

SHOPLINE homepages read product handles through native SLINE all_products first and retain the configured fallback. Offline checks confirm the configured handles exist in the corresponding published rows in the bundled migration CSV. The fallback is not Ajax-only.

The V35 resource archive contains 3,600 Shopify files and 3,300 SHOPLINE files. Shopify bundles use four Liquid files, one product CSV, and seven policies. SHOPLINE bundles use three SLINE files, one migration CSV, and seven policies. The two platforms are exported independently.

Offline validation does not establish live Shopify/SHOPLINE import success, image availability or rights, storefront rendering, legal accuracy, or platform approval.

## Run locally

1. Use Python 3.10 or later.
2. Create and activate a virtual environment.
3. Install runtime dependencies with python -m pip install -r requirements.txt.
4. Start with python desktop_start.py on Windows or python launcher.py on a local development machine.
5. Open http://127.0.0.1:8787/ and use the one-time administrator password printed during setup.

The application binds to loopback by default. Do not expose it to a public network without a separate security review. Add local API credentials only to .env; start from .env.example and never commit .env.

For isolated development, set BIGBANG_DATA_DIR to a disposable data directory containing copies of the clean seed database and asset manifest. Do not point tests at a live runtime database.

## Quality checks

Install development dependencies with python -m pip install -r requirements-dev.txt, then run:

    python scripts/verify_release.py
    python scripts/run_regression_tests.py

CI also compiles all Python, checks JavaScript syntax, runs browser layout checks at the configured viewport sizes, and builds and smoke-tests a Windows package. A test with mocked APIs is labelled as simulated. A real platform test requires an authorized test store and is reported separately.

## Branches and releases

- main: stable baseline and accepted releases.
- develop: integration branch for the next version.
- feature/*: new capabilities.
- fix/*: defects and regressions.
- release/*: release preparation and hardening.

Merge changes through pull requests after CI passes. A version tag triggers release validation and Windows packaging; the release job is blocked if validation or packaging fails. Each release attaches an inventory and SHA-256 manifest, the changelog, test status, and known limitations. The Windows build is generated from the available Python source and must not be represented as the original EXE.

## Current limitations

- No live SHOPLINE storefront or Shopify admin account was included for end-to-end verification.
- The original V35 EXE has no source project or reproducible build instructions in the supplied files.
- Existing README history contains older V8–V11 descriptions; this file and HANDOFF.md describe the recovered V35 baseline.
