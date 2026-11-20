# WFS PROJECT v4.4.0-rc1

Local release candidate. Strict PostgreSQL lab retries now require replay acknowledgement even for an existing live lease. The disposable lab tests standby lag, promotion and read-only rejoin. Stopped-clone artifact checks can verify all delivered projects in a batch. Production admission remains DENIED. No application database migration or PostgreSQL API integration.
