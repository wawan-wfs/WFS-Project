# WFS PROJECT v2.4 — Security review and unresolved gates

## Boundaries retained / regression validated

- HTTP gateway does **not** receive Docker Engine socket or execute code emitted by AI agents. Local operator runner remains a distinct approval surface.
- Authenticated `/api/office/live` requires a valid session; explicitly requested private project IDs pass `_verify_visible`, while visible aggregate event/agent lists are scoped to project membership; checked by existing private-project tests.
- CSRF for mutating endpoints, `HttpOnly` and strict `SameSite` cookies, trusted hosts, artifact integrity, preview sandboxing, SSE replay scope, bounded task recovery and provider token accounting are retained. See tests for coverage; none of this is a penetration-test certificate.
- New GLB parser uses local paths only, bounded asset size / accessor counts, typed primitive validation and no dynamic code evaluation. Invalid assets fall back rather than granting capabilities.
- New inspector uses `.textContent` for agent/task/project strings, avoiding HTML interpretation of private data supplied by the API. No new privileged API route added.
- Frontend still has no tenant-wide MFA/SSO or fully authenticated isolated preview gateway; do not expose to the public Internet.

## Known risks

1. Live preview containers require an operator and may serve untrusted source code. Docker's kernel isolation is not a complete security boundary; perform adversarial container breakout/isolation acceptance on a dedicated host.
2. Independent user/project RBAC does not equal independently secured customer tenancy. Full organization/tenant isolation, audit retention and backup-at-rest encryption remain pending.
3. CSP and TLS policy must be validated behind any reverse proxy; cookies require `WFS_COOKIE_SECURE=true` with HTTPS for remote use.
4. Production versions need resource-limit evidence, runtime filesystem permissions, network deny-by-default, secrets scanning, SCA, application penetration testing and incident response drills.
5. GPU WebGL2 shader and driver robustness cannot be certified from the CPU fixture. Invalid/unsafe shaders and GLBs should be tested under real browser GPU environments.

The release classification is **Local Release Candidate**, not production certification.
