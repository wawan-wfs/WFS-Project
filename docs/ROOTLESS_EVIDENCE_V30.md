# WFS PROJECT v3.0 — Real runner evidence collection (not host attestation)

**Status: source implementation and mocked regression tests only. NO independent Linux host or remote Docker daemon was accessed for this release.** The system remains a local, operator-controlled partial release candidate.

## Changes to strict QA

- `scripts/sandbox-qa.py` continues to require the digest-pinned image, verified Docker mTLS transport, a daemon reporting Linux/rootless, exact per-attempt staging path, immutable filesystem flags and source/probe SHA-256 parity.
- After `docker create` and policy `docker inspect`, the exact approved staged bytes and `FS_IMMUTABLE_FL` flags are rechecked in a pinned, disconnected Python image **immediately before each** separate QA container is started. A failed recheck **prevents `docker start`**. This closes one preventable stale-preflight window but is **not** atomic daemon-side file admission; a sufficiently privileged host administrator could still mutate staged files.
- The `run_check` result cannot be `pass` if `docker rm`/`docker inspect`/post-cleanup `docker info` cannot verify container removal. Timeout and uncertain cleanup are reported as failures.
- `scripts/acceptance_v28_remote.py` also rejects cases where the probe passes but daemon status cannot be retrieved or cleanup cannot be verified. It does not claim host firewall proof.

## Operator-only evidence workflow

On the **separate Linux rootless runner host**, after immutable per-attempt staging from `docs/ROOTLESS_ATTEMPTS_V29.md` and the operator's independently verified host setup:

```bash
# Run as a trusted operator with access to that host's rootless Docker CLI.
python3 scripts/acceptance_v30_host.py \
  --project-id <20-hex-project-id> \
  --attempt-id <32-hex-attempt-id> \
  --stage /srv/wfs-runner/staging/<project-id>/<attempt-id> \
  --probe-egress \
  --output /secure-evidence/v30-host-<attempt-id>.json
```

This program actually queries `docker info`, checks unified cgroup v2 and user namespace availability, probes filesystem type with `findmnt`, verifies `FS_IMMUTABLE_FL` on every stage entry and root-owned staging parents, and optionally attempts outbound TCP 443. It fails closed for unavailable commands, unsealed staging, a reachable probe address, and missing evidence. A single denied TCP probe is not a complete firewall audit. The output intentionally leaves `independent_host_verified`, `certificate_revocation_verified`, and `firewall_default_deny_verified` **false**, because those require separate independent evidence. The report does not include TLS credentials or model keys.

On the **trusted operator terminal** (never in the dashboard/API container):

```bash
python scripts/acceptance_v28_remote.py --output /secure-evidence/v30-negative.json
python scripts/sandbox-qa.py <project-id> --strict-remote --attempt-id <attempt-id>
```

Do not place remote Docker CA/client key, private registry tokens or host credentials in API/worker containers. Never run this from an untrusted agent. Save the Docker CLI version, rootless daemon logs, firewall rules, ext4 mount configuration, cgroup v2 controllers, container `inspect` payload **redacted for sensitive fields**, resource exhaustion results, image scan/attestation proof and timed cleanup with the evidence record. Nothing in source-only unit tests substitutes for these host records.

## Explicitly open gates

A separate VM has **not** been provisioned here. Per-run daemon-side mTLS identities/certificate revocation, signed image admission and scanning, filesystem disk quotas, TTL garbage collection, crash recovery/replay policy, host firewall audit, actual network/privilege breakout tests, and tamper-resistant TOCTOU controls remain **blocked**. Do not enable unattended QA or public previews based solely on local test passes.
