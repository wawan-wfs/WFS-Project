# v4.9 PostgreSQL rejoin acceptance lab

This is a disposable, loopback-only experiment. It is not wired to the WFS application or to HTTP. Run the two commands sequentially from the source root with the optional lab dependencies and PostgreSQL binaries.

```bash
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
```

The lab first demonstrates the same-host stop-before-promote guard and verifies 17 existing lease receipts after promotion. The newly promoted process refuses strict reservations before the standby is enrolled and the lab confirms no new receipt was written for that rejection. A fresh base backup becomes the replacement standby, rejects writes, and is explicitly enrolled as a synchronous standby. The strict `remote_apply` path then acknowledges one new lease. A repeat of that same request returns the same lease. The rebuilt standby independently shows that lease and all 17 retained receipts.

The original paused-replay scenario still verifies a locally committed but unacknowledged transaction, strict retry, and return of the same lease after replay. A watchdog expiry does not mean rollback. Cancellation is best effort and is not an end-to-end network deadline. No application timeout, quota or SQL changed. The same-host sequence is not proof of independent hosts, distributed fencing, automatic failover or physical power-loss recovery.
