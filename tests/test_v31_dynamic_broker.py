"""v3.1 preview broker: local Unix-socket fixture, NEVER public TLS acceptance."""
from __future__ import annotations

import hashlib
import os
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import auth,config,dynamic_broker,preview_gateway,store
from app.main import app as dashboard

PASSWORD='OperatorV31!securepassword'
KEY='v31-gateway-operator-proxy-key-with-sufficient-entropy'
BASE='https://preview.wfs.example.test'
DOMAIN='dyn.wfs.example.test'


class LocalApplication(BaseHTTPRequestHandler):
    def do_GET(self):
        content=('payload path='+self.path+';secret='+str(self.headers.get('Cookie'))).encode()
        self.send_response(200)
        self.send_header('Content-Type','text/plain')
        self.send_header('Set-Cookie','generated_app_should_not_set=1')
        self.end_headers()
        self.wfile.write(content)
    def do_POST(self):
        data=self.rfile.read(int(self.headers.get('content-length','0')))
        self.send_response(200)
        self.send_header('Content-Type','text/plain')
        self.end_headers()
        self.wfile.write(b'echo:'+data)
    def log_message(self,*args):pass


class DynamicPreviewV31(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)
        self.socket_root=self.p/'trusted-sockets';self.socket_root.mkdir(mode=0o700)
        self.patches=[patch.object(config,'configured',return_value=True),
                      patch.object(store,'DATA',self.p),patch.object(store,'DB',self.p/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',self.p/'projects'),patch.object(config,'DATA',self.p),
                      patch.object(config,'PROJECTS',self.p/'projects'),
                      patch.dict(os.environ,{'WFS_PREVIEW_PUBLIC_ORIGIN':BASE,'WFS_PREVIEW_PROXY_KEY':KEY,
                          'WFS_PREVIEW_DYNAMIC_DOMAIN':DOMAIN,'WFS_PREVIEW_SOCKET_ROOT':str(self.socket_root),
                          'WFS_PREVIEW_SOCKET_UID':str(os.getuid())},clear=False)]
        for p in self.patches:p.start()
        store.init_db()
        self.owner=store.provision_organization('v31-owner','Owner','v31owner',auth.hash_password(PASSWORD))
        self.outsider=store.provision_organization('v31-other','Other','v31other',auth.hash_password(PASSWORD))
        brief='Build private FastAPI project with source code and verified tests'
        self.pid=store.create_project('Dynamic owner',brief,'demo','fastapi',created_by=self.owner)['id']
        self.other=store.create_project('Other project',brief,'demo','fastapi',created_by=self.outsider)['id']
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='completed' WHERE id IN (?,?)",(self.pid,self.other))
        self.socket_path=self.socket_root/(self.pid+'.sock')
        class Server(socketserver.UnixStreamServer):allow_reuse_address=True
        self.server=Server(str(self.socket_path),LocalApplication)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
        self.dashboard=TestClient(dashboard);self.dashboard.__enter__()
        login=self.dashboard.post('/api/login',json={'username':'v31owner','password':PASSWORD})
        self.assertEqual(login.status_code,200,login.text)
        self.csrf=login.json()['csrf']
        self.host='https://'+self.pid+'.'+DOMAIN
        self.client=TestClient(preview_gateway.app,base_url=self.host);self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.dashboard.__exit__(None,None,None)
        self.server.shutdown();self.server.server_close();self.worker.join(timeout=3)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def headers(self):
        return {'x-wfs-preview-proxy-key':KEY,'x-forwarded-proto':'https'}

    def redeem(self):
        issue=self.dashboard.post(f'/api/projects/{self.pid}/preview-ticket',headers={'X-WFS-CSRF':self.csrf})
        self.assertEqual(issue.status_code,201,issue.text)
        issued=issue.json()['url']
        self.assertEqual(urlsplit(issued).netloc,self.pid+'.'+DOMAIN)
        r=self.client.get(urlsplit(issued).path,headers=self.headers(),follow_redirects=False)
        self.assertEqual(r.status_code,303,r.text)
        self.assertEqual(r.headers['location'],'/')
        return r

    def test_gateway_proxy_per_project_dns_and_no_cookie_forwarding(self):
        self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
        r=self.redeem()
        self.assertIn('httponly',r.headers['set-cookie'].lower())
        self.assertIn('secure',r.headers['set-cookie'].lower())
        page=self.client.get('/docs?x=valid',headers={**self.headers(),'Authorization':'Bearer confidential','Cookie':self.client.cookies.get('wfs_preview') and 'wfs_preview='+self.client.cookies.get('wfs_preview')})
        self.assertEqual(page.status_code,200,page.text)
        self.assertIn('payload path=/docs?x=valid',page.text)
        self.assertIn('secret=None',page.text) # no dashboard or preview session forwarded
        self.assertNotIn('generated_app_should_not_set',str(page.headers))
        self.assertIn('default-src',page.headers['content-security-policy'])
        posted=self.client.post('/api/data',content=b'payload',headers={**self.headers(),'Content-Type':'text/plain'})
        self.assertEqual(posted.status_code,200,posted.text)
        self.assertEqual(posted.content,b'echo:payload')
        self.assertEqual(self.client.get('/%2e%2e/secret',headers=self.headers()).status_code,404)
        logout=self.dashboard.post('/api/logout',headers={'X-WFS-CSRF':self.csrf})
        self.assertEqual(logout.status_code,200,logout.text)
        self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)

    def test_wrong_host_does_not_burn_one_use_ticket(self):
        issued=self.dashboard.post(f'/api/projects/{self.pid}/preview-ticket',
            headers={'X-WFS-CSRF':self.csrf})
        self.assertEqual(issued.status_code,201)
        ticket=urlsplit(issued.json()['url']).path
        with TestClient(preview_gateway.app,base_url=BASE) as wrong:
            self.assertEqual(wrong.get(ticket,headers=self.headers()).status_code,404)
        self.assertEqual(self.client.get(ticket,headers=self.headers(),follow_redirects=False).status_code,303)
        self.assertEqual(self.client.get(ticket,headers=self.headers()).status_code,404)

    def test_oversize_body_and_client_proxy_spoof_are_denied(self):
        self.redeem()
        self.assertEqual(self.client.post('/api/data',content=b'x'*1_000_001,
            headers=self.headers()).status_code,404)
        self.assertEqual(self.client.get('/',headers={'x-wfs-preview-proxy-key':'forged',
            'x-forwarded-proto':'https'}).status_code,503)
        self.assertEqual(self.client.get('/',headers={'x-wfs-preview-proxy-key':KEY,
            'x-forwarded-proto':'http'}).status_code,503)

    def test_unregistered_broker_or_cross_tenant_is_denied(self):
        self.redeem()
        with TestClient(preview_gateway.app,base_url='https://'+self.other+'.'+DOMAIN) as cross:
            cross.cookies.set('wfs_preview',self.client.cookies.get('wfs_preview'))
            self.assertEqual(cross.get('/',headers=self.headers()).status_code,404)
        with patch.dict(os.environ,{'WFS_PREVIEW_SOCKET_UID':str(os.getuid()+10000)}):
            self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
        # Refuse to issue for other tenant even if it has a socket.
        with self.assertRaises(preview_gateway.GatewayError):
            preview_gateway.issue(self.other,self.owner,self.dashboard.cookies.get('wfs_session'))
        with patch.dict(os.environ,{'WFS_PREVIEW_DYNAMIC_DOMAIN':'localhost'}):
            self.assertEqual(self.client.get('/',headers=self.headers()).status_code,503)

    def test_fail_closed_when_socket_is_replaced_by_symlink_or_untrusted_dir(self):
        self.redeem()
        self.server.shutdown();self.server.server_close();self.worker.join(timeout=3)
        self.socket_path.unlink()
        self.socket_path.symlink_to('/tmp/any-other-socket')
        self.assertEqual(self.client.get('/',headers=self.headers()).status_code,404)
        self.socket_path.unlink()
        self.socket_root.chmod(0o777)
        with self.assertRaises(dynamic_broker.BrokerUnavailable):dynamic_broker.project_socket(self.pid)

if __name__=='__main__':unittest.main()
