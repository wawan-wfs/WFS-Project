# WFS PROJECT — Security Boundaries

## Proteksi yang diimplementasikan

- Single admin random password PBKDF2-HMAC-SHA256, hash session, HttpOnly cookies, SameSite Strict, CSRF header/origin check, trusted-host filtering. Login throttling persisten di SQLite. Dashboard default hanya `127.0.0.1:8080`.
- Control API dan worker memproses source AI sebagai data, tidak menjalankan source di container utama. Tidak memasang Docker socket ke API atau worker.
- Docker Compose: non-root UID 10001, cap-drop ALL, read-only root, no-new-privileges, CPU/memory/PID limits. Healthcheck API ada; worker non-HTTP tidak memakai healthcheck API.
- Validasi manifest SHA-256 setiap akses/read/ZIP/preview statis/revisi, path relatif, larangan traversal, nama file khusus Windows, filename case-insensitive collision, batas file/total, pola credential, syntax checks untuk Python/JSON, report QA advisory.
- Preview HTML menggunakan CSP `sandbox allow-scripts` tanpa `allow-same-origin`, `connect-src none`, `form-action none`, dan iframe `sandbox=allow-scripts`. Hanya asset lokal yang diproses; preview React build berupa inline asset yang dibatasi ukuran.
- Opt-in Docker QA offline tidak memasang secret atau Docker socket; syntax QA tidak mengeksekusi source, sementara mode runtime FastAPI membutuhkan `--accept-risk`, Docker tanpa network dan batas proses/memori/CPU/waktu. Opt-in React npm install menjalankan `--ignore-scripts`; tahap build menjalankan source yang **tidak dipercaya**, sehingga ditempatkan di disposable Docker container, dengan jaringan terputus dan hanya salinan temp proyek yang dapat ditulis.
- Provider API calls menggunakan `store=false` dan mencatat token usage. API key tidak dikirim ke browser. `.env` tidak termasuk arsip source dan dikecualikan dari semua Docker build context lewat `.dockerignore`.
- Percobaan panggilan model dicatat di SQLite, termasuk status gagal, untuk membatasi retries; token yang tidak dilaporkan provider tidak dapat direkonstruksi dari aplikasi. High/critical QA issue mengunci status menjadi `review_required`; approval manual memerlukan CSRF dan dicatat dalam events. Ini tidak menjamin bebas bug.

## Batasan dan risiko residu

- Aplikasi **bukan** platform multi-user/multi-tenant; belum ada MFA/SSO/RBAC dan belum dipersiapkan untuk host publik.
- Kode AI dapat mengandung bug, malware, logika palsu atau dependency berbahaya. Sandbox Docker bersifat mitigasi, bukan bukti isolasi sempurna. Host harus dipercaya; dependency installation membutuhkan koneksi internet.
- Snapshot/recovery data, malware/dependency scan, audit log sentral, pentest, serta rate limit tingkat edge belum lengkap. Backup perlu dienkripsi di luar aplikasi.
- CSP/opaque origin melindungi preview browser tetapi tidak membuktikan output web aman dipublikasikan.
- Generated docs/README/brief dapat berisi prompt injection dan belum boleh dianggap instruksi operator. Jangan jalankan perintah hasil AI tanpa review.
- Docker image versions menggunakan tag (bukan digest pinning); perlu image/SBOM/vulnerability management berkala untuk produksi.
- LLM dan API key terhubung ke provider eksternal; pastikan brief tidak memasukkan data pribadi/secret yang tidak ingin dikirim ke penyedia model.

## Jika terjadi insiden

Hentikan `docker compose down`, buat backup data/log untuk forensik yang aman, rotasi `OPENAI_API_KEY`, reset password/session secret, jangan membuka dashboard ke internet. Periksa semua hasil yang pernah di-preview atau dieksekusi.

## v1.5 additions

- Collaboration reads require a valid administrator session. Operator note writes require CSRF and an allowed category, with 3–1500 characters.
- User-supplied note text is HTML-escaped in all dashboard rendering; never interpreted as commands.
- SSE is authenticated, no-store, has 28-second bounded streams, revalidates the active session, and has replay cursors. An open SSE connection is **not** evidence that an agent is executing.
- All collaboration state is stored locally in SQLite and included in the project audit export, which only an authenticated admin can retrieve. SQLite audit entries are not tamper-proof or externally anchored.
- Public internet exposure remains unsupported; add reverse-proxy TLS, rate limiting, hardened tenancy, external secrets management, threat review and penetration testing before launch.


## v1.6 approval/host-runner boundary

Manual task reviews are CSRF protected and scoped to active project attempts and the `task_approval` phase; they cannot mutate tasks that are already running. The operator-job API is limited to a fixed allowlist of actions and cannot accept arbitrary command arguments. Separate host CLI execution requires typed confirmation. No Docker socket or `gh` credentials are available to the AI worker. Browser content is escaped before insertion; previews run on a distinct localhost origin and never receive the WFS admin cookie. Docker's internal network and host-port firewall assumptions must be verified on the target OS; local preview has no authentication and does not constitute a secure multi-tenant sandbox.

## v1.7 operator-journal security

SQLite operator steps store only bounded stage labels from the trusted runner; untrusted command stdout is not appended as a timeline message. API job detail and retry require admin session; retry and bulk task approval require CSRF. Failed/rejected jobs never auto-execute when requeued. Host runner heartbeat permits stalled-job warning without dangerous duplicate execution. React builds install dependencies using an isolated, disposable Docker container; carefully audit any npm supply-chain risk and run only reviewed AI-generated code.
