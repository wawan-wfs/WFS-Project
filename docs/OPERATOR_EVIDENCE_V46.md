# v4.6 Operator evidence

The collector runs each selected check once and continues after a blocked or failed check. It records the 17 expected focused test cases and six two-API checks by ID. It requires the expected test cases to be present exactly once. A missing case, unexpected skip, invalid report, partial two-API result, or failed test cannot produce a pass. Known AF_UNIX skips and the two-API unavailable result are recorded as blocked. The collector returns 0 for all requested checks passed, 77 for blocked without failures, and 1 for a failure or timeout. Results are local, not production attestations.

On an approved Linux host with AF_UNIX, after verifying the source ZIP and installing the dev requirements:

```bash
python scripts/run-operator-evidence-v46.py --output evidence-linux.json
```

The default runs manifest, Unix transport, focused regression, HTTP and workers. The two PostgreSQL labs are opt-in with `--gate postgres-replica` or `--gate postgres-scale`; run them separately on a quiet machine. The evidence destination must be a new path. To reproduce the focused tests without the collector:

```bash
PYTHONPATH=.:tests python -m pytest -q -rs tests/test_v40_sse_admission.py tests/test_v38_broker_deadlines.py tests/test_v41_sse_identity.py
```

Do not substitute TCP. The local report distinguishes the cases tested in process from the real Unix cases that did not run. Neither the older collector nor the new one removes the need to use an approved host.

## Restore and Windows

Use the independently recorded backup inventory and stopped clone procedure in [OPERATOR_EVIDENCE_V45.md](OPERATOR_EVIDENCE_V45.md). Run the verifier once on the full restored clone and once on a separate disposable negative-control clone with a known missing expected delivery. Do not alter the original snapshot. Then independently start the intact Windows Docker Desktop clone. Retain separate evidence for 600 seconds each on hardware Chrome and Edge, native zoom at 200%, keyboard, NVDA and test-account MFA recovery. No Windows result is asserted here.

## Pending handoff

| Owner | Missing prerequisite | First action |
|---|---|---|
| Linux test operator | Approved isolated host with usable AF_UNIX | Run the default collector above and return the redacted JSON |
| PostgreSQL test operator | Approved disposable independent nodes and verified fencing controls | Follow POSTGRES_REPLICATION_LAB_V46.md and return fence, replay and rejoin evidence |
| Windows test operator | Separate Windows Docker Desktop restore clone, browser hardware and NVDA | Run windows-evidence-preflight.ps1, then verify-windows-restore-clone.ps1 against the backup inventory |
| Infrastructure and billing owners | Independent rootless Docker/TLS/CRL and authorized provider reconciliation | Use the existing operator runbooks after scope and access are available |
