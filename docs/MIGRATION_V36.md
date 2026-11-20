# v3.6 local upgrade / rollback

This checkpoint adds **no database schema migrations**, no new API auth cookies and no change to the existing Docker topology. SSE now executes additional authorization reads during streaming and can close/reconnect a revoked project's stream.

1. Stop v3.5 processes and preview workers; back up `.env`/secrets and data directory separately. Never include these in source ZIP.
2. Unpack verified v3.6 source into a **new** directory and validate `python scripts/verify-release.py` before restoring old data into a nonproduction clone.
3. Run targeted SSE/provider tests, backend regression, HTTP and worker E2E. Confirm revoked SSE events are no longer sent and local preview/FinOps still function.
4. Official cost fetch is **opt-in operator-only** and does not run from WFS startup or change spending state. Keep the adapter disabled operationally without verified operator approval.
5. For rollback stop v3.6 completely and restore the **matched v3.5 source AND its data backup** into a fresh folder. Do not run both versions against a shared SQLite database. Review any SSE reconnect diagnostics and ensure service host ports are still private.

No real operator migration or restore drill was executed in this environment. This is an actionable runbook, not proof of real Windows rollback.
