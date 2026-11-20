# WFS PROJECT — Agent engineering policies

For UI/UX requests first read `.agents/skills/wfs-ui-ux-pro/SKILL.md`; for 3D read `.agents/skills/wfs-3d-spatial-ui/SKILL.md`; for accessibility read `.agents/skills/wfs-accessibility/SKILL.md`.

Do not ship screenshots in place of code. Keep all application functions, RBAC checks, telemetry truthfulness, and Docker approval boundaries intact. Run tests and screenshot browser fixtures after UI changes. Fix regressions before declaring a release. Each release must include `docs/NEXT_PROMPT.md` with the next actionable development phase and a bounded feature checklist.

## v2.3 implementation follow-up
Before changing the Spatial Office, read `docs/DESIGN_SYSTEM_V23.md`, `app/static/models/ASSET_LICENSES.md`, the original asset generator, and `docs/UX_AUDIT_V23.md`. Preserve building-to-floor navigation, local-only asset policy, truthful `/api/office/live` status, reduced motion, 2.5D fallback, and all three project-local skills. Maintain `Ctrl+K` palette across thirteen existing menus. Do not present CPU fallback screenshots as proof of real GPU asset rendering.

## v2.4 supplementary acceptance policy
Read `docs/DESIGN_SYSTEM_V24.md`, `docs/UX_AUDIT_V24.md`, `docs/SECURITY_AUDIT_V24.md` and `docs/WINDOWS_ACCEPTANCE_V24.md` before modifying spatial assets or browser capabilities. Eight original GLBs, bounded parser, 13-float vertex layout and both CPU/GPU backends must stay compatible. Use authenticated `/api/office/live` data and native task inspector. Do not classify fixture screenshots as real WebGL2 GPU execution or user project activity. Current procedural avatar is not skeletal-rigged. Report all Windows/Docker/browser/security acceptance gaps openly.

## v2.5 security and GPU policy
Before modifying MFA endpoints, read `docs/SECURITY_AUDIT_V25.md` and `app/mfa.py`. Never log or screenshot TOTP secrets, codes or recovery codes. Protect per-account session scope, replay handling and local-only break-glass reset. Do not claim optional GPU timer queries measure FPS/VRAM, and never report CPU fallback as real GPU validation. Preserve native inspector and demo/live distinction. See `docs/NEXT_PROMPT.md` for v2.6.

## v2.6.0-rc1 tenant boundary and security continuity
Read `docs/SECURITY_AUDIT_V26.md`, `docs/MIGRATION_V26.md` and `docs/ACCEPTANCE_MATRIX_V26.md` before changing auth, store or operator preview. All authenticated project endpoints and aggregates must enforce organization membership, including revisions, SSE and FinOps. Organization selection comes from the server-side account, never a client-supplied org ID. Keep mandatory MFA's enrollment-only exception, recovery and per-account session revocation; preserve v2.5 functionality and never log/photograph secrets. Treat `V26_FIXTURE_SCREENS` as synthetic fixture evidence only. Do not certify production without real Windows Docker GPU, isolated runner, TLS preview, provider and external security evidence.

## v2.7 strict remote QA policy
Read `docs/RUNNER_ISOLATION_V27.md` and `docs/ACCEPTANCE_MATRIX_V27.md` before modifying untrusted-code execution. Strict QA must fail closed for mutable image references, non-rootless engines, insecure Docker transport, unsafe mounts or remote staging digest mismatches. Do not declare host isolation from mocked tests. Local preview remains untrusted and must never be publicly exposed.

## v2.8 tenant spend + preview release safeguards
Read `docs/ROOTLESS_RUNNER_V28.md`, `docs/PREVIEW_GATEWAY_V28.md`, `docs/MIGRATION_V28.md` and `docs/ACCEPTANCE_MATRIX_V28.md`. Cost reservations are atomic estimates, not invoices or actual provider hard limits. Strict remote QA now requires immutable Linux filesystem staging proof (FS_IOC_GETFLAGS) plus SHA-256 parity and mTLS/rootless inspect; never bypass these gates for a convenience pass. Preview tickets are one-use, bound to active session/project/org and need a distinct TLS gateway origin, not the dashboard hostname. Never serve dynamic Docker preview ports publicly. Keep all screenshot fixture labels; never claim real Windows GPU or production QA without operator-host evidence.

## v2.9 per-attempt and provider reconciliation policy
Read `docs/ROOTLESS_ATTEMPTS_V29.md`, `docs/PROVIDER_RECONCILIATION_V29.md` and `docs/ACCEPTANCE_MATRIX_V29.md` before changing runner or AI billing. Strict remote QA must use a unique immutable attempt namespace. A `billing_unknown` provider attempt must NEVER be treated as free or bypassed by dashboard state. Operator-provided exports do not prove authenticity. Do not claim Docker/TLS/GPU/paid-provider acceptance from fixture or mock tests.

## v3.0 additional admission policy

Read `docs/ROOTLESS_EVIDENCE_V30.md`, `docs/ACCEPTANCE_MATRIX_V30.md` and `docs/SECURITY_REVIEW_V30.md` before editing runner or preview admission. A strict QA pass requires inspecting the created container, immediately rechecking immutable staging flags/SHA-256, and independently verifying cleanup with a live daemon query. Never mark an unreachable host or unverified deletion as passed. Operator-only host evidence collection is not a certificate or proof that the host is independent. Do not clear `billing_unknown` or expose dynamic preview containers until authentic provider/host/TLS gates are satisfied.

## v3.1 dynamic preview security boundary
Read `docs/PREVIEW_BROKER_V31.md` and `docs/SECURITY_REVIEW_V31.md` before modifying the gateway. Dynamic preview must use an operator-configured *per-project hostname*, private Unix socket, owner/peer UID validation, strict size limits, stripped auth/cookie/CORS headers and per-request dashboard-session/org/project revocation checks. Neither user-supplied URL nor raw Docker port is an authorized routing target. Keep the feature disabled until isolated real TLS ingress is installed. Local tests are not real TLS or Docker proof.

## v3.2 segregated dynamic authority
Read `docs/PREVIEW_AUTHORITY_V32.md` and `docs/SECURITY_REVIEW_V32.md` before modifying the preview gateway. Gateway remote-authority mode must never access SQLite: ticket and session checks go via a private signed UDS to the DB-owning authority service. Deny unsigned, replayed, stale and wrong-origin requests; keep authority socket mode 0600 and directory 0700. Do not mount the WFS DB or runner secrets on a public gateway. Local compatibility mode and fixture screenshots remain **NOT PRODUCTION**.

## v3.3 opt-in mTLS and autonomous handoff

Read `docs/MTLS_AUTHORITY_V33.md`, `docs/SECURITY_REVIEW_V33.md` and `docs/ACCEPTANCE_MATRIX_V33.md` before enabling cross-host authority communication. The new `mtls` transport is opt-in and must validate a trusted CA, server hostname, client key permissions and HMAC signed requests; no HTTP fallback. Client certificate validation alone does not prove per-client revocation and must not be labeled production. Read `docs/NEXT_PROMPT.md` for the autonomous v3.4+ engineering loop; execute across checkpoints within the current session, never promise offline/background continuation.

## v3.5 runner lifecycle and nginx syntax policy
Read `docs/ROOTLESS_GC_V35.md`, `docs/ACCEPTANCE_MATRIX_V35.md`, `docs/SECURITY_REVIEW_V35.md` before touching the operator-only GC or immutable staging. The GC is read-only by default; never call `--apply` or `--purge` without operator approval and actual independent rootless Docker inspection. The shared pause marker and lock are not proof that all engine clients are disabled. Nginx local `-t` with test CA and bind substitution is NOT evidence of cross-host PKI, firewall or production CRL revocation. SQLite nonce profiling is local only. Real host/provider/Windows gates remain blocked.

## v3.6 security continuity

Per-event SSE reauthorization must not be bypassed: verify session, original account, organization MFA and project grant immediately before delivery, even after cursor selection. New `provider-official-costs-v36.py` can only produce a **read-only aggregated provider report**, never per-response invoice proof or `billing_unknown` clearance. Its official live API mode requires actual operator credentials and approval. No independent host, DNS, GPU or paid provider results are assumed. Keep production admission DENIED until real evidence is collected.

## v3.7 local load and stream policy

Read `docs/SSE_BACKPRESSURE_V37.md` and `docs/PREVIEW_BACKPRESSURE_V37.md` before editing SSE or dynamic preview. Limits are per process only. Never disable tenant/session/MFA per-event revocation, never forward preview cookies/authorization upstream, never treat CPU fallback or fixture/test mocks as hardware evidence. Production remains DENIED.

## v3.8 preview and SSE worker safety

Read `docs/PREVIEW_TIMEOUTS_V38.md`, `docs/SSE_INGRESS_V38.md` and `docs/WORKER_FENCING_V38.md`. Broker deadline/cancellation and local Unix SO_PEERCRED checks must not be bypassed; worker leases are unique per claim and live telemetry must reflect only active verified worker instances. SSE reservation release must be safe before first stream pull. Nginx snippet is per-IP operator-only and not cluster tenant control. Production admission DENIED without independently verified external infrastructure.


## v3.9 delivery and specialist fencing policy
Read `docs/ARTIFACT_FENCING_V39.md`. Never publish project delivery or manifest outside a live per-claim worker lease; never accept stale specialist completions. SQL transactions do not make filesystem writes power-loss atomic. All distributed hardware/proxy/provider gates remain denied without original independent proof.

## v4.0 — Worker and shared SSE admission contract
Read `docs/ARTIFACT_RECOVERY_V40.md` and `docs/SSE_SHARED_ADMISSION_V40.md` before changing worker or stream paths. Do not restore manifest-only `save_artifacts` or introduce worker writes without a per-claim lease. Optional SSE shared admission is a PRIVATE single-host UDS quota authority and **not** production cross-host proof; never downgrade to local limits after configured authority failure. No forged tenant IDs from proxy headers. Running source tests on a local Python process is not Docker/TLS/GPU/provider verification.

## v4.1 — Scoped SSE assertion and worker recovery

Read `docs/SSE_IDENTITY_V41.md`, `docs/ARTIFACT_RECOVERY_V41.md` and `docs/MIGRATION_V41.md`. Never let a configured assertion path fall back to process-local quota. The issuer is local and its private signing key must remain in the authority process. Worker mutation APIs require a current lease, and agent run ownership must be verified against its recorded claim. Operator event writes are explicit, internal and subject to existing route permissions. Preserve previous artifact generations for operator review. Do not infer multi-host, power-loss, billing, or Windows hardware acceptance from the local tests.

## v4.2 — PostgreSQL lab and recovery verification

Read docs/POSTGRES_QUOTA_LAB_V42.md and docs/ARTIFACT_RECOVERY_V42.md. The quota experiment is loopback only and does not replace any HTTP authentication or per-event authorization. Keep it separate until replication, HA, identity and transport are independently verified. Run candidate matching on an offline clone. Do not automatically promote or purge retained generations. Do not claim production acceptance from local processes or fixtures.

## v4.3 — Replica lab and retained recovery evidence

Read docs/POSTGRES_REPLICATION_LAB_V43.md and docs/ARTIFACT_RECOVERY_V43.md. Keep the quota experiment outside app HTTP. Its single-host stop-before-promote fence is not proof of distributed leader fencing. If artifact compensation fails, preserve all retained generations for operator review. Verify matched backups only on offline clones.

## v4.4 — Replay acknowledgement and operator evidence

Read docs/POSTGRES_REPLICATION_LAB_V44.md and docs/OPERATOR_EVIDENCE_V44.md. Strict lab receipt retries must still wait for synchronous replay. Never use the same-host promotion guard as a distributed fence. Verify only stopped clones. Classify tool or platform absence as blocked, not as a local pass.

## v4.5 — Commit watchdog and backup inventory

Read docs/POSTGRES_REPLICATION_LAB_V45.md and docs/OPERATOR_EVIDENCE_V45.md. A timed-out strict acknowledgement may have committed locally. Do not acknowledge it without verified replay on retry. Verify stopped restore clones against independently recorded expected delivery IDs when completeness is required. Do not treat the local watchdog, read-only verifier, or screenshots as independent host evidence.

## v4.6 — Per-case acceptance evidence

Read docs/OPERATOR_EVIDENCE_V46.md and docs/POSTGRES_REPLICATION_LAB_V46.md. Never interpret a successful pytest process as proof that skipped Unix-socket checks ran. Keep same-host database evidence separate and use a stopped clone for restore checks.

## v4.7 — Synchronous rejoin and exact restore inventory

Read docs/OPERATOR_EVIDENCE_V47.md and docs/POSTGRES_REPLICATION_LAB_V47.md. Same-host replica re-enrolment does not prove distributed fencing. Use exact restore inventory only with the complete independent delivery list from backup time. Do not infer Windows acceptance from the Python test.

## v4.8 — Independently retained backup fingerprints

Read docs/OPERATOR_EVIDENCE_V48.md. A generation fingerprint compares the restored delivery against an external reference. Never generate the reference from the candidate being verified, and never read a changing live tree as a stopped backup. An inventory is not an attestation or a substitute for independent hosts.

## v4.9 — Pinned and redacted recovery proof

Read docs/OPERATOR_EVIDENCE_V49.md. When pinning an inventory, use the independently saved raw SHA-256 from before restore. Use summary output for shared evidence and retain detailed reports privately. A local Python verification is not Windows acceptance.
