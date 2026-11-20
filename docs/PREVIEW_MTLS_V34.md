# WFS PROJECT v3.4 — Cross-host authority mTLS / replay hardening

**Status:** LOCAL CODE / OFFLINE NGINX CONFIG ONLY. There is no independent host, valid public DNS, deployed PKI, independently verified nginx instance or production admission evidence in this release. **Do not enable public ingress.**

## Changes

1. `scripts/render_authority_mtls_proxy.py` renders a bounded, operator-only nginx HTTP-scope config for a *dedicated private IPv4* authority listener. It rejects public/wildcard/loopback bindings, same-address gateway identity, injection in server name/paths, privileged ports and expired/non-clientAuth certificates. It requires a CA and CRL, validates client certificates with `ssl_verify_client on`, and restricts the registered client identity by nginx `$ssl_client_fingerprint:$ssl_client_serial`. SHA1 here is nginx's **certificate identity selector**, not the authentication primitive; the actual cryptographic certificate trust is verified against the CA and CRL. Operators must verify nginx interpretation of the fingerprint on the deployed version; this code has not run `nginx -t`.
2. Requests from other gateway IPv4 addresses are rejected. Only three `/internal/...` POST routes proxy to the trusted API-host UDS; request cookies and `Authorization` are stripped and no access log can record tickets/query strings. The authority application **still requires its HMAC signature**, timestamp, nonce and DB-based per-request authorization.
3. Signed nonce replay protection now persists in the **trusted dashboard/identity SQLite database** table `preview_authority_nonces`, with a transactionally serialized unique primary key and 120-second retention. Prior in-process nonce caching could be reset by a process restart. Database failure is **deny by default**. The application never auto-creates this table from incoming HTTP requests.
4. The existing opt-in direct Uvicorn mTLS development listener and v3.2 UDS local mode remain available. **They do not by themselves satisfy production client revocation**. For independent-host deployment, use an audited ingress enforcing client identity, issuer, CRL and network policy in addition to the authority service's HMAC checks.

## Example *offline* configuration generation

Choose exact, real operator-controlled paths and RFC1918 IPs; never copy this example unmodified. An authenticated operator should check expiry, issuer, SAN, EKU, CA trust and CRL independently and keep secrets outside the repo. A private ingress is not a public preview TLS gateway.

```bash
python scripts/render_authority_mtls_proxy.py \
  --bind 10.18.0.5 --gateway 10.18.0.6 \
  --hostname auth.internal.example --port 9443 \
  --socket /run/wfs-preview/authority/authority.sock \
  --server-cert /etc/wfs/tls/server.pem \
  --server-key /etc/wfs/tls/server.key \
  --client-ca /etc/wfs/tls/gateway-ca.pem \
  --client-crl /etc/wfs/tls/revoked.pem \
  --client-cert /secure/verified-gateway-client.pem \
  --output /secure/generated-wfs-authority-nginx.conf
```

The output is written mode `0600` and refuses to overwrite an existing file. It must be installed manually by an authorized operator inside **nginx `http {}`**, not nested inside a `server` block. Ensure the nginx worker has access to the private UDS, without ever making it world accessible. Perform operator-controlled `nginx -t` **before** reloading. The generated config is **NOT** a signed CA, PKI issuance service, remote authenticated admission, or proof of deployment.

The trusted host should start `scripts/serve_preview_authority.py --socket /run/wfs-preview/authority/authority.sock` *after* applying the database migration. Restrict socket directory to 0700 and socket to 0600; assign nginx/authority trusted service roles without exposing the socket to untrusted workloads or the runner. The gateway client uses `WFS_PREVIEW_AUTHORITY_MODE=mtls`, exact private TLS endpoint, trusted CA, client cert and private key, separately managed HMAC key, and **no access to production SQLite**.

## External acceptance checks (not executed here)

- Use `nginx -t`, then verify correct server SAN/hostname, client cert, trusted CA, CRL and exact gateway IP. Reject wrong/expired/revoked client certificate, wrong hostname/SNI, incorrect issuer, missing CRL, wrong IP, wrong request HMAC, replay and authority restarts. Check certificate *renewal and CRL reload* before and after rotation; do not assume CRL updates instantly affect established TLS connections.
- Capture redacted original firewall config, listener process/UID/mount namespace, real TLS wire negotiation, timestamped revocation tests, 2-tenant browser HAR (no cookies/tickets), DNS records, and proxy access denials. Separate hosted static vs dynamic previews; do not expose raw project ports.
- Keep the actual API identity host isolated from the preview gateway and Docker runner. Never mount database, credential store or Docker socket in the gateway.

## Migration / rollback

Before starting a new authority version, stop affected preview ingress and make a **matched backup of trusted SQLite data and `.env`**, keeping exact old code. From a separate trusted operator/identity process, run the existing application migration `store.init_db()` on a **nonproduction clone first**, review resulting table `preview_authority_nonces`, then restart the authority. A missing migration will reject signed requests rather than bypass replay protection. No existing rows need alteration or deletion; migration is additive and idempotent. To roll back, close ingress/revoke tickets, restore matched v3.3 source and database backup, restart only internal services. Do not drop the nonce table or downgrade to unsafe public UDS/plaintext access during an active session.
