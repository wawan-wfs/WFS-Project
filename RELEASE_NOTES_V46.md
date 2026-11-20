# WFS PROJECT 4.6.0-rc1

- The operator collector now separates blocked, skipped, missing and passed evidence for the focused cases and the two-API Unix-socket lab. Existing v4.4 collector stays available.
- Added regression coverage for ambiguous or late PostgreSQL commit acknowledgements. The quota load fixture no longer depends on a 12-second lease surviving the benchmark. No application timeout, quota, authorization, worker logic or UI asset changed.
- Repeat verification used the v4.5 source as baseline. Local candidate only. Production admission remains denied.
