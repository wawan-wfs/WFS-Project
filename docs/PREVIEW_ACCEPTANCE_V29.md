# WFS PROJECT v2.9 — Preview isolation status

The existing v2.8 isolated-origin static/React gateway is retained, including one-use tickets, per-request tenant/session authorization, secure path-bound cookies and CSP sandbox. See `docs/PREVIEW_GATEWAY_V28.md`. Local TestClient assertions are **not** proof of production TLS/DNS/proxy isolation.

**Production gates still blocked:** a dedicated public preview hostname with independently verified TLS, mTLS/identity-bound trusted reverse proxy, secret-stripped proxy access logging, CSP/SameSite cross-origin browser red team and real concurrent tenant tests; securely brokered FastAPI/Node preview containers over an internal network (not public loopback ports), per-project origin isolation and request-by-request revocation. Do not enable public preview ports or put dynamic code behind an unreviewed reverse proxy configuration. Operator must capture evidence from a real deployment without credentials/URL tickets.
