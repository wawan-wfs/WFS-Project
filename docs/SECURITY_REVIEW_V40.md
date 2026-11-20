# WFS PROJECT v4.0 — Security review and unresolved risks

**Classification:** PARTIAL LOCAL RELEASE CANDIDATE; PRODUCTION ADMISSION DENIED.

## Confirmed local changes

- Disabled unscoped legacy `save_artifacts`, preventing a worker from rewriting the artifact manifest without synchronized, lease-checked filesystem publication.
- Enforced optional per-claim lease on agent start, agent success, worker events/phase, task-plan creation, handoffs and manual review suspension, with production pipeline passing lease across specialist threads. Historical admin/test callers without lease remain *trusted only*, and must not be exposed as public functions.
- Added read-only crash directory/manifest hash audit; no automatic disk repair or destructive GC.
- Added separately running local UDS admission quota service with HMAC, replay nonces, atomic SQLite slots, per-session/org/global TTL and failure-closed 503. HTTP origin/IP are never used for tenant identity. It is optional and not installed by default.
- Preserved provider `billing_unknown`, MFA/per-event revocation, origin separation, 13 menus, 10 divisions, and 8 licensed original local GLBs.

## Remaining high-risk gaps

- Shared SSE authority runs on **one operator Linux host** over UDS. It is neither a real independent edge nor a multi-host consensus service. Compromise of a trusted API-process HMAC key can forge admission calls. Multi-host TLS, issuer/audience-bound claims, admin revocation and rate-limit load proof are still required.
- WFS application SQLite and delivery filesystem cannot commit atomically across power loss; audit is read-only and no fsync-backed journal recovery is claimed.
- Legacy operator/internal store mutations with absent lease are preserved for compatible administrative actions and should not be exposed to untrusted execution; future work should separate public worker APIs from operator APIs.
- Independent rootless Docker runner, pinned/signed/scanned images, egress deny, Docker daemon and CPU/memory/PID/disk acceptance, dynamic preview TLS, real provider per-response invoice/hard limits, Windows GPU/NVDA/MFA/backup-restore remain **BLOCKED_EXTERNAL**.
- No source was published online and no paid provider requests were issued. Unit tests and local process runs do not establish real production host security.
