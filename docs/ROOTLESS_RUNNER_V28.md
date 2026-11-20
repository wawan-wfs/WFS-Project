# WFS PROJECT v2.8 — Operator runbook: isolated rootless QA host

**Status: implementation/runbook only. NO isolated remote runner host was provisioned or tested by this release.** The current environment does not provide the Docker CLI/daemon or an independently administered Linux VM. Strict QA remains disabled unless an operator configures all required controls.

## Architecture and trust boundaries

```
Windows operator (approved QA only) ── verified mTLS ──> separate Linux rootless dockerd
  │                                                       │
  ├─ offline approved delivery TAR ── SSH/SCP/stager ────> root-owned immutable stage
  └─ approved input/source SHA-256                         │
                                              network=none, pinned digest image
                                              cap-drop=ALL, UID 10001, read-only root
                                              readonly immutable binds, /tmp tmpfs
                                              bounded CPU/memory/swap/pids/timeout
```

The dashboard API and AI worker **must not** have the Docker socket, remote daemon credentials, operator staging keys, host filesystem mounts or ability to start the QA script. Use a **separate Linux machine/VM**, separate OS accounts and management network. Windows Docker Desktop alone is **not** evidence of separate-host isolation. The rootless daemon is still sensitive: a client that can access its API can fully control resources owned by its daemon user. Treat all certificates and keys as privileged.

## Stage A — Provision the independent Linux host (operator task, NOT executed here)

1. Provision a dedicated current, patched Ubuntu/Debian VM, with disk and filesystem supporting Linux `FS_IMMUTABLE_FL` (`chattr +i`, such as ext4). Do not co-locate it with the API/worker, application DB, secrets or preview gateway. Create an unprivileged account `wfsrunner` and separate root-operated staging/import administrative path. Configure outbound firewall *deny by default*, allowing only explicitly reviewed management endpoints; prove it with host-level tests, not only Docker `--network none`.
2. Install official packaged Docker Engine plus `docker-ce-rootless-extras`, `uidmap`, and ensure `newuidmap`/`newgidmap` with subordinate UID/GID ranges. Under a proper login session as `wfsrunner`, run `dockerd-rootless-setuptool.sh install`, enable `systemctl --user` service and verify `docker info` reports `rootless`. Rootless service with cgroup v2/systemd is needed for meaningful resource enforcement.
3. Configure the daemon with **verified mTLS** bound only to the management interface (not public internet), firewall port 2376, separate client CA/cert/key distribution, server DNS certificate matching and rotation. Docker API on unauthenticated TCP and SSH into host with shared agent keys are disallowed. Restrict the management network using Tailscale ACL or equivalent. One-time per-run client identity issuance/revocation **is NOT implemented**; a persistent mTLS credential remains a blocker for full admission.
4. Administrator creates strictly root-owned mode-0755 `/srv/wfs-runner`, `/srv/wfs-runner/staging`, `/srv/wfs-runner/trusted` on supporting storage. Verify the rootless user cannot write there. Prefer a separate read-only mount and full audit logs. Do not give rootless daemon account passwordless sudo or membership that grants rootful Docker control.
5. Review and pin approved Python/Node QA images to registry `@sha256:<64 lowercase hex>` references. Images must be built and scanned outside the agent-generated workspace. Network access for image pulls occurs only on the host's controlled provisioning channel; runtime QA uses `--network none`. Never use arbitrary AI-generated Dockerfile, Docker Compose, npm install or pip install at runtime.

Official security guidance: [Docker rootless mode](https://docs.docker.com/engine/security/rootless/), [rootless usage](https://docs.docker.com/engine/security/rootless/tips/), [protect daemon socket](https://docs.docker.com/engine/security/protect-access/), and [container resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).

## Stage B — Prepare trusted snapshots without host-side TOCTOU

On the trusted operator workstation, after delivery and artifact integrity verification:

```powershell
cd C:\WFS_PROJECT
python scripts/runner-stage-package.py <20-hex-project-id> --output C:\wfs-secure\snapshot.tar.gz
Get-FileHash -Algorithm SHA256 C:\wfs-secure\snapshot.tar.gz
```

Transfer the TAR to the separate staging host via a restricted, audited SSH/SCP channel managed by an operator, **not** via the model/API worker. Compare its full SHA-256 against an independently retained value. On the root-owned Linux staging host, after creating the protected staging directories:

```bash
sudo python3 scripts/runner-import-seal.py /secure-inbox/snapshot.tar.gz \
  --project-id <20-hex-project-id> \
  --expected-sha256 <archive-sha256>
```

The importer checks TAR paths, file types and per-entry digests, refuses overwrites, writes to a temporary directory, sets file/directory permissions read-only and calls `chattr +i`, then atomically publishes `/srv/wfs-runner/staging/<project-id>` and `/srv/wfs-runner/trusted/v28`. If filesystem immutability is unsupported, **do not bypass it**: QA must fail closed. Actual `FS_IOC_GETFLAGS` checks on **every** file/directory are included in the remote staging SHA preflight. Trusted probes must be exactly `qa_probe.py` and `qa-node.js`. Do not move a mutable staged tree into the QA directory. The root administrator can still unseal it, so host-side audit/separation remains necessary.

Never stage `.env`, API keys, cookies, session secrets, private certificates or other sensitive control-plane files. Keep the archive offline/protected after verification. For changing a project, use a **new approved snapshot/run namespace**; this partial release still mounts a stable `<project-id>` path, so independent immutable per-attempt namespace and lifecycle enforcement need further implementation.

## Stage C — Run real remote acceptance (must be done on operator workstation)

Configure only on the operator's Windows PowerShell:

```powershell
$env:WFS_RUNNER_DOCKER_HOST='tcp://runner.internal.example:2376'
$env:WFS_RUNNER_CA='C:\wfs-secure\ca.pem'
$env:WFS_RUNNER_CERT='C:\wfs-secure\client-cert.pem'
$env:WFS_RUNNER_KEY='C:\wfs-secure\client-key.pem'
$env:WFS_RUNNER_PROJECT_ROOT='/srv/wfs-runner/staging/<20-hex-project-id>'
$env:WFS_RUNNER_PROBE_ROOT='/srv/wfs-runner/trusted/v28'
$env:WFS_QA_PYTHON_DIGEST='registry.example/approved-python@sha256:<approved-digest>'
$env:WFS_QA_NODE_DIGEST='registry.example/approved-node@sha256:<approved-digest>'
# For explicit runtime Python only:
# $env:WFS_QA_RUNTIME_DIGEST='registry.example/approved-python-runtime@sha256:<approved-digest>'
python scripts/acceptance_v28_remote.py --output .\docs\evidence\remote-acceptance.json
python scripts/sandbox-qa.py <20-hex-project-id> --strict-remote
```

The first command performs a real Docker negative probe for socket visibility, outbound egress and container cleanup. The second enforces rootless/mTLS/digest approval, immutable remote staging, SHA-256 snapshot parity, pre-start container inspection and two language checks. Explicit `--runtime --accept-risk` remains required for generated runtime execution, which should only happen after operator review. These commands were **NOT** run on remote Docker during this release.

Also collect real evidence from the host: firewall rules and a host-level outbound request that fails; blocked writes into sealed staging from rootless UID; digest identity before/after QA; real `docker inspect` JSON showing no Docker socket or writable mounts and the memory/swap/PID/CPU limits; network egress denied and host port zero; full expiration/cleanup under daemon crash, SIGTERM and power loss. The current project scripts do **not** prove all of those gates.

## Incident and rollback

An unexpected path hash, `FS_IMMUTABLE_FL` failure, daemon rootless mismatch, insecure cert, foreign mount, or Docker inspect mismatch must stop the run. Revoke exposed access, quarantine/stage evidence, verify certificates and rootless account audit, and recover only from a previously verified operator snapshot. For production, separate host policy/authorization plugin, per-run mTLS credentials, immutable image admission, disk quotas and cleanup TTL must be independently tested before enabling unattended execution. **Never enable public preview ports.**
