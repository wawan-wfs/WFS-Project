#!/usr/bin/env python3
"""Run two API processes and the local assertion authority on disposable data."""
from contextlib import ExitStack
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time


def free_port():
    with socket.socket(socket.AF_INET) as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=4)


def wait_ready(probe, process):
    until=time.monotonic()+8
    while time.monotonic()<until and process.poll() is None:
        try:
            if probe():return
        except (OSError,RuntimeError):pass
        time.sleep(.05)
    raise RuntimeError('Disposable lab process did not become ready')


def call(port,path,*,session=None,method='GET',body=None,csrf=None):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
    try:
        headers={'Cookie':'wfs_session='+session} if session else {}
        if body is not None:headers['Content-Type']='application/json'
        if csrf:headers['X-WFS-CSRF']=csrf
        conn.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=conn.getresponse()
        return response.status,response.getheaders(),response.read()
    finally:conn.close()


def open_stream(port,token):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
    try:
        conn.request('GET','/api/live/events',headers={'Cookie':'wfs_session='+token})
        res=conn.getresponse()
        assert res.status==200,res.status
        assert res.readline()==b': wfs-stream-open\n'
        return conn,res
    except BaseException:
        conn.close()
        raise


def main():
    try:
        with socket.socket(socket.AF_UNIX):pass
    except (AttributeError,OSError) as exc:
        print(json.dumps({'classification':'BLOCKED_RUNTIME','detail':'AF_UNIX not available','errno':getattr(exc,'errno',None)}))
        return 77
    from app.sse_admission import AdmissionClient
    with tempfile.TemporaryDirectory(prefix='wfs-uds-lab-') as work,ExitStack() as jobs:
        root=Path(work).resolve()
        data=root/'wfs'
        socket_path=root/'edge.sock'
        quota_db=root/'quota.sqlite'
        password=secrets.token_urlsafe(22)
        salt=secrets.token_bytes(16)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,260000).hex()
        edge_secret=secrets.token_urlsafe(32)
        env={k:v for k,v in os.environ.items() if k!='OPENAI_API_KEY' and not k.startswith('WFS_SSE_EDGE_')}
        env.update(WFS_DATA_DIR=str(data), WFS_SESSION_SECRET=secrets.token_urlsafe(32),
                   WFS_ADMIN_PASSWORD_HASH=f'pbkdf2_sha256:260000:{salt.hex()}:{digest}',
                   WFS_COOKIE_SECURE='false',WFS_ALLOWED_HOSTS='localhost,127.0.0.1,testserver',
                   WFS_SSE_EDGE_SECRET=edge_secret,WFS_SSE_EDGE_SOCKET=str(socket_path),WFS_SSE_EDGE_ASSERTIONS='1')
        def launch(*args):
            proc=subprocess.Popen([sys.executable,*args],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            jobs.callback(stop,proc)
            return proc
        def api():
            port=free_port()
            proc=launch('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--log-level','error')
            wait_ready(lambda:call(port,'/ready')[0]==200,proc)
            return port
        first,second=api(),api()
        def authority():
            proc=launch('-m','app.sse_admission','--socket',str(socket_path),'--db',str(quota_db),
                        '--identity-db',str(data/'wfs.sqlite3'),'--per-session','1')
            client=AdmissionClient(socket_path,env['WFS_SSE_EDGE_SECRET'])
            wait_ready(lambda:client.request('release',lease='0'*32)['status']=='allowed',proc)
            return proc,client
        daemon,client=authority()
        status,headers,login_body=call(first,'/api/login',method='POST',body={'password':password})
        assert status==200
        cookie=next(v for k,v in headers if k.lower()=='set-cookie' and v.startswith('wfs_session='))
        token=cookie.split(';',1)[0].split('=',1)[1]
        csrf=json.loads(login_body)['csrf']
        held,stream=open_stream(first,token)
        try:
            assert call(second,'/api/live/events?once=true',session=token)[0]==429
        finally:
            stream.close()
            held.close()
        deadline=time.monotonic()+4
        while True:
            status=call(second,'/api/live/events?once=true',session=token)[0]
            if status==200:break
            assert status==429 and time.monotonic()<deadline
            time.sleep(.05)

        old_assertion=client.request('authorize',token=token,project=None)['assertion']
        stop(daemon)
        socket_path.unlink(missing_ok=True)
        assert call(first,'/api/live/events?once=true',session=token)[0]==503
        assert call(second,'/api/live/events?once=true',session=token)[0]==503
        env['WFS_SSE_EDGE_SECRET']=secrets.token_urlsafe(32)
        daemon,rotated=authority()
        assert client.request('authorize',token=token,project=None)['status']=='denied'
        assert rotated.request('acquire',assertion=old_assertion)['status']=='unauthorized'
        assert call(first,'/api/live/events?once=true',session=token)[0]==503
        new_api=api()
        assert call(new_api,'/api/live/events?once=true',session=token)[0]==200
        # Revoke a live synthetic session through the normal authenticated API.
        held,stream=open_stream(new_api,token)
        try:
            assert call(new_api,'/api/logout',session=token,method='POST',csrf=csrf)[0]==200
            assert b'event: wfs-event' not in stream.read()
            assert call(new_api,'/api/live/events?once=true',session=token)[0]==401
        finally:
            stream.close()
            held.close()
        print(json.dumps({'classification':'PASS_LOCAL_UDS','separate_api_processes':3,
              'cross_process_quota':True,'disconnect_release':True,'outage_fail_closed':True,
              'transport_secret_rotation':True,'old_assertion_rejected':True,'live_session_revocation':True},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
