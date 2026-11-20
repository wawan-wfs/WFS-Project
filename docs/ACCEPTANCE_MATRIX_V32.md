# WFS PROJECT v3.2.0-rc1 — Evidence matrix

**Classification: PARTIAL RELEASE CANDIDATE, production admission DENIED.** Exact baseline: `WFS_PROJECT_v3.1_DYNAMIC_PREVIEW_PARTIAL_Windows_Docker.zip`. No claim of real TLS, Docker rootless, provider invoices, or Windows GPU/acceptance.

| Gate | Verified evidence | Outcome |
|---|---|---|
| Source continuity: 13 UI menus, ten divisions, original eight GLBs, MFA, FinOps, queue | Baseline source retained, new code limited to dynamic gateway authority and testing/docs | PRESERVED / local regression |
| Independent preview DB boundary | Real separate Uvicorn process on private UDS; gateway's local `store.connect()` intentionally disabled; dynamic ticket and resource access still succeeded | LOCAL PASS; not independent VM |
| Signed service requests | HMAC-SHA256 timestamp+nonce+path+body, ≤30-second skew, bounded replay cache; bad signature/replay/stale/method rejected | LOCAL PASS |
| Preview revocation / cross-tenant | Session logout, wrong project host, bad authority secret, missing UDS, unavailable SQLite at gateway | LOCAL PASS |
| No public/remote app ports | UDS transport and operator policy retained, but no real firewall/ingress inspected | NOT PROVEN |
| Independent Linux rootless Docker, immutable ext4, signed pinned images, deny egress, mTLS-per-attempt, quotas, TTL and GC | Operator scripts preserved; no independent runner available | NOT RUN |
| Authentic wildcard TLS, two-tenant real HAR, DNS certificate, trusted proxy | v3.1 probe retained only; public infrastructure unavailable | NOT RUN |
| Actual provider invoices, live request IDs, true hard spend caps | Read-only cost comparison retained; no independently authenticated provider API/exports | NOT RUN |
| Windows Docker Desktop, Chrome+Edge GPU WebGL2 10-minute timings, VRAM/driver | No Windows machine or GPU available | NOT RUN |
| NVDA, MFA recovery on Windows, full backup restore | Manual/operator acceptance required | NOT RUN |
| Skeletal-rigged licensed GLBs and PBR hardware | Original GLBs untouched; no rig/engine claim | BLOCKED pending real GPU + licenses |
| Full regression, HTTP E2E, parallel workers, fixture screenshots, checksum | Details in `TEST_REPORT.md` v3.2 section after execution | LOCAL ONLY |

**Release condition:** every P0 gate above must be validated on **real** separately trusted operator hardware, with redacted original evidence and independent authorization review. A green unit test is never a certificate.
