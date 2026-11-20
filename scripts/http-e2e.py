"""Real local HTTP/API/worker end-to-end smoke test using Python stdlib only.

Starts a temporary FastAPI process and uses a test admin account. No external
network, live AI model or Docker execution. Deletes all test data on exit.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import http.cookiejar
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def available_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix='wfs-http-e2e-') as root:
        data=Path(root)
        password='temp-e2e-'+secrets.token_hex(16)
        salt=secrets.token_hex(16)
        password_hash=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000).hex()
        env=os.environ.copy()
        env.update(WFS_DATA_DIR=str(data),WFS_ADMIN_PASSWORD_HASH=f'pbkdf2_sha256:260000:{salt}:{password_hash}',
                   WFS_SESSION_SECRET=secrets.token_hex(32),WFS_ALLOWED_HOSTS='localhost,127.0.0.1,testserver')
        env.pop('OPENAI_API_KEY',None)
        port=available_port()
        root_url=f'http://127.0.0.1:{port}'
        jar=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        csrf=None

        def request(path,method='GET',body=None,binary=False):
            nonlocal csrf
            headers={}
            raw=None
            if body is not None:
                raw=json.dumps(body).encode('utf-8')
                headers['Content-Type']='application/json'
            if method!='GET' and csrf:headers['X-WFS-CSRF']=csrf
            r=opener.open(urllib.request.Request(root_url+path,data=raw,headers=headers,method=method),timeout=10)
            with r:payload=r.read()
            return payload if binary else json.loads(payload)

        with (data/'server-test.log').open('wb') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1',
                         '--port',str(port),'--log-level','error'],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(70):
                    if server.poll() is not None:raise RuntimeError('Local server failed to start')
                    try:
                        if request('/ready')['status']=='ready':break
                    except Exception:time.sleep(.12)
                else:raise RuntimeError('Local API readiness timed out')
                csrf=request('/api/login',method='POST',body={'password':password})['csrf']
                assert csrf and request('/api/session')['authenticated']
                new=request('/api/projects',method='POST',body={
                    'title':'WFS HTTP integration smoke','prompt':'Generate a simple responsive landing page and validate output',
                    'stack':'static','mode':'demo'})
                pid=new['id']
                assert request(f'/api/projects/{pid}/pause',method='POST')['status']=='paused'
                assert any(x['id']==pid for x in request('/api/queue')['paused'])
                assert request(f'/api/projects/{pid}/priority',method='POST',body={'priority':3})['priority']==3
                assert request(f'/api/projects/{pid}/resume',method='POST')['status']=='queued'
                assert request('/api/queue')['queued'][0]['id']==pid
                worker=subprocess.run([sys.executable,'-m','app.worker','--once'],env=env,cwd=ROOT,
                                      capture_output=True,timeout=30)
                if worker.returncode:raise RuntimeError('Worker exited with error (logs hidden)')
                result=request(f'/api/projects/{pid}')
                assert result['status']=='completed',result.get('error')
                files=request(f'/api/projects/{pid}/files')
                assert len(files)>=4
                assert '<html' in request(f'/preview/{pid}/index.html',binary=True).decode().lower()
                exported=request(f'/api/projects/{pid}/download',binary=True)
                with zipfile.ZipFile(io.BytesIO(exported)) as package:
                    assert 'index.html' in package.namelist()
                board=request(f'/api/projects/{pid}/collaboration')
                assert board['project_id']==pid and board['tasks']==[] # offline template does not invent agent work
                operator=request(f'/api/projects/{pid}/operator-jobs',method='POST',body={'kind':'qa-static'})
                job_id=operator['job_id']
                jobs=request('/api/operator/jobs?project_id='+pid)
                assert jobs[0]['id']==job_id and jobs[0]['status']=='queued'
                assert request(f'/api/operator/jobs/{job_id}/cancel',method='POST')['status']=='cancelled'
                assert request('/api/operator/jobs?project_id='+pid)[0]['status']=='cancelled'

                live_cursor=request('/api/live/cursor')['cursor']
                note=request(f'/api/projects/{pid}/notes',method='POST',body={
                    'category':'decision','message':'Operator verified demo template, not production software'})
                assert note['category']=='decision'
                trace_stream=request(f'/api/live/events?after_id={live_cursor}&project_id={pid}&once=true',binary=True)
                assert b'event: wfs-event' in trace_stream and b'Human Operator' in trace_stream
                board=request(f'/api/projects/{pid}/collaboration')
                assert len(board['notes'])==1
                trace=request(f'/api/projects/{pid}/trace')
                assert trace['project']['id']==pid
                assert any(e['state']=='paused' for e in trace['events'])
                assert any(e['agent']=='Delivery Manager' for e in trace['events'])
                page=request('/api/workspace/events?after_id=0&limit=2&project_id='+pid)
                assert len(page['events'])==2 and page['has_more']
                assert request('/api/diagnostics')['workers_online']==0
                # v1.9 real HTTP checks; no paid model call or Docker engine required.
                rate=request('/api/finops/prices',method='POST',body={
                    'model':'e2e-test-model','input_usd_per_million':1.2,'output_usd_per_million':3.4})
                assert rate['saved']
                budget=request(f'/api/projects/{pid}/budget',method='POST',body={'limit_usd':5,'alert_pct':75})
                assert budget['enabled'] and budget['limit_usd']==5.0 and budget['alert_pct']==75
                assert request(f'/api/projects/{pid}/budget')['limit_usd']==5.0
                assert any(b['project_id']==pid for b in request('/api/finops/budgets'))
                csv_body=request('/api/finops/export.csv?period=all&project_id='+pid,binary=True)
                assert b'input_rate_snapshot,output_rate_snapshot' in csv_body
                capabilities=request('/api/meta')['capabilities']
                assert capabilities['project_budgets'] and capabilities['postgres_preview_request']
                print('PASS: independent uvicorn process, auth, queue, worker, preview, ZIP, collaboration notes, SSE replay, audit cursor, budget config & cost export')
            finally:
                server.terminate()
                try:server.wait(timeout=4)
                except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)


if __name__=='__main__':main()
