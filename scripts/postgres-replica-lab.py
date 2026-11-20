#!/usr/bin/env python3
"""Disposable single-host primary/standby failover experiment. Never uses a real DB."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from app.sse_pg_lab import PostgresQuotaLab, QuotaUnavailable

spec=importlib.util.spec_from_file_location('single_primary_lab',Path(__file__).with_name('postgres-quota-lab.py'))
single=importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)


def main():
    bin_dir=single.postgres_bin()
    with tempfile.TemporaryDirectory(prefix='wfs-replica-lab-') as temp:
        root=Path(temp)
        main_db,copy_db,rejoin_db=root/'primary',root/'standby',root/'rebuilt-standby'
        with closing(socket.socket()) as a,closing(socket.socket()) as b:
            a.bind(('127.0.0.1',0))
            b.bind(('127.0.0.1',0))
            primary_port,standby_port=a.getsockname()[1],b.getsockname()[1]
        secret=secrets.token_urlsafe(32)
        pw=root/'init-password'
        pw.write_text(secret)
        pw.chmod(0o600)
        passfile=root/'replication-password'
        passfile.write_text(f'127.0.0.1:{primary_port}:replication:wfs_lab:{secret}\n')
        passfile.chmod(0o600)
        def run(program,*args,ok=True):
            result=subprocess.run([str(bin_dir/program),*map(str,args)],capture_output=True,text=True,timeout=22)
            if ok and result.returncode:
                raise RuntimeError(f'{program} failed ({result.returncode}): {result.stderr[-600:]}')
            return result
        retired=set()
        def start(path,port):
            if path in retired:raise RuntimeError('Retired writer directory cannot be restarted by this lab')
            run('pg_ctl','-D',path,'-l',path.with_suffix('.log'),'-t','10','-w','start',
                '-o',f"-h 127.0.0.1 -p {port} -c unix_socket_directories='' -c max_connections=48")
        def stop(path,mode='fast'):
            if (path/'postmaster.pid').exists():
                run('pg_ctl','-D',path,'-t','10','-m',mode,'-w','stop')
        def dsn(port):
            return make_conninfo(host='127.0.0.1',port=port,dbname='postgres',user='wfs_lab',password=secret)
        def connect(port):
            return psycopg.connect(dsn(port),connect_timeout=2,autocommit=True)
        def is_sync(port=primary_port, name='wfs_standby'):
            with connect(port) as cx:
                return cx.execute("""SELECT EXISTS (SELECT 1 FROM pg_stat_replication
                    WHERE application_name=%s AND state='streaming' AND sync_state='sync')""",(name,)).fetchone()[0]
        def fenced_promote():
            if run('pg_ctl','-D',main_db,'status',ok=False).returncode!=3:
                raise RuntimeError('Old primary must be stopped before standby promotion')
            with closing(socket.socket()) as probe:
                probe.settimeout(1)
                if probe.connect_ex(('127.0.0.1',primary_port))==0:
                    raise RuntimeError('Old primary endpoint still accepts connections')
            run('pg_ctl','-D',copy_db,'-t','10','-w','promote')
        try:
            run('initdb','-D',main_db,'--auth=scram-sha-256','-U','wfs_lab','--pwfile',pw,'--no-locale','--encoding=UTF8')
            pw.unlink()
            start(main_db,primary_port)
            local=PostgresQuotaLab(dsn(primary_port))
            local.install(session=2,tenant=8,total=24,ttl=60)
            repl=make_conninfo(host='127.0.0.1',port=primary_port,user='wfs_lab',
                               passfile=str(passfile),application_name='wfs_standby',sslmode='disable')
            run('pg_basebackup','-D',copy_db,'--dbname',repl,'-R','-X','stream','-c','fast','-w')
            start(copy_db,standby_port)
            with connect(primary_port) as cx:
                cx.execute("ALTER SYSTEM SET synchronous_standby_names TO 'FIRST 1 (wfs_standby)'")
                cx.execute('SELECT pg_reload_conf()')
            deadline=time.monotonic()+8
            while not is_sync():
                if time.monotonic()>=deadline:raise RuntimeError('Standby did not become synchronous')
                time.sleep(.08)

            try:fenced_promote()
            except RuntimeError as exc:
                assert str(exc)=='Old primary must be stopped before standby promotion'
            else:raise AssertionError('Fence accepted a running primary')
            with connect(standby_port) as cx:
                assert cx.execute('SELECT pg_is_in_recovery()').fetchone()[0]
                try:cx.execute('UPDATE wfs_sse_lab_gate SET total_cap=total_cap')
                except psycopg.errors.ReadOnlySqlTransaction:pass
                else:raise AssertionError('Standby unexpectedly writable')

            replicated=PostgresQuotaLab(dsn(primary_port),synchronous_commit='remote_apply',commit_ack_seconds=1.2)
            with connect(primary_port) as cx:
                version=cx.execute('SHOW server_version').fetchone()[0]
                issued=int(cx.execute('SELECT extract(epoch FROM clock_timestamp())').fetchone()[0])
            cases=[(uuid4(),uuid4(),f'{i+1:064x}',f'tenant-{i%4}',issued) for i in range(16)]
            receipts=[replicated.reserve(*item) for item in cases]
            assert all(r.state=='allowed' and r.lease for r in receipts)
            with connect(standby_port) as cx:
                assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt').fetchone()[0]==len(receipts)
            lag_case=(uuid4(),uuid4(),'e'*64,'lag-tenant',int(time.time()))
            with connect(standby_port) as cx:
                cx.execute('SELECT pg_wal_replay_pause()')
                deadline=time.monotonic()+5
                while cx.execute('SELECT pg_get_wal_replay_pause_state()').fetchone()[0]!='paused':
                    if time.monotonic()>=deadline:raise RuntimeError('Standby did not pause replay')
                    time.sleep(.03)
            def sync_waiter(pending):
                deadline=time.monotonic()+3
                while time.monotonic()<deadline and not pending.done():
                    with connect(primary_port) as cx:
                        found=cx.execute("""SELECT pid FROM pg_stat_activity
                            WHERE application_name='wfs-sse-quota-lab' AND wait_event='SyncRep'""").fetchone()
                    if found:return found[0]
                    time.sleep(.025)
                return None

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    begin=time.monotonic()
                    pending=pool.submit(replicated.reserve,*lag_case)
                    try:
                        assert sync_waiter(pending),'Reservation did not wait for synchronous replay'
                        try:pending.result(timeout=4)
                        except QuotaUnavailable as exc:
                            assert str(exc)=='Synchronous lab commit acknowledgement uncertain',str(exc)
                        else:raise AssertionError('Synchronous commit past the watchdog was acknowledged')
                        cancel_elapsed=round(time.monotonic()-begin,3)
                        assert cancel_elapsed>=replicated.commit_ack_seconds
                    finally:
                        if not pending.done():
                            with connect(standby_port) as cx:
                                cx.execute('SELECT pg_wal_replay_resume()')
                with connect(primary_port) as cx:
                    locally_committed=cx.execute('SELECT lease_id FROM wfs_sse_lab_receipt WHERE request_id=%s',
                                                 (lag_case[0],)).fetchone()
                assert locally_committed and locally_committed[0]
                with connect(standby_port) as cx:
                    assert not cx.execute('SELECT 1 FROM wfs_sse_lab_receipt WHERE request_id=%s',
                                          (lag_case[0],)).fetchone()
                # Retrying an already committed local receipt must still wait
                # for a synchronous WAL barrier, not return a read-only hit.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(replicated.reserve,*lag_case)
                    try:
                        assert sync_waiter(pending),'Retry did not wait for synchronous replay'
                    finally:
                        with connect(standby_port) as cx:
                            cx.execute('SELECT pg_wal_replay_resume()')
                    recovered=pending.result(timeout=4)
                    assert recovered.lease==locally_committed[0]
            finally:
                with connect(standby_port) as cx:
                    cx.execute('SELECT pg_wal_replay_resume()')
            cases.append(lag_case)
            receipts.append(recovered)
            stop(copy_db)
            try:replicated.reserve(uuid4(),uuid4(),'f'*64,'unavailable',issued)
            except QuotaUnavailable:pass
            else:raise AssertionError('Synchronous reservation accepted without standby')
            start(copy_db,standby_port)
            deadline=time.monotonic()+8
            while not is_sync():
                if time.monotonic()>=deadline:raise RuntimeError('Standby did not rejoin')
                time.sleep(.08)
            start_time=time.monotonic()
            stop(main_db,'immediate')
            fenced_promote()
            retired.add(main_db)
            with connect(standby_port) as cx:
                assert not cx.execute('SELECT pg_is_in_recovery()').fetchone()[0]
                assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt').fetchone()[0]==len(receipts)
            promoted=PostgresQuotaLab(dsn(standby_port))
            assert [promoted.reserve(*item) for item in cases]==receipts
            assert promoted.reserve(uuid4(),cases[0][1],cases[0][2],cases[0][3],issued).state=='replayed'
            promoted_strict=PostgresQuotaLab(dsn(standby_port),synchronous_commit='remote_apply')
            post_promotion_case=(uuid4(),uuid4(),'d'*64,'post-promotion',int(time.time()))
            try:promoted_strict.reserve(*post_promotion_case)
            except QuotaUnavailable as exc:
                assert str(exc)=='Synchronous lab standby unavailable',str(exc)
            else:raise AssertionError('Promoted primary accepted strict work before standby enrolment')
            with connect(standby_port) as cx:
                assert not cx.execute('SELECT 1 FROM wfs_sse_lab_receipt WHERE request_id=%s',
                                      (post_promotion_case[0],)).fetchone()
            elapsed=round(time.monotonic()-start_time,3)
            try:start(main_db,primary_port)
            except RuntimeError as exc:
                assert str(exc)=='Retired writer directory cannot be restarted by this lab'
            else:raise AssertionError('Lab unexpectedly restarted the retired primary')

            # Rejoin using a fresh base backup of the promoted primary, never
            # restart the old writer's data directory as a writable server.
            passfile.write_text(f'127.0.0.1:{standby_port}:replication:wfs_lab:{secret}\n')
            rejoin=make_conninfo(host='127.0.0.1',port=standby_port,user='wfs_lab',
                                  passfile=str(passfile),application_name='wfs_rebuilt',sslmode='disable')
            run('pg_basebackup','-D',rejoin_db,'--dbname',rejoin,'-R','-X','stream','-c','fast','-w')
            start(rejoin_db,primary_port)
            with connect(primary_port) as cx:
                assert cx.execute('SELECT pg_is_in_recovery()').fetchone()[0]
                assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt').fetchone()[0]==len(receipts)
                try:cx.execute('UPDATE wfs_sse_lab_gate SET total_cap=total_cap')
                except psycopg.errors.ReadOnlySqlTransaction:pass
                else:raise AssertionError('Rebuilt standby unexpectedly writable')
            with connect(standby_port) as cx:
                cx.execute("ALTER SYSTEM SET synchronous_standby_names TO 'FIRST 1 (wfs_rebuilt)'")
                cx.execute('SELECT pg_reload_conf()')
            deadline=time.monotonic()+8
            while not is_sync(standby_port,'wfs_rebuilt'):
                if time.monotonic()>=deadline:raise RuntimeError('Rebuilt standby did not become synchronous')
                time.sleep(.08)
            post_promotion_case=(*post_promotion_case[:4],int(time.time()))
            new_receipt=promoted_strict.reserve(*post_promotion_case)
            assert new_receipt.state=='allowed' and new_receipt.lease
            assert promoted_strict.reserve(*post_promotion_case)==new_receipt
            with connect(primary_port) as cx:
                assert cx.execute('SELECT pg_is_in_recovery()').fetchone()[0]
                assert cx.execute('SELECT lease_id FROM wfs_sse_lab_receipt WHERE request_id=%s',
                                  (post_promotion_case[0],)).fetchone()==(new_receipt.lease,)
                assert cx.execute('SELECT count(*) FROM wfs_sse_lab_receipt').fetchone()[0]==len(receipts)+1
            print(json.dumps({'classification':'PASS_SINGLE_HOST_REPLICATION_LAB','postgres':version,
                'acknowledged_leases':len(receipts),'retained_identical':len(receipts),'standby_read_only':True,
                'missing_standby_rejected':True,'promotion_refused_while_old_primary_running':True,
                'old_primary_stopped_before_promotion':True,'promotion_and_replay_seconds':elapsed,
                'replay_paused_not_acknowledged':True,'retry_waited_for_replay':True,
                'commit_watchdog_seconds':replicated.commit_ack_seconds,
                'unavailable_after_seconds':cancel_elapsed,'cancel_mode':'client watchdog; no operator cancel',
                'lab_refused_restart_of_retired_directory':True,'rebuilt_standby_read_only':True,
                'post_promotion_strict_rejected_before_rejoin':True,
                'post_promotion_mode':'remote_apply after explicit synchronous enrolment',
                'post_promotion_new_lease_replayed':True,'independent_hosts':False},indent=2))
        finally:
            try:stop(rejoin_db)
            finally:
                try:stop(copy_db)
                finally:stop(main_db)


if __name__=='__main__':
    main()
