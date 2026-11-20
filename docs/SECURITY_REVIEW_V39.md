# WFS PROJECT v3.9 — Security Delta

## Closed locally

1. **Stale artifact overwrite:** `pipeline.run` no longer calls the unfenced filesystem + manifest sequence. `store.publish_artifacts` stages first and checks a per-claim worker ID under `BEGIN IMMEDIATE` before replacing delivered files and SQLite records. Negative tests cover stale/reclaimed leases and canceled projects.
2. **Recoverable publication failure:** old manifest and directory restored on injected DB failure. Fatal kill or storage failure is not proven crash-atomic; leave `production_admission=DENIED`.
3. **Canceled specialist success:** late AI results no longer emit a truthful-but-stale `done` or save task results after cancellation/lease takeover in the coding task path. Test responses are mocked; no paid call made.

## Unresolved risks (must not be downgraded)

- A process crash between filesystem rename and SQLite COMMIT is not an atomic DB+FS operation; delivery status is never implicitly completed. Backup artifacts must be examined by the operator after a crash.
- Legacy `store.save_artifacts` and legacy `worker_id=None` internal calls remain trusted, unscoped internal APIs. They should be audited before external worker plugins can call them. Public project delivery uses the fenced path.
- No authentic hardware proof for rootless Docker, signed immutable images, default-deny egress, mTLS revocation, ext4 staging, or privileged cleanup.
- No production wildcard TLS or real two-tenant HAR; preview gateway still needs approved independent origin.
- Per-process SSE and broker caps are not distributed and not a substitute for an authenticated shared ingress.
- No independent paid provider usage/invoice and daily limit verification; `billing_unknown` must remain blocked.
- No Windows Chrome/Edge GPU 600s, NVDA, real MFA recovery, data restore or licensed skeletal avatar acceptance.

**Security decision: PRODUCTION ADMISSION DENIED.** This is a local engineering checkpoint only.
