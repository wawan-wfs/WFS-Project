# WFS PROJECT v3.3 — Security review delta

## Implemented and locally tested

- Added **explicit opt-in** `WFS_PREVIEW_AUTHORITY_MODE=mtls` with `https://` origin validation, trusted operator CA, mutual certificate, hostname verification, bounded HTTP response and the existing HMAC timestamp/nonce request signatures. UDS mode remains the default.
- Added private-IP-only authority server launcher with TLS server identity and mandatory verification of client certificates from the specified CA. No wildcard/public bind is permitted by the script. The gateway does not need any WFS SQLite or Docker credentials.
- Deny untrusted CA, incorrect hostname, key permission errors, missing certificate, insecure URL shape, unsupported authority mode and invalid private-IP server binds. The tests use a real localhost SSL handshake, not mocked network TLS.

## Known limitations / must not classify production-ready

- A CA-signed client certificate is accepted by this basic TLS listener even if a particular client identity was later revoked; **independently configured short-lived issuance + serial allowlist/CRL enforcement and operator review are still required** before production. Any client cert signed by the accepted CA plus knowledge of HMAC service key potentially authenticates; use a dedicated minimal-scope CA, segmented host/network and rotated secrets.
- No real separate Linux hosts, firewall policy, userns/cgroup v2, immutable staging negative tests, daemon-side per-attempt certificate revocation, rootless Docker, real TLS wildcard ingress, provider invoices, paid API hard limits, Windows GPU/NVDA/MFA recovery or disaster recovery evidence was supplied.
- Existing `WFS_PREVIEW_PROXY_KEY` is a shared reverse-proxy proof header restricted to loopback. Physical separation and trust of the real reverse proxy are not proven by tests.
- `WFS_PREVIEW_AUTHORITY_URL` and TLS secret paths must be provisioned and reviewed by the operator, not derived from tenant input. Runtime code never falls back to unverified TLS or plaintext on an invalid configuration.

**Disposition:** Keep Internet deployment and unattended untrusted code execution disabled pending independent real-host evidence and explicit operator approval.
