# Operator QA: sandbox usage and limits

## Prerequisites

Windows 10/11 + Docker Desktop Linux containers, Python 3 on Windows, selected project has finished generating source code. Keep `.env` outside the generated project. The runner reads SHA-256 checksums from the local WFS database and aborts if files changed after delivery.

## Commands (PowerShell, from WFS folder)

```powershell
py -3 .\scripts\sandbox-qa.py YOUR_20_HEX_ID
py -3 .\scripts\sandbox-qa.py YOUR_20_HEX_ID --runtime --accept-risk
```

The second form **executes generated FastAPI imports and potentially tests**, and therefore requires an explicit risk acknowledgment. The script builds a trusted Python QA image, never a generated Dockerfile. It uses constrained Docker containers: non-root UID, `--network none`, read-only root, read-only generated source, `--cap-drop ALL`, `no-new-privileges`, PIDs/memory/CPU/time limits and a disposable tmpfs. It does not pass your AI key, `.env`, Docker socket, or repository credentials into the sandbox.

The first form checks Python AST, JSON syntax, JavaScript syntax (not JSX/TSX transpilation). In FastAPI runtime mode, a trusted probe searches common entrypoint modules, creates an in-process TestClient, verifies OpenAPI and optionally executes repository `pytest` files. Projects with other dependencies can fail, and there is no guarantee of full runtime coverage or complete container isolation against unknown kernel vulnerabilities.

Results are saved in `data/reports/PROJECT_ID/*.json` and displayed as **operator QA** in the project panel. Operators can supply their own reports via access to this local disk; these are not signed or remote attestations. They do **not** change a project into a certified production deployment.

For React, use the separate `BUILD_REACT_PREVIEW.cmd`. Dependency retrieval requires network access and should be reviewed before you opt in. The build itself runs in a container without network; no API keys are passed. For browser E2E you still need a properly configured Windows browser test environment.
