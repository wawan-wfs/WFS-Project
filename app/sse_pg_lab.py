"""Single-primary PostgreSQL quota experiment; deliberately not wired to WFS HTTP.

Callers in this lab are trusted and pass synthetic, already-verified scope.
This module is not an assertion issuer, a distributed identity service, or HA.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import ipaddress
import re
from threading import Event, Timer
from time import monotonic
from uuid import UUID

SCHEMA = """
CREATE TABLE IF NOT EXISTS wfs_sse_lab_gate (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    session_cap integer NOT NULL CHECK (session_cap > 0),
    tenant_cap integer NOT NULL CHECK (tenant_cap >= session_cap),
    total_cap integer NOT NULL CHECK (total_cap >= tenant_cap),
    ttl integer NOT NULL CHECK (ttl BETWEEN 1 AND 300)
);
CREATE TABLE IF NOT EXISTS wfs_sse_lab_receipt (
    request_id uuid PRIMARY KEY,
    nonce uuid NOT NULL UNIQUE,
    session_id text NOT NULL,
    tenant_id text NOT NULL,
    issued_at bigint NOT NULL,
    state text NOT NULL CHECK (state IN ('allowed','denied','released')),
    lease_id uuid UNIQUE,
    lease_until timestamptz NOT NULL,
    retain_until timestamptz NOT NULL,
    CHECK ((state='denied') = (lease_id IS NULL))
);
CREATE INDEX IF NOT EXISTS wfs_sse_lab_receipt_retention ON wfs_sse_lab_receipt (retain_until);
CREATE INDEX IF NOT EXISTS wfs_sse_lab_active ON wfs_sse_lab_receipt (lease_until)
    WHERE state='allowed';
"""

ASSERTION_SECONDS = 30
FUTURE_SKEW_SECONDS = 2
RECEIPT_SECONDS = 90
CLEANUP_BATCH = 128


@dataclass(frozen=True)
class Receipt:
    state: str
    lease: UUID | None = None


class QuotaUnavailable(RuntimeError):
    """Fail closed; callers may retry with the exact same request identity."""


class PostgresQuotaLab:
    def __init__(self, dsn, *, synchronous_commit="on", commit_ack_seconds=2.0):
        if synchronous_commit not in ("on","remote_apply"):
            raise ValueError("Unsupported lab commit policy")
        if type(commit_ack_seconds) not in (int,float) or not 0.1 <= commit_ack_seconds <= 10:
            raise ValueError("Invalid synchronous lab acknowledgement deadline")
        self.synchronous_commit=synchronous_commit
        self.commit_ack_seconds=commit_ack_seconds
        from psycopg.conninfo import conninfo_to_dict
        values = conninfo_to_dict(dsn)
        # Force a numeric loopback target and ignore libpq environment routing.
        if set(values) - {'host','port','dbname','user','password'} or not {'host','port','dbname','user'} <= values.keys():
            raise ValueError('Lab requires explicit host, port, database and user; no service files')
        try:
            address = ipaddress.ip_address(values['host'])
        except ValueError:
            raise ValueError('Lab requires a numeric loopback address') from None
        if not address.is_loopback or not values['port'].isdigit() or not 1 <= int(values['port']) <= 65535:
            raise ValueError('Lab is restricted to a single loopback PostgreSQL primary')
        self.connection = {**values,'hostaddr':str(address),'password':values.get('password',''),
                           'connect_timeout':2,'sslmode':'disable','gssencmode':'disable',
                           'target_session_attrs':'read-write','application_name':'wfs-sse-quota-lab'}

    @contextmanager
    def transaction(self):
        import psycopg
        strict=self.synchronous_commit=='remote_apply'
        if strict and not psycopg.capabilities.has_cancel_safe():
            raise QuotaUnavailable('Synchronous lab requires libpq with nonblocking cancel support')
        try:
            with psycopg.connect(**self.connection, autocommit=True) as cx:
                warnings=[]
                expired=Event()
                watchdog=None
                deadline=None
                late=False
                if strict:
                    cx.add_notice_handler(lambda notice: warnings.append(notice.severity_nonlocalized)
                                          if notice.severity_nonlocalized=='WARNING' else None)
                def cancel_commit():
                    # A response racing the watchdog must still fail closed.
                    expired.set()
                    try:
                        cx.cancel_safe(timeout=1.0)
                    except (psycopg.Error,OSError):
                        # A cancel request is best effort, not a network deadline.
                        pass
                try:
                    with cx.transaction():
                        cx.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                        cx.execute("SET LOCAL lock_timeout='700ms'")
                        cx.execute("SET LOCAL statement_timeout='1500ms'")
                        cx.execute("SET LOCAL idle_in_transaction_session_timeout='3000ms'")
                        cx.execute("SELECT set_config('synchronous_commit',%s,true)",(self.synchronous_commit,))
                        if strict and not cx.execute("""
                            SELECT current_setting('synchronous_standby_names')<>'' AND EXISTS
                            (SELECT 1 FROM pg_stat_replication WHERE state='streaming' AND sync_state IN ('sync','quorum'))
                            """).fetchone()[0]:
                            raise QuotaUnavailable('Synchronous lab standby unavailable')
                        if cx.execute("SELECT current_setting('fsync')").fetchone()[0] != 'on':
                            raise QuotaUnavailable('PostgreSQL lab requires fsync')
                        yield cx
                        if strict:
                            timer=Timer(self.commit_ack_seconds,cancel_commit)
                            timer.daemon=True
                            deadline=monotonic()+self.commit_ack_seconds
                            timer.start()
                            watchdog=timer
                    # Check the clock even if the scheduler delayed the timer.
                    late=deadline is not None and monotonic()>=deadline
                finally:
                    if watchdog is not None:
                        watchdog.cancel()
                        watchdog.join()
                # PostgreSQL can warn (rather than abort) when a synchronous
                # commit wait is canceled after local WAL flush.
                if warnings or late or expired.is_set():
                    raise QuotaUnavailable('Synchronous lab commit acknowledgement uncertain')
        except psycopg.Error as exc:
            raise QuotaUnavailable('PostgreSQL lab transaction failed') from exc

    def install(self, *, session=2, tenant=8, total=24, ttl=65):
        if not all(type(x) is int for x in (session,tenant,total,ttl)) or not (1<=session<=tenant<=total<=10000 and 1<=ttl<=300):
            raise ValueError('Invalid lab quota settings')
        with self.transaction() as cx:
            cx.execute(SCHEMA)
            cx.execute('INSERT INTO wfs_sse_lab_gate VALUES(true,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                       (session,tenant,total,ttl))
            if self._lock(cx)!=(session,tenant,total,ttl):
                raise ValueError('Lab quota settings differ from the installed configuration')

    @staticmethod
    def _lock(cx):
        row=cx.execute('SELECT session_cap,tenant_cap,total_cap,ttl FROM wfs_sse_lab_gate WHERE singleton FOR UPDATE').fetchone()
        if row is None:
            raise QuotaUnavailable('PostgreSQL quota lab not initialized')
        return row

    @staticmethod
    def _identity(session,tenant):
        return (isinstance(session,str) and re.fullmatch('[0-9a-f]{64}',session)
                and isinstance(tenant,str) and re.fullmatch('[A-Za-z0-9_.:-]{1,128}',tenant))

    def reserve(self,request_id,nonce,session,tenant,issued_at):
        if (not isinstance(request_id,UUID) or not isinstance(nonce,UUID) or
                not self._identity(session,tenant) or type(issued_at) is not int or not 0<=issued_at<2**63):
            raise ValueError('Invalid verified lab scope')
        with self.transaction() as cx:
            session_cap,tenant_cap,total_cap,ttl=self._lock(cx)
            at=cx.execute('SELECT clock_timestamp()').fetchone()[0]
            if not int(at.timestamp())-ASSERTION_SECONDS < issued_at <= int(at.timestamp())+FUTURE_SKEW_SECONDS:
                return Receipt('expired')
            record=cx.execute('''SELECT nonce,session_id,tenant_id,issued_at,state,lease_id,lease_until
                                 FROM wfs_sse_lab_receipt WHERE request_id=%s''',(request_id,)).fetchone()
            if record:
                if record[:4]!=(nonce,session,tenant,issued_at):
                    return Receipt('conflict')
                state,lease,until=record[4:]
                if state=='allowed' and at>=until:
                    return Receipt('expired')
                if state=='allowed' and self.synchronous_commit=='remote_apply':
                    # A read-only retry might otherwise return a locally
                    # committed lease whose earlier acknowledgement was lost.
                    # Force a WAL commit past that receipt before acknowledging.
                    cx.execute('UPDATE wfs_sse_lab_gate SET ttl=ttl WHERE singleton')
                return Receipt(state,lease if state=='allowed' else None)
            if cx.execute('SELECT 1 FROM wfs_sse_lab_receipt WHERE nonce=%s',(nonce,)).fetchone():
                return Receipt('replayed')
            count,ns,nt=cx.execute("""SELECT count(*),count(*) FILTER (WHERE session_id=%s),
                       count(*) FILTER (WHERE tenant_id=%s) FROM wfs_sse_lab_receipt
                       WHERE state='allowed' AND lease_until>%s""",(session,tenant,at)).fetchone()
            from datetime import timedelta
            from uuid import uuid4
            allowed=count<total_cap and ns<session_cap and nt<tenant_cap
            state,lease=('allowed',uuid4()) if allowed else ('denied',None)
            cx.execute('INSERT INTO wfs_sse_lab_receipt VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (request_id,nonce,session,tenant,issued_at,state,lease,at+timedelta(seconds=ttl),
                 at+timedelta(seconds=max(RECEIPT_SECONDS,ttl+ASSERTION_SECONDS+FUTURE_SKEW_SECONDS))))
            return Receipt(state,lease)

    @staticmethod
    def _cleanup(cx, at, limit):
        return cx.execute('''WITH expired AS (
            SELECT request_id FROM wfs_sse_lab_receipt WHERE retain_until<=%s
            ORDER BY retain_until,request_id LIMIT %s
          ) DELETE FROM wfs_sse_lab_receipt r USING expired e WHERE r.request_id=e.request_id''',
                          (at,limit)).rowcount

    def cleanup(self, limit=CLEANUP_BATCH):
        if type(limit) is not int or not 1<=limit<=CLEANUP_BATCH:
            raise ValueError('Cleanup limit exceeds the lab transaction budget')
        with self.transaction() as cx:
            self._lock(cx)
            return self._cleanup(cx,cx.execute('SELECT clock_timestamp()').fetchone()[0],limit)

    def release(self, lease, session, tenant):
        if not isinstance(lease,UUID) or not self._identity(session,tenant):
            raise ValueError('Invalid verified lab scope')
        with self.transaction() as cx:
            self._lock(cx)
            row=cx.execute('''UPDATE wfs_sse_lab_receipt SET state='released'
                              WHERE lease_id=%s AND session_id=%s AND tenant_id=%s
                              AND state IN ('allowed','released') RETURNING request_id''',
                           (lease,session,tenant)).fetchone()
            return row is not None
