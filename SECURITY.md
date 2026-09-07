# Security Policy

## Supported versions

| Branch | Supported |
| --- | --- |
| `main` | yes |
| `cursor/*` feature branches | best effort until merged |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

1. Email the maintainers privately (use the contact on the GitHub org/account that owns this repository).
2. Include: affected surface (product / lab / course / Studio), steps to reproduce, impact, and any suggested fix.
3. Allow up to **14 days** for an initial response.

We will acknowledge receipt, triage severity, and coordinate a fix and disclosure timeline.

## Scope notes

- **Course / Studio** can spawn local shell commands (`learn/scripts/`). Treat Studio as a **trusted-operator** tool, not a multi-tenant SaaS. Do not expose it to the public internet without authentication and network isolation.
- **Product / lab** cooks are heavy and touch ORFS artifacts. Follow [`AGENTS.md`](AGENTS.md): one heavy cook at a time, no locked-variant writes.
- Third-party PDKs, Calibre decks, and foundry data are **not** distributed by this repository. Do not commit credentials, tokens, or proprietary blobs.

## Safe defaults

- Set `STUDIO_RUN_TOKEN` when Studio is reachable beyond localhost; the run stream API honors Bearer auth.
- Keep `.env*` local (gitignored). Never commit `GITHUB_TOKEN`, ORFS licenses, or foundry keys.
