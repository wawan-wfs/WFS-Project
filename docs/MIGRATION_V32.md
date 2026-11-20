# WFS PROJECT v3.1 → v3.2 local upgrade and rollback

1. Stop API, workers, operator preview jobs and current gateway. Create a **matched encrypted backup** of v3.1 source, `data/`, `.env` and session secret. Verify checksums and file permissions before upgrading. Never upload plaintext production secrets to support tickets.
2. Extract the v3.2 source ZIP in a fresh directory. Run `python scripts/verify-release.py` there and run `PYTHONPATH=. python -m pytest -q`, `python scripts/http-e2e.py` and `python scripts/parallel-e2e.py` using nonproduction data.
3. No WFS SQLite schema migration is required. Existing sessions and grants remain in the trusted data store. The public gateway **must not** get a copy of that store.
4. Dynamic-only remote authority is **opt-in**. Configure only after provisioning the trusted auth sidecar, private UDS, distinct wildcard TLS, separate gateway runtime, private generated app sockets, and network policy. Detailed procedure: `docs/PREVIEW_AUTHORITY_V32.md`. Do not publicly enable the v3.1 local-mode fallback.
5. Verify live revocation, MFA, two tenants, TLS/HAR evidence, Docker firewall and restore on the actual operator environment before any Internet/public code access. Do not use synthetic browser fixtures as evidence.
6. Rollback: disable external ingress; stop dynamic socket/proxy and authority; restore **matched** v3.1 code/data/environment backup and check MFA, private projects, queues, costs and preview revocation. Do not run v3.1 and v3.2 simultaneously on a shared SQLite database.
