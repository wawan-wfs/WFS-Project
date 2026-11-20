# WFS PROJECT v2.9 — Per-attempt QA admission (operator runbook)

**Scope:** source-only controls and local adversarial tests. **No real remote rootless daemon or firewall tested here.** All untrusted work stays disabled unless a human operator independently verifies the host and approved snapshots. Read `docs/ROOTLESS_RUNNER_V28.md` and `docs/RUNNER_ISOLATION_V27.md` first.

## New v2.9 admission boundary

Each approved QA attempt has a unique 32-character lowercase hexadecimal `attempt_id`. The trusted operator stages only under:

`/srv/wfs-runner/staging/<20-lowercase-hex-project-id>/<32-lowercase-hex-attempt-id>`

The v2.9 strict QA CLI refuses the older stable `/staging/<project-id>` path. Reusing an attempt directory is refused by the importer. Every imported regular source file and directory is sealed with `chattr +i`, and runtime preflight verifies `FS_IMMUTABLE_FL` and source SHA-256 before Docker execution. Root-owned stage parent directories must be protected from rootless Docker user writes. A privileged root operator can still mutate files by unsealing them: this must be controlled through independent OS audit and administrative separation.

## Operator workflow (execute only on your own audited machines)

1. Provision a dedicated, patched Linux host/VM with ext4, rootless Docker Engine and cgroup v2, independent from the dashboard/API, AI worker, DB, private keys and preview gateway. Deny outbound network by default at host firewall; only operator-approved management and provisioning traffic is allowed. Prove denied host/container egress with real negative tests.
2. Install pinned, scanned QA images with complete immutable `@sha256` digests using a controlled privileged provisioning channel. Do not pull packages, build Dockerfiles or install untrusted dependencies at task runtime. Independently install and seal the exact `qa_probe.py` and `qa-node.js` from the approved release under `/srv/wfs-runner/trusted/v28`. Verify the directory ownership and immutability. Restrict stage import and certificate issuance to human-reviewed operators.
3. Prepare the archive on an authorized Windows workstation. Use a fresh identifier for each attempt; retain printed `attempt_id`, `sha256` and the `remote_path` separately:

```powershell
cd C:\WFS_PROJECT
python scripts/runner-stage-package-v29.py <PROJECT_ID> --output C:\wfs-secure\qa-attempt-001.tar.gz
Get-FileHash -Algorithm SHA256 C:\wfs-secure\qa-attempt-001.tar.gz
```

4. Copy the archive to the independent runner's restricted inbox through an authenticated, least-privilege operator channel. On the *Linux host as root*, compare its full SHA256 to the independent result, then import; use the exact `attempt_id` reported by step 3:

```bash
sudo python3 scripts/runner-import-seal-v29.py /secure-inbox/qa-attempt-001.tar.gz \
  --project-id <PROJECT_ID> --attempt-id <ATTEMPT_ID> \
  --expected-sha256 <64_hex_SHA256>
```

5. Configure remote connection only on the trusted QA operator terminal. Protect CA/client key files (0600 on Linux), use a verified TLS hostname, and do not place them in API/worker containers:

```powershell
$env:WFS_RUNNER_DOCKER_HOST='tcp://runner.internal.example:2376'
$env:WFS_RUNNER_CA='C:\wfs-secure\ca.pem'
$env:WFS_RUNNER_CERT='C:\wfs-secure\client-cert.pem'
$env:WFS_RUNNER_KEY='C:\wfs-secure\client-key.pem'
$env:WFS_RUNNER_ATTEMPT_ID='<ATTEMPT_ID>'
$env:WFS_RUNNER_PROJECT_ROOT='/srv/wfs-runner/staging/<PROJECT_ID>/<ATTEMPT_ID>'
$env:WFS_RUNNER_PROBE_ROOT='/srv/wfs-runner/trusted/v28'
$env:WFS_QA_PYTHON_DIGEST='registry.example/approved-python@sha256:<64-hex-digest>'
$env:WFS_QA_NODE_DIGEST='registry.example/approved-node@sha256:<64-hex-digest>'
python scripts/acceptance_v28_remote.py --output .\data\acceptance-v29\remote.json
python scripts/sandbox-qa.py <PROJECT_ID> --strict-remote --attempt-id <ATTEMPT_ID>
```

6. Save redacted `docker info`, inspect JSON, filesystem flags, firewall output and negative probes (network, socket, host namespaces), disk/process/CPU/memory bounds, image digests, TTL cleanup and recovery evidence. Do not post certificates, raw access logs, MFA codes or model keys. A real test failure must halt admission.

## Still unimplemented and blocking

The stage importer does not issue or revoke unique Docker daemon client certificates. It does not perform daemon-side authorization per attempt, enforce filesystem disk quotas or run a TTL garbage collector. These controls require real host design, operators, auditd/systemd and proof under crashes. The policy still relies on a privileged root stager to publish immutable data. Do **not** run unattended AI-authored code until those mechanisms and breakout tests are verified. Old v2.8 `runner-stage-package.py` and `runner-import-seal.py` remain for historical compatibility but are **not valid** for the v2.9 strict per-attempt admission path.
