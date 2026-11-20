"""Fail-closed remote Docker runner admission for operator QA.

This module validates CLI config and checks an actual daemon at execution time.
It does not provision, attest, or certify the remote host. These are minimum gates.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

DIGEST_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}$")

class RunnerPolicyError(RuntimeError):
    pass


def validate_image(image: str) -> str:
    if not isinstance(image, str) or not DIGEST_RE.fullmatch(image):
        raise RunnerPolicyError('Strict QA requires an immutable registry image@sha256:<64 hex>')
    return image


def remote_docker_prefix(host: str, ca: str, cert: str, key: str) -> list[str]:
    parsed = urlsplit(host)
    if parsed.scheme != 'tcp' or not parsed.hostname or not parsed.port or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise RunnerPolicyError('Runner host must be a dedicated tcp://host:2376 Docker TLS endpoint')
    # Docker TLS flags ensure the daemon is contacted only using verified transport.
    files = [Path(p) for p in (ca, cert, key)]
    if any(not f.is_file() or f.is_symlink() for f in files):
        raise RunnerPolicyError('Runner CA, client certificate and key must be existing regular non-symlink files')
    if os.name != 'nt' and any(f.stat().st_mode & 0o077 for f in files[2:]):
        raise RunnerPolicyError('Runner client private key must not be group/world accessible')
    return ['docker','--host',host,'--tlsverify','--tlscacert',str(files[0]),'--tlscert',str(files[1]),'--tlskey',str(files[2])]


def check_daemon(info: dict) -> None:
    options = info.get('SecurityOptions', [])
    if not isinstance(options, list) or not any('rootless' in str(x).lower() for x in options):
        raise RunnerPolicyError('Dedicated remote Docker daemon does not report rootless mode')
    if info.get('OSType') != 'linux':
        raise RunnerPolicyError('Strict QA requires a Linux rootless daemon')
    if info.get('Swarm', {}).get('LocalNodeState') == 'active':
        raise RunnerPolicyError('Strict QA cannot run against a swarm manager')


def inspect_container(container: dict, expected_image: str, expected_project: str | None = None, expected_probe: str | None = None) -> None:
    """Reject unexpected mount/network/privilege config after Docker creates the container."""
    host = container.get('HostConfig') or {}
    if container.get('Config',{}).get('Image') != expected_image:
        raise RunnerPolicyError('Runner used unexpected image')
    if host.get('NetworkMode') != 'none' or not host.get('ReadonlyRootfs') or host.get('Privileged'):
        raise RunnerPolicyError('Runner network, readonly root or privilege policy was violated')
    if host.get('CapAdd') or host.get('Devices'):
        raise RunnerPolicyError('Unexpected capabilities or devices were attached')
    if not host.get('Memory') or not host.get('NanoCpus') or not host.get('PidsLimit'):
        raise RunnerPolicyError('Missing Docker cgroup resource limits')
    # Rootless does not replace per-container defense in depth. Inspect the
    # Docker-created object, not only the command string we intended to send.
    if not (0 < host.get('Memory',0) <= 1024*1024*1024 and
            host.get('MemorySwap') == host.get('Memory') and
            0 < host.get('NanoCpus',0) <= 2_000_000_000 and
            0 < host.get('PidsLimit',0) <= 128):
        raise RunnerPolicyError('Unexpected resource bounds on strict QA container')
    if str(container.get('Config',{}).get('User','')) not in ('10001:10001',):
        raise RunnerPolicyError('Strict QA container does not use approved nonroot UID')
    if 'ALL' not in (host.get('CapDrop') or []):
        raise RunnerPolicyError('Container capabilities are not fully dropped')
    if 'no-new-privileges' not in (host.get('SecurityOpt') or []):
        raise RunnerPolicyError('No-new-privileges was not enforced')
    if host.get('PidMode') in ('host',) or host.get('IpcMode') in ('host',) or host.get('UsernsMode') == 'host':
        raise RunnerPolicyError('Host process, IPC or user namespace leak')
    if host.get('CgroupnsMode') == 'host' or host.get('ExtraHosts') or host.get('PortBindings'):
        raise RunnerPolicyError('Host cgroup/network exposure in strict QA')
    restart=host.get('RestartPolicy') or {}
    if restart.get('Name','no') not in ('no',''):
        raise RunnerPolicyError('Strict QA must not restart automatically')
    mounts = container.get('Mounts') or []
    if len(mounts)!=2 or any(m.get('Type')!='bind' or m.get('RW') for m in mounts):
        raise RunnerPolicyError('Unexpected writable or extra runner mounts')
    destinations={m.get('Destination') for m in mounts}
    if expected_project is not None and not any(m.get('Destination') == '/workspace' and m.get('Source') == expected_project for m in mounts):
        raise RunnerPolicyError('Runner project staging mount differs from approved path')
    if expected_probe is not None and not any(str(m.get('Destination','')).startswith('/trusted/') and m.get('Source') == expected_probe for m in mounts):
        raise RunnerPolicyError('Runner trusted probe mount differs from approved path')
    if '/workspace' not in destinations or not any(str(x).startswith('/trusted/') for x in destinations):
        raise RunnerPolicyError('Expected trusted probe + readonly project mounts not found')
    if any('/docker.sock' in str(m.get('Source','')) for m in mounts):
        raise RunnerPolicyError('Docker socket passed into runner')


def remote_staging_path(path: str, *, trusted: bool = False) -> str:
    """Reject arbitrary remote bind-mount sources and host-sensitive locations."""
    import posixpath
    prefix = '/srv/wfs-runner/trusted/' if trusted else '/srv/wfs-runner/staging/'
    if not isinstance(path, str) or not path.startswith(prefix):
        raise RunnerPolicyError('Remote bind mount must be under dedicated /srv/wfs-runner staging')
    if posixpath.normpath(path) != path or path.endswith('/') or '\x00' in path:
        raise RunnerPolicyError('Invalid remote staging path')
    return path


def validate_attempt_path(path: str, project_id: str, attempt_id: str) -> str:
    """Require exact immutable project/attempt namespace; deny stable v2.8 paths."""
    if not re.fullmatch(r'[a-f0-9]{20}',project_id) or not re.fullmatch(r'[a-f0-9]{32}',attempt_id):
        raise RunnerPolicyError('Strict runner project and attempt IDs must be hex')
    expected=f'/srv/wfs-runner/staging/{project_id}/{attempt_id}'
    if remote_staging_path(path)!=expected:
        raise RunnerPolicyError('Remote staging path is not the approved per-attempt namespace')
    return path


def local_snapshot(root: Path, trusted: list[Path]) -> dict:
    """Hash all staged files, not just artifact DB rows; reject symlinks and special files."""
    import hashlib
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise RunnerPolicyError('Invalid local project snapshot')
    files = {}
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise RunnerPolicyError('Project snapshot contains symlink or special file')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    probes = {}
    for p in trusted:
        if not p.is_file() or p.is_symlink():
            raise RunnerPolicyError('Invalid local trusted probe')
        probes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {'project':files,'trusted':probes}


# Executed by a pinned, trusted Python base image with network disabled.
# No imports from untrusted project, no eval, no shell interpolation.
STAGING_CHECK = '''import fcntl,hashlib,json,os,pathlib,stat,struct,sys
expected=json.loads(sys.argv[1]); FS_IOC_GETFLAGS=0x80086601; FS_IMMUTABLE_FL=0x00000010
def immutable(path):
 fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
 try:out=fcntl.ioctl(fd,FS_IOC_GETFLAGS,struct.pack('I',0))
 finally:os.close(fd)
 if not struct.unpack('I',out)[0]&FS_IMMUTABLE_FL:
  print('UNSEALED_STAGING',file=sys.stderr);sys.exit(38)
def scan(root):
 p=pathlib.Path(root)
 if p.is_symlink():sys.exit(38)
 result={}
 # Paths are sealed with FS_IMMUTABLE_FL by privileged offline stager.
 # Read-only Docker mounts alone are not sufficient to stop a host-side writer.
 for x in [p,*p.rglob('*')]:
  st=x.lstat()
  if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)) or x.is_symlink():sys.exit(38)
  immutable(x)
  if x.is_file():result[x.relative_to(p).as_posix()]=hashlib.sha256(x.read_bytes()).hexdigest()
 return result
observed={'project':scan('/workspace'),'trusted':scan('/trusted')}
if observed!=expected:
 print('REMOTE_STAGING_MISMATCH',file=sys.stderr);sys.exit(37)
print('REMOTE_STAGING_MATCH_AND_SEALED')
'''


def staging_check_command(prefix: list[str], image: str, project: str, trusted_dir: str, snapshot: dict) -> list[str]:
    validate_image(image)
    remote_staging_path(project)
    remote_staging_path(trusted_dir,trusted=True)
    return [*prefix,'run','--rm','--network','none','--read-only',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32',
            '--memory','256m','--memory-swap','256m','--cpus','1','--user','10001:10001',
            '--mount',f'type=bind,source={project},target=/workspace,readonly',
            '--mount',f'type=bind,source={trusted_dir},target=/trusted,readonly',
            image,'python','-B','-c',STAGING_CHECK,json.dumps(snapshot,sort_keys=True)]
