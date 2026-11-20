"""Offline syntax and deployment-footgun tests for SSE ingress snippets."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sse_ingress',ROOT/'scripts/render_sse_edge_v38.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class SSEEdgeConfigV38(unittest.TestCase):
    def test_render_no_overwrite_and_explicit_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'nginx'
            mod.render(dest)
            self.assertIn('$binary_remote_addr',(dest/'http_zones.conf').read_text())
            loc=(dest/'location_sse.conf').read_text()
            self.assertIn('proxy_buffering off',loc)
            self.assertIn('limit_conn wfs_sse_ip 8',loc)
            self.assertIn('per-session RBAC',loc)
            with self.assertRaises(ValueError):mod.render(dest)

    @unittest.skipUnless(shutil.which('nginx'),'Nginx binary unavailable; syntax NOT_RUN')
    def test_real_nginx_syntax_without_deploying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            snippets=root/'snippets';mod.render(snippets)
            config=root/'nginx.conf'
            config.write_text('''worker_processes 1;\npid %s;\nevents { worker_connections 32; }\nhttp { include %s;\nserver { listen 127.0.0.1:18081; include %s; }\n}\n''' % (root/'nginx.pid',snippets/'http_zones.conf',snippets/'location_sse.conf'))
            result=subprocess.run(['nginx','-t','-c',str(config),'-p',str(root)+'/'],capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
