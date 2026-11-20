# WFS PROJECT v1.5 — User Guide (Windows / Docker)

## Start

1. Extract ZIP to a writable Windows folder, start Docker Desktop with Linux containers and WSL2.
2. Run `START_WFS_PROJECT.cmd` (no winget required). First-time bootstrap generates an administrator password; save it privately.
3. Open `http://localhost:8080`, sign in, and ensure the worker health indicator reads **online**.
4. Without a model key, create a `Static Web` mission using **Offline Demo Template**. With your own working API key, select `Real AI Agents` for a production-stack source build. API charges are separate.

## All eight menu pages

| Menu | Actual functions |
|---|---|
| Mission Control | Create mission; select static/FastAPI/React stack and demo/AI mode; overview counters; floor mini-cards; navigate to other areas |
| Projects & Missions | Search and filter projects by status, view task events and agent runs, read delivered files, static/React-built preview, download source ZIP, cancel/retry, QA approval, revise version, archive/restore/delete, edit display name and notes, observe in office |
| Virtual AI Office | Three floors, animated agent workstations, select project, inspect agent task, heartbeat-aware live status, activity stream, zoom, pause motion, explicit offline demo tour |
| Agent Directory | Ten specialist divisions, live/finished/interrupted runs, search and status filter, per-agent detail and link to project or office |
| QA & Audit Center | Review-required/failed/completed project board, QA navigation, operator runtime QA command reference; **does not execute AI-generated programs automatically** |
| Deliverables | Search and project filter, SHA-256 file inventory, file reader, ZIP download |
| Activity Feed | Auditable recent project events, search and state filter, deep link to project details |
| System & Settings | Database and worker health, model routing and limits, security boundaries, copy operator commands, persist visual preferences in browser |

## Visual AI Office — understanding animation

- **LIVE**: a character types at its workstation **only when** a real agent_run record is in working status, its project is running, the worker is reported online and heartbeat age is below 45 seconds.
- **FINISHED**: most recent recorded agent may remain at desk but does **not** type or walk.
- **IDLE**: empty chair / no assigned agent run on that floor.
- **INTERRUPTED**: agent run said working but worker or project is no longer verifiably active. It is **not** animated as active.
- **Preview demo tour**: all avatars and activity are example-only; top bar shows **DEMO SCENE · NOT LIVE** and the inspector explicitly states sample. No actual AI task is dispatched. Click **Exit demo tour** to return to real telemetry.

Use **Floor 01** (Management, Architecture, Operations), **Floor 02** (Engineering, Creative Studio, AI & Data, Documentation), or **Floor 03** (Quality Lab, Infrastructure, Security). Filter by a specific project to see only its task run history. The browser refreshes the office periodically, without requiring a page reload.

## Manage missions safely

- **Change display name/notes**: Projects → select mission → **Edit project info**. Changes are logged; original prompt and code stay intact.
- **Request Revision**: completed AI projects only, with a configured AI key. Creates a new version and preserves its parent.
- **Archive/Restore**: terminal projects; can restore later.
- **Delete**: terminal projects without child revisions; requires explicit project ID. Permanently deletes code and database record.
- **Manual QA approval**: only for `review_required`; it acknowledges unresolved findings, it does **not** certify safety.
- **Preview**: static web; React after operator-approved build, and FastAPI code tested separately. No automatic FastAPI public web preview.

## QA and GitHub

After reviewing source manually, operators can run:

- `RUN_SANDBOX_QA.cmd` — isolated syntax/JSON/AST checks
- `RUN_FASTAPI_SMOKE.cmd` — optional network-disabled FastAPI smoke test
- `BUILD_REACT_PREVIEW.cmd` — operator-approved React build
- `PUBLISH_GITHUB_PR.cmd` — dry-run by default, explicit CLI approval for branch + draft PR

These tools must be run only on a trusted computer with Docker Desktop. The web dashboard **never** mounts Docker socket or executes arbitrary generated code.

## System preferences

System & Settings → **Visual preferences**: pause/enable avatar motion; set office zoom and default floor; set polling interval (3, 6, or 12 seconds). Stored in **browser localStorage**, not the backend, and contains no secrets.

## Production caveats

This is a tested **single-admin, local-first** application. It is **not certified production SaaS**, and still needs real Windows/Docker testing, live paid-model API verification, a full browser↔backend E2E run, multitenant RBAC/MFA, centralized observability, hardened deployment and a third-party security audit. Browser component smoke tests in the build environment used mocked API fixture responses because local network access in Chromium was blocked by environment policy; API tests ran against the actual FastAPI routes separately.

---

## v1.4: Queue Manager dan observasi agent

**Queue Manager** (menu baru) menampilkan `Pending missions` berdasarkan prioritas dan `Paused before execution`. Pilih `Urgent`, `High`, `Normal`, atau `Low`, lalu tekan **Save**. Tekan **Hold** untuk menahan misi yang *belum mulai*; tekan **Resume** agar kembali masuk antrean. Jika misi sudah berjalan, sistem menolak pause atau perubahan prioritas. Gunakan cancel untuk menghentikan alur pada titik pemeriksaan berikutnya; ini bukan penghentian seketika terhadap API model yang sedang dipanggil.

Di **Projects & Missions**, kontrol queue yang sama tersedia pada misi berstatus `queued` atau `paused`. Informasi prioritas dan nomor antrean muncul di panel detail. **Export audit JSON** menyediakan jejak aktivitas dan checksum tanpa isi password atau API key. Arsip dan hapus misi yang masih `paused` tidak diizinkan; batalkan dulu bila perlu.

Di **Virtual AI Office**, panel kanan sekarang menampilkan **Execution Checkpoint** (tahap yang dicatat server) dan **Mission Queue**. Angka tersebut tidak dianggap persentase penyelesaian atau estimasi waktu. Klik misi untuk melihat status dan hasilnya. Klik avatar untuk melihat tugas dan rincian eksekusi yang diperbarui dari backend.

Di **Activity Feed**, pilih **Browse full history** untuk menelusuri riwayat secara kronologis dengan cursor (50 event per halaman). Tekan **Load next 50 records** untuk melanjutkan atau **Back to latest** untuk kembali ke 80 event terbaru.

**Perhatian:** Semua visualisasi dalam `Preview demo tour` merupakan contoh. Hanya mode normal yang memanfaatkan catatan kerja dan heartbeat aktual; keduanya tidak menggantikan review keamanan ataupun pengujian pada aplikasi yang dihasilkan.

## Collaboration Board (v1.5)

1. Open **Collaboration Board** (the tenth menu) and choose a project. Existing v1.4 projects show no task plan because the previous version did not record structured task ownership.
2. For a new **AI mission** with a configured model, the planning agent assigns files to specialist tasks; the board shows each task's status and file list, only after server records actual work.
3. **Agent handoffs** reflect recorded phase transitions, never fictitious chat.
4. Use **Operator decision log** to save decisions, blockers, and review findings. Only administrators can submit notes. Notes **do not** become agent instructions; use Request Revision to generate new code versions.
5. The top bar **EVENTS: LIVE** means the event channel is connected. Agent activity is separately validated from the worker heartbeat. If SSE is blocked, the dashboard continues polling.
6. Open a project → **Task & Handoff Board** for the same project or export project audit JSON to obtain collaboration evidence.


## v1.6 — Task Approval / Operator Command Hub

For Human Gate, create a new AI mission with Coding Approval set to **Human gate**. Open Collaboration Board, review each planned task's file ownership and click Approve or Block. The worker cannot start coding while pending/blocked tasks remain. The original operator notes still only record audit annotations.

In **Operator Command Hub**, choose a delivered project then queue an isolated QA check, FastAPI runtime smoke, local FastAPI preview start/stop, or GitHub draft PR request. Nothing runs until the operator explicitly authorizes `python scripts/operator-runner.py --job <JOB_ID>` on the Windows host. Queued jobs can be cancelled in the dashboard. See `docs/OPERATOR_COMMAND_HUB.md` for limitations.

## v1.7 — Operator history and bulk task approvals

Operator Command Hub now supports status filtering, search, durable per-job timeline, stale heartbeat warnings, requeue (failed/rejected only), and React/Vite preview build requests through the Windows host runner. Virtual AI Office shows these host operations separately from animated AI agents. In Collaboration Board, **Approve N pending tasks** approves only pending/planned tasks in a human-gated AI project; blocked tasks remain blocked. See `OPERATOR_OPERATIONS_V17.md`.


## v1.8: AI Cost Center and nonblocking collaboration

Open **AI Cost Center** (twelfth dashboard menu) to view token totals, call attempts, estimated spend by model/project/day, active project capacity, and operator-entered pricing. Choose 7 days, 30 days, or all history. Estimates use price snapshots at usage-record time, not provider invoices. Enter USD prices per one million input/output tokens; saved rates are effective for new usage only. Older unpriced records remain unpriced.

With **Human Task Review** enabled, tasks awaiting approval pause at a durable checkpoint, and the worker is released to process other projects. Approve or block individual tasks from **Collaboration Board**; once all are approved, the project returns to the queue with the same attempt and planned tasks. Blocked tasks do not silently proceed.

To run **Node.js Web/API** apps, select `node-web` as the project stack; projects use Node's built-in HTTP server and no external npm dependencies. The separate Operator Command Hub + host runner can create a time-limited local Docker preview after explicit approval; arbitrary apps are not accepted. Consult `docs/PARALLEL_PREVIEW_FINOPS_V18.md` for exact commands, security limits, and remaining production readiness work.
