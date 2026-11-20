#!/usr/bin/env python3
"""Collect REAL (not simulated) local Linux rootless runner host observations.

Operator-only. Must be run ON the independent Linux runner, never from API/worker.
The report is useful evidence, NOT a production attestation or replacement for
reviewed firewall rules, certificate revocation or an independent pentest.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import platform
import re
import socket
import stat
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.runner_policy import check_daemon, RunnerPolicyError, validate_attempt_path
except ModuleNotFoundError as exc:
    if exc.name not in ('scripts', 'scripts.runner_policy'):
        raise
    from runner_policy import check_daemon, RunnerPolicyError, validate_attempt_path

FS_IOC_GETFLAGS=0x80086601
FS_IMMUTABLE_FL=0x00000010


def immutable(path:Path)->bool:
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        value=fcntl.ioctl(fd,FS_IOC_GETFLAGS,struct.pack('I',0))
        return bool(struct.unpack('I',value)[0]&FS_IMMUTABLE_FL)
    finally:os.close(fd)


def check_staging(stage:Path, project_id:str, attempt_id:str)->dict:
    validate_attempt_path(str(stage),project_id,attempt_id)
    # Only inspect this exact existing directory, never follow symlink children.
    if not stage.is_dir() or stage.is_symlink():
        raise ValueError('Stage missing or link')
    scanned=0
    total_bytes=0
    for child in [stage,*stage.rglob('*')]:
        mode=child.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError('Nonregular staged file')
        if not immutable(child):
            raise ValueError('Unsealed staged entry')
        scanned+=1
        if stat.S_ISREG(mode):total_bytes+=child.lstat().st_size
        if scanned>512 or total_bytes>8_000_000:
            raise ValueError('Unexpected staged file count/size')
    for parent in (stage.parent, stage.parent.parent):
        meta=parent.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=0 or meta.st_mode&0o022:
            raise ValueError('Mutable or non-root-owned staging parent')
    return {'sealed_entries':scanned,'sealed_bytes':total_bytes,'immutable_flag_proven':True}


def collect(stage:Path,project_id:str,attempt_id:str,probe_egress:bool=False,egress_ip='1.1.1.1'):
    observations={'measured_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'classification':'LOCAL HOST OBSERVATION - NOT A PRODUCTION SECURITY CERTIFICATE',
        'platform':platform.system(),'rootless':False,'cgroup_v2':False,
        'staging_immutable':False,'host_egress_denied':None,'independent_host_verified':False,
        'certificate_revocation_verified':False,'firewall_default_deny_verified':False}
    errors=[]
    if platform.system()!='Linux':errors.append('Requires real Linux host')
    if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():errors.append('Unified cgroup v2 unavailable')
    else:observations['cgroup_v2']=True
    if not Path('/proc/sys/user/max_user_namespaces').is_file() or int(Path('/proc/sys/user/max_user_namespaces').read_text().strip())<=0:
        errors.append('User namespaces not available')
    try:
        info=subprocess.run(['docker','info','--format','{{json .}}'],text=True,capture_output=True,timeout=20,check=True)
        check_daemon(json.loads(info.stdout))
        observations['rootless']=True
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired,subprocess.CalledProcessError,json.JSONDecodeError) as e:
        errors.append('Rootless Docker daemon not verified')
    try:
        fs=subprocess.run(['findmnt','--noheadings','--output','FSTYPE','--target',str(stage)],
                           capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        if fs!='ext4':raise ValueError('Staging must reside on ext4')
        observations['staging_filesystem']='ext4'
        observations.update(check_staging(stage,project_id,attempt_id))
        observations['staging_immutable']=True
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:
        errors.append('Immutable ext4 staging not verified')
    if probe_egress:
        # Positive connection means fail; a single denied connection is not a
        # complete firewall default-deny attestation.
        try:
            with socket.create_connection((egress_ip,443),timeout=3):
                observations['host_egress_denied']=False
                errors.append('Host outbound probe reached public IP')
        except OSError:
            observations['host_egress_denied']=True
    observations['errors']=errors
    observations['local_prerequisites_passed']=not errors and observations['host_egress_denied'] is True
    return observations


def main():
    p=argparse.ArgumentParser(description='Operator-only live Linux host evidence collector')
    p.add_argument('--project-id',required=True)
    p.add_argument('--attempt-id',required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--probe-egress',action='store_true',help='Explicitly test outbound TCP 443 to a public IP')
    a=p.parse_args()
    if not re.fullmatch(r'[a-f0-9]{20}',a.project_id) or not re.fullmatch(r'[a-f0-9]{32}',a.attempt_id):
        p.error('Invalid project/attempt IDs')
    try:
        if a.output.exists() or a.output.is_symlink():raise ValueError('Evidence report exists; never overwrite')
        evidence=collect(a.stage,a.project_id,a.attempt_id,a.probe_egress)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as f:
            json.dump(evidence,f,indent=2)
        print('PASS local prereqs' if evidence['local_prerequisites_passed'] else 'BLOCKED',a.output)
        return 0 if evidence['local_prerequisites_passed'] else 1
    except (OSError,ValueError) as exc:
        p.error(str(exc))

if __name__=='__main__':sys.exit(main())
