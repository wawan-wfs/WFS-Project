# WFS PROJECT — Windows 10/11 Operations Runbook

## Instalasi pertama

1. Pastikan WSL2 aktif, Docker Desktop berjalan dengan **Linux containers**, dan dapat menjalankan `docker info`.
2. Ekstrak paket ke folder user seperti `D:\WFS-PROJECT`; hindari folder sistem/protected.
3. Double-click **`START_WFS_PROJECT.cmd`** atau jalankan `powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1`.
4. Inisialisasi menghasilkan password admin acak, ditampilkan sekali. Simpan di password manager. Bootstrap mencoba Python Windows jika ada dan beralih ke image Python Docker jika Python tidak ada.
5. Masuk ke **http://localhost:8080**. Pilih Demo Mode, buat project dan cek hasilnya.
6. Untuk API model, edit `.env` dan set `OPENAI_API_KEY=...`, pilih `OPENAI_MODEL` yang tersedia di akun API, kemudian `docker compose up -d --force-recreate`.

## Upgrade dari rilis sebelumnya

Hentikan versi lama; backup `data/` dan `.env` terpisah, ekstrak paket v1.3 ke folder baru, salin `data/` dan `.env` lama, lalu jalankan `START_WFS_PROJECT.cmd`. Migrations mengisi kolom versi/arsip dan tabel status worker dan percobaan provider. Pastikan proyek lama terlihat dan buat satu demo sebelum membersihkan folder lama. Jangan menyalin `app/` lama ke paket baru.

## Operasi harian

| Aksi | Perintah |
|---|---|
| Mulai/rebuild | `docker compose up --build -d` |
| Hentikan | `docker compose down` |
| Status | `docker compose ps` |
| Diagnosa dashboard | `VERIFY_WFS_PROJECT.cmd` |
| API log | `docker compose logs --tail=100 api` |
| Worker log | `docker compose logs --tail=100 worker` |
| Backup | `powershell -File .\scripts\backup-windows.ps1` |
| Restore | `powershell -File .\scripts\restore-windows.ps1 -BackupZip "D:\path\wfs-backup-yyyymmdd.zip"` |

Backup memakai `.zip` dari folder `data/` setelah API+worker dihentikan untuk menghindari inkonsistensi database; `.env` **tidak ikut**, harus disimpan terenkripsi secara terpisah. Restore memerlukan konfirmasi dan mempertahankan salinan folder lama sebelum mengganti data.

## QA untuk proyek hasil AI

**Syntax QA (offline Docker)**: jalankan `QA_PROJECT.cmd`, masukkan ID proyek 20 hex. Script ini menjalankan JSON/Python AST dan `node --check` JavaScript dalam container yang hanya bisa membaca proyek; network none. Ini bukan pengujian runtime aplikasi, dan JSX/TSX tidak dikompilasi.

**React/Vite opt-in build**: jalankan `BUILD_REACT_PREVIEW.cmd`, masukkan ID proyek, baca peringatan, ketik `BUILD`. Script menyalin source ke direktori sementara, menjalankan `npm install --ignore-scripts` (perlu akses registry npm), lalu menjalankan build dalam Docker tanpa jaringan, tanpa credential dan tanpa Docker socket. Setelah sukses, buka proyek pada dashboard dan klik Open Preview. Build dengan import dinamis atau aset tambahan bisa membutuhkan adaptasi lebih lanjut.

**FastAPI**: Gunakan `RUN_SANDBOX_QA.cmd` terlebih dahulu. `RUN_FASTAPI_SMOKE.cmd` dapat menjalankan app dan tests hasil AI di container Docker terkunci setelah konfirmasi eksplisit. Tidak ada preview jaringan FastAPI otomatis. Lihat `docs/QA_OPERATOR.md`.

**GitHub**: `PUBLISH_GITHUB_PR.cmd` hanya memperlihatkan dry-run. Publikasi aktual memerlukan Git, GitHub CLI, branch baru, konfirmasi `--publish`, dan audit manusia. Tidak pernah otomatis merge. Lihat `docs/GITHUB_PUBLISH.md`.

**Project lifecycle**: proyek `completed` dapat dibuat versi revisinya via dashboard. Proyek terminal dapat diarsipkan/dikembalikan. Hapus permanen butuh project ID persis dan ditolak jika masih aktif atau memiliki versi turunan.

## Admin password reset

Stop dulu: `docker compose down` lalu `py -3 scripts/reset-password.py`, dan `docker compose up -d`. Jika Python tidak tersedia di Windows, jalankan script reset dari Python host atau container Python resmi dengan mount folder proyek ke `/setup`; pastikan `.env` ter-backup sebelum mengubahnya.

## Pemeriksaan production

- Buka http://localhost:8080, login, buat proyek demo, cek timeline + status `completed`, file, preview, ZIP, kemudian logout.
- Stop/start Docker, pastikan proyek masih ada.
- Dengan API asli, uji brief kecil dan periksa penggunaan token serta biaya pada dashboard provider.
- Uji satu project yang QA review-nya high/critical (status `review_required`), tinjau kode, baru jika siap pilih Approve.
- Jalankan `QA_PROJECT.cmd` terhadap ZIP/source yang tersimpan dan inspeksi hasil.
- Sebelum produksi, lakukan backup/restore drill, scan dependency, pentest dan cek keamanan jaringan.

## Troubleshooting

- Docker CLI tidak ada: instal Docker Desktop, pastikan PATH benar.
- Docker Engine tidak berjalan: buka Docker Desktop dan tunggu hingga `docker info` sukses.
- Port 8080 dipakai: ubah mapping host di `compose.yaml`, lalu sesuaikan browser. Jika mengubah host name, periksa `WFS_ALLOWED_HOSTS`.
- Startup gagal setelah bootstrap: cek `.env` untuk placeholder dan `docker compose logs api worker`.
- Browser `401/403`: login ulang, periksa CSRF/Origin. Jika memakai reverse proxy, jangan expose publik tanpa audit.
- Model API `400/429`: cek model ID, API key, billing, rate limits, lalu Retry. Retry ulang seluruh pipeline dan bisa mengulang biaya.
- React build gagal: periksa `package.json`/dependencies dan output `docker run`; folder build sementara akan dibersihkan otomatis.
- `review_required`: QA masih melaporkan prioritas tinggi. Baca `WFS_DELIVERY.md`; persetujuan manual tidak menghapus temuan.
- `interrupted`: worker lease expired; cek log dan Retry.
- Permission volume: user Linux UID 10001 harus dapat menulis `data/`. Di Windows pastikan Docker Desktop memiliki file sharing yang benar.

## Upgrade to v1.4

Preserve existing `.env` and `data/` outside the old release folder. Extract v1.4 into a **new** folder and put only those two items in it. `START_WFS_PROJECT.cmd` applies additive migrations for `priority` (Normal = 1) and `queued_at`. Verify **Queue Manager** Hold/Resume and **Activity Feed** audit history on a demo mission. To test browser↔live backend locally, install Python development dependencies and Playwright with Chromium, then run `python scripts/browser-local-e2e.py`. Do not share the temporary password or credentials. Review `TEST_REPORT.md` for what has and has not been independently validated.

## Upgrade to v1.5 (Collaboration & Live Office)

1. Stop the old installation and back up `data/` and `.env` separately.
2. Extract v1.5 into a new directory. Restore **only** `data/` and `.env`, never old source folders.
3. Rebuild and start with `START_WFS_PROJECT.cmd`. The new collaboration tables are added automatically and idempotently.
4. Verify the previously delivered files are intact; enter **Collaboration Board** and add a test operator note. New AI missions show specialist task states; historical v1.4 missions do not have structured past tasks.
5. Check the top bar `EVENTS: LIVE` connection indicator (or fallback polling). Confirm an event makes the dashboard refresh.
6. Run `VERIFY_WFS_PROJECT.cmd`, then the optional real browser E2E (`python scripts/browser-local-e2e.py`) on your Windows machine. Check logs and backups before retiring the previous version.


## v1.6 operator jobs

Install Python 3 on Windows for the host-side operator runner, in addition to Docker Desktop for container QA/preview. `RUN_OPERATOR_JOBS.cmd` lists pending jobs. In PowerShell use `python scripts/operator-runner.py --job JOB_ID` and confirm the exact ID. For GitHub publishing, install Git and GitHub CLI (`gh auth login`) first. No automatic publication is performed when the dashboard request is submitted. Read `docs/OPERATOR_COMMAND_HUB.md`.

## v1.8 update — worker replicas, human checkpoints and preview

This supersedes references to v1.3 in older upgrade paragraphs. For upgrades from v1.7, stop the old install, back up `data/` and `.env` separately, unpack v1.8 to a **new** directory, restore those two items and run `START_WFS_PROJECT.cmd`. Never overwrite old data with ZIP contents. Existing data gets additive migrations. Initial startup defaults to three worker replicas; adjust with `powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1 -WorkerReplicas 1` (valid 1–8), or use `docker compose up --build -d --scale worker=3`. Increase CPU/RAM headroom and monitor contention before raising concurrency. API will not execute generated project code.

With Human Task Review enabled, a project awaiting task decisions is parked with a persistent checkpoint. Approve tasks in Collaboration Board to resume, or cancel the waiting mission. The v1.8 worker does **not** sit blocked while waiting. `WFS_MAX_ACTIVE_PROJECTS` sets the cap for active claims (default 3), independent of the number of replicas.

For Node.js web/API previews, create an operator `preview-start` request for a `node-web` project in Operator Command Hub. On the Windows host, run `RUN_OPERATOR_JOBS.cmd` (or `python scripts/operator-runner.py --list` and `python scripts/operator-runner.py --job JOB_ID`) and confirm explicitly. The runner executes source inside a resource-constrained Docker container, with localhost-only binding and a 15-minute TTL. Inspect the URL in the operator result. Use a separate `preview-stop` request for shutdown if appropriate. Generated Node projects are limited to Node builtin HTTP; arbitrary node_modules dependencies and multi-service databases are **not supported**. Verify previews locally before relying on them. The FastAPI counterpart uses the same human approval mechanism.

Open **AI Cost Center** for daily/model/project estimates and pricing setup. Rates are operator-entered USD per 1 million input/output tokens. Rates affect only future usage snapshots, not prior records, and are not synchronized with provider bills. `WFS_MAX_ESTIMATED_COST_USD=0` disables the soft cost guard; this is not a hard billing ceiling. Never expose the dashboard publicly without independent security and deployment validation.
