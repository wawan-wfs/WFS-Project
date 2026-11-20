# v2.8 — local run evidence (not production certification)

Recorded on 2026-11-08 against the unpacked v2.7 → v2.8 working source. Execution environment is Linux; Docker daemon unavailable.

```text
$ PYTHONPATH=. python -m pytest -q
166 passed, 40 subtests passed in 21.45s

$ python scripts/http-e2e.py
PASS: independent uvicorn process, auth, queue, worker, preview, ZIP, collaboration notes, SSE replay, audit cursor, budget config & cost export

$ python scripts/parallel-e2e.py
PASS: 3 worker processes completed 9 independent projects, 45 validated artifacts; attempts=1 each

$ node --check app/static/finops.js && node --check app/static/app.js && node --check app/static/mfa-ui.js
PASS

$ python -m compileall -q app scripts
PASS

$ 2026-11-08 v2.7 source DB smoke → v2.8 init_db() twice
PASS v27->v28 <project id omitted> default default

$ WFS_RESPONSIVE_AUDIT_ONLY=1 python scripts/browser-ui-fixture-smoke.py
13 menus at widths 1440, 820, 390: no horizontal overflow (synthetic fixtures)

$ WFS_V28_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py
26 synthetic screenshots captured; local CPU 3D, gpuTimerSupported=False
```

The fixture was not a Windows screen reader, paid LLM, or GPU test. Real rootless Docker/mTLS/immutable Linux filesystem/egress negative tests, TLS proxy and dynamic-origin testing, MFA recovery, 200% zoom and operator acceptance remain blocked.
