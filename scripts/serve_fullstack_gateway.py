"""Fixed trusted localhost gateway for prebuilt static frontend + FastAPI backend.

Runs only inside a restricted operator-confirmed Docker preview container.
Generated source and frontend asset files are mounted read-only. No shell is run.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
import mimetypes
import os

ROOT=Path('/workspace').resolve()
BACKEND=os.getenv('WFS_BACKEND','')
ALLOWED_METHODS={'GET','HEAD','POST','PUT','PATCH','DELETE'}
BLOCKED_HEADERS={'connection','keep-alive','proxy-authenticate','proxy-authorization',
                 'te','trailer','transfer-encoding','upgrade','host','cookie','set-cookie'}

class Gateway(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def _reply(self,status,data=b'',content_type='text/plain; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)
    def _request(self):
        try:
            path=urlsplit(self.path)
            decoded=unquote(path.path)
            if self.command not in ALLOWED_METHODS:
                return self._reply(405,b'Not allowed')
            if decoded=='/api' or decoded.startswith('/api/'):
                return self._proxy(path)
            if self.command not in ('GET','HEAD'):
                return self._reply(405,b'Static files are read only')
            # Deny dotfiles and disallow path traversal (including URL-encoded segments).
            segments=decoded.split('/')
            if any(x in ('.','..') or x.startswith('.') for x in segments if x):
                return self._reply(404,b'Not found')
            target=(ROOT/decoded.lstrip('/')).resolve()
            if not target.is_relative_to(ROOT):return self._reply(404,b'Not found')
            if target.is_dir():target=target/'index.html'
            if not target.exists() or not target.is_file():
                # SPA fallback for client-side routes, but never for missing asset filenames.
                if '.' not in target.name and (ROOT/'index.html').exists():target=ROOT/'index.html'
                else:return self._reply(404,b'Not found')
            if target.is_symlink() or not target.resolve().is_relative_to(ROOT):
                return self._reply(404,b'Not found')
            if target.stat().st_size>5_000_000:return self._reply(413,b'Asset too large')
            return self._reply(200,target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        except Exception:
            return self._reply(502,b'Gateway error')
    def _proxy(self,path):
        if not BACKEND.startswith('http://wfs-preview-'):
            return self._reply(502,b'Backend not configured')
        size=int(self.headers.get('Content-Length','0'))
        if size>1_000_000:return self._reply(413,b'Request too large')
        content=self.rfile.read(size) if size else None
        url=BACKEND+path.path+('?' + path.query if path.query else '')
        headers={name:value for name,value in self.headers.items() if name.lower() not in BLOCKED_HEADERS}
        request=Request(url,data=content,headers=headers,method=self.command)
        try:
            response=urlopen(request,timeout=8)
        except HTTPError as err:response=err
        except URLError:return self._reply(502,b'Backend unavailable')
        with response:
            body=response.read(4_000_001)
            if len(body)>4_000_000:return self._reply(502,b'Response too large')
            return self._reply(response.status,body,response.headers.get('Content-Type','application/octet-stream'))
    def do_GET(self):self._request()
    def do_HEAD(self):self._request()
    def do_POST(self):self._request()
    def do_PUT(self):self._request()
    def do_PATCH(self):self._request()
    def do_DELETE(self):self._request()
    def log_message(self,fmt,*args):pass

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8000),Gateway).serve_forever()
