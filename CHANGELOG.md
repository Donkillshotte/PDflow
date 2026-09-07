# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Apache-2.0 `LICENSE`, `SECURITY.md`, and this changelog.
- Dependabot for `studio/` npm dependencies.
- PR and issue templates under `.github/`.
- `.nvmrc` for reproducible Studio Node version.

### Changed

- `.gitignore` excludes `.env*` and local secrets.

### Security

- `scripts/publish_to_github.sh` no longer embeds a token in the git remote URL (uses plain HTTPS + `gh auth setup-git`).

- See `SECURITY.md` for reporting and Studio/`STUDIO_RUN_TOKEN` notes.
