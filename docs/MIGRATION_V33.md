# WFS PROJECT v3.2 → v3.3 upgrade and rollback

1. Stop trusted API, workers, preview gateway, proxy and active dynamic previews. Produce an encrypted matched source/data/.env backup and verify existing SHA-256. Do not ship production credentials or user SQLite in the source ZIP.
2. Extract the v3.3 ZIP into a **new folder**. Run `python scripts/verify-release.py`, `PYTHONPATH=. python -m pytest -q`, `python scripts/http-e2e.py`, and `python scripts/parallel-e2e.py` in nonproduction mode. Verify 13 UI routes and private MFA flows.
3. There are **no database schema changes** in v3.3. Existing v3.2 data, keys, and private project grants remain valid when mounted only to the trusted API/authority host.
4. By default the original UDS authority remains. New mTLS transport requires explicit opt-in and a physically independent private network/PKI. Review `docs/MTLS_AUTHORITY_V33.md` and finish actual TLS host identity + revocation/firewall proof before considering production.
5. Roll back by disabling public TLS ingress, stopping preview workloads, revoking tickets and terminating the mTLS listener, then restoring matched v3.2 source+data+environment. Never directly expose generated project ports or copy the WFS database to the public gateway.
6. Repeat MFA recovery, worker consistency, preview revocation and data restore drills on Windows before production admission.
