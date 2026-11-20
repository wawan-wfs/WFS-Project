# WFS PROJECT 4.9.0-rc1

- Offline restore verification can pin the exact bytes of the independently retained backup inventory with SHA-256. A mismatch stops before checking the clone.
- Optional summary output separates missing deliveries, extra deliveries, generation changes and local artifact-check failures without exposing project IDs, filenames, paths or hashes.
- Local tests validate intact, missing and mixed clones and a replaced inventory. Prior exact-ID and detailed verification modes remain supported.
- No database migration, application UI asset change, production rollout, public preview or paid provider call. External acceptance remains open.
