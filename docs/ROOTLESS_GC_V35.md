# v3.5 Rootless Runner — Operator Lifecycle, Not a Host Attestation

**Classification:** LOCAL SOURCE + NEGATIVE TESTS. No independent Linux rootless Docker daemon, admitted signed image, root-owned ext4 staging or actual garbage collection was available for execution in this environment. Do not expose untrusted QA to the Internet or mark the runner certified.

## What changed

`runner_gc_v35.py` is a new **operator-only**, two-stage TTL collector for immutable per-attempt QA staging. It deliberately never executes as part of the WFS API/worker/gateway. By default it prints read-only JSON inventory of `/srv/wfs-runner/staging/<20hex-project>/<32hex-attempt>` and any previous `.gc-<32hex-attempt>` quarantine. It refuses special files, symlinks, hardlinked files, unknown namespaces, over-limit trees, a TTL below one hour, and unexpected host paths. It bounds candidate inspection to 512 descendants/8 MB.

An authenticated human operator must first disable independent QA admissions **and container starts** on the host, install a root-owned `/srv/wfs-runner/.admissions-paused` marker containing exactly `DISABLED\n`, permission `0600` and not older than two hours, and run in an operator-approved maintenance window. The importer in `runner-import-seal-v29.py` now respects the same marker and serializes with GC on `.operator-maintenance.lock`. The marker/lock are additional controls, **not evidence that all Docker engine clients are stopped**. The operator must ensure no other client can create/start containers during the window.

With `--apply`, the collector requires Linux root, protected root-owned parent directories, an explicit non-root user's exact `/run/user/<uid>/docker.sock`, a responding rootless Linux daemon, full **including stopped** Docker container inspection, and zero bind-mount references before quarantine. It removes only the top-level immutable flag when moving a sealed attempt atomically into `.gc-...`, then reseals it. A separate `--apply --purge` run checks the real daemon again and requires **at least one hour** since quarantine before attempting chattr unseal, deletion and absence verification. Any exception fails closed. Partial purges remain quarantined and require reinspection/cleanup; no automation retries them blindly.

## Operator procedures (do not run against production without explicit approval)

On a genuinely separate, audited Linux rootless-runner host, after proving the runner is idle and new sessions cannot start:

```bash
# READ-ONLY inventory: no privilege or Docker needed for this step
python3 scripts/runner_gc_v35.py --ttl-hours 72

# Manual approval prerequisite (on operator-controlled dedicated host):
# disable new admission/starts OUTSIDE this script; confirm cgroup/docker process state.
sudo install -m 0600 -o root -g root /dev/null /srv/wfs-runner/.admissions-paused
printf 'DISABLED\n' | sudo tee /srv/wfs-runner/.admissions-paused >/dev/null
sudo chmod 0600 /srv/wfs-runner/.admissions-paused

# Explicitly audit all containers, then quarantine only eligible attempts
sudo python3 scripts/runner_gc_v35.py --apply --ttl-hours 72 \
  --docker-socket /run/user/1001/docker.sock

# NOT earlier than one hour later and after a NEW daemon/host verification:
sudo python3 scripts/runner_gc_v35.py --apply --purge --ttl-hours 72 \
  --docker-socket /run/user/1001/docker.sock

# Check audit logs and staging integrity; remove pause marker ONLY after
# independent operator confirmation that admissions may resume.
```

**Warning:** `/run/user/1001/docker.sock` and the private IPs in other guides are **examples**, not discovered infrastructure. The script does not provision Docker, issue per-attempt certificates, revoke daemon identities, sign images, create disk quotas, configure firewall, or prove rootless host separation. Physical host evidence, signed-image admission, daemon-side mTLS revocation, rootless Docker negative tests, quotas and crash recovery remain `BLOCKED_EXTERNAL`.

## Test coverage and residual risks

Unit tests cover TTL bounds, adversarial names, symlinks/hardlinks, malformed daemon data, socket ownership/path, inactive bind references, maintenance marker and import lock, and quarantine cooldown. **They do not run chattr, cleanup, Docker Engine, firewall, auditd or crash drill on an actual host.** A privileged root attacker could still tamper with paths or engine state. A maintenance window must be enforced outside this script by the operator; this tool must never become an unattended privileged service without a separate threat review.
