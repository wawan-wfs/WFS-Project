# v4.4 PostgreSQL replay and rejoin evidence

The optional quota experiment remains disconnected from WFS HTTP. Two PostgreSQL 16.2 processes ran on one Linux machine. PostgreSQL replay was paused on the standby after a set of confirmed reservations. The harness canceled a waiting synchronous commit on its disposable primary and confirmed that the lease had committed locally but was not visible on the standby. The client returned unavailable, not an acknowledgement.

A retry of that live receipt previously took a read-only path. Strict mode now issues a WAL-generating update under the same quota lock before returning an existing allowed receipt. In the test the retry entered the synchronous replication wait state and returned the same lease only after replay resumed. No second slot was allocated. This is a synchronous commit barrier, not a replacement for checking the receipt or authoritative tenant scope.

Promotion remained forbidden while the old primary was running. After an explicit stop and local standby promotion, all 17 acknowledged lease IDs matched. The harness refused to start the retired data directory. It created a new base backup from the promoted node and verified the replacement at the original endpoint was read-only. Post-promotion quota requests used an explicitly chosen local commit mode. The new replica was not enrolled as a synchronous standby in this run.

```bash
python -m pip install -r requirements-postgres-lab.txt
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
```

The lag injection uses a bounded test-side cancel and is not a guarantee that PostgreSQL statement timeout bounds a synchronous COMMIT in every deployment. The lab is not distributed fencing, quorum or multi-host HA evidence. A stopped process and a retired directory list are insufficient for an independent node or network partition.

References: [PostgreSQL recovery control](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-RECOVERY-CONTROL) and [synchronous commit settings](https://www.postgresql.org/docs/16/runtime-config-wal.html).
