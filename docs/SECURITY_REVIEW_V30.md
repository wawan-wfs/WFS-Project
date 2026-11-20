# WFS PROJECT v3.0 — Bounded security review

This is a targeted **source review and local test pass**, not an independent SAST/DAST penetration test or production certification.

## Changes

1. Strict QA previously trusted one staging preflight before multiple QA commands and could report pass despite unverified cleanup. It now rechecks immutable SHA-256 staging after container creation and before each start; fail-closed inspection/cleanup/daemon-health checks gate a pass. Tests simulate tampered stage, missing preflight, timeout, removal failure and daemon loss.
2. The optional real remote acceptance runner previously inferred no container leak from an empty `docker ps` output even when `docker ps` failed. It now requires successful `ps` and post-probe daemon health, and reports timeouts separately.
3. Added a host-side evidence collector that checks cgroup v2, rootless daemon reporting, immutable ext4 staging and optional external network probe. It deliberately cannot assert independent VM placement, cert revocation or global firewall deny from these observations.

## Residual and release-blocking risks

- Real daemon-side one-time per-attempt mTLS authz, certificate revocation, signed image policy, host-level egress firewall, disk quotas and crash-proof stage GC are not implemented or attested. Privileged host mutation between preflight and execution remains theoretically possible.
- Preview TLS, actual dynamic full-stack origin isolation, CSP/same-site browser red-team and host-port denial are not proven.
- `billing_unknown` records remain unresolved under strict budgets until independently authentic provider data is obtained and reviewed. A CSV checksum only proves byte integrity, **not provider authenticity**. Provider-side daily spending caps are not configured or verified.
- Windows 10/11 Docker Desktop, Chrome and Edge GPU timer/driver/VRAM evidence, MFA device recovery, NVDA, 200% zoom and full disaster recovery drill have not been run.
- Eight original CC0 GLBs are retained; avatar is stylized and **not skeletal-rigged**. No new engine, GLB, or GPU fidelity claim is made.

**Production admission: DENIED.** Public deployment and unattended untrusted code execution remain prohibited until the P0 gates above have real evidence.
