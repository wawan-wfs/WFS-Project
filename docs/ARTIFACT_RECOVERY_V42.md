# v4.2 Artifact recovery and exact-match verification

Worker publication still checks the current claim under the SQLite write lock. On an error before commit, filesystem compensation now runs before releasing that lock and retains a rejected promoted directory as `.wfs-stage-rejected-*`. If an error arrives after a COMMIT attempt that has already ended the SQLite transaction, the result is uncertain. Both generations are preserved for audit instead of assuming that the old manifest still applies. This does not make filesystem and database commits crash-atomic.

On a nonproduction clone, stop all writers and compare a directory with the matching SQLite snapshot. The read-only verifier checks the complete manifest, byte lengths, SHA-256, additional paths and unsafe entries. It refuses missing manifests. It does not promote, delete, repair or execute any candidate.

```bash
PYTHONPATH=. python scripts/verify-artifact-generation.py \
  --db /private/backup/wfs.sqlite3 \
  --project <20-character-project-id> \
  --candidate /private/clone/project-directory
```

Exit 0 is an exact match. Exit 2 means investigate or choose a different paired backup. An exact match is not release approval, payment evidence or a statement about data outside the project's artifact manifest. Keep configuration and any applicable SQLite WAL/SHM in the matching offline backup. Do not point the verifier at a live writable project or a candidate that another process can change.

Tests inject ENOSPC during staging and rename, EIO at directory fsync, and a simulated lost SQLite acknowledgement after commit. They restore a real disposable SQLite snapshot and project copy into a separate directory. The source delivery stays untouched. These are process/filesystem-lab results, not physical disk-full, power-cut or Windows acceptance.
