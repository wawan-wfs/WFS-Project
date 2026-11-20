# WFS PROJECT v3.1 — Per-project dynamic preview broker

**Classification: source implementation and local Unix-socket tests only. NOT a publicly deployed TLS gateway or a production isolation certificate.**

The v2.8/v3.0 static/React isolated-origin gateway remains unchanged in its public interface. The new v3.1 path allows an *operator-provisioned* FastAPI or Node preview to speak HTTP through a Unix-domain socket to the same trusted gateway code. No container TCP port is exposed or looked up by request. PostgreSQL is **not** proxied to the browser: it stays on the isolated application network. No Docker socket or registry admin credentials belong in the gateway, dashboard or generated container.

## Security contract

- Static: `https://preview.example.invalid/p/<id>/index.html`, ticket under `/t/<secret>`.
- Dynamic: `https://<20-hex-project-id>.dyn-preview.example.invalid/`, ticket under that same exact host `/t/<secret>`. Every project gets a distinct **browser origin** (hostname and cookie scope), preventing an app from reading another project's `localStorage` or session.
- The gateway requires an operator-controlled proxy on loopback, its private header and `X-Forwarded-Proto: https`; incoming user-supplied copies of those headers MUST be stripped and overwritten by the trusted proxy. Configure different public DNS names for the dashboard, static gateway and wildcard dynamic domain, preferably independent registrable domains.
- Tickets are random, single-redeem, short-lived; the correct host is checked **before** consumption. Session, organization, project grants, and project status are checked on **each** dynamic request. Disabled sessions and revoked project access fail closed. Cookies are Secure, HttpOnly and host-only (no Domain attribute).
- Dynamic request bodies are streamed with a 1 MB cap; responses are bounded to 4 MB. Query and path are checked, dot-segments/ambiguous URL encoding rejected. No upstream `Set-Cookie`, `Authorization`, `Cookie`, `X-WFS-*`, CORS headers, WebSocket upgrade or arbitrary outbound URL is forwarded. Returned pages receive a restrictive CSP and cache prohibition. Unsafe inline scripts, cross-origin assets, and certain apps requiring custom cookies will **not** work; this is intentional.
- The gateway connects ONLY to `${WFS_PREVIEW_SOCKET_ROOT}/<project-id>.sock`, never to arbitrary IP/ports. Socket root and socket must not be group/world writable; both file ownership and live Linux `SO_PEERCRED` UID must match `WFS_PREVIEW_SOCKET_UID` (or trusted root ownership for the root directory). This transport is **Linux only**.
- A Unix socket is not by itself a container sandbox. The operator must prove the preview host, application container and its DB network are isolated; workload process cannot write the gateway's socket directory, database, auth store or operator credentials.

## Operator setup (illustrative, NOT executed on a production host)

1. Create two DNS zones/hostnames with genuine TLS (including a wildcard certificate for `*.dyn-preview.example.invalid`) via the trusted reverse proxy. Keep dashboard and previews on distinct, non-shared browser origins. Make sure no raw app `127.0.0.1` port is exposed to the public network.
2. Create a private root-owned or trusted-operator-owned socket directory, e.g. `/run/wfs-preview/sockets`, mode `0700`. For each approved dynamic project, start its **isolated** workload on a private UDS named `<project-id>.sock`. The identity presented by the workload process/socket must be explicitly operator approved; never accept a user-submitted socket path, UID or hostname. This stage is not automated by WFS v3.1.
3. Configure the **gateway service**, not a generated app:

   ```text
   WFS_PREVIEW_PUBLIC_ORIGIN=https://preview.example.invalid
   WFS_PREVIEW_DYNAMIC_DOMAIN=dyn-preview.example.invalid
   WFS_PREVIEW_SOCKET_ROOT=/run/wfs-preview/sockets
   WFS_PREVIEW_SOCKET_UID=<trusted-operator-approved-uid>
   WFS_PREVIEW_PROXY_KEY=<random-secret-at-least-32-chars>
   ```

   Keep the proxy key and database authorization access only in trusted, restricted processes. Starting the ASGI app by itself does not configure TLS: the trusted proxy must be provisioned separately. Bind the ASGI gateway only to loopback and ensure the public proxy overwrites the two trust headers. Disable or redact `/t/*` access logs and redact HAR, auth cookies and private tickets.
4. Confirm the private preview app has a **separate Linux sandbox** with deny-by-default egress, read-only source, no Docker socket, no gateway DB, memory/CPU/PID/FS limits, unique identity and TTL cleanup. Approve and scan fixed image digests. Dynamic broker transport is not a replacement for this step.
5. With two approved test projects and two non-identical tenants, run the local regression suite and collect real browser/HAR evidence for: unauthenticated denial, ticket reuse, wrong-host ticket denial, login/MFA, cross-project cookie replay, revocation after logout, revocation during session, CSP/cookie/origin inspection and generated app asset loading. Record server-side logs with secret redaction.
6. On a real TLS deployment, run the **negative-only** operator probe:

   ```bash
   python scripts/acceptance_v31_tls_preview.py \
     --static-origin https://preview.example.invalid \
     --dynamic-origin https://aaaaaaaaaaaaaaaaaaaa.dyn-preview.example.invalid \
     --dynamic-origin https://bbbbbbbbbbbbbbbbbbbb.dyn-preview.example.invalid \
     --output /secure-evidence/v31-preview-tls.json
   ```

   Use actual configured DNS names and approved project IDs. The probe checks TLS certificate verification, unauthenticated access denial and protective headers. It does **not** prove authorization, concurrent multi-tenant security, Docker isolation or live application functionality.

## Operational boundaries and remaining blockers

The application currently uses the WFS store to validate dashboard session/project grants. This source release does not provide a replicated authorization service with independent credentials for a separately deployed gateway host; do **not** copy the production SQLite database to an untrusted runner. The code has no public deployment proof, external red team, wildcard TLS certificate, DNS, per-attempt mTLS daemon identity or real Docker inspect records. It is a **local/operator-controlled release candidate only**. Keep `WFS_PREVIEW_DYNAMIC_DOMAIN` and `WFS_PREVIEW_SOCKET_ROOT` unset until the operator has isolated the workload and installed the trusted proxy.

## Rollback

Stop the gateway and operator preview workers; revoke preview sessions via logout/grant revocation, delete all temporary Unix sockets after stopping their owners, restore the matched v3.0 source and its data backup. There is **no database schema migration** in v3.1. Never reuse the new dynamic-preview hosts with the old gateway and never expose app TCP ports as a workaround.
