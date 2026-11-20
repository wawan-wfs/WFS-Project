"""Atomic, tenant-scoped *estimated* AI spend reservations.

This is an admission control mechanism, not a provider invoice. Cost estimates
may differ from provider billing (cached tokens, retries, failure billing, tax).
No client-supplied organization identity is trusted by this module.
"""
from __future__ import annotations

import math
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from . import store, config


class QuotaDenied(ValueError):
    """A quota or price-policy prevented a provider request."""


def install(cx: sqlite3.Connection) -> None:
    """Additive schema migration; call only *after* organization migration."""
    cx.execute('BEGIN IMMEDIATE')
    cx.execute('''CREATE TABLE IF NOT EXISTS workspaces (
        organization_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY(organization_id,id))''')
    cx.execute('''INSERT OR IGNORE INTO workspaces(organization_id,id,name,created_at)
        SELECT id,'default','Main workspace',? FROM organizations''',(store.now(),))
    if 'workspace_id' not in {r['name'] for r in cx.execute('PRAGMA table_info(projects)')}:
        cx.execute("ALTER TABLE projects ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default'")
    cx.execute('CREATE INDEX IF NOT EXISTS idx_projects_org_workspace ON projects(organization_id,workspace_id)')
    cx.execute('''CREATE TABLE IF NOT EXISTS spend_limits (
        organization_id TEXT NOT NULL, scope TEXT NOT NULL, scope_id TEXT NOT NULL,
        limit_usd REAL NOT NULL CHECK(limit_usd>=0 AND limit_usd<=1000000),
        updated_at TEXT NOT NULL,
        PRIMARY KEY(organization_id,scope,scope_id),
        CHECK(scope IN ('organization','workspace')))''')
    cx.execute('''CREATE TABLE IF NOT EXISTS cost_reservations (
        id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
        project_id TEXT NOT NULL, model TEXT NOT NULL,
        input_rate_snapshot REAL NOT NULL DEFAULT 0,
        output_rate_snapshot REAL NOT NULL DEFAULT 0,
        estimated_usd REAL NOT NULL CHECK(estimated_usd>=0),
        status TEXT NOT NULL CHECK(status IN ('reserved','settled','released','expired')),
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, finished_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE)''')
    cols={r['name'] for r in cx.execute('PRAGMA table_info(cost_reservations)')}
    if 'input_rate_snapshot' not in cols:
        cx.execute('ALTER TABLE cost_reservations ADD COLUMN input_rate_snapshot REAL NOT NULL DEFAULT 0')
    if 'output_rate_snapshot' not in cols:
        cx.execute('ALTER TABLE cost_reservations ADD COLUMN output_rate_snapshot REAL NOT NULL DEFAULT 0')
    cx.execute('CREATE INDEX IF NOT EXISTS idx_reservation_active ON cost_reservations(status,expires_at,organization_id,workspace_id,project_id)')
    cx.execute('COMMIT')


def _identity(cx, pid: str):
    row=cx.execute('SELECT organization_id,workspace_id FROM projects WHERE id=?',(pid,)).fetchone()
    if not row:raise QuotaDenied('Project not found')
    return row['organization_id'], row['workspace_id']


def _limits(cx, org: str, workspace: str, pid: str):
    rows=cx.execute('''SELECT scope,scope_id,limit_usd FROM spend_limits WHERE organization_id=?
        AND ((scope='organization' AND scope_id=?) OR (scope='workspace' AND scope_id=?))''',
        (org,org,workspace)).fetchall()
    result=[(r['scope'],float(r['limit_usd'])) for r in rows if r['limit_usd']>0]
    project=cx.execute('SELECT limit_usd FROM project_budgets WHERE project_id=?',(pid,)).fetchone()
    if project and project['limit_usd']>0:result.append(('project',float(project['limit_usd'])))
    if config.MAX_ESTIMATED_COST_USD>0:result.append(('project',config.MAX_ESTIMATED_COST_USD))
    return result


def _total(cx, scope: str, org: str, workspace: str, pid: str) -> float:
    terms={'organization':('p.organization_id=?',(org,)),
           'workspace':('p.organization_id=? AND p.workspace_id=?',(org,workspace)),
           'project':('p.id=? AND p.organization_id=? AND p.workspace_id=?',(pid,org,workspace))}
    cond,args=terms[scope]
    used=cx.execute('''SELECT COALESCE(SUM(u.estimated_usd),0) v FROM usage u
        JOIN projects p ON p.id=u.project_id WHERE '''+cond,args).fetchone()['v']
    active_cond={'organization':'r.organization_id=?','workspace':'r.organization_id=? AND r.workspace_id=?',
                 'project':'r.project_id=? AND r.organization_id=? AND r.workspace_id=?'}[scope]
    reserved=cx.execute('SELECT COALESCE(SUM(r.estimated_usd),0) v FROM cost_reservations r WHERE r.status=? AND r.expires_at>? AND '+active_cond,
        ('reserved',store.now(),*args)).fetchone()['v']
    return float(used)+float(reserved)


def set_scope_limit(user_id: str, scope: str, limit_usd: float, workspace_id='default') -> dict:
    if scope not in ('organization','workspace'):
        raise QuotaDenied('Allowed scopes: organization or workspace')
    if isinstance(limit_usd,bool) or not isinstance(limit_usd,(int,float)) or not math.isfinite(limit_usd) or limit_usd<0 or limit_usd>1000000:
        raise QuotaDenied('Limit must be a finite USD value between 0 and 1,000,000')
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        actor=cx.execute('SELECT organization_id,role,disabled FROM users WHERE id=?',(user_id,)).fetchone()
        if not actor or actor['disabled'] or actor['role'] not in ('owner','manager'):
            raise QuotaDenied('Organization billing administrator required')
        org=actor['organization_id']
        if not cx.execute('SELECT 1 FROM workspaces WHERE organization_id=? AND id=?',(org,workspace_id)).fetchone():
            raise QuotaDenied('Workspace not found in current organization')
        sid=org if scope=='organization' else workspace_id
        cx.execute('''INSERT INTO spend_limits(organization_id,scope,scope_id,limit_usd,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(organization_id,scope,scope_id) DO UPDATE SET
            limit_usd=excluded.limit_usd,updated_at=excluded.updated_at''',(org,scope,sid,float(limit_usd),store.now()))
        cx.execute('COMMIT')
    return {'scope':scope,'scope_id':sid,'limit_usd':float(limit_usd),'estimate_only':True}


def read_scope_limits(user_id: str) -> list[dict]:
    with store.connect() as cx:
        user=cx.execute('SELECT organization_id FROM users WHERE id=? AND disabled=0',(user_id,)).fetchone()
        if not user:return []
        return [dict(row) for row in cx.execute('''SELECT scope,scope_id,limit_usd,updated_at FROM spend_limits
                WHERE organization_id=? ORDER BY scope,scope_id''',(user['organization_id'],))]


def reserve(pid: str, model: str, input_estimate_tokens: int, output_max_tokens: int, ttl_seconds: int=900) -> str | None:
    """Serialize concurrent admissions against org, workspace and project limits.

    Returns None when no hard limit is active (historical behavior preserved).
    Work admitted with pricing at reservation time; usage settles at real provider
    token counts, which can exceed the estimate. Future requests then fail closed.
    """
    if not 1<=ttl_seconds<=900 or min(input_estimate_tokens,output_max_tokens)<0:
        raise QuotaDenied('Invalid reservation lifetime or token estimate')
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        org,workspace=_identity(cx,pid)
        limits=_limits(cx,org,workspace,pid)
        if not limits:
            cx.execute('COMMIT')
            return None
        cx.execute("UPDATE cost_reservations SET status='expired',finished_at=? WHERE status='reserved' AND expires_at<=?",(store.now(),store.now()))
        # A provider timeout, malformed response or server error can still be
        # billable.  Never silently discard unknown liabilities under a cap.
        for scope, _cap in limits:
            cond,args={
                'organization':('p.organization_id=?',(org,)),
                'workspace':('p.organization_id=? AND p.workspace_id=?',(org,workspace)),
                'project':('p.id=? AND p.organization_id=?',(pid,org)),
            }[scope]
            ambiguous=cx.execute('SELECT COUNT(*) n FROM provider_attempts a JOIN projects p ON p.id=a.project_id WHERE '+cond+
                " AND a.status='billing_unknown'",args).fetchone()['n']
            if ambiguous:
                raise QuotaDenied(f'Provider billing unresolved in {scope}; operator reconciliation required')
        # Only prior unknown costs in a *limited* scope are relevant.
        for scope, _cap in limits:
            cond,args={
                'organization':('p.organization_id=?',(org,)),
                'workspace':('p.organization_id=? AND p.workspace_id=?',(org,workspace)),
                'project':('p.id=? AND p.organization_id=?',(pid,org)),
            }[scope]
            unknown=cx.execute('SELECT COUNT(*) n FROM usage u JOIN projects p ON p.id=u.project_id WHERE '+cond+
                ' AND u.estimated_usd IS NULL',args).fetchone()['n']
            if unknown:raise QuotaDenied(f'Unpriced historical usage in {scope}: review before more AI calls')
        price=cx.execute('''SELECT input_usd_per_million,output_usd_per_million
            FROM organization_model_pricing WHERE organization_id=? AND model=?''',(org,model)).fetchone()
        if not price:
            raise QuotaDenied('No model rate configured for current organization')
        estimate=round((input_estimate_tokens*price['input_usd_per_million']+
                        output_max_tokens*price['output_usd_per_million'])/1_000_000,8)
        if estimate<=0:
            raise QuotaDenied('Zero-price reservation is not supported under a hard spend limit')
        for scope,cap in limits:
            if _total(cx,scope,org,workspace,pid)+estimate > cap+1e-9:
                raise QuotaDenied(f'{scope.capitalize()} budget cannot reserve this AI request')
        rid=secrets.token_hex(24)
        start=datetime.now(timezone.utc)
        cx.execute('''INSERT INTO cost_reservations(id,organization_id,workspace_id,project_id,model,
            input_rate_snapshot,output_rate_snapshot,estimated_usd,status,created_at,expires_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            (rid,org,workspace,pid,model,price['input_usd_per_million'],price['output_usd_per_million'],
             estimate,'reserved',start.isoformat(timespec='seconds'),
             (start+timedelta(seconds=ttl_seconds)).isoformat(timespec='seconds')))
        cx.execute('COMMIT')
        return rid


def finish(rid: str | None, status: str) -> None:
    if not rid:return
    if status not in ('released','settled'):
        raise QuotaDenied('Invalid reservation state')
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cx.execute("UPDATE cost_reservations SET status=?,finished_at=? WHERE id=? AND status='reserved'",(status,store.now(),rid))
        cx.execute('COMMIT')


def hold_uncertain(rid: str | None) -> None:
    """Keep an estimated liability reserved indefinitely pending reconciliation.

    A failed call may still be billed by the provider. This never claims the
    estimate is actual spend. The separate billing_unknown attempt blocks new
    admissions under a hard scope limit until independently reviewed.
    """
    if rid is None:
        return
    with store.connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        changed=cx.execute('''UPDATE cost_reservations SET expires_at=?,finished_at=NULL
            WHERE id=? AND status='reserved' ''',('9999-12-31T23:59:59+00:00',rid)).rowcount
        if changed!=1:
            raise QuotaDenied('Uncertain provider charge has no live reservation')
        cx.execute('COMMIT')


def reservation_is_settled(rid: str | None) -> bool:
    if rid is None:
        return False
    with store.connect() as cx:
        r=cx.execute('SELECT status FROM cost_reservations WHERE id=?',(rid,)).fetchone()
        return bool(r and r['status']=='settled')


def reservation_rates(cx, rid:str, pid:str, model:str):
    row=cx.execute('''SELECT input_rate_snapshot,output_rate_snapshot FROM cost_reservations
        WHERE id=? AND project_id=? AND model=? AND status='reserved' AND expires_at>?''',
        (rid,pid,model,store.now())).fetchone()
    if not row:raise QuotaDenied('AI reservation does not match project, model or live attempt')
    return row


def settle_in_transaction(cx, rid: str | None, pid: str) -> None:
    if not rid:return
    result=cx.execute('''UPDATE cost_reservations SET status='settled',finished_at=?
        WHERE id=? AND project_id=? AND status='reserved' AND expires_at>?''',(store.now(),rid,pid,store.now()))
    if result.rowcount != 1:
        raise QuotaDenied('AI cost reservation expired, repeated or belongs to another project')
