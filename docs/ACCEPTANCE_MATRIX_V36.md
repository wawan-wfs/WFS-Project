# WFS PROJECT v3.6.0-rc1 — Evidence and acceptance

| Gate | Evidence | Classification |
|---|---|---|
| Baseline v3.5 | Exact v3.5 ZIP, safe members, no symlinks, SHA-256 of all 570 manifest paths | PASS_LOCAL |
| SSE query-to-send revocation | 4 tests, streaming response, permitted/denied projects and swapped account | PASS_LOCAL_TEST |
| Official costs adapter | Fixed official GET origin, TLS/redirect/parser/pagination/output controls, 6 tests + 7 subtests (mocked transport) | PASS_LOCAL_FIXTURE |
| Official authenticated provider costs | No operator key/account, no HTTPS request made | BLOCKED_EXTERNAL |
| Per-response invoice reconciliation and unknown-charge clearance | OpenAI costs endpoint is aggregate; no per-response paid bill proof or clearance implemented | BLOCKED_EXTERNAL |
| Provider-enforced spend caps | No authorized provider account configuration or independent enforcement measurement | BLOCKED_EXTERNAL |
| Entire Python regression | Three independently completed groups: 150+78+16=244 passed, 40+53=93 subtests, **each exit 0**. A combined command also produced the same summary once but other attempts timed out. Logs under `docs/V36_EVIDENCE/`. | PASS_LOCAL_GROUPED; COMBINED FLAKY |
| HTTP end-to-end | Independent localhost Uvicorn/demo workflow, process exit 0 | PASS_LOCAL |
| Parallel worker | 3 worker processes, 9 projects, 45 artifacts, process exit 0 | PASS_LOCAL |
| Independent rootless Linux runner | No Docker CLI/daemon, no real host inspect, firewall, quota or GC apply | BLOCKED_EXTERNAL |
| mTLS preview on separate host | Local config preserved; no operator host/DNS/CRL deployment | BLOCKED_EXTERNAL |
| Windows physical GPU/NVDA/MFA/restore | Not available here, no live screenshots or 600-second GPU proof | BLOCKED_EXTERNAL |
| Existing screenshot gallery | Previous 26 v3.3 fixtures reused; no UI changed | REUSED_FIXTURE |
| Production admission | Requires all independent host, provider, TLS, Windows and restore artifacts | **DENIED** |

Never infer production security from fixture tests. No paid provider calls, privileged GC, DNS/TLS deployment or destructive operations were performed.
