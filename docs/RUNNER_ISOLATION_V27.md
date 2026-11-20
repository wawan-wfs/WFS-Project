# WFS PROJECT v2.7-rc1 — Strict remote QA runner (partial)

**This is a fail-closed admission tool, NOT a provisioned or certified isolated runner service.** It does not turn the existing local operator QA, local preview runtime or API worker into production-approved untrusted-code execution.

## What changed

The existing `scripts/sandbox-qa.py` retains its **default local** QA mode for backward compatibility. Its new `--strict-remote` mode requires: a remote Docker TCP API reachable over verified mutual TLS; existing CA and client certificate/key files (no key symlinks or world-readable Unix private key); a Linux daemon reporting rootless mode; no active swarm; registry images pinned by immutable SHA-256 digest, including a separately approved runtime dependency image for `--runtime`; deny-all network, read-only filesystem, dropped capabilities, no-new-privileges, PIDs/CPU/memory limits, nonroot user, only the two approved read-only bind mounts; verification of the **created** container configuration before starting it, and unconditional removal. A SHA-256 comparison between every local project file and the pre-staged remote snapshot, plus the two trusted probes, is performed on the remote engine before QA. Missing or different files cause rejection.

**Trust model and limitations:** The remote host is administered separately and must be secured by a human operator. Path prefixes and TLS do not attest a host. The remote staging tree can still change between the SHA comparison and launch (TOCTOU); lock it down read-only and prevent writers, and do not deploy until that has been independently verified. A successfully returning Docker API can be malicious. No installed rootless Docker daemon, runner network firewall, immutable host storage, real Docker negative test, live preview proxy, certificate rotation or external red-team proof was available here. The local operator preview uses separate code and is **not** upgraded by strict QA. Docker daemon access must never be given to model-authored code or the API/AI worker. Security is incomplete.

## Operator setup on Windows (after provisioning independent Linux runner)

Prepare an isolated Linux machine/VM whose **rootless** Docker endpoint is exposed only through a restricted management network using mutual TLS. Protect CA and client certificates, prohibit public exposure of port 2376, and enable host firewall egress deny. Image digest must come from a separately reviewed build/pull and be verified against the intended registry/asset policy. Use a single immutable staged directory per project ID, e.g. `/srv/wfs-runner/staging/<20-hex-project-id>`, and an immutable trusted-probe directory, e.g. `/srv/wfs-runner/trusted/v27/` containing ONLY `qa_probe.py` and `qa-node.js`. Remote files must match local source and probes exactly. Stage files through an independently secured audited workflow: **this release does not implement remote file transfer or staging locking**.

On the operator's Windows PowerShell (not an AI worker or production API process):

```powershell
$env:WFS_RUNNER_DOCKER_HOST = 'tcp://runner.internal.example:2376'
$env:WFS_RUNNER_CA = 'C:\\wfs-secure\\ca.pem'
$env:WFS_RUNNER_CERT = 'C:\\wfs-secure\\client-cert.pem'
$env:WFS_RUNNER_KEY = 'C:\\wfs-secure\\client-key.pem'
$env:WFS_RUNNER_PROJECT_ROOT = '/srv/wfs-runner/staging/<project-id>'
$env:WFS_RUNNER_PROBE_ROOT = '/srv/wfs-runner/trusted/v27'
$env:WFS_QA_PYTHON_DIGEST = 'registry.example/approved-python@sha256:<approved-64hex>'
$env:WFS_QA_NODE_DIGEST = 'registry.example/approved-node@sha256:<approved-64hex>'
# For Python runtime QA only, also provide WFS_QA_RUNTIME_DIGEST.
python scripts/sandbox-qa.py <project-id> --strict-remote
```

These are **placeholders**; no actual digest, endpoint or certificate is included. Do not paste sample image values unchanged. The `--runtime --accept-risk` flags remain mandatory for explicitly running generated code, and `WFS_QA_RUNTIME_DIGEST` must be configured in strict remote mode. Never execute arbitrary AI-authored source on the Windows host.

## Verification and incident handling

`python -m pytest tests/test_v27_runner_policy.py -q` covers missing digest, mutable tags, insecure hosts, improper certificate permissions, non-rootless Docker, unsafe container privileges/mounts and symlinked local files. This is mocked/pure-Python coverage, **not** proof of real Docker Engine isolation. A container failing inspection must be deleted and reported as an error. Reports indicate `strict_remote`; do not treat a local QA pass as a strict remote pass. If a mismatch occurs, immediately stop QA, rotate potentially exposed credentials, audit staging/snapshot/runner daemon logs and preserve evidence. Operator must also test Docker socket denial, egress prevention, resource and timeout handling, runner loss/cleanup and restored backups on real hardware before considering future certification.
