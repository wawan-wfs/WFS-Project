# WFS PROJECT v2.7.0-rc1 — acceptance matrix

| Gate | Evidence | Status |
|---|---|---|
| Exact v2.6.0-rc1 source continuity | v2.6 partial tenant-boundary source was modified in place; no rewrite of 13-menu UI or 3D | PASS source continuity |
| Docker QA strict admission implementation | `scripts/runner_policy.py`, `scripts/sandbox-qa.py`: mutual TLS, rootless daemon validation, digest-only images, readonly staging, pre-run inspect, 2-bind allowlist, SHA-256 remote staging comparison | PARTIAL implemented, mocked tests |
| Negative policy tests | `tests/test_v27_runner_policy.py`: 8 tests with 20 subtests | PASS local tests |
| Full Python test suite | `python -m pytest -q`: 157 passed and 40 subtests | PASS local |
| HTTP API real localhost process | `python scripts/http-e2e.py`: PASS | PASS local |
| Parallel worker | `python scripts/parallel-e2e.py`: 3 workers, 9 fixture/demo projects, 45 artifacts | PASS local/demo |
| Rootless remote Docker daemon actual execution/negative tests | No dedicated trusted engine or remote staging host available here | NOT RUN |
| Remote staging race-free immutable snapshots | SHA-256 preflight included but no remotely enforced immutable staging | BLOCKED |
| Host egress deny, mTLS rotation, CPU/disk quotas and TTL evidence | No independent deployment, firewall audit or measured limits | NOT RUN |
| Authenticated HTTPS preview origin isolation | Existing local preview remains; no production TLS preview proxy | NOT IMPLEMENTED |
| Workspace tenancy, quota reservations and reconciliation | Only v2.6 organization boundaries retained | INCOMPLETE |
| GPU WebGL2, skeletal rig and true PBR engine | Previous nonrigged assets unchanged; no Windows hardware tests | NOT RUN / NOT IMPLEMENTED |
| Real Windows Docker Desktop browser E2E and NVDA | No real Windows hardware session in this environment | NOT RUN |
| Provider billing reconciliation and MFA recovery drill | No paid provider or real device recovery exercise | NOT RUN |

**Release:** LOCAL RC ONLY. Never label as production ready. Previous v2.6 fixture screenshots remain labeled *FIXTURE*, not real telemetry. See `docs/RUNNER_ISOLATION_V27.md` for restrictions.
