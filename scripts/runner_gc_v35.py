#!/usr/bin/env python3
"""Operator-only rootless-runner attempt garbage collection (v3.5).

Default is READ-ONLY audit. This script is NOT a daemon and cannot attest an
independent runner. A maintenance window must stop new QA admissions/starts.
Deletion requires an actual rootless daemon inspection, a root-owned host path,
and a second invocation for quarantine purge. No API/worker may execute it.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from runner_policy import RunnerPolicyError, check_daemon

ROOT = Path('/srv/wfs-runner')
STAGING = ROOT / 'staging'
PROJECT_RE = re.compile(r'^[a-f0-9]{20}$')
ATTEMPT_RE = re.compile(r'^[a-f0-9]{32}$')
GC_RE = re.compile(r'^\.gc-([a-f0-9]{32})$')
QUARANTINE_COOLDOWN_SECONDS = 3600
SOCKET_RE = re.compile(r'^/run/user/([1-9][0-9]*)/docker\.sock$')
MAX_ENTRIES = 512
MAX_BYTES = 8_000_000


class GarbageCollectionError(ValueError):
    pass


def _plain_dir(path: Path, *, root_owned: bool = False) -> os.stat_result:
    meta = path.lstat()  # never follow a symlink into a privileged target
    if not stat.S_ISDIR(meta.st_mode) or (root_owned and (meta.st_uid != 0 or meta.st_mode & 0o022)):
        raise GarbageCollectionError('Untrusted staging directory')
    return meta


def check_root() -> None:
    if os.name != 'posix' or not sys.platform.startswith('linux') or os.geteuid() != 0:
        raise GarbageCollectionError('Only a privileged operator on Linux can modify root-owned staging')
    for path in (ROOT, STAGING):
        _plain_dir(path, root_owned=True)
    # This marker is installed by a human operator only AFTER disabling new QA
    # admission and container starts. Its presence alone is not host attestation.
    paused = ROOT / '.admissions-paused'
    meta = paused.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o077:
        raise GarbageCollectionError('Admissions pause marker missing or untrusted')
    if paused.read_bytes() != b'DISABLED\n' or time.time() - meta.st_mtime > 7200:
        raise GarbageCollectionError('Admissions pause marker missing/expired')


def _attempt_info(path: Path, now: int, ttl_seconds: int, *, quarantine: bool = False) -> dict:
    name = path.name
    if not (GC_RE.fullmatch(name) if quarantine else ATTEMPT_RE.fullmatch(name)):
        raise GarbageCollectionError('Unrecognized staging attempt name')
    meta = _plain_dir(path, root_owned=True)
    # Never traverse unbounded or unsafe filesystem objects, even in audit mode.
    count, total = 0, 0
    def fail_walk(error: OSError) -> None:
        raise GarbageCollectionError('Unable to inspect full attempt tree') from error
    for directory, dirs, files in os.walk(path, topdown=True, followlinks=False, onerror=fail_walk):
        for entry in [*dirs, *files]:
            child = Path(directory) / entry
            st = child.lstat()
            if not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
                raise GarbageCollectionError('Special file or symbolic link inside attempt')
            if st.st_nlink > 1 and stat.S_ISREG(st.st_mode):
                raise GarbageCollectionError('Hardlinked staged file forbidden')
            count += 1
            total += st.st_size if stat.S_ISREG(st.st_mode) else 0
            if count > MAX_ENTRIES or total > MAX_BYTES:
                raise GarbageCollectionError('Staging size/file count exceeds bounded cleanup policy')
    age = max(0, now - int(meta.st_mtime))
    return {'project_id':path.parent.name, 'attempt_id':GC_RE.fullmatch(name).group(1) if quarantine else name,
            'quarantined':quarantine, 'age_seconds':age, 'eligible':age >= ttl_seconds,
            'files':count, 'bytes':total, 'inode':meta.st_ino,
            'quarantine_cooldown_passed':not quarantine or (now-int(meta.st_ctime) >= QUARANTINE_COOLDOWN_SECONDS)}


def audit(staging: Path = STAGING, *, ttl_seconds: int = 72*3600, now: int | None = None) -> list[dict]:
    if ttl_seconds < 3600:
        raise GarbageCollectionError('Minimum TTL is one hour')
    now = int(time.time()) if now is None else now
    _plain_dir(staging)
    result = []
    for project in sorted(staging.iterdir()):
        if not PROJECT_RE.fullmatch(project.name):
            raise GarbageCollectionError('Unexpected project namespace in staging')
        _plain_dir(project)
        for path in sorted(project.iterdir()):
            is_gc = bool(GC_RE.fullmatch(path.name))
            result.append(_attempt_info(path, now, ttl_seconds, quarantine=is_gc))
    return result


def _docker_socket(socket: Path) -> list[str]:
    match = SOCKET_RE.fullmatch(str(socket))
    if not match:
        raise GarbageCollectionError('Docker socket must be exact /run/user/<nonroot UID>/docker.sock')
    meta = socket.lstat()
    if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != int(match.group(1)):
        raise GarbageCollectionError('Invalid rootless daemon socket ownership/type')
    return ['docker', '--host', 'unix://' + str(socket)]


def _run_json(cmd: list[str]) -> object:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


def active_mount_sources(socket: Path) -> set[str]:
    """Inspect ALL containers, even stopped. Any unknown daemon failure is fatal."""
    prefix = _docker_socket(socket)
    info = _run_json([*prefix, 'info', '--format', '{{json .}}'])
    if not isinstance(info, dict):
        raise GarbageCollectionError('Docker daemon returned malformed info')
    check_daemon(info)
    result = subprocess.run([*prefix, 'ps', '--all', '--quiet', '--no-trunc'],
                            capture_output=True, text=True, check=True, timeout=30)
    ids = result.stdout.split()
    if len(ids) > 2000 or any(not re.fullmatch(r'[0-9a-f]{64}', cid) for cid in ids):
        raise GarbageCollectionError('Unbounded or invalid daemon container list')
    mounts = set()
    for cid in ids:
        details = _run_json([*prefix, 'inspect', cid])
        if not isinstance(details, list) or len(details) != 1 or not isinstance(details[0], dict):
            raise GarbageCollectionError('Docker inspect did not return exactly one container')
        data = details[0]
        for mount in (data.get('Mounts') or []):
            if not isinstance(mount, dict):
                raise GarbageCollectionError('Unknown Docker mount shape')
            source = mount.get('Source')
            if source:
                mounts.add(os.path.normpath(source))
        for bind in (data.get('HostConfig') or {}).get('Binds') or []:
            if not isinstance(bind, str):
                raise GarbageCollectionError('Unknown Docker bind shape')
            mounts.add(os.path.normpath(bind.split(':', 1)[0]))
    return mounts


def _mounted(path: Path, mounts: set[str]) -> bool:
    source = str(path)
    return any(m == source or m.startswith(source + '/') or source.startswith(m + '/') for m in mounts)


@contextlib.contextmanager
def maintenance_lock():
    # Operator must first disable admission and container starts on the runner.
    check_root()
    lock = ROOT / '.operator-maintenance.lock'
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
            raise GarbageCollectionError('Unsafe operator maintenance lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def _unseal_and_remove(path: Path) -> None:
    # chattr can be unavailable on some storage: fail closed rather than skipping it.
    entries = [path, *path.rglob('*')]
    for item in sorted(entries, key=lambda p: len(p.parts), reverse=True):
        mode = item.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise GarbageCollectionError('Unsafe object during unseal')
        subprocess.run(['chattr', '-i', '--', str(item)], check=True, capture_output=True, timeout=10)
    shutil.rmtree(path)
    if path.exists() or path.is_symlink():
        raise GarbageCollectionError('Quarantine deletion not verified')


def apply_gc(socket: Path, *, ttl_seconds: int, purge: bool = False) -> list[dict]:
    """Two-step operator-only deletion; quarantine first, purge on a later run."""
    with maintenance_lock():
        candidates = audit(ttl_seconds=ttl_seconds)
        mounts = active_mount_sources(socket)
        result = []
        for candidate in candidates:
            if not candidate['eligible'] or candidate['quarantined'] != purge or not candidate['quarantine_cooldown_passed']:
                continue
            project_id = candidate['project_id']; attempt_id = candidate['attempt_id']
            src = STAGING / project_id / (('.gc-' if purge else '') + attempt_id)
            old = STAGING / project_id / attempt_id
            quarantined = STAGING / project_id / ('.gc-' + attempt_id)
            # Do not process if the daemon references either original or quarantine.
            if _mounted(old, mounts) or _mounted(quarantined, mounts):
                result.append({'attempt_id':attempt_id,'action':'HELD_DOCKER_REFERENCE'})
                continue
            fresh = _attempt_info(src, int(time.time()), ttl_seconds, quarantine=purge)
            if not fresh['eligible'] or fresh['inode'] != candidate['inode'] or not fresh['quarantine_cooldown_passed']:
                raise GarbageCollectionError('Staging candidate changed during cleanup')
            if purge:
                _unseal_and_remove(src)
                result.append({'attempt_id':attempt_id,'action':'PURGED_VERIFIED'})
            else:
                if quarantined.exists() or quarantined.is_symlink():
                    raise GarbageCollectionError('Quarantine path already exists')
                # Immutable dirs cannot be renamed: unseal only the top-level
                # attempt under an exclusive operator maintenance lock.
                subprocess.run(['chattr', '-i', '--', str(src)],check=True,capture_output=True,timeout=10)
                try:
                    src.rename(quarantined)  # atomic within root-owned namespace
                except Exception:
                    subprocess.run(['chattr', '+i', '--', str(src)],check=True,capture_output=True,timeout=10)
                    raise
                subprocess.run(['chattr', '+i', '--', str(quarantined)],check=True,capture_output=True,timeout=10)
                result.append({'attempt_id':attempt_id,'action':'QUARANTINED'})
        return result


def main() -> int:
    p = argparse.ArgumentParser(description='Operator-only staging TTL GC; audit mode by default')
    p.add_argument('--ttl-hours', type=int, default=72)
    p.add_argument('--apply', action='store_true', help='Explicitly quarantine eligible attempts')
    p.add_argument('--purge', action='store_true', help='With --apply, remove previously quarantined attempts')
    p.add_argument('--docker-socket', type=Path, help='Explicit rootless /run/user/<uid>/docker.sock')
    a = p.parse_args()
    if a.ttl_hours < 1 or a.ttl_hours > 365*24:
        p.error('TTL must be between 1 hour and 365 days')
    if a.purge and not a.apply:
        p.error('--purge requires --apply')
    try:
        if a.apply:
            if not a.docker_socket:
                p.error('--apply requires an operator-specified rootless Docker socket')
            report = apply_gc(a.docker_socket, ttl_seconds=a.ttl_hours*3600, purge=a.purge)
        else:
            report = audit(ttl_seconds=a.ttl_hours*3600)
        print(json.dumps({'mode':'PURGE' if a.purge else 'QUARANTINE' if a.apply else 'AUDIT_ONLY',
                          'production_attested':False,'attempts':report}, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, RunnerPolicyError) as exc:
        print('DENIED: operator GC failed closed:',type(exc).__name__,file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
