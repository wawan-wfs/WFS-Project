# WFS PROJECT v3.3.0-rc1 — Evidence and stop conditions

**Overall:** PARTIAL LOCAL RELEASE CANDIDATE — **PRODUCTION ADMISSION DENIED**. Exact input source: v3.2.0-rc1 partial release ZIP, verified 506 source checksum entries before edits.

| Gate | Current evidence | Disposition |
|---|---|---|
| 13 menus, 10 divisions, office telemetry, MFA, FinOps, original GLBs | Source unchanged except new opt-in authority mTLS and fixture capture support; regression and browser fixture tests completed | PRESERVED / LOCAL PASS |
| Cross-host mTLS preview authority code | New opt-in HTTPS mTLS client and private-IP-only Uvicorn launcher, actual localhost server/client TLS test with HMAC, wrong CA, wrong hostname, invalid credentials | LOCAL PASS; NO independent host |
| Secure authority revocation and PKI | HMAC nonce replay, per-request permission checks retained; independent CA policy, server-side client identity allowlist, CRL/OCSP or certificate revocation not deployed | INCOMPLETE / BLOCKED_EXTERNAL |
| Secure dynamic full-stack preview | v3.2 signed UDS authority and private socket broker preserved, separate TLS proxy not deployed | LOCAL PASS only / REAL TLS NOT RUN |
| Independent Linux rootless runner | v3.0 observation scripts preserved but no separate runner host available, no real Docker inspect, nftables, signed image policy, revocation, TTL/negative breakout proof | NOT RUN / BLOCKED_EXTERNAL |
| Authentic provider billing and hard caps | Existing local comparison and unknown-charge hold retained; official authenticated provider invoice/export unavailable | NOT RUN / BLOCKED_EXTERNAL |
| Windows Docker/GPU/NVDA/MFA recovery/restore | No Windows hardware available here; browser fixture CPU-3d only, no 10-minute Windows WebGL2 timings | NOT RUN / BLOCKED_EXTERNAL |
| Licensed rigged skeletal GLBs | Eight original CC0 GLBs retained; no rigged replacement because license/hardware evidence unavailable | NOT IMPLEMENTED / GATED |
| Local Python regression, HTTP, worker, Node, fixture screenshots | See `TEST_REPORT.md` for actual completed counts/logs | LOCAL PASS |
| Production-ready approval | Mandatory physical host, real wildcard TLS, authenticated provider, Windows GPU/NVDA/MFA/restore, real red team and independent review missing | **DENIED** |

No original daemon, firewall, certificate revocation logs, provider invoice or Windows hardware evidence is fabricated or substituted with synthetic screenshots.
