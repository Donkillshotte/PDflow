# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Apache-2.0 `LICENSE`, `SECURITY.md`, and this changelog.
- GitHub Actions `fast-gates` workflow: Python smoke, engine native tests, Studio lint/build.
- Dependabot for `studio/` npm dependencies.
- PR and issue templates under `.github/`.
- `learn/sim/reports/sta_arrivals_flowlab.json` fixture for honesty gates on clean checkout.
- Studio security headers (CSP baseline, `nosniff`, frame protection).
- `.nvmrc` and Node `engines` for reproducible Studio builds.

### Changed

- CI skips ORFS-live F6 parse when flow logs are absent (synthetic gates still run).
- `.gitignore` excludes `.env*` and local secrets.

### Security

- ASAP7 lab variant guards, Studio run-stream auth, and fail-closed e2e analysis (see PR #1).
