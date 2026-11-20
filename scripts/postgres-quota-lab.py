#!/usr/bin/env python3
"""Run the quota experiment against a disposable single-primary PostgreSQL."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from app.sse_pg_lab import PostgresQuotaLab, QuotaUnavailable


def postgres_bin():
    chosen=os.environ.get('WFS_PG_LAB_BIN')
    if chosen:return Path(chosen).resolve()
    found=shutil.which('pg_ctl')
    if found:return Path(found).resolve().parent
    fixture=importlib.util.find_spec('pgserver')
    if fixture and fixture.origin:return Path(fixture.origin).parent/'pginstall'/'bin'
    raise SystemExit('Install PostgreSQL binaries or the optional pgserver lab fixture')


@contextmanager
def instance():
    bindir=postgres_bin()
    with tempfile.TemporaryDirectory(prefix='wfs-pg-lab-') as work:
        root=Path(work)
        with socket.socket(socket.AF_INET) as s:
            s.bind(('127.0.0.1',0))
            port=s.getsockname()[1]
        password=secrets.token_urlsafe(32)
        pw=root/'pw'
        pw.write_text(password)
        pw.chmod(0o600)
        data=root/'db'
        def run(program,*args):
            result=subprocess.run([str(bindir/program),*map(str,args)],timeout=20,capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError(f'{program} failed ({result.returncode}): {result.stderr[-800:]}')
        run('initdb','-D',data,'--auth=scram-sha-256','-U','wfs_lab','--pwfile',pw,'--no-locale','--encoding=UTF8')
        pw.unlink()
        options=f"-h 127.0.0.1 -p {port} -c unix_socket_directories=''"
        def start():
            run('pg_ctl','-D',data,'-l',root/'postgres.log','-o',options,'-t','10','-w','start')
        def stop(mode='fast'):
            run('pg_ctl','-D',data,'-t','10','-m',mode,'-w','stop')
        def restart(mode='fast'):
            stop(mode)
            start()
        dsn=make_conninfo(host='127.0.0.1',port=port,dbname='postgres',user='wfs_lab',password=password)
        try:
            start()
            yield dsn,restart
        finally:
            if (data/'postmaster.pid').exists():stop()


def main():
    with instance() as (dsn,restart):
        lab=PostgresQuotaLab(dsn)
        # The expiry case below explicitly expires a lease. Keep the load
        # fixture's leases live throughout a bounded benchmark even on slow CI.
        lab.install(session=2,tenant=8,total=24,ttl=300)
        with psycopg.connect(dsn) as cx:
            version=cx.execute('SHOW server_version').fetchone()[0]
            settings=cx.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit')").fetchone()
            assert settings==('on','on')
            at=cx.execute('SELECT extract(epoch FROM clock_timestamp())::bigint').fetchone()[0]
        sid='a'*64
        request=(uuid4(),uuid4(),sid,'alpha',at)
        # Commit succeeds, but the application's first acknowledgement is discarded.
        committed=lab.reserve(*request)
        assert committed.state=='allowed'
        restart()
        received=lab.reserve(*request)
        assert received.lease and received==committed
        restart('immediate')  # Force PostgreSQL crash recovery, not a physical power cut.
        assert received==lab.reserve(*request)
        assert lab.reserve(uuid4(),request[1],sid,'alpha',at).state=='replayed'
        assert lab.reserve(request[0],request[1],sid,'beta',at).state=='conflict'
        assert lab.reserve(uuid4(),uuid4(),sid,'alpha',at-31).state=='expired'
        assert lab.reserve(uuid4(),uuid4(),sid,'alpha',at+15).state=='expired'
        assert not lab.release(received.lease,sid,'beta')
        assert lab.release(received.lease,sid,'alpha')
        assert lab.release(received.lease,sid,'alpha')
        assert lab.reserve(*request).state=='released'
        expiring=(uuid4(),uuid4(),'f'*64,'expiry',at)
        lease=lab.reserve(*expiring).lease
        assert lease
        with psycopg.connect(dsn) as cx:
            cx.execute("UPDATE wfs_sse_lab_receipt SET lease_until=clock_timestamp()-interval '1 second' WHERE lease_id=%s",(lease,))
        assert lab.reserve(*expiring).state=='expired'
        assert lab.reserve(uuid4(),uuid4(),expiring[2],'expiry',at).state=='allowed'

        with psycopg.connect(dsn,autocommit=True) as cx:
            with cx.transaction():
                cx.execute('SELECT 1 FROM wfs_sse_lab_gate FOR UPDATE')
                try:lab.reserve(uuid4(),uuid4(),sid,'alpha',at)
                except QuotaUnavailable:pass
                else:raise AssertionError('Lock contention must fail closed')
        rollback_id=uuid4()
        try:
            with lab.transaction() as cx:
                cx.execute("INSERT INTO wfs_sse_lab_receipt VALUES(%s,%s,%s,'alpha',%s,'denied',NULL,clock_timestamp(),clock_timestamp())",
                           (rollback_id,uuid4(),sid,at))
                raise RuntimeError('local rollback fixture')
        except RuntimeError as exc:
            if str(exc)!='local rollback fixture':raise
        with psycopg.connect(dsn) as cx:
            assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt WHERE request_id=%s',(rollback_id,)).fetchone()[0]==0
            # Reset only the temporary test database between scenarios.
            cx.execute('TRUNCATE wfs_sse_lab_receipt')

        def concurrent_requests(batch, clients):
            tasks=[(f'{i%12+1:064x}',f'tenant-{i%4}') for i in range(batch)]
            def reserve(arg):
                start=time.perf_counter()
                try:state=lab.reserve(uuid4(),uuid4(),*arg,int(time.time())).state
                except QuotaUnavailable as exc:
                    state='unavailable'
                    reason=getattr(exc.__cause__,'sqlstate',None) or type(exc.__cause__).__name__
                else:reason=None
                return arg,state,(time.perf_counter()-start)*1000,reason
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=clients) as pool:
                results=list(pool.map(reserve,tasks))
            elapsed=time.perf_counter()-start
            issued=[scope for scope,state,_,_ in results if state=='allowed']
            counts=Counter(state for _,state,_,_ in results)
            if elapsed>=300:
                raise RuntimeError('Quota benchmark outlasted the lease fixture')
            assert len(issued)==24,dict(counts)
            assert set(counts)<={'allowed','denied','unavailable'} and counts['denied']>0,dict(counts)
            assert all(issued.count(scope)<=2 for scope in set(issued))
            assert all(sum(tenant==scope[1] for scope in issued)<=8 for _,tenant in issued)
            times=sorted(ms for _,_,ms,_ in results)
            return {'attempted':batch,'admitted':len(issued),'denied':counts['denied'],'unavailable':counts['unavailable'],
                    'unavailable_reasons':dict(Counter(reason for *_,reason in results if reason)),'clients':clients,
                    'elapsed_s':round(elapsed,3),'requests_per_s':round(batch/elapsed,1),
                    'median_ms':round(statistics.median(times),2),'p95_ms':round(times[(95*batch+99)//100-1],2)}
        # Make tenant-cap and session-cap denials observable before global saturation.
        def fresh(scope,tenant):
            return lab.reserve(uuid4(),uuid4(),scope,tenant,at)
        assert [fresh(sid,'alpha').state for _ in range(3)]==['allowed','allowed','denied']
        for i in range(1,7):
            assert fresh(f'{i:064x}','alpha').state=='allowed'
        assert fresh('b'*64,'alpha').state=='denied'
        assert fresh('b'*64,'beta').state=='allowed'
        with psycopg.connect(dsn) as cx:
            cx.execute('TRUNCATE wfs_sse_lab_receipt')
        with psycopg.connect(dsn) as cx:
            cx.execute('''INSERT INTO wfs_sse_lab_receipt
                SELECT gen_random_uuid(),gen_random_uuid(),%s,'cleanup',0,'denied',NULL,
                       clock_timestamp()-interval '1 hour',clock_timestamp()-interval '1 hour'
                FROM generate_series(1,10000)''',(sid,))
        assert lab.cleanup(64)==64
        with psycopg.connect(dsn) as cx:
            assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt').fetchone()[0]==9936
        started=time.perf_counter()
        drained=0
        batches=0
        while (count:=lab.cleanup()):
            drained+=count
            batches+=1
            assert count<=128 and batches<=80
        cleanup={'seeded':10000,'first_batch':64,'remaining_deleted':drained,
                 'remaining_batches':batches,'remaining_elapsed_s':round(time.perf_counter()-started,3)}
        assert drained==9936
        metrics=concurrent_requests(1200,32)
        with psycopg.connect(dsn) as cx:
            assert cx.execute("SELECT count(*) FROM wfs_sse_lab_receipt WHERE tenant_id='cleanup'").fetchone()[0]==0
        assert lab.cleanup()==0
        print(json.dumps({'classification':'PASS_LOCAL_SINGLE_PRIMARY','postgres':version,'fsync':settings[0],
            'synchronous_commit':settings[1],'clean_restart':True,'immediate_stop_recovery':True,'discarded_commit_ack_retry':True,'rollback':True,
            'expired_lease_replaced':True,'bounded_lock_wait':True,'fixture_lease_ttl_seconds':300,
            'cleanup':cleanup,'benchmark':metrics},indent=2))


if __name__=='__main__':main()
