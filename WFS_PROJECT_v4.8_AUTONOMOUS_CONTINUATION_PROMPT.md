# WFS PROJECT v4.8 — Operator acceptance and release batch

Start from the published v4.7 ZIP. Match the distribution SHA-256 and every manifest entry before editing. Read AGENTS.md, docs/AUTONOMOUS_STATE.json, docs/ACCEPTANCE_MATRIX_V47.md, docs/OPERATOR_EVIDENCE_V47.md and docs/POSTGRES_REPLICATION_LAB_V47.md. Work on WFS PROJECT, not the separate AI-Office repository.

Run each authorized, independent task during this session and save evidence at checkpoints. For missing prerequisites record the owner, observed blocker, next command and required proof, then continue other runnable work. Do not treat a skipped test, fixture, or local substitute as an independent acceptance pass.

1. On approved isolated Linux with AF_UNIX, run `python scripts/run-operator-evidence-v46.py --output evidence-linux.json`. Review both two-API results and focused test IDs for quota, release, fail-closed outage, rotation, revocation, restart and broker deadlines. No TCP substitution.
2. On approved independent disposable PostgreSQL hosts use verified fencing before promotion. Prove old-writer refusal and a strict retry under lag or loss. After promotion verify strict requests are rejected until a read-only replacement is synchronously enrolled. Confirm the new acknowledged lease is visible on the replacement. Run the two loopback labs serially as a separate track. Do not present same-host results as independent.
3. On a separate approved Windows Docker Desktop clone validate the exact delivery inventory from backup time. Test an intact and a separate incomplete or mixed-restore clone. Start the intact clone independently. Capture 600 seconds each on hardware Chrome and Edge, native 200% zoom, keyboard, NVDA and test-account MFA recovery. With no Windows host, retain local Python checks only and record the PowerShell gap.
4. Preserve 13 menus, 10 divisions, truthful telemetry, tenant/MFA, budget and leased workers. Re-run source, browser and responsive checks, HTTP and workers. Deduplicate overlapping results, preserve redacted evidence, produce versioned source and fixture gallery, verify both from clean extraction and write next prompt and state.

Production remains denied pending independent evidence. No production changes, public previews, real credentials or paid provider use are authorized here.
