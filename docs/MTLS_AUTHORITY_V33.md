# WFS PROJECT v3.3 — Optional mTLS preview authority transport

**Classification: LOCAL CODE + ACTUAL LOOPBACK TLS TESTS ONLY. No independently deployed host, real public wildcard TLS or production admission.** Source baseline is the exact v3.2 partial ZIP and its verified release manifest. The v3.2 UDS mode remains the local default. This addition is only for the trusted **API/identity** authority and isolated **preview gateway** to communicate across two operator-controlled private hosts. It is **not** a remote Docker runner mTLS certificate mechanism.

## Trust model

- Dashboard/identity service is the only process with the production WFS SQLite store, MFA/session state and project grants. The dynamic preview gateway has none of them; it must not mount the DB, Docker socket, provider keys, or generated project source.
- The authority exposes the existing bounded signed operations (`ticket`, `exchange`, `verify`) with per-request HMAC-SHA256 timestamp/nonce replay defense. The new transport uses TLS with server certificate/hostname verification plus a client certificate trusted by the authority; UDS mode still performs SO_PEERCRED.
- The example service launcher accepts ONLY an explicit private/loopback IP; wildcard, public IP and link-local binds are rejected. Client requires exact `https://<host-or-IP>:<port>` with no path, query, userinfo or HTTP downgrade, a pinned trusted CA bundle, client cert and private key. Private key must be an operator-owned regular file with mode 0600/0400 (or equivalent, not a symlink). Invalid setup fails closed.
- Separate your PKI root, HMAC service key, TLS client private key, session tokens and Docker runner credentials. Never store actual secrets in Git, screenshots, logs, `.env.example` or source ZIP.

## Operator setup (NOT performed by this release)

1. Provision two distinct trusted Linux hosts or properly separated isolated nodes; install firewall restrictions so ONLY the gateway identity may reach the authority private IP/port. Do not expose the authority or dynamic app sockets to the public Internet. Ensure gateway has **no** production SQLite or runner credentials.
2. Configure a dedicated, least-privilege private CA or subordinate issuance policy specifically for preview authority. Issue a server cert with the actual hostname/IP SAN, EKU for TLS server auth; issue gateway client cert with client auth EKU, short lifetime and subject identity. Configure cert issuance logs, renewal, emergency revocation and a reliable CRL/OCSP/allowlist enforcement layer; do not claim that base Uvicorn alone proves active revocation. This build does not implement an allowlist/revocation check at the application layer.
3. Supply secrets through your service manager with restrictive mode/owner and a rotated **separate** 32+ character `WFS_PREVIEW_AUTHORITY_KEY` available to authority and gateway only. Start the trusted server (sample; choose your real private IP and paths):

```bash
export WFS_PREVIEW_AUTHORITY_KEY='<read securely from service manager, not a shell-history command>'
python scripts/serve_preview_authority_mtls.py \
  --bind 10.20.30.4 --port 9443 \
  --server-cert /run/secrets/wfs-authority-server.pem \
  --server-key /run/secrets/wfs-authority-server.key \
  --client-ca /run/secrets/wfs-gateway-client-ca.pem
```

4. Configure **only the gateway** with:

```ini
WFS_PREVIEW_AUTHORITY_REQUIRED=1
WFS_PREVIEW_AUTHORITY_MODE=mtls
WFS_PREVIEW_AUTHORITY_URL=https://10.20.30.4:9443
WFS_PREVIEW_AUTHORITY_CA=/run/secrets/wfs-authority-ca.pem
WFS_PREVIEW_AUTHORITY_CERT=/run/secrets/wfs-gateway-client.pem
WFS_PREVIEW_AUTHORITY_CLIENT_KEY=/run/secrets/wfs-gateway-client.key
WFS_PREVIEW_AUTHORITY_KEY=<same operator-managed service HMAC secret>
```

5. Require an **independently deployed** TLS wildcard ingress for each dynamic preview origin, exact host-only cookie scoping, redacted ticket logging, no open raw app ports, and internal-only preview runtime broker. `app/preview_gateway.py` still mandates trusted proxy proof. Do not use demo localhost test certs in production.
6. Test issuer compromise, mismatched hostname, expired/revoked client, CA rotation, HMAC rotation, concurrent tenants, grant/session revocation, downtime, firewall, actual HAR redaction and fail-closed behavior. Keep original redacted evidence. A successful loopback test does not prove host independence or revocation.

## Local verification actually completed

`PYTHONPATH=. python -m pytest -q tests/test_v33_authority_mtls.py` tested a real in-process localhost SSL server requesting client certificates, successful mutual TLS + signed HTTP, wrong CA, wrong hostname, missing/unsafe key, explicit HTTPS origin validation and private-bind policy. This is **not** a deployed reverse proxy or a production mTLS/PKI lifecycle test. Full local regression, HTTP and worker E2E are separately recorded in `TEST_REPORT.md`.

## Rollback

First disable public ingress and revoke new preview tickets/cookies, then shut down the mTLS listener. Remove gateway `WFS_PREVIEW_AUTHORITY_MODE=mtls` and URL/client cert settings and restore previous `WFS_PREVIEW_AUTHORITY_MODE=uds` plus trusted UDS setup **only for local/private deployment**. Restore the matched v3.2 source + backup if needed. Never downgrade a physically separate gateway to plaintext or a shared DB for convenience. There is no v3.3 database schema migration.
