"""Separate persistent queue worker. No Docker socket or subprocess execution."""
from __future__ import annotations
import argparse
import os
import signal
import threading
import time
import uuid
from . import config, store, pipeline

STOP=threading.Event()


def attempt_lease_identity(worker_id: str) -> str:
    """Fresh identity for each claim, even when the same daemon is reused.

    A recovered/reclaimed attempt must NEVER accept a completion from an
    earlier attempt with the same stable worker daemon identity.
    """
    return worker_id + '-lease-' + uuid.uuid4().hex


def execute_one(worker_id=None):
    temporary_worker=worker_id is None
    worker_id=worker_id or ('wfs-'+uuid.uuid4().hex[:12])
    lease_id=attempt_lease_identity(worker_id)
    project=store.claim(lease_id)
    if not project:return False
    pid=project['id']
    # The per-claim identity is also the observable worker identity while
    # busy; the stable daemon identity is restored only while idle.
    store.worker_depart(worker_id)
    store.worker_ping(lease_id,pid)
    tick=threading.Event()
    def keepalive():
        while not tick.wait(8):
            try:
                store.heartbeat(pid,lease_id)
                store.worker_ping(lease_id,pid)
            except Exception:pass
    t=threading.Thread(target=keepalive,daemon=True);t.start()
    store.event(pid,'Master Orchestrator','working','Worker menerima misi dan memulai proses',worker_id=lease_id)
    try:
        outcome=pipeline.run(project)
        if store.get_project(pid)['status']=='cancel_requested':
            store.finish(pid,'cancelled','Dibatalkan administrator',worker_id=lease_id)
        else:
            if not store.finish(pid,'review_required' if outcome=='review_required' else 'completed',worker_id=lease_id):
                store.finish(pid,'cancelled','Dibatalkan administrator',worker_id=lease_id)
    except pipeline.Deferred:
        pass
    except pipeline.Cancelled as exc:
        store.event(pid,'Master Orchestrator','cancelled',str(exc),worker_id=lease_id)
        store.finish(pid,'cancelled',str(exc),worker_id=lease_id)
    except Exception as exc:
        # Never print raw external API response or secrets.
        message=str(exc)[:600]
        cancelled=store.get_project(pid)['status']=='cancel_requested'
        state='cancelled' if cancelled else 'failed'
        store.event(pid,'Master Orchestrator',state,message,worker_id=lease_id)
        store.finish(pid,state,message,worker_id=lease_id)
    finally:
        tick.set();t.join(timeout=2)
        store.worker_depart(lease_id)
        if not temporary_worker:store.worker_ping(worker_id,None)
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if not config.configured():raise SystemExit('Konfigurasi admin/session belum tersedia; jalankan bootstrap')
    store.init_db()
    store.recover_stale(180)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set())
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    worker_id='wfs-'+uuid.uuid4().hex[:12]
    last_ping=0.0
    try:
        while not STOP.is_set():
            if time.monotonic()-last_ping>8:
                store.worker_ping(worker_id,None)
                last_ping=time.monotonic()
            store.recover_stale(180)
            if execute_one(worker_id):
                if args.once:break
            elif args.once:break
            else:STOP.wait(1.5)
    finally:
        store.worker_depart(worker_id)

if __name__=='__main__':main()
