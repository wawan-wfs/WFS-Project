# v4.2 local PostgreSQL quota experiment

The prototype is **not connected to the WFS API**. It accepts synthetic, already-verified identities from a trusted local test harness. It neither authenticates a real WFS user nor replaces the existing session and per-event authorization. Both the code and the lab runner restrict PostgreSQL to loopback. The WFS application does not import the lab dependencies.

The transaction takes a shared singleton row lock under explicit READ COMMITTED isolation. The database clock determines freshness, expiration and receipt retention after lock acquisition. Unique request IDs, nonce and lease IDs, scope-bound release, and a committed receipt make a retry with the exact same request identity return the same live lease. A changed scope, a duplicate nonce under a new request ID, an expired assertion or a released lease cannot allocate a second live slot. Lock/database failure is unavailable, never a local fallback. The single lock deliberately trades throughput for a simple shared cap. Local WAL flush is required. No primary election, replica failover, quorum durability, clock rollback qualification or external identity bridge is implemented.

Run on a disposable Linux environment with PostgreSQL binaries or the optional wheel fixture:

```bash
python -m pip install -r requirements-postgres-lab.txt
PYTHONPATH=. python scripts/postgres-quota-lab.py
```

The harness starts a password-authenticated temporary database bound to 127.0.0.1 and stops it on exit. It exercises a clean restart, immediate-stop crash recovery, discarded acknowledgement, rollback, timeout, expiry, and simultaneous quota checks. The latency measurement includes new database connections and measures a single process with eight client threads, not an application request or an HA cluster. See the raw result in `docs/V42_EVIDENCE/postgres-rc.log`.

Reference: [PostgreSQL transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html) and [PostgreSQL WAL settings](https://www.postgresql.org/docs/16/runtime-config-wal.html).
