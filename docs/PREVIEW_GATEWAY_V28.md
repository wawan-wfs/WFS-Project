# WFS PROJECT v2.8 — Isolated-origin preview gateway (partial)

**Status: isolated FastAPI gateway and TestClient security tests implemented. Real HTTPS reverse proxy, DNS isolation and external red team are NOT tested.** Local operator dynamic Docker previews are still loopback-only and are **not** proxied by this gateway. Supported new gateway content: verified static and single-HTML inlined React/Vite output. It must NEVER run on the dashboard's origin.

## Trust model

- Dashboard `POST /api/projects/{pid}/preview-ticket` requires active login, CSRF and project read access; returns a high-entropy one-use URL expiring after 5 minutes. Ticket is kept as a SHA-256 hash in the existing database.
- Browser visits the dedicated `https://preview.example.com/t/<opaque>` origin. A **separate** TLS proxy sends only validated requests to `127.0.0.1:8091` with an operator-controlled secret header; the gateway refuses nonloopback direct requests, missing proxy authorization, wrong host or missing HTTPS forwarded protocol.
- On a valid exchange, gateway stores only the preview session cookie **hash**, redirects to a clean `/p/{pid}/index.html` URL, and sets a `Secure; HttpOnly; SameSite=Lax` 5-minute cookie scoped to the specific project path. Ticket reuse fails.
- On **every content request** gateway verifies the DB grant is not expired/revoked; the original dashboard login session remains active; account/org/project are still permitted; project delivery status and signed artifact manifest are valid. Logout, disabled account and removed project permission stop subsequent requests. Served HTML has a sandboxed CSP with opaque origin and no network/form access, no caching and no permissive embedding.
- No preview bearer secret is stored in localStorage. **The one-use URL is still a bearer token until redeemed; redact `/t/*` from proxy logs, never place it in analytics, and never forward it via Referer.** TTL mitigates but does not eliminate interception risks.

## Reverse proxy example — illustrative, NOT deployed

Set `WFS_PREVIEW_PUBLIC_ORIGIN=https://preview.example.com` and `WFS_PREVIEW_PROXY_KEY=<strong-random-dedicated-secret-at-least-32-chars>` **only** in the separately deployed gateway environment. Ensure dashboard `WFS_ALLOWED_HOSTS` lists dashboard hostname only and never lists preview hostname or `*`. Use a valid externally trusted TLS certificate and no direct firewall ingress to port 8091.

```nginx
server {
    listen 443 ssl http2;
    server_name preview.example.com;
    ssl_certificate /etc/ssl/private/preview-fullchain.pem;
    ssl_certificate_key /etc/ssl/private/preview-key.pem;
    # Configure TLS protocols, OCSP, headers and rate limits according to operator policy.
    access_log off;  # Do not log one-time /t/<ticket> URLs.
    location / {
        proxy_pass http://127.0.0.1:8091;
        proxy_set_header Host preview.example.com;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-WFS-Preview-Proxy-Key "<EXACT-SAME-PRIVATE-RANDOM-SECRET>";
        proxy_set_header Cookie $http_cookie;
        proxy_read_timeout 30s;
        proxy_buffering on;
    }
}
```

Start **only** on preview gateway host (and only after TLS ingress is deployed, verified, and access controls reviewed):

```bash
python -m uvicorn app.preview_gateway:app --host 127.0.0.1 --port 8091 --no-access-log
```

The gateway requires the same authorized `data/` database for immediate grant revocation; do not grant access to the Docker daemon or host SSH keys. A production deployment should move grants to a purpose-built shared authorization store with its own narrow credentials, as direct database sharing between hosts is not yet an approved isolation architecture.

Dashboard local preview `/preview/{pid}/index.html` remains for backwards-compatible local-only use with opaque sandbox. It must not be served publicly. Operator-created FastAPI/Node/Postgres previews still publish loopback ports for local use; public exposure is forbidden until a dedicated authenticated origin proxy and internal-only container routing are implemented.

## Manual red-team checklist (NOT RUN)

Ticket replay; missing/altered `X-WFS-Preview-Proxy-Key`; direct port 8091 access; forged `Host`/`X-Forwarded-Proto`; external `Origin` and CSRF; session logout, disabled account, revoked member and deleted project while a preview tab stays open; cross-organization project UUID guessed; sandbox `fetch`, JS `document.cookie`, forms, iframe escape and cross-origin navigation; TLS certificate mismatch; caching and access log leakage. Run on real reverse proxy, save HTTP traces without tokens or secrets, and maintain a rollback plan.
