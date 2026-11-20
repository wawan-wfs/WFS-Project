"""v2.5: 3D occupancy source of truth is scoped, fresh backend telemetry."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from app import store
from app.config import STATIC


class SpatialTelemetryV25(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        path=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',path/'projects')]
        for p in self.patches:p.start()
        store.init_db()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def make_runs(self):
        project=store.create_project('Simulated occupancy','Build a frontend application with source and QA','demo','static')
        pid=project['id']
        store.worker_ping('spatial-test-worker',pid)
        with store.connect() as cx:
            cx.execute("UPDATE projects SET status='running',phase='implementation',worker_id=?,heartbeat_at=? WHERE id=?",
                       ('spatial-test-worker',store.now(),pid))
        for i in range(2):
            store.agent_start(pid,f'Engineer {i+1}','Engineering',f'Task {i+1}',worker_id='spatial-test-worker')
        return pid

    def test_multiple_live_agents_from_backend_without_fabricated_activity(self):
        pid=self.make_runs()
        result=store.office_live(floor=2,project_id=pid,scope_user='owner')
        self.assertEqual(len(result['agents']),2)
        self.assertEqual(sum(x['live'] is True for x in result['agents']),2)
        self.assertEqual(result['divisions']['Engineering']['working'],2)
        self.assertNotIn('worker_id',result['agents'][0])
        js=(STATIC/'office3d.js').read_text()
        self.assertIn('activeCount=runs.filter(a=>a.live===true).length',js)
        self.assertIn('Math.min(3,occupants)',js)

    def test_stale_worker_marks_runs_interrupted_and_no_live_avatars(self):
        pid=self.make_runs()
        old=(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat(timespec='seconds')
        with store.connect() as cx:
            cx.execute('UPDATE worker_instances SET last_seen=?',(old,))
            cx.execute('UPDATE projects SET heartbeat_at=? WHERE id=?',(old,pid))
        snapshot=store.office_live(floor=2,project_id=pid,scope_user='owner')
        self.assertFalse(any(x['live'] for x in snapshot['agents']))
        self.assertEqual(snapshot['divisions']['Engineering']['working'],0)
        self.assertEqual(snapshot['divisions']['Engineering']['interrupted'],2)

    def test_gpu_metrics_are_separated_from_cpu_submit_metric(self):
        renderer=(STATIC/'office3d.js').read_text()
        self.assertIn('EXT_disjoint_timer_query_webgl2',renderer)
        self.assertIn('meanGpuTimeMs:',renderer)
        self.assertIn('gpuTimerSupported:',renderer)
        self.assertIn('CPU submit wall time only; GPU time unverified',renderer)
        self.assertIn('window.WFSOffice3D',renderer)

if __name__=='__main__':unittest.main()
