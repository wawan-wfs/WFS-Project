"""Durable single-node SQLite storage. All claims are atomic under BEGIN IMMEDIATE."""
from __future__ import annotations
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from . import config
from .config import DATA, PROJECTS, DB


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    PROJECTS.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(str(DB), timeout=30, isolation_level=None)
    cx.row_factory = sqlite3.Row
    cx.execute('PRAGMA busy_timeout=30000')
    cx.execute('PRAGMA foreign_keys=ON')
    try:
        yield cx
    finally:
        cx.close()


def init_db():
    with connect() as cx:
        cx.execute('PRAGMA journal_mode=WAL')
        cx.executescript('''
          CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, prompt TEXT NOT NULL,
            mode TEXT NOT NULL, stack TEXT NOT NULL, status TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT 'intake', error TEXT, worker_id TEXT,
            heartbeat_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
            idempotency_key TEXT UNIQUE,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            agent TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id,id);
          CREATE INDEX IF NOT EXISTS idx_projects_queue ON projects(status,created_at);
          CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            agent TEXT NOT NULL, division TEXT NOT NULL, status TEXT NOT NULL,
            task TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS artifacts (
            project_id TEXT NOT NULL, name TEXT NOT NULL, bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL, PRIMARY KEY(project_id,name),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS sessions (
            id_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS preview_authority_nonces (
            nonce TEXT PRIMARY KEY, used_at INTEGER NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_preview_authority_nonce_age
            ON preview_authority_nonces(used_at);
          CREATE TABLE IF NOT EXISTS auth_failures (
            ip TEXT NOT NULL, at_epoch INTEGER NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_auth_failures_ip_time ON auth_failures(ip,at_epoch);
          CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            agent TEXT NOT NULL, model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS worker_instances (
            worker_id TEXT PRIMARY KEY, first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL, current_project TEXT
          );
          CREATE TABLE IF NOT EXISTS provider_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            role TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, finished_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_provider_attempts_pid ON provider_attempts(project_id);
          CREATE TABLE IF NOT EXISTS planned_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            attempt INTEGER NOT NULL, task_key TEXT NOT NULL,
            role TEXT NOT NULL, division TEXT NOT NULL, description TEXT NOT NULL,
            files_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
            UNIQUE(project_id,attempt,task_key),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_planned_tasks_project ON planned_tasks(project_id,attempt,id);
          CREATE TABLE IF NOT EXISTS agent_handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            attempt INTEGER NOT NULL, source TEXT NOT NULL, destination TEXT NOT NULL,
            summary TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_agent_handoffs_project ON agent_handoffs(project_id,id);
          CREATE TABLE IF NOT EXISTS operator_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            category TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_operator_notes_project ON operator_notes(project_id,id);
        ''')
        # Serialize migrations across API and worker starting concurrently on a fresh DB.
        cx.execute('BEGIN IMMEDIATE')
        # Idempotent migrations for users upgrading with an existing SQLite database.
        columns={r['name'] for r in cx.execute('PRAGMA table_info(projects)')}
        if 'parent_id' not in columns:
            cx.execute('ALTER TABLE projects ADD COLUMN parent_id TEXT')
        if 'archived_at' not in columns:
            cx.execute('ALTER TABLE projects ADD COLUMN archived_at TEXT')
        if 'notes' not in columns:
            cx.execute("ALTER TABLE projects ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        if 'priority' not in columns:
            cx.execute('ALTER TABLE projects ADD COLUMN priority INTEGER NOT NULL DEFAULT 1')
        if 'queued_at' not in columns:
            cx.execute('ALTER TABLE projects ADD COLUMN queued_at TEXT')
        if 'recovery_count' not in columns:
            cx.execute('ALTER TABLE projects ADD COLUMN recovery_count INTEGER NOT NULL DEFAULT 0')
        if 'task_review_mode' not in columns:
            cx.execute("ALTER TABLE projects ADD COLUMN task_review_mode TEXT NOT NULL DEFAULT 'auto'")
        if 'claim_id' not in {r['name'] for r in cx.execute('PRAGMA table_info(agent_runs)')}:
            cx.execute('ALTER TABLE agent_runs ADD COLUMN claim_id TEXT')
            # Pre-v4.1 rows do not prove which claim created them.
            cx.execute("UPDATE agent_runs SET status='interrupted',finished_at=? WHERE status='working'",(now(),))
        cx.execute('UPDATE projects SET queued_at=created_at WHERE queued_at IS NULL')
        cx.execute('CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_id)')
        cx.execute('CREATE INDEX IF NOT EXISTS idx_queue_priority ON projects(status,priority DESC,queued_at,id)')
        cx.execute('COMMIT')
        cx.executescript('''
          CREATE TABLE IF NOT EXISTS task_reviews (
            project_id TEXT NOT NULL, attempt INTEGER NOT NULL, task_key TEXT NOT NULL,
            decision TEXT NOT NULL DEFAULT 'pending', feedback TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, attempt, task_key),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS operator_jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            kind TEXT NOT NULL, options_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT, result_json TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_operator_jobs_state ON operator_jobs(status, created_at);
          CREATE TABLE IF NOT EXISTS operator_job_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL, stage TEXT NOT NULL, summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES operator_jobs(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_operator_job_steps_job ON operator_job_steps(job_id,id);
        ''')
        cx.execute('BEGIN IMMEDIATE')
        operator_columns={r['name'] for r in cx.execute('PRAGMA table_info(operator_jobs)')}
        if 'retry_of' not in operator_columns:
            cx.execute('ALTER TABLE operator_jobs ADD COLUMN retry_of TEXT')
        cx.execute('COMMIT')
        cx.executescript("""
          CREATE TABLE IF NOT EXISTS project_checkpoints (
            project_id TEXT PRIMARY KEY, attempt INTEGER NOT NULL,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS model_pricing (
            model TEXT PRIMARY KEY, input_usd_per_million REAL NOT NULL,
            output_usd_per_million REAL NOT NULL, updated_at TEXT NOT NULL
          );
        """)
        cx.execute('BEGIN IMMEDIATE')
        usage_columns={r['name'] for r in cx.execute('PRAGMA table_info(usage)')}
        if 'estimated_usd' not in usage_columns:
            cx.execute('ALTER TABLE usage ADD COLUMN estimated_usd REAL')
        cx.execute('COMMIT')
        cx.executescript('''
          CREATE TABLE IF NOT EXISTS project_budgets (
            project_id TEXT PRIMARY KEY, limit_usd REAL NOT NULL,
            alert_pct INTEGER NOT NULL DEFAULT 80, updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS budget_alerts (
            project_id TEXT NOT NULL, level TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(project_id,level),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
        ''')
        cx.executescript("""
          CREATE TABLE IF NOT EXISTS task_results (
            project_id TEXT NOT NULL, attempt INTEGER NOT NULL, task_key TEXT NOT NULL,
            output_json TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(project_id,attempt,task_key),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
        """)
        # v2.0 user directory. Built-in owner continues to authenticate with .env
        # so existing password reset tooling remains valid.
        cx.executescript("""
          CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL
              CHECK(role IN ('owner','manager','developer','viewer')),
            disabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS access_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL,
            action TEXT NOT NULL, subject_id TEXT NOT NULL,
            created_at TEXT NOT NULL
          );
        """)
        cx.execute('BEGIN IMMEDIATE')
        session_columns={r['name'] for r in cx.execute('PRAGMA table_info(sessions)')}
        if 'user_id' not in session_columns:
            cx.execute('ALTER TABLE sessions ADD COLUMN user_id TEXT')
        cx.execute("INSERT OR IGNORE INTO users(id,username,password_hash,role,created_at) VALUES('owner','admin','','owner',?)",(now(),))
        cx.execute("UPDATE sessions SET user_id='owner' WHERE user_id IS NULL")
        cx.execute('COMMIT')
        # v2.6 session/device inventory: no raw session token or IP stored.
        cx.execute('BEGIN IMMEDIATE')
        if 'device_label' not in {r['name'] for r in cx.execute('PRAGMA table_info(sessions)')}:
            cx.execute("ALTER TABLE sessions ADD COLUMN device_label TEXT NOT NULL DEFAULT 'Previous browser'")
        cx.execute('COMMIT')
        # v2.5: encrypted TOTP enrollment and single-use account recovery tokens.
        cx.execute('BEGIN IMMEDIATE')
        mfa_cols={r['name'] for r in cx.execute('PRAGMA table_info(users)')}
        if 'mfa_secret' not in mfa_cols:
            cx.execute('ALTER TABLE users ADD COLUMN mfa_secret TEXT')
        if 'mfa_last_step' not in mfa_cols:
            cx.execute('ALTER TABLE users ADD COLUMN mfa_last_step INTEGER NOT NULL DEFAULT -1')
        cx.execute('COMMIT')
        cx.executescript(''' 
          CREATE TABLE IF NOT EXISTS mfa_pending (
            user_id TEXT PRIMARY KEY, session_hash TEXT NOT NULL,
            secret TEXT NOT NULL, expires_epoch INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS mfa_recovery (
            user_id TEXT NOT NULL, code_hash TEXT NOT NULL,
            PRIMARY KEY(user_id,code_hash),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
          );
          CREATE TABLE IF NOT EXISTS mfa_failures (
            user_id TEXT NOT NULL, at_epoch INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_mfa_failures ON mfa_failures(user_id,at_epoch);
        ''')
        cx.execute('BEGIN IMMEDIATE')
        col_names={row['name'] for row in cx.execute('PRAGMA table_info(usage)')}
        if 'provider_response_id' not in col_names:
            cx.execute('ALTER TABLE usage ADD COLUMN provider_response_id TEXT')
        cx.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_provider_response ON usage(provider_response_id) WHERE provider_response_id IS NOT NULL')
        if 'input_rate_snapshot' not in col_names:
            cx.execute('ALTER TABLE usage ADD COLUMN input_rate_snapshot REAL')
        if 'output_rate_snapshot' not in col_names:
            cx.execute('ALTER TABLE usage ADD COLUMN output_rate_snapshot REAL')
        cx.execute('COMMIT')
        # v2.1: existing projects keep workspace sharing for backwards compatibility.
        # New private missions are visible only to their creator and invited members.
        cx.execute('BEGIN IMMEDIATE')
        project_columns={r['name'] for r in cx.execute('PRAGMA table_info(projects)')}
        if 'visibility' not in project_columns:
            cx.execute("ALTER TABLE projects ADD COLUMN visibility TEXT NOT NULL DEFAULT 'workspace'")
        if 'created_by' not in project_columns:
            cx.execute("ALTER TABLE projects ADD COLUMN created_by TEXT NOT NULL DEFAULT 'owner'")
        cx.execute('COMMIT')
        cx.executescript('''
          CREATE TABLE IF NOT EXISTS project_members (
            project_id TEXT NOT NULL, user_id TEXT NOT NULL,
            permission TEXT NOT NULL CHECK(permission IN ('view','edit')),
            granted_by TEXT NOT NULL, granted_at TEXT NOT NULL,
            PRIMARY KEY(project_id,user_id),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
          );
          CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id,project_id);
          CREATE TABLE IF NOT EXISTS project_access_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            actor_id TEXT NOT NULL, target_id TEXT,
            action TEXT NOT NULL, at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
          );
        ''')
        # v2.6: additive, transactional organization boundary. Existing databases
        # remain in the 'default' tenant. Project and member scope never relies
        # on a client-provided organization identifier.
        cx.execute('BEGIN IMMEDIATE')
        cx.execute('''CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY, display_name TEXT NOT NULL, created_at TEXT NOT NULL)''')
        cx.execute("INSERT OR IGNORE INTO organizations(id,display_name,created_at) VALUES('default','WFS Local Workspace',?)",(now(),))
        if 'mfa_required' not in {r['name'] for r in cx.execute('PRAGMA table_info(organizations)')}:
            cx.execute('ALTER TABLE organizations ADD COLUMN mfa_required INTEGER NOT NULL DEFAULT 0')
        if 'organization_id' not in {r['name'] for r in cx.execute('PRAGMA table_info(users)')}:
            cx.execute("ALTER TABLE users ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'default'")
        if 'organization_id' not in {r['name'] for r in cx.execute('PRAGMA table_info(projects)')}:
            cx.execute("ALTER TABLE projects ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'default'")
        cx.execute('CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(organization_id,created_at)')
        cx.execute('CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id,username)')
        cx.execute('''CREATE TABLE IF NOT EXISTS organization_model_pricing (
            organization_id TEXT NOT NULL, model TEXT NOT NULL,
            input_usd_per_million REAL NOT NULL, output_usd_per_million REAL NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(organization_id,model))''')
        cx.execute('''INSERT OR IGNORE INTO organization_model_pricing
            (organization_id,model,input_usd_per_million,output_usd_per_million,updated_at)
            SELECT 'default',model,input_usd_per_million,output_usd_per_million,updated_at FROM model_pricing''')
        # Repair any pre-migration cross-organization grants deterministically.
        cx.execute('''DELETE FROM project_members WHERE EXISTS (
            SELECT 1 FROM projects p JOIN users u ON u.id=project_members.user_id
            WHERE p.id=project_members.project_id AND p.organization_id!=u.organization_id)''')
        cx.execute('COMMIT')
        # v2.8: install transactional workspace/quota tables after tenant migration.
        from . import quota
        quota.install(cx)
        from . import preview_gateway
        preview_gateway.install(cx)


def can_access_project(pid, user_id, write=False):
    '''Deny private resources without an active grant. Global role limits are separate.'''
    with connect() as cx:
        account=cx.execute('SELECT role,disabled,organization_id FROM users WHERE id=?',(user_id,)).fetchone()
        if not account or account['disabled']:return False
        row=cx.execute('SELECT visibility,created_by,organization_id FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or account['organization_id']!=row['organization_id']:return False
        if account['role']=='owner' or row['created_by']==user_id:return True
        if row['visibility']=='workspace':return True
        member=cx.execute('SELECT permission FROM project_members WHERE project_id=? AND user_id=?',(pid,user_id)).fetchone()
        return bool(member and (not write or member['permission']=='edit'))


def visible_project_ids(user_id):
    """Visible IDs are ALWAYS tenant-scoped, including the built-in owner."""
    with connect() as cx:
        user=cx.execute('SELECT role,organization_id FROM users WHERE id=? AND disabled=0',(user_id,)).fetchone()
        if not user:return set()
        cond,params=_project_scope_condition(user_id)
        rows=cx.execute('SELECT p.id FROM projects p WHERE 1=1'+cond,params)
        return {r['id'] for r in rows}


def project_access(pid):
    with connect() as cx:
        p=cx.execute('SELECT visibility,created_by FROM projects WHERE id=?',(pid,)).fetchone()
        if not p:return None
        rows=cx.execute('''SELECT m.user_id,u.username,m.permission,m.granted_at
            FROM project_members m JOIN users u ON u.id=m.user_id
            WHERE m.project_id=? ORDER BY u.username''',(pid,))
        return {'visibility':p['visibility'],'created_by':p['created_by'],
                'members':[dict(r) for r in rows]}


def project_access_audit(pid, limit=50):
    with connect() as cx:
        return [dict(r) for r in cx.execute('''SELECT actor_id,target_id,action,at
            FROM project_access_audit WHERE project_id=? ORDER BY id DESC LIMIT ?''',(pid,limit))]


def manage_project_access(pid, actor_id, visibility=None, user_id=None, permission=None, remove=False):
    '''Atomic ACL edit and immutable audit log. A creator or Owner may manage grants.'''
    if visibility is not None and visibility not in ('private','workspace'):raise ValueError('Invalid visibility')
    if permission is not None and permission not in ('view','edit'):raise ValueError('Invalid permission')
    if visibility is None and user_id is None:raise ValueError('No access change')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        actor=cx.execute('SELECT role,disabled,organization_id FROM users WHERE id=?',(actor_id,)).fetchone()
        project=cx.execute('SELECT visibility,created_by,organization_id FROM projects WHERE id=?',(pid,)).fetchone()
        if (not actor or actor['disabled'] or not project or
            actor['organization_id']!=project['organization_id'] or
            (actor['role']!='owner' and project['created_by']!=actor_id)):
            cx.execute('ROLLBACK');return False
        if visibility is not None:
            cx.execute('UPDATE projects SET visibility=?,updated_at=? WHERE id=?',(visibility,now(),pid))
            if visibility=='private':
                cx.execute("""WITH RECURSIVE descendants(id) AS (
                    SELECT id FROM projects WHERE parent_id=?
                    UNION ALL SELECT p.id FROM projects p JOIN descendants d ON p.parent_id=d.id
                ) UPDATE projects SET visibility='private',updated_at=? WHERE id IN (SELECT id FROM descendants)""",(pid,now()))
            action='visibility_'+visibility
            target_id=None
        else:
            user=cx.execute('SELECT id,role,disabled,organization_id FROM users WHERE id=?',(user_id,)).fetchone()
            if (user is None or user['disabled'] or user_id==project['created_by'] or
                user['role']=='owner' or user['organization_id']!=project['organization_id']):
                cx.execute('ROLLBACK');raise ValueError('Invalid member')
            if remove:
                cx.execute('DELETE FROM project_members WHERE project_id=? AND user_id=?',(pid,user_id))
                action='member_removed'
            else:
                cx.execute('''INSERT INTO project_members(project_id,user_id,permission,granted_by,granted_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET
                   permission=excluded.permission,granted_by=excluded.granted_by,granted_at=excluded.granted_at''',
                   (pid,user_id,permission,actor_id,now()))
                action='member_'+permission
            target_id=user_id
        cx.execute('INSERT INTO project_access_audit(project_id,actor_id,target_id,action,at) VALUES(?,?,?,?,?)',
                   (pid,actor_id,target_id,action,now()))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Team & Access','access_changed',action+' by authorized operator',now()))
        cx.execute('COMMIT')
        return True


def public_user_directory(scope_user):
    with connect() as cx:
        return [dict(x) for x in cx.execute('''SELECT id,username,role FROM users WHERE disabled=0
            AND organization_id=(SELECT organization_id FROM users WHERE id=? AND disabled=0)
            ORDER BY username''',(scope_user,))]


def scope_dashboard_stats(ids):
    if ids is None:return dashboard_stats()
    with connect() as cx:
        # Never reveal another member's private project totals in aggregate metrics.
        statuses={}
        for r in cx.execute('SELECT id,status FROM projects WHERE archived_at IS NULL'):
            if r['id'] in ids:statuses[r['status']]=statuses.get(r['status'],0)+1
        tokens={'calls':0,'input_tokens':0,'output_tokens':0}
        for r in cx.execute('SELECT project_id,input_tokens,output_tokens FROM usage'):
            if r['project_id'] in ids:
                tokens['calls']+=1;tokens['input_tokens']+=r['input_tokens'];tokens['output_tokens']+=r['output_tokens']
        archived=sum(1 for r in cx.execute('SELECT id FROM projects WHERE archived_at IS NOT NULL') if r['id'] in ids)
    return {'statuses':statuses,'usage':tokens,'archived':archived}


def scope_office_overview(ids):
    if ids is None:return office_overview()
    with connect() as cx:
        rows=cx.execute('''SELECT a.project_id,a.division,a.status,p.status project_status,a.created_at,a.claim_id,p.worker_id
          FROM agent_runs a JOIN projects p ON p.id=a.project_id WHERE p.archived_at IS NULL''')
        out={}
        for r in rows:
            if r['project_id'] not in ids:continue
            agg=out.setdefault(r['division'],{'active':0,'finished':0,'last_activity':None})
            if r['status']=='working' and r['project_status']=='running' and r['claim_id'] and r['claim_id']==r['worker_id']:agg['active']+=1
            if r['status']=='done':agg['finished']+=1
            agg['last_activity']=max(agg['last_activity'] or '',r['created_at'])
    return out


def scope_concurrency(snapshot,ids):
    if ids is None:return snapshot
    snapshot['active']=[x for x in snapshot['active'] if x['id'] in ids]
    snapshot['active_count']=len(snapshot['active'])
    snapshot['workers']=[x for x in snapshot['workers'] if x['current_project'] in ids]
    with connect() as cx:
        states=[r['status'] for r in cx.execute('SELECT id,status FROM projects') if r['id'] in ids]
    snapshot['queued_count']=states.count('queued')
    snapshot['awaiting_approval_count']=states.count('awaiting_approval')
    snapshot['free_slots']=max(0,snapshot['max_active_projects']-snapshot['active_count'])
    return snapshot


def create_project(title, prompt, mode, stack, idempotency_key=None, parent_id=None, task_review_mode='auto',
                   created_by='owner', visibility='workspace'):

    if task_review_mode not in ('auto','manual'):raise ValueError('Invalid task review mode')
    if visibility not in ('private','workspace'):raise ValueError('Invalid project visibility')
    pid = uuid.uuid4().hex[:20]
    t = now()
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        creator=cx.execute('SELECT organization_id FROM users WHERE id=? AND disabled=0',(created_by,)).fetchone()
        if not creator:
            cx.execute('ROLLBACK');raise ValueError('Invalid project creator')
        organization_id=creator['organization_id']
        if idempotency_key:
            existing = cx.execute('SELECT id,status,mode,title,prompt,stack,parent_id,task_review_mode,created_by,visibility,organization_id FROM projects WHERE idempotency_key=?', (idempotency_key,)).fetchone()
            if existing:
                if (existing['title'],existing['prompt'],existing['mode'],existing['stack'],existing['parent_id'],existing['task_review_mode'])!=(title,prompt,mode,stack,parent_id,task_review_mode):
                    cx.execute('ROLLBACK')
                    raise ValueError('Idempotency-Key pernah dipakai untuk brief yang berbeda')
                # A shared Idempotency-Key must not return a private mission from another user.
                if existing['created_by']!=created_by or existing['organization_id']!=organization_id or existing['visibility']!=visibility or not can_access_project(existing['id'],created_by):
                    cx.execute('ROLLBACK');raise ValueError('Idempotency-Key belongs to another private mission')
                cx.execute('COMMIT')
                return {k:existing[k] for k in ('id','status','mode')}
        if parent_id:
            parent=cx.execute('SELECT status,stack,mode,visibility,created_by,organization_id FROM projects WHERE id=?',(parent_id,)).fetchone()
            if not parent or parent['organization_id']!=organization_id or parent['status']!='completed' or parent['stack']!=stack or mode!='ai':
                cx.execute('ROLLBACK')
                raise ValueError('Revisi memerlukan versi induk berstatus completed, stack sama, dan mode AI')
            # Revisions inherit visibility and creator; don't downgrade privacy.
            visibility=parent['visibility'];created_by=parent['created_by']
        cx.execute('''INSERT INTO projects (id,title,prompt,mode,stack,status,phase,idempotency_key,parent_id,created_at,updated_at,queued_at,task_review_mode,created_by,visibility,organization_id)
                       VALUES(?,?,?,?,?,'queued','intake',?,?,?,?,?,?,?,?,?)''', (pid,title,prompt,mode,stack,idempotency_key,parent_id,t,t,t,task_review_mode,created_by,visibility,organization_id))
        if parent_id:
            cx.execute('''INSERT INTO project_members(project_id,user_id,permission,granted_by,granted_at)
                          SELECT ?,user_id,permission,granted_by,? FROM project_members WHERE project_id=?''',(pid,t,parent_id))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Master Orchestrator','queued','Misi diterima. Menunggu worker.',t))
        cx.execute('COMMIT')
    return {'id':pid,'status':'queued','mode':mode}


def get_project(pid):
    with connect() as cx:
        result = cx.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        return dict(result) if result else None


def list_projects(include_archived=False,scope_user=None):
    with connect() as cx:
        conditions=[];args=[]
        if not include_archived:conditions.append('p.archived_at IS NULL')
        cond,params=_project_scope_condition(scope_user)
        if cond:
            conditions.append(cond.removeprefix(' AND '));args.extend(params)
        sql='SELECT p.* FROM projects p'+(' WHERE '+' AND '.join(conditions) if conditions else '')+' ORDER BY p.created_at DESC LIMIT 500'
        return [dict(r) for r in cx.execute(sql,args)]


def dashboard_stats():
    with connect() as cx:
        rows=cx.execute('SELECT status,COUNT(*) AS n FROM projects WHERE archived_at IS NULL GROUP BY status').fetchall()
        usage=cx.execute('SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) input_tokens, COALESCE(SUM(output_tokens),0) output_tokens FROM usage').fetchone()
        return {'statuses':{r['status']:r['n'] for r in rows},'usage':dict(usage),
                'archived':cx.execute('SELECT COUNT(*) FROM projects WHERE archived_at IS NOT NULL').fetchone()[0]}


def set_archived(pid, archive=True):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or row['status'] in ('queued','paused','running','awaiting_approval','cancel_requested'):
            cx.execute('ROLLBACK')
            return False
        cx.execute('UPDATE projects SET archived_at=?,updated_at=? WHERE id=?',
                   (now() if archive else None,now(),pid))
        cx.execute('COMMIT')
        return True


def remove_project(pid):
    """Remove DB record only after operator verifies project is terminal and childless."""
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
        child=cx.execute('SELECT 1 FROM projects WHERE parent_id=? LIMIT 1',(pid,)).fetchone()
        active_job=cx.execute("SELECT 1 FROM operator_jobs WHERE project_id=? AND status IN ('queued','running') LIMIT 1",(pid,)).fetchone()
        if not row or row['status'] in ('queued','paused','running','awaiting_approval','cancel_requested') or child or active_job:
            cx.execute('ROLLBACK')
            return False
        cx.execute('DELETE FROM projects WHERE id=?',(pid,))
        cx.execute('COMMIT')
        return True



def list_events(pid):
    with connect() as cx:
        return [dict(r) for r in cx.execute('SELECT * FROM events WHERE project_id=? ORDER BY id LIMIT 1000',(pid,))]


def list_agents(pid):
    with connect() as cx:
        return [dict(r) for r in cx.execute('SELECT id,project_id,agent,division,status,task,created_at,finished_at FROM agent_runs WHERE project_id=? ORDER BY id',(pid,))]


def list_artifacts(pid):
    with connect() as cx:
        return [dict(r) for r in cx.execute('SELECT name,bytes,sha256 FROM artifacts WHERE project_id=? ORDER BY name',(pid,))]


def get_usage(pid):
    with connect() as cx:
        row = cx.execute('SELECT COALESCE(SUM(input_tokens),0) AS input_tokens,COALESCE(SUM(output_tokens),0) AS output_tokens,COUNT(*) AS calls FROM usage WHERE project_id=?',(pid,)).fetchone()
        result=dict(row)
        result['attempts']=cx.execute('SELECT COUNT(*) FROM provider_attempts WHERE project_id=?',(pid,)).fetchone()[0]
        return result


def model_attempt_started(pid,role,model):
    with connect() as cx:
        result=cx.execute('INSERT INTO provider_attempts(project_id,role,model,status,started_at) VALUES(?,?,?,?,?)',
                          (pid,role,model,'started',now()))
        return result.lastrowid


def model_attempt_finished(attempt_id,status):
    with connect() as cx:
        cx.execute('UPDATE provider_attempts SET status=?,finished_at=? WHERE id=?',
                   (status,now(),attempt_id))


def _live_lease(cx, pid, worker_id, *, allow_cancel=False):
    if not isinstance(worker_id, str) or not worker_id:
        return False
    state=('running','cancel_requested') if allow_cancel else ('running',)
    row=cx.execute('SELECT 1 FROM projects WHERE id=? AND worker_id=? AND status IN ('+
                   ','.join('?' for _ in state)+')',(pid,worker_id,*state)).fetchone()
    return row is not None


def _insert_event(cx,pid,agent,state,message):
    cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
               (pid,agent,state,str(message)[:1000],now()))


def operator_event(pid,agent,state,message):
    """Trusted control-plane audit entry, not a worker operation."""
    with connect() as cx:
        _insert_event(cx,pid,agent,state,message)


def event(pid,agent,state,message,*,worker_id):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not _live_lease(cx,pid,worker_id,allow_cancel=state in ('cancelled','error','failed','warning','blocked')):
            cx.execute('ROLLBACK');return False
        _insert_event(cx,pid,agent,state,message)
        cx.execute('COMMIT')
        return True


def phase(pid,p,*,worker_id):
    with connect() as cx:
        return cx.execute('UPDATE projects SET phase=?,updated_at=? WHERE id=? AND status=? AND worker_id=?',
                          (p,now(),pid,'running',worker_id)).rowcount==1


def agent_start(pid,name,division,task,*,worker_id):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK')
            raise ValueError('Worker lease is no longer valid for agent start')
        cur=cx.execute('INSERT INTO agent_runs(project_id,agent,division,status,task,created_at,claim_id) VALUES(?,?,?,?,?,?,?)',
                       (pid,name,division,'working',str(task)[:400],now(),worker_id))
        cx.execute('COMMIT')
        return cur.lastrowid


def agent_finish(aid,state,*,worker_id):
    if state not in ('done','failed','cancelled'):
        raise ValueError('Invalid agent finish state')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT project_id FROM agent_runs WHERE id=? AND claim_id=?',(aid,worker_id)).fetchone()
        if not row or not _live_lease(cx,row['project_id'],worker_id,allow_cancel=state=='cancelled'):
            cx.execute('ROLLBACK');return False
        change=cx.execute("UPDATE agent_runs SET status=?,finished_at=? WHERE id=? AND status='working'",(state,now(),aid))
        cx.execute('COMMIT')
        return change.rowcount==1


def _interrupt_agent_runs(cx,pid):
    cx.execute("UPDATE agent_runs SET status='interrupted',finished_at=? WHERE project_id=? AND status='working'",(now(),pid))


def usage(pid, agent, model, input_tokens, output_tokens, reservation_id=None, provider_response_id=None):
    """Record provider usage with the CURRENT operator-defined rate snapshot.

    Missing prices remain NULL, rather than incorrectly representing unknown costs as $0.
    Historical cost rows are not recalculated when pricing changes.
    """
    import re
    if provider_response_id is not None and (not isinstance(provider_response_id,str) or
            not re.fullmatch(r'[A-Za-z0-9._:-]{8,160}',provider_response_id)):
        raise ValueError('Provider response identifier invalid')
    incoming=max(0,int(input_tokens));outgoing=max(0,int(output_tokens))
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if reservation_id:
            from . import quota
            reserved_rate=quota.reservation_rates(cx,reservation_id,pid,model)
            rate={'input_usd_per_million':reserved_rate['input_rate_snapshot'],
                  'output_usd_per_million':reserved_rate['output_rate_snapshot']}
        else:
            rate=cx.execute('''SELECT input_usd_per_million,output_usd_per_million
                FROM organization_model_pricing WHERE organization_id=(
                  SELECT organization_id FROM projects WHERE id=?) AND model=?''',(pid,model)).fetchone()
        estimate=(round((incoming*rate['input_usd_per_million']+outgoing*rate['output_usd_per_million'])/1_000_000,8) if rate else None)
        cx.execute('INSERT INTO usage(project_id,agent,model,input_tokens,output_tokens,created_at,estimated_usd,input_rate_snapshot,output_rate_snapshot,provider_response_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (pid,agent,model,incoming,outgoing,now(),estimate,
                    rate['input_usd_per_million'] if rate else None,
                    rate['output_usd_per_million'] if rate else None,provider_response_id))
        if reservation_id is not None:
            from . import quota
            quota.settle_in_transaction(cx,reservation_id,pid)
        budget=cx.execute('SELECT limit_usd,alert_pct FROM project_budgets WHERE project_id=?',(pid,)).fetchone()
        if budget and budget['limit_usd']>0:
            amount=cx.execute('SELECT COALESCE(SUM(estimated_usd),0) FROM usage WHERE project_id=?',(pid,)).fetchone()[0]
            for level,threshold in (('warning',budget['alert_pct']),('exceeded',100)):
                if amount*100 < budget['limit_usd']*threshold:continue
                marker=cx.execute('INSERT OR IGNORE INTO budget_alerts(project_id,level,created_at) VALUES(?,?,?)',(pid,level,now()))
                if marker.rowcount:
                    cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                        (pid,'AI Cost Center','budget_'+level,
                         'Estimated budget '+level+' ('+str(round(amount,6))+' USD / '+str(budget['limit_usd'])+' USD). Not official provider billing.',now()))
        cx.execute('COMMIT')
    return estimate


def set_model_price(model, input_rate, output_rate, scope_user='owner'):
    import re
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,100}',model) or '..' in model or model.startswith(('.', '/', '-')):
        raise ValueError('Invalid model name')
    for rate in (input_rate,output_rate):
        if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not 0<=rate<=10000:
            raise ValueError('Rate must be 0..10000 USD per million tokens')
    with connect() as cx:
        org=cx.execute('SELECT organization_id FROM users WHERE id=? AND disabled=0',(scope_user,)).fetchone()
        if not org:raise ValueError('Unknown pricing organization')
        cx.execute('''INSERT INTO organization_model_pricing(organization_id,model,input_usd_per_million,output_usd_per_million,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(organization_id,model) DO UPDATE SET
            input_usd_per_million=excluded.input_usd_per_million,
            output_usd_per_million=excluded.output_usd_per_million,updated_at=excluded.updated_at''',
            (org['organization_id'],model,float(input_rate),float(output_rate),now()))


def get_model_prices(scope_user='owner'):
    with connect() as cx:
        return [dict(r) for r in cx.execute('''SELECT model,input_usd_per_million,output_usd_per_million,updated_at
            FROM organization_model_pricing WHERE organization_id=(SELECT organization_id FROM users WHERE id=? AND disabled=0)
            ORDER BY model''',(scope_user,))]


def cost_report(project_id=None, period='30d', scope_user=None):
    """Financial estimate only: excludes retries without usage and provider-side billing adjustments."""
    import json
    if period not in ('7d','30d','all'):raise ValueError('Invalid period')
    from datetime import timedelta
    clauses=[];args=[]
    if project_id:
        clauses.append('u.project_id=?');args.append(project_id)
    cond,params=_project_scope_condition(scope_user)
    if cond:
        clauses.append('u.project_id IN (SELECT p.id FROM projects p WHERE 1=1'+cond+')')
        args.extend(params)
    if period!='all':
        cutoff=(datetime.now(timezone.utc)-timedelta(days=int(period[:-1]))).isoformat(timespec='seconds')
        clauses.append('u.created_at>=?');args.append(cutoff)
    where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
    with connect() as cx:
        rows=[dict(r) for r in cx.execute('SELECT u.project_id,u.agent,u.model,u.input_tokens,u.output_tokens,u.estimated_usd,u.created_at FROM usage u'+where+' ORDER BY u.id DESC LIMIT 30001',args)]
        truncated=len(rows)>30000
        if truncated:rows=rows[:30000]
        attempts_query='SELECT status,COUNT(*) n FROM provider_attempts WHERE 1=1'
        attempt_args=[]
        if project_id:attempts_query+=' AND project_id=?';attempt_args.append(project_id)
        if cond:
            attempts_query+=' AND project_id IN (SELECT p.id FROM projects p WHERE 1=1'+cond+')'
            attempt_args.extend(params)
        if period!='all':attempts_query+=' AND started_at>=?';attempt_args.append(cutoff)
        attempts_query+=' GROUP BY status'
        attempts={r['status']:r['n'] for r in cx.execute(attempts_query,attempt_args)}
    def group(key):
        result={}
        for r in rows:
            name=r[key]
            g=result.setdefault(name,{'name':name,'calls':0,'input_tokens':0,'output_tokens':0,'priced_calls':0,'unpriced_calls':0,'estimated_usd':0.0})
            g['calls']+=1;g['input_tokens']+=r['input_tokens'];g['output_tokens']+=r['output_tokens']
            if r['estimated_usd'] is None:g['unpriced_calls']+=1
            else:g['priced_calls']+=1;g['estimated_usd']+=r['estimated_usd']
        return sorted(({**g,'estimated_usd':round(g['estimated_usd'],6)} for g in result.values()),key=lambda a:-a['estimated_usd'])
    days={}
    for r in rows:
        day=r['created_at'][:10]
        g=days.setdefault(day,{'day':day,'calls':0,'input_tokens':0,'output_tokens':0,'estimated_usd':0.0,'unpriced_calls':0})
        g['calls']+=1;g['input_tokens']+=r['input_tokens'];g['output_tokens']+=r['output_tokens']
        if r['estimated_usd'] is None:g['unpriced_calls']+=1
        else:g['estimated_usd']+=r['estimated_usd']
    by_day=[{**g,'estimated_usd':round(g['estimated_usd'],6)} for _,g in sorted(days.items())]
    priced=sum(r['estimated_usd'] or 0 for r in rows)
    unpriced=sum(r['estimated_usd'] is None for r in rows)
    return {'period':period,'project_id':project_id,'calls':len(rows),'input_tokens':sum(r['input_tokens'] for r in rows),
            'output_tokens':sum(r['output_tokens'] for r in rows),'estimated_usd':round(priced,6),'unpriced_calls':unpriced,
            'price_coverage_complete':unpriced==0,'truncated':truncated,'model_attempts':attempts,'by_day':by_day,'by_model':group('model'),'by_project':group('project_id'),'by_agent':group('agent'),
            'disclaimer':'Operator-defined pricing estimate; NOT a provider bill. Missing rates are not treated as zero. Cached tokens, taxes, currency conversion and failed-call billing may differ.'}



def set_project_budget(pid,limit_usd,alert_pct=80):
    import math
    if isinstance(limit_usd,bool) or not isinstance(limit_usd,(int,float)) or not math.isfinite(limit_usd) or not 0<=limit_usd<=100000:
        raise ValueError('Budget estimate limit must be between 0 and 100000 USD')
    if type(alert_pct) is not int or not 10<=alert_pct<=99:
        raise ValueError('Alert percentage must be 10 to 99')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not cx.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():
            cx.execute('ROLLBACK');return None
        cx.execute('''INSERT INTO project_budgets(project_id,limit_usd,alert_pct,updated_at) VALUES(?,?,?,?)
            ON CONFLICT(project_id) DO UPDATE SET limit_usd=excluded.limit_usd,alert_pct=excluded.alert_pct,updated_at=excluded.updated_at''',
            (pid,float(limit_usd),alert_pct,now()))
        cx.execute('DELETE FROM budget_alerts WHERE project_id=?',(pid,))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                  (pid,'AI Cost Center','budget_configured','Operator updated project estimate limit to '+str(float(limit_usd))+' USD; 0 disables project limit',now()))
        cx.execute('COMMIT')
    return project_budget(pid)


def project_budget(pid):
    with connect() as cx:
        if not cx.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():return None
        budget=cx.execute('SELECT limit_usd,alert_pct,updated_at FROM project_budgets WHERE project_id=?',(pid,)).fetchone()
        summary=cx.execute('''SELECT COALESCE(SUM(estimated_usd),0) spent,COUNT(*) calls,
            SUM(CASE WHEN estimated_usd IS NULL THEN 1 ELSE 0 END) unpriced FROM usage WHERE project_id=?''',(pid,)).fetchone()
        limit=budget['limit_usd'] if budget else 0.0
        alerts=[dict(x) for x in cx.execute("SELECT level,created_at FROM budget_alerts WHERE project_id=? ORDER BY CASE level WHEN 'warning' THEN 0 ELSE 1 END,created_at",(pid,))]
    spent=round(summary['spent'],8)
    return {'project_id':pid,'limit_usd':limit,'alert_pct':budget['alert_pct'] if budget else 80,
            'updated_at':budget['updated_at'] if budget else None,'estimated_usd':spent,
            'calls':summary['calls'],'unpriced_calls':summary['unpriced'] or 0,
            'percent_used':round(spent*100/limit,2) if limit>0 else None,'enabled':limit>0,
            'limit_reached':limit>0 and spent>=limit,'alerts':alerts,
            'disclaimer':'Soft pre-call gate; in-flight and concurrent requests may overshoot. Not official provider billing.'}


def list_project_budgets():
    with connect() as cx:
        ids=[r['project_id'] for r in cx.execute('SELECT project_id FROM project_budgets ORDER BY updated_at DESC LIMIT 500')]
    return [project_budget(pid) for pid in ids]


def usage_export_rows(project_id=None,period='30d',limit=30000,scope_user=None):
    # CSV source; caller protects against spreadsheet formula injection.
    if period not in ('7d','30d','all'):raise ValueError('Invalid period')
    cutoff=None
    if period!='all':cutoff=(datetime.now(timezone.utc)-timedelta(days=int(period[:-1]))).isoformat(timespec='seconds')
    where=[];args=[]
    if project_id:where.append('project_id=?');args.append(project_id)
    cond,params=_project_scope_condition(scope_user)
    if cond:
        where.append('project_id IN (SELECT p.id FROM projects p WHERE 1=1'+cond+')')
        args.extend(params)
    if cutoff:where.append('created_at>=?');args.append(cutoff)
    sql='SELECT id,created_at,project_id,agent,model,input_tokens,output_tokens,estimated_usd,input_rate_snapshot,output_rate_snapshot FROM usage'
    if where:sql+=' WHERE '+' AND '.join(where)
    sql+=' ORDER BY id DESC LIMIT ?'
    with connect() as cx:
        rows=[dict(x) for x in cx.execute(sql,args+[limit+1])]
    return rows[:limit],len(rows)>limit


def claim(worker_id):
    """Atomic lease, respecting a global active-project limit across worker replicas."""
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        active=cx.execute("SELECT COUNT(*) FROM projects WHERE status IN ('running','cancel_requested')").fetchone()[0]
        if active>=config.MAX_ACTIVE_PROJECTS:
            cx.execute('COMMIT');return None
        row=cx.execute("SELECT p.*,cp.attempt checkpoint_attempt FROM projects p LEFT JOIN project_checkpoints cp ON cp.project_id=p.id WHERE p.status='queued' ORDER BY p.priority DESC,p.queued_at,p.id LIMIT 1").fetchone()
        if not row:
            cx.execute('COMMIT');return None
        resume=row['checkpoint_attempt'] is not None and row['checkpoint_attempt']==row['attempts']
        cx.execute("UPDATE projects SET status='running',phase=?,worker_id=?,heartbeat_at=?,attempts=attempts+?,updated_at=? WHERE id=? AND status='queued'",
                   ('architecture' if resume else 'planning',worker_id,now(),0 if resume else 1,now(),row['id']))
        cx.execute('COMMIT')
        return get_project(row['id'])


def heartbeat(pid, worker_id):
    with connect() as cx:
        cx.execute("UPDATE projects SET heartbeat_at=? WHERE id=? AND worker_id=? AND status IN ('running','cancel_requested')",(now(),pid,worker_id))


def finish(pid,status,error=None,*,worker_id):
    if status not in ('completed','review_required','cancelled','failed'):
        raise ValueError('Invalid worker finish state')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not _live_lease(cx,pid,worker_id,allow_cancel=status=='cancelled'):
            cx.execute('ROLLBACK');return False
        cx.execute('UPDATE projects SET status=?,phase=?,error=?,worker_id=NULL,updated_at=? WHERE id=?',
                   (status,'delivered' if status=='completed' else status,str(error)[:1000] if error else None,now(),pid))
        _interrupt_agent_runs(cx,pid)
        if status in ('cancelled','failed'):
            _block_tasks(cx,pid)
        if status in ('completed','review_required','cancelled'):
            cx.execute('DELETE FROM project_checkpoints WHERE project_id=?',(pid,))
        cx.execute('COMMIT')
        return True


def cancel(pid):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
        if not row:
            cx.execute('ROLLBACK')
            return None
        if row['status'] in ('queued','paused','awaiting_approval'):
            state='cancelled'
        elif row['status']=='running':
            state='cancel_requested'
        else:
            state=row['status']
        cx.execute('UPDATE projects SET status=?,updated_at=? WHERE id=?',(state,now(),pid))
        if state=='cancelled':_block_tasks(cx,pid)
        cx.execute('COMMIT')
    return state


def retry(pid):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
        if row is None:
            cx.execute('ROLLBACK')
            return None
        if row['status'] not in ('failed','interrupted','cancelled'):
            cx.execute('ROLLBACK')
            return False
        cx.execute('DELETE FROM project_checkpoints WHERE project_id=?',(pid,))
        cx.execute("UPDATE projects SET status='queued',phase='intake',error=NULL,worker_id=NULL,recovery_count=0,queued_at=?,updated_at=? WHERE id=?",(now(),now(),pid))
        cx.execute('COMMIT')
        return True


def recover_stale(seconds=180):
    cutoff=(datetime.now(timezone.utc)-timedelta(seconds=seconds)).isoformat(timespec='seconds')
    with connect() as cx:
        # Serialize recovery across multiple workers. A stale lease must not be reclaimed twice.
        cx.execute('BEGIN IMMEDIATE')
        rows=cx.execute("SELECT id,attempts,recovery_count FROM projects WHERE status IN ('running','cancel_requested') AND (heartbeat_at IS NULL OR heartbeat_at<?)",(cutoff,)).fetchall()
        for row in rows:
            _interrupt_agent_runs(cx,row['id'])
            project=cx.execute('SELECT status,recovery_count FROM projects WHERE id=?',(row['id'],)).fetchone()
            checkpoint=cx.execute('SELECT attempt FROM project_checkpoints WHERE project_id=?',(row['id'],)).fetchone()
            if project['status']=='running' and checkpoint and checkpoint['attempt']==row['attempts'] and project['recovery_count']<2:
                # Requeue already-planned work, preserving done task results.
                cx.execute("UPDATE projects SET status='queued',phase='implementation',worker_id=NULL,heartbeat_at=NULL,queued_at=?,updated_at=?,error=NULL,recovery_count=recovery_count+1 WHERE id=?",
                           (now(),now(),row['id']))
                cx.execute("UPDATE planned_tasks SET status='planned',started_at=NULL WHERE project_id=? AND attempt=? AND status='working'",
                           (row['id'],row['attempts']))
                cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                           (row['id'],'Master Orchestrator','queued','Worker lease expired; resuming durable task checkpoint',now()))
            else:
                state='cancelled' if project['status']=='cancel_requested' else 'interrupted'
                cx.execute('UPDATE projects SET status=?,worker_id=NULL,error=?,updated_at=? WHERE id=?',
                           (state,'Worker heartbeat expired; retry manually',now(),row['id']))
                _block_tasks(cx,row['id'])
        cx.execute('COMMIT')
    return len(rows)


def queue_snapshot(limit=200,scope_user=None):
    """Ordered queue with project ACL applied before pagination, not just in UI."""
    limit=max(1,min(int(limit),500))
    cond,params=_project_scope_condition(scope_user)
    with connect() as cx:
        query="""SELECT p.id,p.title,p.stack,p.mode,p.status,p.priority,p.queued_at,p.created_at
                 FROM projects p WHERE p.status=? AND p.archived_at IS NULL"""+cond
        waiting=[dict(r) for r in cx.execute(query+' ORDER BY p.priority DESC,p.queued_at,p.id LIMIT ?', ['queued']+params+[limit])]
        held=[dict(r) for r in cx.execute(query+' ORDER BY p.updated_at DESC LIMIT ?', ['paused']+params+[limit])]
    for i,job in enumerate(waiting,1):job['position']=i
    for job in held:job['position']=None
    return {'queued':waiting,'paused':held,'note':'Position is a snapshot, not an ETA. Running missions cannot be paused from this menu.'}


def change_queue_state(pid, operation):
    """Only queued -> paused and paused -> queued transitions are permitted."""
    expected,new_state={'pause':('queued','paused'),'resume':('paused','queued')}[operation]
    t=now()
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cursor=cx.execute('''UPDATE projects SET status=?,phase=?,queued_at=CASE WHEN ?='queued' THEN ? ELSE queued_at END,
                           updated_at=? WHERE id=? AND status=?''',
                          (new_state,'held' if new_state=='paused' else 'intake',new_state,t,t,pid,expected))
        if cursor.rowcount!=1:
            cx.execute('ROLLBACK')
            return False
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Queue Manager',new_state,'Operator '+('menahan proyek sebelum worker mengambilnya' if new_state=='paused' else 'mengembalikan proyek ke antrean'),t))
        cx.execute('COMMIT')
    return True


def change_priority(pid, priority):
    if type(priority) is not int or not 0<=priority<=3:
        raise ValueError('Priority harus 0 (low), 1 (normal), 2 (high) atau 3 (urgent)')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cursor=cx.execute("UPDATE projects SET priority=?,updated_at=? WHERE id=? AND status IN ('queued','paused')",(priority,now(),pid))
        if cursor.rowcount!=1:
            cx.execute('ROLLBACK')
            return False
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Queue Manager','priority',f'Prioritas diubah menjadi {priority} oleh administrator',now()))
        cx.execute('COMMIT')
    return True


def queue_position(pid,scope_user=None):
    with connect() as cx:
        row=cx.execute('SELECT status,priority,queued_at,id FROM projects WHERE id=?',(pid,)).fetchone()
        if row is None or row['status']!='queued':return None
        cond,params=_project_scope_condition(scope_user)
        return cx.execute("""SELECT COUNT(*) FROM projects p WHERE p.status='queued'
                AND (p.priority>? OR (p.priority=? AND (p.queued_at<? OR (p.queued_at=? AND p.id<=?))))"""+cond,
                (row['priority'],row['priority'],row['queued_at'],row['queued_at'],row['id'],*params)).fetchone()[0]


def activity_cursor(after_id=0,limit=50,project_id=None,scope_user=None):
    """Monotonic pagination for audit and live monitoring, never offsets that skip insertions."""
    limit=max(1,min(int(limit),200))
    with connect() as cx:
        query='''SELECT e.id,e.project_id,e.agent,e.state,e.message,e.created_at,p.title project_title
                  FROM events e JOIN projects p ON e.project_id=p.id
                  WHERE e.id>? AND p.archived_at IS NULL'''
        args=[after_id]
        if project_id:
            query+=' AND e.project_id=?'
            args.append(project_id)
        cond,params=_project_scope_condition(scope_user)
        query+=cond;args.extend(params)
        query+=' ORDER BY e.id LIMIT ?'
        args.append(limit+1)
        rows=[dict(r) for r in cx.execute(query,args)]
    has_more=len(rows)>limit
    rows=rows[:limit]
    return {'events':rows,'next_cursor':rows[-1]['id'] if rows else after_id,'has_more':has_more}


def agent_run_detail(run_id):
    with connect() as cx:
        row=cx.execute('''SELECT a.id,a.project_id,a.agent,a.division,a.status,a.task,a.created_at,a.finished_at,
                     p.title project_title,p.status project_status,p.phase,p.heartbeat_at,p.worker_id,a.claim_id
                     FROM agent_runs a JOIN projects p ON p.id=a.project_id WHERE a.id=?''',(run_id,)).fetchone()
    if row is None:return None
    current=datetime.now(timezone.utc)
    live_ids={x['worker_id'] for x in diagnostics()['workers']}
    return _agent_state(row,live_ids,current)


def project_trace(pid):
    """Read-only inspection record. No API credentials, raw session cookies or worker IDs."""
    with connect() as cx:
        project=cx.execute('''SELECT id,title,mode,stack,status,phase,created_at,updated_at,attempts,
                                   priority,parent_id,archived_at FROM projects WHERE id=?''',(pid,)).fetchone()
        if not project:return None
        events=[dict(r) for r in cx.execute('''SELECT id,agent,state,message,created_at FROM events
                              WHERE project_id=? ORDER BY id''',(pid,))]
        runs=[dict(r) for r in cx.execute('''SELECT id,agent,division,status,task,created_at,finished_at FROM agent_runs
                              WHERE project_id=? ORDER BY id''',(pid,))]
        files=[dict(r) for r in cx.execute('''SELECT name,bytes,sha256 FROM artifacts WHERE project_id=? ORDER BY name''',(pid,))]
        usage=cx.execute('''SELECT COUNT(*) calls,COALESCE(SUM(input_tokens),0) input_tokens,
                            COALESCE(SUM(output_tokens),0) output_tokens FROM usage WHERE project_id=?''',(pid,)).fetchone()
        attempts=[dict(r) for r in cx.execute('''SELECT role,model,status,started_at,finished_at FROM provider_attempts
                              WHERE project_id=? ORDER BY id''',(pid,))]
    return {'schema_version':1,'exported_at':now(),'project':dict(project),'events':events,
            'agent_runs':runs,'artifacts':files,'usage':dict(usage),'provider_attempts':attempts,
            'note':'Activity trace, not evidence of successful runtime deployment or security certification.',
            'collaboration':collaboration_details(pid)}


def _sync_artifact_directory(path):
    import os
    if os.name=='posix':
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)


def _sync_artifact_stage(root):
    import os
    from pathlib import Path
    for path,_,files in os.walk(root,topdown=False):
        directory=Path(path)
        for name in files:
            with (directory/name).open('r+b') as f:
                os.fsync(f.fileno())
        _sync_artifact_directory(directory)


class ArtifactRecoveryRequired(OSError):
    """Publication was not safely reconciled. Preserve both generations."""

    def __init__(self, original, compensation):
        super().__init__('Artifact compensation incomplete; inspect retained generations before recovery')
        self.original = original
        self.compensation = compensation


def publish_artifacts(pid, files, stack, worker_id):
    """Publish verified delivery only while holding the live worker claim.

    Stage outside the database lock, then check ownership and promote under
    BEGIN IMMEDIATE (the same lock as claim/recovery). An ordinary SQL/FS
    exception restores the prior delivery directory before releasing the lock.
    Abrupt process death between filesystem rename and commit is *not* a
    cross-resource transaction: status stays non-delivered; the next worker
    regenerates and verifies before finish. Never expose running artifacts.
    """
    import os
    import re
    import shutil
    import tempfile
    from pathlib import Path
    from . import validation
    if not isinstance(worker_id,str) or not worker_id:
        raise ValueError('Current worker lease is required for publication')
    if not isinstance(pid,str) or not re.fullmatch(r'[a-f0-9]{20}',pid):
        raise ValueError('Invalid delivery project identifier')
    notes = validation.check_files(files,stack)
    root = PROJECTS/pid
    root.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.wfs-stage-',dir=root.parent))
    manifest = [(name,len(files[name].encode('utf-8')),
                 hashlib.sha256(files[name].encode('utf-8')).hexdigest())
                for name in sorted(files)]
    keep_stage = False
    try:
        validation.safe_write(stage,files)
        _sync_artifact_stage(stage)
        with connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            row=cx.execute('SELECT worker_id,status FROM projects WHERE id=?',(pid,)).fetchone()
            if not row or row['status']!='running' or row['worker_id']!=worker_id:
                cx.execute('ROLLBACK')
                raise ValueError('Worker lease is no longer valid for artifact publication')
            backup = None
            backed_up = False
            promoted = False
            commit_attempted = False
            try:
                if root.is_symlink() or (root.exists() and not root.is_dir()):
                    raise ValueError('Unsafe artifact delivery directory')
                if root.exists():
                    backup = root.parent / ('.wfs-previous-' + uuid.uuid4().hex)
                    os.replace(root,backup)
                    backed_up = True
                os.replace(stage,root)
                promoted = True
                _sync_artifact_directory(root.parent)
                cx.execute('DELETE FROM artifacts WHERE project_id=?',(pid,))
                for name,size,checksum in manifest:
                    cx.execute('INSERT INTO artifacts(project_id,name,bytes,sha256) VALUES(?,?,?,?)',
                               (pid,name,size,checksum))
                commit_attempted = True
                cx.execute('COMMIT')
            except BaseException as original:
                # An error after an ended COMMIT is ambiguous. Do not swap
                # directories back or guess which generation the DB committed.
                if commit_attempted and not cx.in_transaction:
                    raise
                try:
                    if promoted:
                        rejected=root.parent/('.wfs-stage-rejected-'+uuid.uuid4().hex)
                        os.replace(root,rejected)
                    if backed_up:
                        os.replace(backup,root)
                    if promoted or backed_up:
                        _sync_artifact_directory(root.parent)
                except OSError as compensation:
                    keep_stage = True
                    raise ArtifactRecoveryRequired(original,compensation) from original
                finally:
                    if not commit_attempted or cx.in_transaction:
                        cx.execute('ROLLBACK')
                raise
            # Preserve every prior generation for an operator-reviewed recovery.
        return notes,manifest
    finally:
        if not keep_stage and stage.exists():shutil.rmtree(stage,ignore_errors=True)


def save_artifacts(pid, manifest):
    """Former unsafe manifest-only writer, permanently fail closed.

    Use publish_artifacts(pid, files, stack, worker_id=per_claim_lease) to
    atomically check ownership and stage the filesystem with the manifest.
    Retaining this trap avoids a silent bypass if an old caller is restored.
    """
    raise ValueError('Unsafe legacy save_artifacts is disabled; use lease-fenced publish_artifacts')


def session_create(token, expiry, user_id="owner", device_label="Browser session"):
    label=''.join(c if 32<=ord(c)<=126 else ' ' for c in (device_label or 'Browser session'))[:96]
    with connect() as cx:
        cx.execute('DELETE FROM sessions WHERE expires_at<=?',(now(),))
        cx.execute('INSERT INTO sessions(id_hash,expires_at,created_at,user_id,device_label) VALUES(?,?,?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(),expiry,now(),user_id,label))


def session_valid(token):
    with connect() as cx:
        r=cx.execute('''SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id_hash=? AND s.expires_at>? AND u.disabled=0''',(hashlib.sha256(token.encode()).hexdigest(),now())).fetchone()
        return bool(r)


def session_account(token):
    with connect() as cx:
        r=cx.execute("""SELECT u.id,u.username,u.role,u.disabled,u.organization_id FROM sessions s
           JOIN users u ON u.id=s.user_id
           WHERE s.id_hash=? AND s.expires_at>?""",
           (hashlib.sha256(token.encode()).hexdigest(),now())).fetchone()
        return dict(r) if r and not r['disabled'] else None


def user_by_username(username):
    with connect() as cx:
        row=cx.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',(username,)).fetchone()
        return dict(row) if row else None


def list_users(scope_user='owner'):
    with connect() as cx:
        return [dict(r) for r in cx.execute('''SELECT id,username,role,disabled,created_at FROM users
           WHERE organization_id=(SELECT organization_id FROM users WHERE id=? AND disabled=0)
           ORDER BY created_at,id''',(scope_user,))]


def create_user(username, password_hash, role, actor_id='owner'):
    if role not in ('manager','developer','viewer'):
        raise ValueError('Owner account cannot be created or downgraded')
    uid=uuid.uuid4().hex
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        actor=cx.execute('SELECT organization_id,role FROM users WHERE id=? AND disabled=0',(actor_id,)).fetchone()
        if not actor or actor['role']!='owner':cx.execute('ROLLBACK');raise ValueError('Invalid account administrator')
        cx.execute('INSERT INTO users(id,username,password_hash,role,created_at,organization_id) VALUES(?,?,?,?,?,?)',
                   (uid,username,password_hash,role,now(),actor['organization_id']))
        cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                   (actor_id,'user_created',uid,now()))
        cx.execute('COMMIT')
    return uid


def change_user(uid, role=None, disabled=None, actor_id='owner', password_hash=None):
    if uid=='owner':return False
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('''SELECT id,role,disabled FROM users WHERE id=? AND organization_id=(
            SELECT organization_id FROM users WHERE id=? AND disabled=0 AND role='owner')''',(uid,actor_id)).fetchone()
        if not row:
            cx.execute('ROLLBACK');return False
        new_role=role if role is not None else row['role']
        if new_role not in ('manager','developer','viewer'):
            cx.execute('ROLLBACK');raise ValueError('Invalid role')
        new_disabled=int(disabled) if disabled is not None else row['disabled']
        cx.execute('UPDATE users SET role=?,disabled=?,password_hash=COALESCE(?,password_hash) WHERE id=?',
                   (new_role,new_disabled,password_hash,uid))
        cx.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                   (actor_id,'user_updated',uid,now()))
        cx.execute('COMMIT')
        return True


def access_log(limit=100,scope_user='owner'):
    with connect() as cx:
        return [dict(r) for r in cx.execute('''SELECT e.* FROM access_events e JOIN users u ON u.id=e.subject_id
              WHERE u.organization_id=(SELECT organization_id FROM users WHERE id=? AND disabled=0)
              ORDER BY e.id DESC LIMIT ?''',(scope_user,min(200,max(1,int(limit)))))]


def session_delete(token):
    with connect() as cx:
        cx.execute('DELETE FROM sessions WHERE id_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))


def login_locked(ip: str):
    """Durable SQLite-backed login throttling, even across API restarts."""
    import time
    cutoff=int(time.time())-300
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cx.execute('DELETE FROM auth_failures WHERE at_epoch<?',(cutoff,))
        n=cx.execute('SELECT count(*) FROM auth_failures WHERE ip=?',(ip,)).fetchone()[0]
        cx.execute('COMMIT')
    return n>=8


def login_failure(ip: str):
    import time
    with connect() as cx:
        cx.execute('INSERT INTO auth_failures(ip,at_epoch) VALUES(?,?)',(ip,int(time.time())))


def login_success(ip: str):
    with connect() as cx:
        cx.execute('DELETE FROM auth_failures WHERE ip=?',(ip,))


def approve(pid: str) -> bool:
    """Require explicit human release for unresolved priority QA findings."""
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        result=cx.execute("UPDATE projects SET status='completed',phase='manually_approved',updated_at=? WHERE id=? AND status='review_required'", (now(),pid))
        cx.execute('COMMIT')
        return result.rowcount==1


def worker_ping(worker_id:str, current_project=None):
    timestamp=now()
    with connect() as cx:
        cx.execute('''INSERT INTO worker_instances(worker_id,first_seen,last_seen,current_project)
            VALUES(?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET last_seen=excluded.last_seen,current_project=excluded.current_project''',
            (worker_id,timestamp,timestamp,current_project))


def worker_depart(worker_id):
    """Forget cleanly stopped workers rather than marking them online for 45 seconds."""
    with connect() as cx:
        cx.execute('DELETE FROM worker_instances WHERE worker_id=?',(worker_id,))


def diagnostics():
    current=datetime.now(timezone.utc)
    with connect() as cx:
        statuses={r['status']:r['n'] for r in cx.execute('SELECT status,COUNT(*) n FROM projects GROUP BY status')}
        live=[]
        for r in cx.execute('SELECT worker_id,first_seen,last_seen,current_project FROM worker_instances ORDER BY last_seen DESC LIMIT 24'):
            age=(current-datetime.fromisoformat(r['last_seen'])).total_seconds()
            if age<=45:
                live.append({'worker_id':r['worker_id'],'last_seen':r['last_seen'],
                    'current_project':r['current_project']})
        return {'database':'ready','workers_online':len(live),'workers':live,
                'queued':statuses.get('queued',0),'running':statuses.get('running',0),
                'review_required':statuses.get('review_required',0),'paused':statuses.get('paused',0)}


def office_overview():
    """Grounded division activity; never fabricate agents or simulated workloads."""
    with connect() as cx:
        rows=cx.execute("""SELECT a.division,
               SUM(CASE WHEN a.status='working' AND p.status='running' AND a.claim_id=p.worker_id THEN 1 ELSE 0 END) AS active,
               SUM(CASE WHEN a.status='done' THEN 1 ELSE 0 END) AS finished,
               MAX(a.created_at) AS latest
            FROM agent_runs a JOIN projects p ON p.id=a.project_id
            WHERE p.archived_at IS NULL GROUP BY a.division""").fetchall()
        return {r['division']:{'active':r['active'],'finished':r['finished'],'last_activity':r['latest']} for r in rows}

# v1.3 live snapshots: display only persisted, attributable agent activity.
FLOOR_DIVISIONS = {
    1: ('Management', 'Architecture', 'Operations'),
    2: ('Engineering', 'Creative Studio', 'AI & Data', 'Documentation'),
    3: ('Quality Lab', 'Infrastructure', 'Security'),
}


def _agent_state(row, live_worker_ids, at_time):
    try:
        fresh = bool(row['heartbeat_at']) and (at_time-datetime.fromisoformat(row['heartbeat_at'])).total_seconds() <= 45
    except (ValueError, TypeError):
        fresh = False
    live = bool(row['status'] == 'working' and row['project_status'] == 'running' and
                fresh and row['worker_id']==row['claim_id'] and row['worker_id'] in live_worker_ids)
    entry = dict(row)
    entry['live'] = live
    entry['state'] = 'working' if live else ('interrupted' if row['status'] == 'working' else row['status'])
    entry.pop('heartbeat_at', None)
    entry.pop('worker_id', None)
    entry.pop('claim_id', None)
    return entry


def office_live(floor: int = 1, project_id: str | None = None, scope_user=None):
    if floor not in FLOOR_DIVISIONS:
        raise ValueError('Floor tidak valid')
    current_time = datetime.now(timezone.utc)
    live_workers = {x['worker_id'] for x in diagnostics()['workers']}
    divisions = FLOOR_DIVISIONS[floor]
    with connect() as cx:
        sql = '''SELECT a.id,a.project_id,a.agent,a.division,a.status,a.task,
                        a.created_at,a.finished_at,p.title AS project_title,
                        p.status AS project_status,p.phase,p.heartbeat_at,p.worker_id,a.claim_id
                 FROM agent_runs a JOIN projects p ON p.id=a.project_id
                 WHERE p.archived_at IS NULL AND a.division IN ({})'''.format(','.join('?' for _ in divisions))
        args = list(divisions)
        if project_id:
            sql += ' AND p.id=?'
            args.append(project_id)
        cond,params=_project_scope_condition(scope_user)
        sql+=cond;args.extend(params)
        rows = cx.execute(sql + ' ORDER BY a.id DESC LIMIT 160', args).fetchall()
        agents = [_agent_state(row, live_workers, current_time) for row in rows]
        counts = {d: {'working': 0, 'done': 0, 'failed': 0, 'interrupted': 0} for d in divisions}
        for a in agents:
            if a['state'] in counts[a['division']]:
                counts[a['division']][a['state']] += 1
        event_sql = '''SELECT e.id,e.project_id,e.agent,e.state,e.message,e.created_at,
                          p.title AS project_title
                       FROM events e JOIN projects p ON p.id=e.project_id
                       WHERE p.archived_at IS NULL'''
        event_args = []
        if project_id:
            event_sql += ' AND p.id=?'
            event_args.append(project_id)
        cond,params=_project_scope_condition(scope_user)
        event_sql+=cond;event_args.extend(params)
        events = [dict(r) for r in cx.execute(event_sql + ' ORDER BY e.id DESC LIMIT 35', event_args)]
        if project_id:
            project_row = cx.execute('SELECT id,title,status,phase,updated_at FROM projects WHERE id=?', (project_id,)).fetchone()
        else:
            project_query="SELECT id,title,status,phase,updated_at FROM projects p WHERE status='running' AND archived_at IS NULL"
            params=[]
            cond,params=_project_scope_condition(scope_user)
            project_query+=cond
            project_row = cx.execute(project_query+' ORDER BY updated_at DESC LIMIT 1',params).fetchone()
        operator_sql = '''SELECT j.id,j.project_id,j.kind,j.status,j.updated_at FROM operator_jobs j
                           JOIN projects p ON p.id=j.project_id WHERE p.archived_at IS NULL'''
        operator_params = []
        if project_id:
            operator_sql += ' AND j.project_id=?'
            operator_params.append(project_id)
        cond,params=_project_scope_condition(scope_user)
        operator_sql+=cond;operator_params.extend(params)
        operator_rows = [dict(r) for r in cx.execute(operator_sql+' ORDER BY j.created_at DESC,j.id DESC LIMIT 8',operator_params)]
        visible_workers={r['worker_id'] for r in rows if r['worker_id'] in live_workers and
                         r['project_status']=='running' and r['status']=='working'}
        return {'floor': floor, 'divisions': counts, 'agents': agents, 'events': events,
                'project': dict(project_row) if project_row else None,
                'operator_jobs': operator_rows,
                'workers_online': len(visible_workers), 'timestamp': now()}


def _project_scope_condition(scope_user):
    # Used by every list/search/activity/operator surface. 'owner' is NOT a
    # cross-tenant escape hatch. Caller with scope_user=None is trusted code.
    if scope_user is None:return '',[]
    return (" AND p.organization_id=(SELECT organization_id FROM users WHERE id=? AND disabled=0)"
            " AND ((SELECT role FROM users WHERE id=?)='owner' OR p.visibility='workspace'"
            " OR p.created_by=? OR EXISTS (SELECT 1 FROM project_members m"
            " WHERE m.project_id=p.id AND m.user_id=?))"),[scope_user]*4


def agent_directory(limit: int = 180,scope_user=None):
    with connect() as cx:
        cond,params=_project_scope_condition(scope_user)
        sql="""SELECT a.id,a.project_id,a.agent,a.division,a.status,a.task,
                    a.created_at,a.finished_at,p.title AS project_title,
                    p.status AS project_status,p.heartbeat_at,p.worker_id,a.claim_id
                 FROM agent_runs a JOIN projects p ON p.id=a.project_id
                 WHERE p.archived_at IS NULL"""+cond+' ORDER BY a.id DESC LIMIT ?'
        rows=cx.execute(sql,params+[limit]).fetchall()
    current_time=datetime.now(timezone.utc)
    live_workers={x['worker_id'] for x in diagnostics()['workers']}
    return [_agent_state(row,live_workers,current_time) for row in rows]


def recent_activity(limit: int = 80,scope_user=None):
    with connect() as cx:
        cond,params=_project_scope_condition(scope_user)
        sql="""SELECT e.id,e.project_id,e.agent,e.state,e.message,
                       e.created_at,p.title AS project_title
                 FROM events e JOIN projects p ON p.id=e.project_id
                 WHERE p.archived_at IS NULL"""+cond+' ORDER BY e.id DESC LIMIT ?'
        return [dict(r) for r in cx.execute(sql,params+[limit])]


def artifact_catalog(limit: int = 250,scope_user=None):
    with connect() as cx:
        cond,params=_project_scope_condition(scope_user)
        sql="""SELECT a.project_id,a.name,a.bytes,a.sha256,
                       p.title AS project_title,p.status AS project_status,p.stack,p.created_at
                 FROM artifacts a JOIN projects p ON p.id=a.project_id
                 WHERE p.archived_at IS NULL"""+cond+' ORDER BY p.updated_at DESC,a.name LIMIT ?'
        return [dict(r) for r in cx.execute(sql,params+[limit])]


def update_project_metadata(pid: str, title: str | None = None, notes: str | None = None):
    """Changes human-facing metadata, not source code or the original project brief."""
    if title is None and notes is None:
        return False
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT id,status FROM projects WHERE id=?',(pid,)).fetchone()
        if not row:
            cx.execute('ROLLBACK')
            return False
        if title is not None:
            cx.execute('UPDATE projects SET title=?,updated_at=? WHERE id=?',(title,now(),pid))
        if notes is not None:
            cx.execute('UPDATE projects SET notes=?,updated_at=? WHERE id=?',(notes,now(),pid))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Workspace Admin','metadata','Project title updated' if title is not None else 'Project notes updated',now()))
        cx.execute('COMMIT')
    return True

# v1.5: Structured, durable collaboration evidence. This is not an autonomous chat simulator.
def _insert_task_plan(cx,pid,attempt,mode,tasks):
    import json
    for t in tasks:
        cx.execute("""INSERT INTO planned_tasks(project_id,attempt,task_key,role,division,description,files_json,status,created_at)
                     VALUES(?,?,?,?,?,?,?,'planned',?)""",
                  (pid,attempt,t['id'],t['role'],t['division'],t['task'][:650],json.dumps(t['files']),now()))
        cx.execute('''INSERT INTO task_reviews(project_id,attempt,task_key,decision,updated_at)
                    VALUES(?,?,?,?,?)''',(pid,attempt,t['id'],
                    'pending' if mode=='manual' else 'approved',now()))


def checkpoint_task_plan(pid,plan,tasks,*,worker_id):
    """Record task ownership, approvals and checkpoint in one worker transaction."""
    import json
    payload=json.dumps({'plan':plan,'tasks':tasks},ensure_ascii=False,separators=(',',':'))
    if len(payload.encode())>250_000:raise ValueError('Work plan exceeds checkpoint limit')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK');raise ValueError('Task plan requires current worker lease')
        row=cx.execute('SELECT attempts,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        attempt,mode=row['attempts'],row['task_review_mode']
        existing=cx.execute('SELECT attempt,payload_json FROM project_checkpoints WHERE project_id=?',(pid,)).fetchone()
        if existing:
            if existing['attempt']!=attempt or json.loads(existing['payload_json'])!=json.loads(payload):
                cx.execute('ROLLBACK');raise ValueError('Existing work plan differs from retry')
            cx.execute('COMMIT');return mode=='manual'
        _insert_task_plan(cx,pid,attempt,mode,tasks)
        cx.execute('INSERT INTO project_checkpoints(project_id,attempt,payload_json,created_at) VALUES(?,?,?,?)',
                   (pid,attempt,payload,now()))
        _insert_event(cx,pid,'Master Orchestrator','done',f'{len(tasks)} specialist tasks assigned')
        cx.execute('INSERT INTO agent_handoffs(project_id,attempt,source,destination,summary,created_at) VALUES(?,?,?,?,?,?)',
                   (pid,attempt,'Product Manager','Architecture + Creative Studio',f'Validated ownership for {len(tasks)} tasks',now()))
        _insert_event(cx,pid,'Agent Handoff','handoff','Product Manager → Architecture + Creative Studio: validated task ownership')
        if mode=='manual':
            _interrupt_agent_runs(cx,pid)
            cx.execute("UPDATE projects SET status='awaiting_approval',phase='task_approval',worker_id=NULL,heartbeat_at=NULL,updated_at=? WHERE id=?",
                       (now(),pid))
            _insert_event(cx,pid,'Master Orchestrator','awaiting_approval','Approve all tasks to re-queue; no worker remains assigned.')
        cx.execute('COMMIT')
        return mode=='manual'


def record_tasks(pid, tasks, worker_id):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT attempts,status,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or row['status'] != 'running' or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK')
            raise ValueError('Task plan requires a running project with current lease')
        attempt=row['attempts']
        _insert_task_plan(cx,pid,attempt,row['task_review_mode'],tasks)
        cx.execute('COMMIT')
    return attempt


def persist_work_plan(pid,plan,tasks,worker_id):
    """Store immutable auto-approval plan before any specialist call is issued."""
    import json
    payload=json.dumps({'plan':plan,'tasks':tasks},ensure_ascii=False,separators=(',',':'))
    if len(payload.encode())>250_000:raise ValueError('Work plan exceeds checkpoint limit')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        proj=cx.execute('SELECT attempts,status FROM projects WHERE id=?',(pid,)).fetchone()
        if not proj or proj['status']!='running' or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK');return False
        cx.execute('INSERT OR IGNORE INTO project_checkpoints(project_id,attempt,payload_json,created_at) VALUES(?,?,?,?)',
                   (pid,proj['attempts'],payload,now()))
        cx.execute('COMMIT')
        return True


def save_task_result(pid,task_key,output,worker_id):
    """Atomic, checksum-stamped task output and done transition; no partial success."""
    import json
    from . import validation
    if not isinstance(output,dict):raise ValueError('Invalid task output')
    for path,content in output.items():
        validation.clean_path(path)
        if not isinstance(content,str):raise ValueError('Task content must be text')
    payload=json.dumps(output,ensure_ascii=False,separators=(',',':'),sort_keys=True)
    if len(payload.encode())>config.MAX_PROJECT_BYTES:raise ValueError('Task result too large')
    checksum=hashlib.sha256(payload.encode()).hexdigest()
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        project=cx.execute('SELECT attempts,status,worker_id FROM projects WHERE id=?',(pid,)).fetchone()
        if not project or project['status']!='running' or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK');raise ValueError('Worker lease is no longer valid')
        row=cx.execute('SELECT files_json,status FROM planned_tasks WHERE project_id=? AND attempt=? AND task_key=?',
                       (pid,project['attempts'],task_key)).fetchone()
        if not row or row['status']!='working' or set(json.loads(row['files_json']))!=set(output):
            cx.execute('ROLLBACK');raise ValueError('Task output differs from approved file ownership')
        cx.execute('INSERT INTO task_results(project_id,attempt,task_key,output_json,sha256,created_at) VALUES(?,?,?,?,?,?)',
                   (pid,project['attempts'],task_key,payload,checksum,now()))
        cx.execute("UPDATE planned_tasks SET status='done',finished_at=? WHERE project_id=? AND attempt=? AND task_key=? AND status='working'",
                   (now(),pid,project['attempts'],task_key))
        cx.execute('COMMIT')
        return checksum


def load_task_results(pid):
    import json
    with connect() as cx:
        project=cx.execute('SELECT attempts FROM projects WHERE id=?',(pid,)).fetchone()
        if not project:return {}
        rows=cx.execute('SELECT task_key,output_json,sha256 FROM task_results WHERE project_id=? AND attempt=?',
                        (pid,project['attempts'])).fetchall()
    out={}
    for row in rows:
        if hashlib.sha256(row['output_json'].encode()).hexdigest()!=row['sha256']:
            raise ValueError('Task checkpoint integrity verification failed')
        out[row['task_key']]=json.loads(row['output_json'])
    return out


def resume_partial_project(pid):
    """Explicit retry from trusted task checkpoints, keeping completed task outputs."""
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        project=cx.execute('SELECT status,attempts FROM projects WHERE id=?',(pid,)).fetchone()
        cp=cx.execute('SELECT attempt FROM project_checkpoints WHERE project_id=?',(pid,)).fetchone()
        if not project or project['status'] not in ('failed','interrupted') or not cp or cp['attempt']!=project['attempts']:
            cx.execute('ROLLBACK');return False
        cx.execute("UPDATE projects SET status='queued',phase='implementation',error=NULL,worker_id=NULL,heartbeat_at=NULL,queued_at=?,updated_at=? WHERE id=?",
                   (now(),now(),pid))
        cx.execute("UPDATE planned_tasks SET status='planned',started_at=NULL,finished_at=NULL WHERE project_id=? AND attempt=? AND status IN ('failed','blocked','working')",
                   (pid,project['attempts']))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Master Orchestrator','queued','Operator resumed from stored specialist checkpoints',now()))
        cx.execute('COMMIT')
        return True


def owns_lease(pid,worker_id):
    with connect() as cx:
        return cx.execute("SELECT 1 FROM projects WHERE id=? AND worker_id=? AND status IN ('running','cancel_requested')",(pid,worker_id)).fetchone() is not None


def task_transition(pid, task_key, from_status, to_status, worker_id):
    allowed={'planned':{'working','blocked'}, 'working':{'done','failed','blocked'}}
    if to_status not in allowed.get(from_status,set()):
        raise ValueError('Invalid task transition')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        current=cx.execute('SELECT attempts,status,worker_id FROM projects WHERE id=?',(pid,)).fetchone()
        if not current or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK')
            return False
        stamp=now()
        if to_status=='working':
            result=cx.execute("""UPDATE planned_tasks SET status=?,started_at=?
                WHERE project_id=? AND attempt=? AND task_key=? AND status=?""",
                (to_status,stamp,pid,current['attempts'],task_key,from_status))
        else:
            result=cx.execute("""UPDATE planned_tasks SET status=?,finished_at=?
                WHERE project_id=? AND attempt=? AND task_key=? AND status=?""",
                (to_status,stamp,pid,current['attempts'],task_key,from_status))
        cx.execute('COMMIT')
        return result.rowcount==1


def _block_tasks(cx,pid):
    cx.execute("""UPDATE planned_tasks SET status='blocked',finished_at=?
                  WHERE project_id=? AND status IN ('planned','working')""",(now(),pid))


def block_outstanding_tasks(pid,*,worker_id):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if not _live_lease(cx,pid,worker_id,allow_cancel=True):
            cx.execute('ROLLBACK');return False
        _block_tasks(cx,pid)
        cx.execute('COMMIT')
        return True


def record_handoff(pid, source, destination, summary, worker_id):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT attempts,status FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or row['status'] not in ('running','cancel_requested') or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK')
            return False
        stamp=now()
        cx.execute("""INSERT INTO agent_handoffs(project_id,attempt,source,destination,summary,created_at)
                    VALUES(?,?,?,?,?,?)""",(pid,row['attempts'],source[:100],destination[:100],summary[:500],stamp))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Agent Handoff','handoff',f'{source[:90]} → {destination[:90]}: {summary[:350]}',stamp))
        cx.execute('COMMIT')
        return True


def add_operator_note(pid, category, message):
    if category not in ('decision','blocker','review'):
        raise ValueError('Invalid note category')
    body=message.strip()
    if not 3<=len(body)<=1500:
        raise ValueError('Invalid operator note length')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT id FROM projects WHERE id=?',(pid,)).fetchone()
        if not row:
            cx.execute('ROLLBACK')
            return None
        stamp=now()
        result=cx.execute('INSERT INTO operator_notes(project_id,category,message,created_at) VALUES(?,?,?,?)',
                          (pid,category,body,stamp))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Human Operator','note',f'{category.upper()}: {body[:300]}',stamp))
        cx.execute('COMMIT')
        return {'id':result.lastrowid,'project_id':pid,'category':category,'message':body,'created_at':stamp}


def collaboration_details(pid):
    import json
    with connect() as cx:
        row=cx.execute('SELECT attempts,status,phase,title,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        if not row:return None
        raw=[dict(r) for r in cx.execute("""SELECT t.task_key,t.role,t.division,t.description,t.files_json,t.status,t.attempt,t.created_at,t.started_at,t.finished_at,
                     COALESCE(r.decision,'approved') AS decision,COALESCE(r.feedback,'') AS feedback
                     FROM planned_tasks t LEFT JOIN task_reviews r
                     ON r.project_id=t.project_id AND r.attempt=t.attempt AND r.task_key=t.task_key
                     WHERE t.project_id=? AND t.attempt=? ORDER BY t.id LIMIT 100""",(pid,row['attempts']))]
        handoffs=[dict(r) for r in cx.execute("""SELECT id,attempt,source,destination,summary,created_at FROM agent_handoffs
                    WHERE project_id=? ORDER BY id DESC LIMIT 100""",(pid,))]
        notes=[dict(r) for r in cx.execute("""SELECT id,category,message,created_at FROM operator_notes
                    WHERE project_id=? ORDER BY id DESC LIMIT 100""",(pid,))]
    for task in raw:
        task['files']=json.loads(task.pop('files_json'))
    counts={name:sum(t['status']==name for t in raw) for name in ('planned','working','done','failed','blocked')}
    return {'project_id':pid,'title':row['title'],'status':row['status'],'phase':row['phase'],
            'attempt':row['attempts'],'task_review_mode':row['task_review_mode'],'tasks':raw,'task_counts':counts,'handoffs':handoffs,'notes':notes,
            'notice':'Structured execution evidence. Operator notes are NOT sent to AI automatically.'}


def live_event_cursor(scope_user=None):
    with connect() as cx:
        cond,params=_project_scope_condition(scope_user)
        return cx.execute('''SELECT COALESCE(MAX(e.id),0) FROM events e
            JOIN projects p ON p.id=e.project_id WHERE 1=1'''+cond,params).fetchone()[0]


# v1.6: human task approval gates; no mutation of working or terminal tasks.
def decide_task(pid,task_key,decision,feedback='',expected_attempt=None):
    if decision not in ('approved','blocked'):raise ValueError('Invalid task decision')
    if not isinstance(feedback,str) or len(feedback)>1000:raise ValueError('Invalid feedback length')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        project=cx.execute('SELECT attempts,status,phase,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        if not project or project['status'] not in ('running','awaiting_approval') or project['phase']!='task_approval' or project['task_review_mode']!='manual' or (expected_attempt is not None and expected_attempt!=project['attempts']):
            cx.execute('ROLLBACK');return False
        task=cx.execute('SELECT status FROM planned_tasks WHERE project_id=? AND attempt=? AND task_key=?',(pid,project['attempts'],task_key)).fetchone()
        if not task or task['status']!='planned':
            cx.execute('ROLLBACK');return False
        result=cx.execute('''UPDATE task_reviews SET decision=?,feedback=?,updated_at=?
                   WHERE project_id=? AND attempt=? AND task_key=?''',
                   (decision,feedback.strip(),now(),pid,project['attempts'],task_key))
        if result.rowcount!=1:cx.execute('ROLLBACK');return False
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Human Task Reviewer','task_'+decision,task_key+' → '+decision+'; '+feedback[:180],now()))
        _release_approved_in_transaction(cx,pid,project['attempts'])
        cx.execute('COMMIT');return True


def task_gate(pid):
    with connect() as cx:
        row=cx.execute('SELECT status,attempts,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        if not row:return None
        counts={r['decision']:r['n'] for r in cx.execute('''SELECT decision,COUNT(*) n FROM task_reviews
                 WHERE project_id=? AND attempt=? GROUP BY decision''',(pid,row['attempts']))}
        total=sum(counts.values())
        return {'mode':row['task_review_mode'],'status':row['status'],'total':total,
                'pending':counts.get('pending',0),'blocked':counts.get('blocked',0),
                'approved':counts.get('approved',0)}


def task_feedback(pid,task_key):
    with connect() as cx:
        row=cx.execute('''SELECT r.feedback FROM task_reviews r JOIN projects p
                    ON p.id=r.project_id AND p.attempts=r.attempt
                    WHERE r.project_id=? AND r.task_key=?''',(pid,task_key)).fetchone()
        return row['feedback'] if row else ''


def create_operator_job(pid,kind,options):
    import json
    if kind not in ('qa-static','qa-fastapi','github-draft','preview-start','preview-stop','preview-stack-start','preview-stack-stop','preview-trio-start','preview-trio-stop','react-build'):
        raise ValueError('Unsupported job kind')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT status,stack FROM projects WHERE id=?',(pid,)).fetchone()
        if not row or row['status'] not in ('completed','review_required'):
            cx.execute('ROLLBACK');raise ValueError('Project not yet delivered')
        if kind in ('qa-fastapi',) and row['stack']!='fastapi':
            cx.execute('ROLLBACK');raise ValueError('FastAPI required')
        if kind in ('preview-start','preview-stop') and row['stack'] not in ('fastapi','node-web'):
            cx.execute('ROLLBACK');raise ValueError('Runtime preview requires FastAPI or Node Web')
        if kind in ('preview-stack-start','preview-stack-stop','preview-trio-start','preview-trio-stop') and row['stack']!='fastapi':
            cx.execute('ROLLBACK');raise ValueError('PostgreSQL full-stack preview requires FastAPI')
        if kind=='react-build' and row['stack']!='react-vite':
            cx.execute('ROLLBACK');raise ValueError('React preview build requires React/Vite')
        if kind=='github-draft' and row['status']!='completed':
            cx.execute('ROLLBACK');raise ValueError('GitHub publish requires approved completed project')
        # Limit outstanding requests and duplicate queueing.
        if cx.execute("SELECT COUNT(*) FROM operator_jobs WHERE project_id=? AND status IN ('queued','running')",(pid,)).fetchone()[0]>=4:
            cx.execute('ROLLBACK');raise ValueError('Outstanding job limit reached')
        jid=uuid.uuid4().hex[:24]
        cx.execute('''INSERT INTO operator_jobs(id,project_id,kind,options_json,status,created_at,updated_at)
                  VALUES(?,?,?,?,'queued',?,?)''',(jid,pid,kind,json.dumps(options,sort_keys=True),now(),now()))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                  (pid,'Operator Job Center','queued',kind+' request queued; requires separate host operator runner',now()))
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (jid,'queued','Operator request submitted; waiting for host confirmation',now()))
        cx.execute('COMMIT')
        return jid


def list_operator_jobs(pid=None,limit=100,scope_user=None):
    import json
    cond,params=_project_scope_condition(scope_user)
    with connect() as cx:
        query="SELECT j.* FROM operator_jobs j JOIN projects p ON p.id=j.project_id WHERE 1=1"
        args=[]
        if pid:query+=' AND j.project_id=?';args.append(pid)
        query+=cond
        args+=params
        rows=[]
        for r in cx.execute(query+' ORDER BY j.created_at DESC,j.id DESC LIMIT ?',args+[limit]):
            data=dict(r);data['options']=json.loads(data.pop('options_json'));data['result']=json.loads(data.pop('result_json') or '{}');rows.append(data)
        return rows


def claim_operator_job(jid):
    import json
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        result=cx.execute('''UPDATE operator_jobs SET status='running',started_at=?,updated_at=?
               WHERE id=? AND status='queued' ''',(now(),now(),jid))
        if result.rowcount!=1:cx.execute('ROLLBACK');return None
        row=cx.execute('SELECT * FROM operator_jobs WHERE id=?',(jid,)).fetchone()
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (jid,'running','Host runner claimed job after human confirmation',now()))
        cx.execute('COMMIT')
        item=dict(row);item['options']=json.loads(item.pop('options_json'));return item


def finish_operator_job(jid,status,result):
    import json
    if status not in ('completed','failed','rejected'):raise ValueError('Invalid operator job status')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute("SELECT project_id,kind FROM operator_jobs WHERE id=? AND status='running'",(jid,)).fetchone()
        if not row:cx.execute('ROLLBACK');return False
        cx.execute('''UPDATE operator_jobs SET status=?,result_json=?,finished_at=?,updated_at=? WHERE id=?''',
                   (status,json.dumps(result,ensure_ascii=False)[:7000],now(),now(),jid))
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (jid,status,'Host runner finished with status '+status,now()))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                  (row['project_id'],'Operator Job Center',status,row['kind']+' → '+status,now()))
        cx.execute('COMMIT');return True


def cancel_operator_job(jid):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute("SELECT project_id,kind FROM operator_jobs WHERE id=? AND status='queued'",(jid,)).fetchone()
        if not row:cx.execute('ROLLBACK');return False
        cx.execute("UPDATE operator_jobs SET status='cancelled',updated_at=?,finished_at=? WHERE id=?",(now(),now(),jid))
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (jid,'cancelled','Operator cancelled before execution',now()))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (row['project_id'],'Operator Job Center','cancelled',row['kind']+' request cancelled before execution',now()))
        cx.execute('COMMIT');return True


# v1.7: structured operator trace. Never log subprocess stdout or credentials as timeline stages.
def operator_job_detail(jid):
    import json
    with connect() as cx:
        row=cx.execute('SELECT * FROM operator_jobs WHERE id=?',(jid,)).fetchone()
        if not row:return None
        result=dict(row)
        result['options']=json.loads(result.pop('options_json'))
        result['result']=json.loads(result.pop('result_json') or '{}')
        result['steps']=[dict(r) for r in cx.execute('''SELECT id,stage,summary,created_at FROM operator_job_steps
                        WHERE job_id=? ORDER BY id''',(jid,))]
        return result


def operator_job_step(jid,stage,summary):
    if stage not in ('preflight','executing','reviewing','publishing','building','verifying'):
        raise ValueError('Invalid stage')
    if not isinstance(summary,str) or not 1<=len(summary)<=180:
        raise ValueError('Invalid stage description')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute("SELECT id FROM operator_jobs WHERE id=? AND status='running'",(jid,)).fetchone()
        if not row:cx.execute('ROLLBACK');return False
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (jid,stage,summary,now()))
        cx.execute('UPDATE operator_jobs SET updated_at=? WHERE id=?',(now(),jid))
        cx.execute('COMMIT')
        return True


def operator_job_heartbeat(jid):
    with connect() as cx:
        return cx.execute("UPDATE operator_jobs SET updated_at=? WHERE id=? AND status='running'",(now(),jid)).rowcount==1


def retry_operator_job(jid):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        row=cx.execute('SELECT * FROM operator_jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['status'] not in ('failed','rejected'):
            cx.execute('ROLLBACK');return None
        pid=row['project_id']
        project=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
        if not project or project['status'] not in ('completed','review_required') or (row['kind']=='github-draft' and project['status']!='completed'):
            cx.execute('ROLLBACK');return None
        if cx.execute("SELECT COUNT(*) FROM operator_jobs WHERE project_id=? AND status IN ('queued','running')",(pid,)).fetchone()[0]>=4:
            cx.execute('ROLLBACK');return None
        new_id=uuid.uuid4().hex[:24]
        cx.execute("INSERT INTO operator_jobs(id,project_id,kind,options_json,status,created_at,updated_at,retry_of) VALUES(?,?,?,?,'queued',?,?,?)",
                   (new_id,pid,row['kind'],row['options_json'],now(),now(),jid))
        cx.execute('INSERT INTO operator_job_steps(job_id,stage,summary,created_at) VALUES(?,?,?,?)',
                   (new_id,'queued','Retry requested; fresh typed host approval is required',now()))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Operator Job Center','queued','Operator re-queued '+row['kind']+' after failure',now()))
        cx.execute('COMMIT')
        return new_id


def approve_pending_tasks(pid,attempt,feedback=''):
    if not isinstance(feedback,str) or len(feedback)>1000:raise ValueError('Invalid feedback')
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        project=cx.execute('SELECT status,phase,task_review_mode,attempts FROM projects WHERE id=?',(pid,)).fetchone()
        if not project or project['status'] not in ('running','awaiting_approval') or project['phase']!='task_approval' or project['task_review_mode']!='manual' or project['attempts']!=attempt:
            cx.execute('ROLLBACK');return None
        tasks=cx.execute("SELECT r.task_key FROM task_reviews r JOIN planned_tasks t ON r.project_id=t.project_id AND r.attempt=t.attempt AND r.task_key=t.task_key WHERE r.project_id=? AND r.attempt=? AND r.decision='pending' AND t.status='planned'",(pid,attempt)).fetchall()
        if not tasks:cx.execute('ROLLBACK');return None
        cx.executemany("UPDATE task_reviews SET decision='approved',feedback=?,updated_at=? WHERE project_id=? AND attempt=? AND task_key=? AND decision='pending'",
                       [(feedback.strip(),now(),pid,attempt,t['task_key']) for t in tasks])
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Human Task Reviewer','task_batch_approved',str(len(tasks))+' pending tasks approved in one decision',now()))
        _release_approved_in_transaction(cx,pid,attempt)
        cx.execute('COMMIT')
        return len(tasks)


# v1.8: nonblocking approval checkpoint. No model call occurs when user is still reviewing tasks.
def release_for_approval(pid,plan,tasks,worker_id):
    import json
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        project=cx.execute('SELECT attempts,status,task_review_mode FROM projects WHERE id=?',(pid,)).fetchone()
        if not project or project['status']!='running' or project['task_review_mode']!='manual' or not _live_lease(cx,pid,worker_id):
            cx.execute('ROLLBACK');return False
        payload=json.dumps({'plan':plan,'tasks':tasks},ensure_ascii=False)
        if len(payload)>250_000:cx.execute('ROLLBACK');raise ValueError('Checkpoint too large')
        cx.execute('INSERT OR REPLACE INTO project_checkpoints(project_id,attempt,payload_json,created_at) VALUES(?,?,?,?)',
                   (pid,project['attempts'],payload,now()))
        _interrupt_agent_runs(cx,pid)
        cx.execute("UPDATE projects SET status='awaiting_approval',phase='task_approval',worker_id=NULL,heartbeat_at=NULL,updated_at=? WHERE id=?",(now(),pid))
        cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
                   (pid,'Master Orchestrator','awaiting_approval','Review tasks without occupying a worker. Approve all to re-queue the project.',now()))
        cx.execute('COMMIT')
        return True


def get_checkpoint(pid):
    import json
    with connect() as cx:
        row=cx.execute('SELECT cp.attempt,cp.payload_json FROM project_checkpoints cp JOIN projects p ON p.id=cp.project_id AND p.attempts=cp.attempt WHERE cp.project_id=?',(pid,)).fetchone()
        return json.loads(row['payload_json']) if row else None


def _release_approved_in_transaction(cx,pid,attempt):
    p=cx.execute('SELECT status FROM projects WHERE id=?',(pid,)).fetchone()
    if not p or p['status']!='awaiting_approval':return False
    counts={r['decision']:r['n'] for r in cx.execute('SELECT decision,COUNT(*) n FROM task_reviews WHERE project_id=? AND attempt=? GROUP BY decision',(pid,attempt))}
    if counts.get('approved',0)<1 or counts.get('blocked',0)>0 or counts.get('pending',0)>0:return False
    if not cx.execute('SELECT 1 FROM project_checkpoints WHERE project_id=? AND attempt=?',(pid,attempt)).fetchone():return False
    cx.execute("UPDATE projects SET status='queued',queued_at=?,updated_at=? WHERE id=?",(now(),now(),pid))
    cx.execute('INSERT INTO events(project_id,agent,state,message,created_at) VALUES(?,?,?,?,?)',
               (pid,'Master Orchestrator','queued','All tasks approved; checkpoint preserved and project requeued',now()))
    return True


def concurrency_snapshot():
    with connect() as cx:
        active=[dict(r) for r in cx.execute("SELECT id,title,phase,worker_id,heartbeat_at FROM projects WHERE status IN ('running','cancel_requested') ORDER BY updated_at DESC LIMIT 30")]
        waiting=cx.execute("SELECT COUNT(*) FROM projects WHERE status='awaiting_approval'").fetchone()[0]
        queued=cx.execute("SELECT COUNT(*) FROM projects WHERE status='queued'").fetchone()[0]
        workers=cx.execute("SELECT worker_id,current_project,last_seen FROM worker_instances ORDER BY last_seen DESC LIMIT 30").fetchall()
    return {'max_active_projects':config.MAX_ACTIVE_PROJECTS,'active_count':len(active),'queued_count':queued,
            'awaiting_approval_count':waiting,'free_slots':max(0,config.MAX_ACTIVE_PROJECTS-len(active)),
            'active':active,'workers':[dict(r) for r in workers],
            'note':'SQLite atomic claiming prevents duplicate claims. Worker replicas run independently; concurrent model requests still have per-project limits.'}


def operator_job_project(jid):
    with connect() as cx:
        r=cx.execute('SELECT project_id FROM operator_jobs WHERE id=?',(jid,)).fetchone()
        return r['project_id'] if r else None


# --- v2.5 MFA: scope is a local account, not an AI agent ---
def mfa_record(user_id: str):
    with connect() as cx:
        row=cx.execute('SELECT mfa_secret,mfa_last_step FROM users WHERE id=? AND disabled=0',(user_id,)).fetchone()
        return dict(row) if row else None


def mfa_begin(user_id: str, session_token: str, encrypted_secret: str, expires_epoch: int):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cx.execute('INSERT INTO mfa_pending(user_id,session_hash,secret,expires_epoch) VALUES(?,?,?,?) '
                   'ON CONFLICT(user_id) DO UPDATE SET session_hash=excluded.session_hash,secret=excluded.secret,expires_epoch=excluded.expires_epoch',
                   (user_id,hashlib.sha256(session_token.encode()).hexdigest(),encrypted_secret,expires_epoch))
        cx.execute('COMMIT')


def mfa_pending_secret(user_id: str, session_token: str):
    import time
    with connect() as cx:
        row=cx.execute('SELECT secret,expires_epoch,session_hash FROM mfa_pending WHERE user_id=?',(user_id,)).fetchone()
        if not row or row['expires_epoch']<=int(time.time()) or row['session_hash']!=hashlib.sha256(session_token.encode()).hexdigest():
            return None
        return row['secret']


def mfa_activate(user_id: str, session_token: str, encrypted_secret: str, matched_step: int, hashes: list[str]):
    import time
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        pending=cx.execute('SELECT secret,expires_epoch,session_hash FROM mfa_pending WHERE user_id=?',(user_id,)).fetchone()
        if (not pending or pending['secret']!=encrypted_secret or pending['expires_epoch']<=int(time.time())
                or pending['session_hash']!=hashlib.sha256(session_token.encode()).hexdigest()):
            cx.execute('ROLLBACK');return False
        cx.execute('UPDATE users SET mfa_secret=?,mfa_last_step=? WHERE id=? AND mfa_secret IS NULL',
                   (encrypted_secret,matched_step,user_id))
        if not cx.execute('SELECT changes()').fetchone()[0]:
            cx.execute('ROLLBACK');return False
        cx.execute('DELETE FROM mfa_pending WHERE user_id=?',(user_id,))
        cx.executemany('INSERT INTO mfa_recovery(user_id,code_hash) VALUES(?,?)',[(user_id,h) for h in hashes])
        cx.execute('DELETE FROM sessions WHERE user_id=? AND id_hash!=?',
                   (user_id,hashlib.sha256(session_token.encode()).hexdigest()))
        cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                   (user_id,'mfa_enabled',user_id,now()))
        cx.execute('COMMIT')
        return True


def mfa_consume_code(user_id: str, matched_step: int | None = None, recovery_hash: str | None = None) -> bool:
    # Single atomic compare/consume prevents concurrent TOTP replay.
    if (matched_step is None)==(recovery_hash is None):return False
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        if matched_step is not None:
            row=cx.execute('UPDATE users SET mfa_last_step=? WHERE id=? AND mfa_secret IS NOT NULL AND mfa_last_step<?',
                           (matched_step,user_id,matched_step))
            ok=row.rowcount==1
        else:
            row=cx.execute('DELETE FROM mfa_recovery WHERE user_id=? AND code_hash=?',(user_id,recovery_hash))
            ok=row.rowcount==1
        cx.execute('COMMIT')
        return ok


def mfa_disable(user_id: str):
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cx.execute('UPDATE users SET mfa_secret=NULL,mfa_last_step=-1 WHERE id=?',(user_id,))
        cx.execute('DELETE FROM mfa_pending WHERE user_id=?',(user_id,))
        cx.execute('DELETE FROM mfa_recovery WHERE user_id=?',(user_id,))
        cx.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                   (user_id,'mfa_disabled',user_id,now()))
        cx.execute('COMMIT')


def mfa_locked(user_id: str) -> bool:
    import time
    with connect() as cx:
        row=cx.execute('SELECT COUNT(*) FROM mfa_failures WHERE user_id=? AND at_epoch>?',
                       (user_id,int(time.time())-300)).fetchone()
        return row[0]>=5


def mfa_failure(user_id: str):
    import time
    with connect() as cx:
        cx.execute('DELETE FROM mfa_failures WHERE at_epoch<?',(int(time.time())-600,))
        cx.execute('INSERT INTO mfa_failures(user_id,at_epoch) VALUES(?,?)',(user_id,int(time.time())))


def mfa_success(user_id: str):
    with connect() as cx:
        cx.execute('DELETE FROM mfa_failures WHERE user_id=?',(user_id,))


# v2.6 offline-only initial organization provisioning. Not a public endpoint.
def provision_organization(org_id: str, display_name: str, username: str, password_hash: str, role: str='manager'):
    import re
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}',org_id) or org_id=='default':
        raise ValueError('Invalid organization id')
    if not 3<=len(display_name.strip())<=100 or role not in ('owner','manager','developer','viewer'):
        raise ValueError('Invalid organization metadata')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{2,31}',username):
        raise ValueError('Invalid username')
    uid=uuid.uuid4().hex
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        cx.execute('INSERT INTO organizations(id,display_name,created_at) VALUES(?,?,?)',(org_id,display_name.strip(),now()))
        # Every newly provisioned tenant gets an independently scoped default workspace.
        cx.execute('INSERT INTO workspaces(organization_id,id,name,created_at) VALUES(?,?,?,?)',
                   (org_id,'default','Main workspace',now()))
        cx.execute('INSERT INTO users(id,username,password_hash,role,created_at,organization_id) VALUES(?,?,?,?,?,?)',
                   (uid,username,password_hash,role,now(),org_id))
        cx.execute('COMMIT')
    return uid


def organization_mfa_required(user_id: str) -> bool:
    """Organization policy, read from the server-side account identity only."""
    with connect() as cx:
        row=cx.execute('SELECT o.mfa_required FROM users u JOIN organizations o ON o.id=u.organization_id WHERE u.id=? AND u.disabled=0',(user_id,)).fetchone()
        return bool(row and row['mfa_required'])


def set_organization_mfa_policy(org_id: str, required: bool) -> None:
    """Offline operator-only; never exposed as a remotely mutable HTTP endpoint."""
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        updated=cx.execute('UPDATE organizations SET mfa_required=? WHERE id=?',
                           (int(bool(required)),org_id)).rowcount
        if not updated:
            cx.execute('ROLLBACK')
            raise ValueError('Organization not found')
        cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',('offline-operator','org_mfa_required' if required else 'org_mfa_optional',org_id,now()))
        # Existing un-enrolled sessions become setup-only on their next request.
        cx.execute('COMMIT')


def list_account_sessions(user_id: str, current_token: str):
    """Opaque list of ONLY this account's sessions; no tokens, IPs or hashes exposed."""
    current_hash=hashlib.sha256(current_token.encode()).hexdigest()
    with connect() as cx:
        return [{'id':r['id_hash'][:20],'created_at':r['created_at'],
                 'expires_at':r['expires_at'],'device':r['device_label'],
                 'current':r['id_hash']==current_hash}
                for r in cx.execute('SELECT id_hash,created_at,expires_at,device_label FROM sessions WHERE user_id=? AND expires_at>? ORDER BY created_at DESC',(user_id,now()))]


def revoke_account_session(user_id: str, session_id: str) -> bool:
    import re
    if not re.fullmatch('[a-f0-9]{20}',session_id):return False
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        result=cx.execute('DELETE FROM sessions WHERE user_id=? AND SUBSTR(id_hash,1,20)=?',
                          (user_id,session_id))
        if result.rowcount:
            cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                       (user_id,'session_revoked',user_id,now()))
        cx.execute('COMMIT')
        return result.rowcount==1


def revoke_other_account_sessions(user_id: str, current_token: str) -> int:
    session_hash=hashlib.sha256(current_token.encode()).hexdigest()
    with connect() as cx:
        cx.execute('BEGIN IMMEDIATE')
        result=cx.execute('DELETE FROM sessions WHERE user_id=? AND id_hash!=?',(user_id,session_hash))
        if result.rowcount:
            cx.execute('INSERT INTO access_events(actor_id,action,subject_id,created_at) VALUES(?,?,?,?)',
                       (user_id,'other_sessions_revoked',user_id,now()))
        cx.execute('COMMIT')
        return result.rowcount
