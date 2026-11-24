# Development and Release Process

## Branching

main holds the stable V35 baseline and published versions. develop integrates work for the next version. Create feature/<short-name> for new capabilities, fix/<short-name> for defects, and release/<version> for final release preparation. Merge through pull requests; require the CI checks to pass before merging.

## Change checklist

1. Read AGENTS.md, HANDOFF.md, and the relevant source modules.
2. Create a branch from develop and preserve existing runtime paths.
3. Add a focused regression test for the behavior being changed.
4. Run the offline resource verifier, Python regression suite, JavaScript checks, responsive browser suite, and Windows package smoke test.
5. Record code and resource changes in CHANGELOG.md. Never replace a resource version or alter a product/template mapping without a reviewed mapping diff.
6. Open a pull request to develop and verify CI reports separately which checks were static, simulated, or live.

## Release checklist

1. Create release/<version> from develop and update VERSION, CHANGELOG.md, and the runtime version string where needed.
2. Verify the source archive SHA-256 and all 300 mapping identities.
3. Run CI and resolve all failures. A missing test dependency, Windows startup failure, or resource mismatch blocks release.
4. Merge the release branch to main, then create the matching v<version> tag.
5. GitHub Actions re-runs release tests and builds the Windows package. It publishes only when both jobs succeed.
6. Review the generated release notes and manifest for file inventory, hashes, changes, actual test results, and known limitations.

The current V35 handoff has offline resource validation, but has not been live-tested on Shopify or SHOPLINE. The separately supplied EXE is a compiled binary without matching native launcher source; do not claim that a later source build reproduces it.
