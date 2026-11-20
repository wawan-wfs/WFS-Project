"""Basic contract checks run without provisioning a database."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
import importlib.util
import unittest
from unittest.mock import MagicMock, patch

from app.sse_pg_lab import PostgresQuotaLab, QuotaUnavailable


class PostgresLabContract(unittest.TestCase):
    def test_commit_ack_deadline_rejects_invalid_limits_before_connecting(self):
        for invalid in (True,0,.09,11,10**1000,float('nan'),float('inf'),'1'):
            with self.subTest(kind=type(invalid).__name__),self.assertRaisesRegex(ValueError,'deadline'):
                PostgresQuotaLab('not a DSN',commit_ack_seconds=invalid)

    def test_scope_validation(self):
        for session,tenant in ((None,'a'),('x'*64,'a'),('a'*64,'a/b')):
            self.assertFalse(PostgresQuotaLab._identity(session,tenant))
        self.assertTrue(PostgresQuotaLab._identity('a'*64,'tenant-a'))

    @unittest.skipUnless(importlib.util.find_spec('psycopg'),'Optional PostgreSQL lab dependency')
    def test_restrict_dsn_to_numeric_loopback_and_explicit_database(self):
        base='port=5432 dbname=postgres user=fixture'
        for suffix in ('host=example.test','host=127.0.0.1,192.0.2.1','host=127.0.0.1 service=x','host=::'):
            with self.subTest(suffix=suffix),self.assertRaises(ValueError):
                PostgresQuotaLab(base+' '+suffix)
        lab=PostgresQuotaLab(base+' host=127.0.0.1')
        with self.assertRaises(ValueError):
            lab.reserve(uuid4(),uuid4(),'invalid','tenant',123)
        with self.assertRaises(ValueError):
            lab.install(session=8,tenant=2)


@unittest.skipUnless(importlib.util.find_spec('psycopg'),'Optional PostgreSQL lab dependency')
class WatchdogContractV46(unittest.TestCase):
    def run_scenario(self, *, clocks, fire=False, warning=False):
        import psycopg
        lab=PostgresQuotaLab('host=127.0.0.1 port=5432 dbname=postgres user=fixture',
                            synchronous_commit='remote_apply',commit_ack_seconds=1.2)
        cx=MagicMock()
        cx.__enter__.return_value=cx
        cx.execute.return_value.fetchone.side_effect=[(True,),('on',)]
        cx.cancel_safe.side_effect=psycopg.OperationalError('synthetic undelivered cancel')
        timer=MagicMock()

        def make_timer(_, callback):
            if fire:
                timer.start.side_effect=callback
            return timer

        @contextmanager
        def transaction():
            yield
            if warning:
                cx.add_notice_handler.call_args.args[0](SimpleNamespace(severity_nonlocalized='WARNING'))

        cx.transaction.side_effect=transaction
        with patch.object(psycopg,'connect',return_value=cx), \
             patch.object(psycopg.capabilities,'has_cancel_safe',return_value=True), \
             patch('app.sse_pg_lab.monotonic',side_effect=clocks), \
             patch('app.sse_pg_lab.Timer',side_effect=make_timer):
            try:
                with lab.transaction():
                    pass
            finally:
                timer.cancel.assert_called_once()
                timer.join.assert_called_once()
                if fire:
                    cx.cancel_safe.assert_called_once_with(timeout=1.0)

    def test_commit_without_warning_or_deadline_passes(self):
        self.run_scenario(clocks=[10,10.5])

    def test_deadline_rejects_late_success_even_if_watchdog_thread_was_delayed(self):
        with self.assertRaisesRegex(QuotaUnavailable,'acknowledgement uncertain'):
            self.run_scenario(clocks=[10,11.3])

    def test_undelivered_cancel_or_commit_warning_fails_closed(self):
        with self.assertRaisesRegex(QuotaUnavailable,'acknowledgement uncertain'):
            self.run_scenario(clocks=[10,10.5],fire=True)
        with self.assertRaisesRegex(QuotaUnavailable,'acknowledgement uncertain'):
            self.run_scenario(clocks=[10,10.5],warning=True)
