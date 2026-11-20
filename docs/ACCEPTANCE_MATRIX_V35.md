# WFS PROJECT v3.5.0-rc1 — Evidence Matrix

| Gate | Genuine current evidence | Classification |
|---|---|---|
| Baseline source | Exact v3.4 ZIP SHA-256 and 557 source entries verified before edits | PASS_LOCAL |
| Nginx mTLS configuration | Real `nginx -t` v1.26.3 on generated config with **ephemeral test-only CA/cert/CRL**, localhost substitution for syntax checking; hash bucket failure found and fixed | PASS_LOCAL, NOT DEPLOYED |
| Preview trusted server, revocation and tenant red team | No separate Linux hosts, production CRL, public DNS/wildcard TLS, network or concurrent real HAR | BLOCKED_EXTERNAL |
| Replay ledger | 64 accepted unique nonces, one of 4 replay competitors admitted; separate process tests, local SQLite index | PASS_LOCAL, NOT HOST PERFORMANCE |
| Runner garbage collector / importer lock | Bounded read-only audit plus negative policy tests and two-stage deletion implementation | PASS_LOCAL POLICY ONLY |
| Actual rootless daemon cleanup, egress, immutable ext4, signed images, mTLS per attempt | Docker CLI/independent runner absent; no destructive apply used | BLOCKED_EXTERNAL |
| Provider request billing / verified invoices | v3.4 offline CSV comparison preserved; no authenticated provider invoice, hard cap or paid sandbox access | BLOCKED_EXTERNAL |
| Existing backend regression | 59 security tests + 92 historical tests + 83 core tests; **234 passed, 86 subtests** in separate completed commands | PASS_LOCAL (grouped) |
| Combined pytest command | Initial -q/-vv attempts timed out; no single complete exit code obtained | INCOMPLETE, NOT PASS |
| HTTP end-to-end | Independent local Uvicorn/demo provider and workflow smoke | PASS_LOCAL |
| Parallel workers | 3 workers, 9 demo projects, 45 validated artifacts | PASS_LOCAL |
| JS/Python syntax | Python compileall and node checks completed | PASS_LOCAL |
| 26 desktop/mobile screenshots | Reused unchanged UI **v3.3 fixture set** already shipped with v3.4; no new live GPU captures | REUSED_FIXTURE |
| Physical Windows acceptance | Docker Desktop, Chrome/Edge 10-min GPU timer/driver/VRAM, NVDA, MFA recovery, restore not accessible | BLOCKED_EXTERNAL |
| Licensed 3D rigging | Existing CC0 eight GLB assets retained; skeletal rigging not added without licenses/hardware | NOT_RUN |
| Production admission | Multiple independent mandatory gates unavailable | **DENIED** |

No user DNS, cloud resources, credentials, production data or paid provider calls were accessed. No privileged filesystem cleanup was executed. Operator must not infer host attestation from local policy tests.
