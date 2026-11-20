"""Real local Unix-socket ASGI IPC test (NOT an external TLS deployment)."""
from __future__ import annotations
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from tests.test_v31_dynamic_broker import DynamicPreviewV31,KEY,DOMAIN
from app import preview_gateway,store,preview_authority_client
from fastapi.testclient import TestClient

AUTH_KEY='v32-authority-key-service-secret-longer-than-32-chars'

class RemoteAuthorityV32(unittest.TestCase):
    setUp=DynamicPreviewV31.setUp
    tearDown=DynamicPreviewV31.tearDown
    headers=DynamicPreviewV31.headers
    def test_dynamic_gateway_works_without_local_database_copy(self):
        ticket_response=self.dashboard.post(f'/api/projects/{self.pid}/preview-ticket',
            headers={'X-WFS-CSRF':self.csrf})
        self.assertEqual(ticket_response.status_code,201,ticket_response.text)
        token_path=urlsplit(ticket_response.json()['url']).path
        socket_path=self.p/'authority.sock'
        settings={
            'WFS_DATA_DIR':str(self.p),
            'WFS_PREVIEW_AUTHORITY_KEY':AUTH_KEY,
            'WFS_PREVIEW_AUTHORITY_SOCKET':str(socket_path),
            'WFS_PREVIEW_AUTHORITY_UID':str(os.getuid()),
            'WFS_PREVIEW_AUTHORITY_REQUIRED':'1',
        }
        env={**os.environ,**settings}
        # Server has its own Python process and its own SQLite connection.
        proc=subprocess.Popen([sys.executable,'scripts/serve_preview_authority.py',
            '--socket',str(socket_path)],
            env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(60):
                if socket_path.exists():break
                if proc.poll() is not None:break
                time.sleep(0.05)
            self.assertTrue(socket_path.exists(),proc.stderr.read().decode() if proc.poll() is not None else 'socket missing')
            with patch.dict(os.environ,settings):
                for attempt in range(40):
                    try:
                        receipt=preview_authority_client.call('ticket',{'ticket':token_path.split('/')[-1]})
                        break
                    except preview_authority_client.AuthorityUnavailable as ex:
                        failure=str(ex)
                        time.sleep(0.05)
                else:
                    self.fail('Independent authorization unavailable: '+failure)
            with patch.dict(os.environ,settings),patch.object(store,'connect',side_effect=AssertionError('Gateway must not read SQLite')):
                r=self.client.get(token_path,headers=self.headers(),follow_redirects=False)
                self.assertEqual(r.status_code,303,r.text)
                self.assertNotIn('domain=',r.headers['set-cookie'].lower())
                self.assertIn('secure',r.headers['set-cookie'].lower())
                page=self.client.get('/profile',headers=self.headers())
                self.assertEqual(page.status_code,200,page.text)
                self.assertIn('payload path=/profile',page.text)
                with TestClient(preview_gateway.app,base_url='https://'+self.other+'.'+DOMAIN) as cross:
                    cross.cookies.set('wfs_preview',self.client.cookies.get('wfs_preview'))
                    self.assertEqual(cross.get('/',headers=self.headers()).status_code,404)
                with patch.dict(os.environ,{'WFS_PREVIEW_AUTHORITY_KEY':'wrong-service-key-value-123456789012'}):
                    self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
                with patch.dict(os.environ,{'WFS_PREVIEW_AUTHORITY_SOCKET':str(self.p/'missing.sock')}):
                    self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
                self.assertEqual(self.client.get('/p/'+self.pid+'/index.html',headers=self.headers()).status_code,404)
            logout=self.dashboard.post('/api/logout',headers={'X-WFS-CSRF':self.csrf})
            self.assertEqual(logout.status_code,200,logout.text)
            with patch.dict(os.environ,settings),patch.object(store,'connect',side_effect=AssertionError('Gateway must not read SQLite')):
                self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
        finally:
            proc.terminate()
            try:proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.communicate(timeout=5)
