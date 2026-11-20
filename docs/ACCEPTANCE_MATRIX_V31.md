# WFS PROJECT v3.1.0-rc1 — Acceptance evidence and gaps

**Classification: partial release candidate / production admission denied.** Baseline is the exact v3.0.0-rc1 ZIP; no new graphical assets or fake agent actions are introduced.

| Admission item | Local evidence | Admission |
|---|---|---|
| Source continuity and 13-menu control plane | v3.0 source preserved; all existing backend tests and offline browser UI fixture rerun | LOCAL PASS |
| Per-project dynamic origin | Gateway issues unique `<pid>.<dynamic-domain>` URL for FastAPI/Node projects; wrong-host ticket not consumed | LOCAL PASS, no real TLS |
| Untrusted app transport | Unix socket only, owner/mode plus Linux peer UID checks, no Docker socket or arbitrary URL proxy | LOCAL TEST PASS; not host proof |
| Tenant and session revocation | User session and org/project grants rechecked on every request; cross-tenant socket fixture and logout tests | LOCAL PASS |
| Dynamic response control | 1 MB request / 4 MB response bound, header filtering, CSP, no generated-app cookie passthrough | LOCAL PASS |
| Linux rootless independent host | No actual separate Docker daemon or rootless host provisioned; `docker` CLI unavailable here | NOT RUN |
| Host firewall deny egress, userns, cgroup2, immutable ext4 | v3.0 operator collectors remain; no real hardware or firewall evidence | NOT RUN |
| One-time daemon-side mTLS identity, TTL GC, disk quota, crash recovery | No working independent admission service or negative host evidence | BLOCKED |
| Actual TLS DNS wildcard per-project dynamic host | Operator-only probe implemented; no authentic public TLS/DNS infrastructure contacted | NOT RUN |
| Concurrent cross-tenant HAR/red team | Local TestClient cross-tenant check only; no real browser HAR | NOT RUN |
| Actual provider usage reconciliation and hard spend controls | v2.9 unknown charges and offline reconciliation retained; actual invoices/credentials absent | NOT RUN |
| Actual Windows Chrome/Edge GPU/NVDA/MFA/restore drill | No Windows hardware used; source UI fixture is CPU 3D | NOT RUN |
| Rigged skeletal animation | Existing eight original CC0 GLBs preserved; stylized avatar is unrigged | NOT IMPLEMENTED |
| Full release SHA-256 | Manifest + independent extraction verification | PASS after independent ZIP extraction and SHA-256 verification (see release manifest) |

A green Python policy test is **never** real Docker, public TLS, provider billing or GPU acceptance. Public/unattended AI-generated code execution remains prohibited until independently measured P0 gates pass.
