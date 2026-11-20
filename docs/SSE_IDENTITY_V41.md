# v4.1 SSE session assertions

The local Linux UDS daemon can independently verify a WFS session before admitting a stream. Its read-only SQLite session lookup derives account and organization and checks mandatory MFA policy and any selected project grant in one query. The issuer signs an eight-second Ed25519 assertion with a fixed issuer and audience, an opaque replay identifier, the session digest and the optional project scope. The quota transaction verifies the signature and immediately rechecks the session, MFA and grant before consuming the assertion. Signature keys are generated in the daemon process and rotate on restart. Quota leases and replay records persist in the separate ledger. The application still rechecks each event before delivery.

The private channel now carries the raw **session bearer** to the identity daemon for the authorization request. It is never written to the ledger, returned in assertions, or logged. The local Unix socket must remain private to the trusted service identity. Do not proxy that socket, give preview workloads access, mount the application DB on a public gateway or reuse the transport credential. The authority trusts the WFS session database and existing login/enrollment MFA semantics, not independent identity-provider attestation. Shared UID processes are still inside one trust boundary.

## Configuration

Default remains the existing process-local admission when neither the socket nor assertion mode is configured. The v4.0 private UDS mode is still available explicitly for compatibility without assertion guarantees. Enable the new mode in a private Linux test installation by starting the authority with:

```bash
python -m app.sse_admission --socket /private/run/admission.sock \
  --db /private/state/sse-quota.sqlite3 --identity-db /private/wfs/wfs.sqlite3
```

Use the same injected `WFS_SSE_EDGE_SECRET` on the API and authority. Set `WFS_SSE_EDGE_SOCKET` and `WFS_SSE_EDGE_ASSERTIONS=1` on the API. Restart both components after changes. Do not reuse an untrusted ledger path or link. Authorization failure is 403, quota exhaustion 429, transport/configuration/database unavailability 503. A configured assertion API never falls back to process-local quota. Releases are idempotent and cancellation during admission triggers late cleanup. TTL bounds lost releases. No local/shared mode is recommended for public ingress in this RC.

## Cross-host datastore decision

Do not run SQLite WAL over a network filesystem. A shared PostgreSQL primary is the first candidate because a single transaction can consume a nonce, expire leases, check session/tenant/global counts and persist a reservation. Benchmark the global coordination point and include a uniqueness/idempotency constraint and bounded transaction wait. Verify primary failover with explicit acknowledged-write durability and authoritative store time before relying on replay protection or global caps.

A Redis script can perform the same bounded reservation efficiently, but asynchronous replica failover can lose an acknowledged reservation or nonce. Demonstrate durability and leader fencing before accepting that option. For either candidate, keep revocation authoritative, enforce private mutually authenticated transport, and test clock skew, rolling key rotation, cancellation, split brain, restart and fairness on independently hosted nodes. This is an architectural evaluation only. No shared database or cross-host issuer was provisioned or tested in v4.1.
