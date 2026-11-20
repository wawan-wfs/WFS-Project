"""Render opt-in, operator-built React/Vite output in an opaque-origin sandbox.

Not a general static file server. Only a size-bounded, single-HTML preview is
returned, so generated JS never gains ordinary dashboard-origin privileges.
"""
from __future__ import annotations
import re
from pathlib import Path
from . import config

PREVIEWS=config.DATA/'previews'
ASSET_RE=re.compile(r'^/?(?:\./)?assets/[A-Za-z0-9_.-]+\.(?:js|mjs|css)$')
ATTR_RE=re.compile(r'\b(?:src|href)\s*=\s*([\'\"])([^\'\"]+)\1',re.I)
LINK_RE=re.compile(r'<link\b[^>]*>',re.I)
SCRIPT_RE=re.compile(r'<script\b[^>]*>\s*</script\s*>',re.I)

class PreviewUnavailable(ValueError): pass


def is_ready(pid: str) -> bool:
    path=PREVIEWS/pid/'index.html'
    return path.is_file() and not path.is_symlink() and 0<path.stat().st_size<300_000


def _read(root:Path,url:str,expected:str) -> str:
    if not ASSET_RE.fullmatch(url) or not url.lower().endswith(expected):
        raise PreviewUnavailable('Hanya asset build React lokal yang diizinkan')
    rel=url.lstrip('/').removeprefix('./')
    target=root/rel
    if target.is_symlink() or not target.is_file() or target.stat().st_size>2_000_000:
        raise PreviewUnavailable('Berkas build tidak tersedia atau terlalu besar')
    return target.read_text(encoding='utf-8')


def inline_react(pid: str) -> str:
    if not is_ready(pid):raise PreviewUnavailable('Build React belum dibuat. Jalankan BUILD_REACT_PREVIEW.cmd')
    root=PREVIEWS/pid
    html=(root/'index.html').read_text(encoding='utf-8')
    seen={'js':0,'css':0}
    def style_replace(match):
        tag=match.group(0)
        if 'stylesheet' not in tag.lower():return tag
        a=ATTR_RE.search(tag)
        if not a:return tag
        content=_read(root,a.group(2),'.css').replace('</style','<\\/style')
        seen['css']+=1
        return '<style>'+content+'</style>'
    def script_replace(match):
        tag=match.group(0)
        a=ATTR_RE.search(tag)
        if not a:return tag
        content=_read(root,a.group(2),'.js').replace('</script','<\\/script')
        seen['js']+=1
        return '<script type="module">'+content+'</script>'
    html=LINK_RE.sub(style_replace,html)
    html=SCRIPT_RE.sub(script_replace,html)
    if seen['js']<1:raise PreviewUnavailable('Tidak ditemukan bundle JS Vite yang dapat di-inline')
    return html
