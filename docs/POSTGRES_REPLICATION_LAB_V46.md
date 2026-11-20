# v4.6 PostgreSQL local repeatability

The connection scope, SQL and strict watchdog in app/sse_pg_lab.py are unchanged from v4.5. The watchdog is an acknowledgement deadline, not an end-to-end network deadline. An undelivered cancel does not turn a late result into a valid acknowledgement. A timeout does not prove rollback. Strict retry keeps the same request identity and requires the replay barrier for an already committed allowed lease. The new contract tests check timely success, a delayed watchdog thread, an undelivered cancel and a server warning. These contract tests simulate those conditions and are separate from the real replica experiment.

```bash
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
```

Run these sequentially. When first run concurrently in this runtime, the labs encountered connection or statement timeouts. A separate v4.5-scale run also failed the fixed-count assertion. The v4.6 load harness uses a 300-second fixture-only lease TTL so the count check is independent of ordinary short lease expiry, and rejects a benchmark that outlasts the fixture. It still explicitly expires a lease in the expiry test. No application timeout, security control, or quota limit was relaxed. The isolated v4.6 scale run returned 24 admitted, 1,176 denied and zero unavailable.

The isolated real replica run observed a paused synchronous replay, client unavailable at 1.766 seconds with a 1.2-second watchdog, and successful strict retry with the same lease after replay resumed. All 17 leases were retained after stop-before-promote. The replacement standby was read-only. The timing is observed for that run and includes more than the watchdog itself.

For independent acceptance, an operator needs two approved disposable hosts, verified fence evidence before promotion, evidence that the old writer cannot commit, a synchronous retry under lag or standby loss, and read-only rejoin. The same-host stop guard and locally rebuilt replica do not meet this requirement. Keep the loopback prototype disconnected from application HTTP.
