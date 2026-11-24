# Changelog

## V35 (recovered baseline)

- Imported the existing BIG BANG application source from `BIG_BANG_V35_GITHUB_SOURCE_HANDOFF.zip`.
- Preserved the original V35 dual-platform resource archive and its 300 fixed Shopify/SHOPLINE template mappings.
- Added repository maintenance instructions and CI/release workflow definitions.
- Updated stale V12/V23 interface labels and platform documentation to describe the recovered V35 resources accurately.
- Added offline regression tests for all 300 mappings, 6,900 resource files, CSV headers, seven policies, SHOPLINE native handles, and non-empty second homepage sections.
- Added Playwright dashboard checks for the requested viewport widths, Python/JavaScript static checks, version/hash gates, and a Windows package smoke-test workflow.
- Stored the canonical ZIP as an XZ-compressed byte stream for repository transport. Startup and CI restore and SHA-256 verify the original ZIP at its existing runtime path; archive contents and mappings are unchanged.
- Offline verification performed during import: Python byte-compilation, JavaScript syntax checks, SQLite integrity, release checks (13/13), and V35 resource regression tests (6/6).
- The complete pytest suite, Playwright browser suite, and Windows package smoke test have not run in this environment; they require the development dependencies and Windows runner.
- Windows executable startup and live Shopify/SHOPLINE installation remain unverified.

The original `BIG_BANG_ORIGINAL_V35_COMPLETE.zip` contains only `BIG_BANG.exe`. It does not contain the native launcher source or a reproducible build project for that binary.
