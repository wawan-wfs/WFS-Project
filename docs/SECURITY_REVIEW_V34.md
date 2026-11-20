# Security delta v3.4.0-rc1

## Fixed locally

- Durable replay nonce ledger in trusted SQLite replaces in-memory-only cache. Conflicting nonces are rejected transactionally, including concurrent clients; DB failures do not downgrade to volatile memory. Additive schema migration; previous data format preserved.
- Offline reverse-proxy renderer requires RFC1918 addresses, exact DNS, CA+CRL and an explicit client cert fingerprint/serial allowlist. It allows only signed HMAC authority routes and strips dashboard cookies/auth. The resulting config has **not** been deployed or tested with real nginx/PKI.
- The offline provider comparison now reports `comparison_complete` separately and always sets `reconciled=false`, `provider_evidence_authenticated=false`, `operator_clearance_eligible=false` for arbitrary CSV inputs. No ledger mutations or unknown-charge clearance.
- Windows script refuses authenticated remote HTTP, records only local metadata by default, and requires explicit `-RunBrowser` opt-in.

## Open vulnerabilities / blocked gates

- Nginx fingerprint output/CRL freshness/client revocation and wildcard TLS behavior require actual runtime and independent reviewer. SHA1 client fingerprint is an nginx identity-selector, not an independent signing scheme. A dedicated trusted CA, CRL, serial enforcement and limited network access are required; no real host evidence exists.
- Signed nonce ledger uses SQLite and writes on every HMAC request; capacity, concurrency, WAL, backup/restore and availability must be profiled on the deployed trusted identity host. Ingress must fail closed when DB unavailable.
- Rootless Docker daemon not available; no true separation, signed image scans, mTLS per-attempt certificate issuance/revocation, cleanup, egress/firewall, immutable ext4 tamper tests or daemon inspect evidence.
- No independent provider invoices/hard spend cap verification, real Windows GPU/NVDA/browser/MFA/recovery/restore, hardware-justified rigged characters or external pen test.
- Existing dynamic preview and static preview still need separate production-grade origins, security audit and real browser red-team. Do not publicly expose preview endpoints or generated code.

## Operational decision

**PRODUCTION ADMISSION DENIED.** Keep v3.4 private/local and operator-controlled, with all external gates separately marked BLOCKED_EXTERNAL. No live accounts, credentials, DNS, firewall, provider spend or production data were changed.
