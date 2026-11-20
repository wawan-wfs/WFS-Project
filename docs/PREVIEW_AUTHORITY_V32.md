# WFS PROJECT v3.2 — Segregated dynamic preview authority

**Evidence classification:** locally tested two-process Unix-domain-socket authorization; **not** a tested public HTTPS deployment, independent host or production admission. Dynamic preview only. The existing static/React preview renderer still reads local store and must be hosted on the trusted local service or be redesigned before independent deployment.

## Purpose / architecture

The v3.1 gateway needed WFS SQLite access to exchange preview tickets and recheck per-request authorization. In v3.2 the **dynamic-only** gateway can instead use a separate, narrowly scoped authority service, with three operations: `ticket`, `exchange` and `verify`. The authority stays inside the trusted API/security boundary with database access. The gateway uses a private Unix socket, a shared service secret **not passed to generated app code**, HMAC-SHA256 over timestamp, unique nonce, endpoint and JSON request body. The authority denies expired timestamps and nonce replay in its one-worker process. The gateway rechecks a session's project/organization grants for every dynamic request via this service and refuses traffic when the authority is unavailable.

- Gateway holds **no copy** of production SQLite, no runner/Docker credentials and no project filesystem mount. Its runtime only needs proxy identity, TLS/DNS config, `WFS_PREVIEW_AUTHORITY_*` client settings, and operator-approved application Unix sockets.
- Authority holds database access and the service-secret verifier; it does **not** serve dynamic project content or accept arbitrary URLs. It must run on the trusted host / trusted Kubernetes node with UDS volume access restricted to the gateway. A UDS **cannot** authenticate across independently separated hosts; do not export this socket over TCP or publicly expose the authority service.
- Generated app listens only on its operator-registered UDS. The broker continues to verify `SO_PEERCRED` and strip dashboard cookies, auth headers and `Set-Cookie`.
- Browser receives a host-only, HttpOnly, Secure cookie for each per-project TLS origin. The application cannot access dashboard tokens. Revocation and MFA access constraints are checked by the authority on every request.

### Setup — disabled unless operator explicitly chooses

1. On the **trusted API/identity host**, create a dedicated private socket directory (mode `0700`) with trusted owner. Example: `/run/wfs-preview/authority/`. Configure service `WFS_DATA_DIR` to the **existing trusted data directory**. The source is otherwise unchanged; there is no DB migration in v3.2.
2. Generate a separate high-entropy `WFS_PREVIEW_AUTHORITY_KEY` (minimum 32 characters; preferably >= 256-bit CSPRNG). Store it outside the repository, in the API-host authority secret store and gateway secret store only; never share with the runner or user applications. Restrict processes and rotate key during a coordinated maintenance outage. Only the generated HMAC signature goes on the UDS wire; the shared key is never sent on it.
3. Start the **authority on Unix socket only**, not TCP:

   ```bash
   python scripts/serve_preview_authority.py --socket /run/wfs-preview/authority/authority.sock
   ```

   The script requires a private existing socket directory and uses `0700` umask and `0600` socket mode. Use a single worker per socket; the replay cache is process-local. Ensure API host, Docker runner and untrusted app are independently permission-separated. Use service-manager private mount namespaces and an approved Unix group / UID only if peer access is deliberately configured.
4. On the gateway side set:

   ```text
   WFS_PREVIEW_AUTHORITY_REQUIRED=1
   WFS_PREVIEW_AUTHORITY_SOCKET=/run/wfs-preview/authority/authority.sock
   WFS_PREVIEW_AUTHORITY_UID=<trusted auth service UID>
   WFS_PREVIEW_AUTHORITY_KEY=<separately managed secret>
   WFS_PREVIEW_DYNAMIC_DOMAIN=<approved wildcard dynamic preview domain>
   WFS_PREVIEW_PUBLIC_ORIGIN=https://<distinct trusted static preview hostname>
   WFS_PREVIEW_PROXY_KEY=<separate trusted reverse-proxy secret>
   WFS_PREVIEW_SOCKET_ROOT=/run/wfs-preview/sockets
   WFS_PREVIEW_SOCKET_UID=<approved application broker UID>
   ```

   **Never set `WFS_DATA_DIR` to a production data copy in the gateway deployment; do not mount the DB into the gateway.** The authority is started on the API/identity side and uses its own configured database. With the remote authority enabled, static preview routes on that gateway are intentionally disabled: keep static preview on the existing local gateway until its content and authorization paths are separately isolated.
5. Configure the real wildcard DNS + certificate, host-only cookies and exact host matching at a TLS reverse proxy, with untrusted forwarded headers stripped. Block raw application ports; expose only the trusted gateway. Validate two concurrently active tenants, reverse proxy request log redaction, host firewall, and real session/grant revocation. Run `scripts/acceptance_v31_tls_preview.py` only **after** installing actual TLS; its negative probe alone is not production proof.

## Verification and limits

`PYTHONPATH=. python -m pytest -q tests/test_v32_remote_authority.py tests/test_v32_authority_signature.py`

The local IPC integration test boots an independent Uvicorn process, then explicitly makes SQLite unavailable **to the gateway process**, proving that dynamic authorization can be performed through the local authority socket. It validates one-time redemption, cross-tenant denial, logout revocation, no secret forwarding, signature failure, stale timestamp and replay denial. It is **not** an Internet TLS test and does not attest Docker isolation, source immutability or per-attempt daemon-side mTLS.

**Residual risks:** no externally provisioned trusted runner, signed image admission, official live provider invoice reconciliation, public wildcard TLS, independent peer review, Windows GPU/NVDA/MFA recovery, or disaster-recovery acceptance. The HMAC key is a long-lived *service credential*, not a one-time Docker client certificate or a substitute for those requirements. A gateway on a physically separate node needs an independently designed mTLS transport and additional security review, **not** a mounted production database or raw-forwarded UDS.

## Rollback

Disable `WFS_PREVIEW_AUTHORITY_REQUIRED` and both authority socket variables **only after closing public TLS ingress**, stop dynamic workloads, and revoke preview grants. Restore the v3.1 source with its matched data backup. Do not run v3.1 on a public gateway with the production DB as a workaround; v3.1 remains a **local-only** fallback.
