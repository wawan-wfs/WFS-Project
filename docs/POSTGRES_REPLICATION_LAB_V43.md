# PostgreSQL quota laboratory v4.3

**Scope:** two PostgreSQL 16.2 processes on one Linux host, separate temporary data directories, numeric loopback, synthetic credentials, no WFS API integration.

```bash
python -m pip install -r requirements-postgres-lab.txt
PYTHONPATH=. python scripts/postgres-quota-lab.py
PYTHONPATH=. python scripts/postgres-replica-lab.py
```

The cleanup command deletes at most 128 expired receipts per transaction. Reservations do not run cleanup, avoiding that extra work under the global lock. Operators of this disposable lab must drive cleanup explicitly. It never deletes a receipt before its database-time retention boundary. The measurement seeded 10,000 expired receipts and verified that a 64-row request left 9,936 rows before draining the rest in 78 bounded batches.

The 32-client local benchmark processed 1,200 attempts, admitted 24 and denied 1,176 at quota, with no unavailability on the recorded final run. Throughput was 145.1 attempts/s and p95 was 361.5 ms, including new database connections. An earlier implementation that cleaned the backlog on the reservation path hit a lock timeout. The final harness records unavailable separately from quota denial and does not retry requests in the measurement.

The replica test took a physical streaming base backup, made one standby synchronous, and reserved 16 leases under `remote_apply`. It verified the standby was read-only, refused promotion while the old primary was running, failed closed while the standby was offline, then stopped the old primary before promoting the standby. All 16 acknowledged receipts returned the same lease identifiers after promotion. The recorded 0.623 seconds covers old-primary stop, promotion, and replay checks, not a service-level RTO. Following promotion the harness explicitly uses single-primary local durability, with no new standby and no implicit change of commit mode for an existing client.

This is **not** multi-host HA, automatic leader fencing, quorum validation, clock rollback qualification, or production authorization. The harness's manual local process fence cannot rule out a network partition on independently hosted systems.

References: [PostgreSQL 16 replication](https://www.postgresql.org/docs/16/runtime-config-replication.html), [WAL commit modes](https://www.postgresql.org/docs/16/runtime-config-wal.html) and [pg_basebackup](https://www.postgresql.org/docs/16/app-pgbasebackup.html).
