# WFS PROJECT v3.1 — Mandatory hardware and deployment evidence (continue from v3.0.0-rc1)

Continue directly from the exact v3.0 source ZIP; read `AGENTS.md`, all project-local skills, `docs/ROOTLESS_EVIDENCE_V30.md`, `docs/ACCEPTANCE_MATRIX_V30.md`, `docs/SECURITY_REVIEW_V30.md`, `docs/PREVIEW_ACCEPTANCE_V30.md` and `TEST_REPORT.md`. Preserve every working feature and data format. No mock screenshots may be presented as live.

P0:
1. Provision a **separate real Linux rootless Docker host** independent from dashboard/worker, with deny-by-default egress. Run `acceptance_v30_host.py`, `acceptance_v28_remote.py` and `sandbox-qa.py --strict-remote` using pinned/scanned images and operator-scoped credentials. Save redacted original Docker inspect, host firewall/cgroup/userns/ext4 immutable proof and timed cleanup. Add real daemon-side per-attempt mTLS identity and revocation; use separate trusted admission/control plane. Build disk quota, TTL cleanup, crash recovery and auditd logs; verify source immutability/TOCTOU resistance under adversarial tests. Fail closed for any ambiguous host condition.
2. Deploy authentic separate TLS preview hostname and reverse proxy with redacted ticket logs, secure session revocation on every request, and real concurrent cross-tenant HAR/browser tests. Add a dynamic internal-only broker for FastAPI/Node/PostgreSQL previews without raw exposed loopback ports; preserve strict origin/CSP separation.
3. Obtain **authenticated actual provider** request/usage/cost export and enforce provider-side daily spend caps. Bind retry IDs, stream partials and unknown charges to operator-reviewed independent evidence; never clear unknown liabilities with self-supplied CSV alone. Run live sandbox budget tests with consent and controlled spending.
4. Run real Windows 10/11 Docker Desktop, Chrome/Edge WebGL2 10-minute driver/GPU timers, NVDA, keyboard, 200% zoom, authenticator recovery and backup rollback. License-audit rigged PBR avatars and add skeletal animation only after hardware results and telemetry truth tests.
5. Produce full versioned ZIP, SHA-256, 26 labeled screenshots, redacted hardware proof, negative security/evidence matrix, migration/rollback and a bounded next prompt.

**Stop condition:** no production admission without independently verified host, TLS, provider, Windows/MFA, browser/GPU, and restoration gates.
