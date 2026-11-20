#!/usr/bin/env python3
"""Start DB-owning internal authz sidecar on a private Unix socket; no TCP listener."""
from __future__ import annotations
import argparse
import os
import stat
import sys
from pathlib import Path

def main():
    import uvicorn
    p=argparse.ArgumentParser(description='Start internal-only preview authority UDS service')
    p.add_argument('--socket',type=Path,required=True)
    a=p.parse_args()
    path=a.socket
    key=os.getenv('WFS_PREVIEW_AUTHORITY_KEY','')
    if os.name!='posix' or not sys.platform.startswith('linux'):
        p.error('Linux Unix-domain-socket host required')
    if len(key)<32:
        p.error('WFS_PREVIEW_AUTHORITY_KEY must be a separately rotated secret of at least 32 characters')
    if not path.is_absolute() or '..' in path.parts:
        p.error('Absolute private Unix-socket path required')
    if path.exists() or path.is_symlink():
        p.error('Socket already exists; manually verify owner/process before removing stale paths')
    try:
        root=path.parent.lstat()
        if not stat.S_ISDIR(root.st_mode) or root.st_mode & 0o077 or root.st_uid not in (0,os.getuid()):
            p.error('Socket directory must be owner-only (0700) and trusted')
    except OSError:
        p.error('Private socket directory missing')
    os.umask(0o077)
    class PrivateServer(uvicorn.Server):
        async def startup(self,sockets=None):
            await super().startup(sockets=sockets)
            # asyncio/Uvicorn may create a world-accessible Unix socket;
            # lock its mode before accepting application traffic.
            os.chmod(path,0o600)
    config=uvicorn.Config('app.preview_authority:app',uds=str(path),log_level='warning',access_log=False)
    PrivateServer(config).run()
    return 0

if __name__=='__main__':raise SystemExit(main())
