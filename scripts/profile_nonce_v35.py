#!/usr/bin/env python3
"""Measure REAL local SQLite replay admission contention; no production claims.

Uses a disposable temp database and independent processes. The report cannot be
used as a Windows/remote-host or production-scale performance certificate.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import secrets
import tempfile
import time
from pathlib import Path


def _attempt(job: tuple[str, str]) -> tuple[bool, float]:
    from app import store, preview_authority
    db_dir, nonce = job
    root = Path(db_dir)
    store.DATA = root
    store.DB = root / 'db.sqlite3'
    store.PROJECTS = root / 'projects'
    started = time.perf_counter()
    result = preview_authority._consume_nonce(nonce, int(time.time()))
    return result, round((time.perf_counter() - started)*1000, 3)


def profile(*, workers: int = 4, count: int = 128) -> dict:
    if not (1 <= workers <= 16 and workers <= count <= 2048):
        raise ValueError('workers 1..16 and workers <= count <= 2048')
    from app import store
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix='wfs-v35-nonce-profile-') as tmp:
        folder = Path(tmp)
        with patch.object(store,'DATA',folder), patch.object(store,'DB',folder/'db.sqlite3'), patch.object(store,'PROJECTS',folder/'projects'):
            store.init_db()
        unique = [secrets.token_hex(16) for _ in range(count)]
        repeated = secrets.token_hex(16)
        jobs = [(tmp, nonce) for nonce in unique] + [(tmp, repeated)]*workers
        started=time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            observed=list(pool.map(_attempt, jobs))
        elapsed=time.perf_counter() - started
        distinct=observed[:count]
        replay=observed[count:]
        latencies=sorted(lat for _,lat in observed)
        if not (all(v for v,_ in distinct) and sum(int(v) for v,_ in replay)==1):
            raise RuntimeError('Nonce admission contention failed, not performance-certified')
        return {'classification':'PASS_LOCAL_ONLY','provider_cost':0,'workers':workers,
                'unique_nonces':count,'replay_competitors':workers,
                'unique_accepted':sum(v for v,_ in distinct),'same_nonce_accepted':sum(v for v,_ in replay),
                'elapsed_ms':round(elapsed*1000,2),'p50_request_ms':latencies[len(latencies)//2],
                'p95_request_ms':latencies[min(len(latencies)-1,int(len(latencies)*0.95))],
                'real_host_proof':False,'production_admission':'DENIED'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--count',type=int,default=128)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Refusing to overwrite existing evidence')
    report=profile(workers=args.workers,count=args.count)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
