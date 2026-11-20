# WFS PROJECT 4.7.0-rc1

- The local PostgreSQL replica lab now verifies strict reservations are rejected after promotion until a rebuilt synchronous standby is explicitly enrolled. A new lease is verified directly on that standby.
- The stopped clone verifier can require an exact delivered-project inventory. It rejects additional as well as missing deliveries without changing subset-mode defaults.
- No production rollout, public preview, provider use, application database migration or UI asset change. This remains a local release candidate.
