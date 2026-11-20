# WFS PROJECT v3.1 — Security delta and residual risks

**Implemented (local only):** trusted-UID Unix-socket dynamic preview transport; per-project HTTPS hostname template; session/org/project revocation check per request; ticket origin check before redemption; private host-only cookies; request/response size ceilings; no client-auth, forwarded cookie, bearer, CORS or upstream Set-Cookie passthrough; restrictive CSP. Added a read-only TLS negative probe for operator-run deployment verification.

**Remaining major risks:** no actual deployed TLS reverse proxy, wildcard certificate, independent authz service, dedicated Linux rootless Docker VM, pinned+scanned container evidence, daemon-side short-lived mTLS revocation, host-level egress proof, disk quota, durable TTL GC, arbitrary code escape/port isolation proof, external pentest, live provider invoice reconciliation, or Windows GPU/MFA/NVDA evidence. Dynamic application subprocess/socket must not share the API/worker privilege boundary. The gateway currently reads WFS SQLite grants and must not have a Docker daemon client certificate.

**No data format changes:** existing projects, identities, invoices/attempts and MFA are unchanged. New dynamic variables default to disabled. Invalid/unconfigured socket origin fails closed. Operator-controlled local preview workflows remain available; no Internet deployment is approved.

**Licenses:** all eight existing local procedurally authored glTF assets remain CC0 as described in `app/static/models/ASSET_LICENSES.md`; no new model, character rig or license was added.
