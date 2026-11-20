#!/usr/bin/env python3
"""Operator-only local Nginx SSE ingress snippet generator (never deploys)."""
from __future__ import annotations
import argparse
from pathlib import Path

HTTP_ZONES = """# Place once in the trusted Nginx http {} block. Per-IP, not per-user/tenant.\nlimit_conn_zone $binary_remote_addr zone=wfs_sse_ip:10m;\nlimit_req_zone $binary_remote_addr zone=wfs_sse_open:10m rate=12r/m;\n"""

LOCATION = """# Place in the approved HTTPS server {} block; never in raw public HTTP.\n# This is complementary ingress protection, not distributed per-session RBAC.\nlocation = /api/live/events {\n    limit_conn wfs_sse_ip 8;\n    limit_req zone=wfs_sse_open burst=4 nodelay;\n    proxy_http_version 1.1;\n    proxy_set_header Connection \"\";\n    proxy_set_header Host $host;\n    proxy_set_header X-Forwarded-Proto https;\n    proxy_buffering off;\n    proxy_cache off;\n    proxy_read_timeout 40s;\n    proxy_send_timeout 15s;\n    proxy_pass http://127.0.0.1:8080;\n}\n"""


def render(root: Path):
    if root.exists():
        raise ValueError('Destination already exists; never overwrite live configuration')
    root.mkdir(mode=0o700,parents=False)
    (root/'http_zones.conf').write_text(HTTP_ZONES)
    (root/'location_sse.conf').write_text(LOCATION)


def main():
    parser=argparse.ArgumentParser(description='Generate local-only per-IP SSE Nginx snippets; no deployment')
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    render(args.output_dir)
    print('Generated operator-only snippets; NOT deployed. Validate with nginx -t before use.')

if __name__=='__main__':main()
