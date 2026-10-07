# Security policy

## Supported versions

Only `main` is supported. Historical tags are frozen for reproducibility but
no longer receive security fixes.

| Version | Supported |
|---|---|
| `main` | ✅ yes |
| any released tag | ❌ no (frozen for reproducibility) |

## Report a vulnerability

**Please do not open a public issue.** Use one of these channels instead:

1. Email the maintainer: `lm203688@users.noreply.github.com` (private)
2. GitHub's security advisory flow:
   `https://github.com/lm203688/flybrain-connectome/security/advisories/new`

Please include:

- The affected version(s).
- A minimal reproduction, if possible.
- The impact and any mitigations you found.

Response targets:

- **Acknowledgement** within 72 hours.
- **Patch or plan** within 14 days for critical severity.
- **Fix committed and tagged** within 30 days.

## What counts as security-relevant

- Secrets or credentials committed to the repo (Gate 1 catches these).
- A path in the CLI/MCP/HTTP surface that reads a file it shouldn't.
- A provenance tampering vector that lets an untrusted payload masquerade as
  a real connectome-derived unit.
- Any `import` in the toolkit that opens a network socket without caller
  consent — the toolkit is offline-first by design.

## What does NOT count

- "Your generated agent topology does X that is biologically wrong" — that
  is a correctness concern, tracked as a normal issue. This is a research
  artifact; wrong biology in a synthetic topology is a bug, not a
  vulnerability.
- The MaleCNS dataset itself. It is third-party data under CC-BY 4.0 and is
  not part of this repo's security surface.

## Automated checks

Every merge to `main` runs:

- Gate 1 — `scripts/check_no_secrets.py` (regex for tokens, keys, private keys)
- `detect-secrets` against a pinned baseline (`.secrets.baseline`)
- Docker build (proves the image ships clean with no stray credentials)

If any of these regress silently, open a security advisory — it means the
CI contract is broken.

## License of the policy

This policy is MIT-licensed with the rest of the project.
