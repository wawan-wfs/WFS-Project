# WFS PROJECT v2.1 — Private Project Access & Team Scoping

## What changed

WFS v2.1 adds project-specific access control to the existing four global RBAC roles. **New missions created in the dashboard or via the v2.1 API default to `private`**; only their creator and the built-in Owner can see them until explicitly shared. Owners and original project creators can invite members in **Team & Access → Private mission access**. Available permissions: `view` and `edit`.

Global role restrictions remain in effect: a Viewer invited with `edit` still cannot perform global role-prohibited mutations. Managers with project `view` can inspect but cannot modify a private mission. Managers granted `edit` may perform operations their role permits. Creators can share or privatize their own projects. No recipient can silently manage another creator's membership list.

## Access matrix

| Who | Workspace project | Private project |
|---|---|---|
| Owner | All data and operations | All data and operations |
| Original creator | Role-permitted access | Role-permitted access and project permission management |
| Team member with `view` | Role-permitted access | Read only |
| Team member with `edit` | Role-permitted access | Read + global-role-permitted writes |
| Other signed-in team user | Role-permitted access | No access; missing/denied project returns 404 |

Auth is enforced on the API, not only by hiding UI controls. Project file reads and downloads, preview documents, operator job detail and retries, QA traces, project timelines, task review, cost report, CSV export, SSE subscriptions, and all other project routes require authorization. Cross-project dashboards, agent directories, the live office, activity streams, project queues, operator job lists, artifact catalogs, budget lists, and financial aggregates are scoped to visible projects. Revocation affects the next request and live event poll without needing logout.

The project creator/Owner can switch a project between `private` and `workspace`. **Making a parent private also makes existing revisions private**. Making a parent workspace does *not* automatically make its private revisions public. New revisions inherit the parent's visibility and members. Grant changes produce project-specific audit records and telemetry without exposing passwords.

## Data migration

On first v2.1 startup, migrations add `projects.visibility` (`workspace` default for existing rows), `projects.created_by` (`owner` default for existing rows), `project_members`, and `project_access_audit`. This preserves **legacy projects as workspace-shared** to avoid unexpectedly breaking teammates' existing work. Review all legacy projects manually and change sensitive ones to Private. No data from `data/` or `.env` is included in the distributed ZIP.

1. Stop v2.0 containers and all preview jobs.
2. Back up `data/` and `.env`, and verify the backup can be restored.
3. Extract v2.1 to a fresh folder. Copy only `data/` and `.env` from v2.0.
4. Start WFS PROJECT. Verify owner login, existing projects, account roles, and the new Private mission access panel.
5. Create a private demo project, grant a Viewer, confirm read-only access, revoke that access, and confirm it immediately returns 404 for the same session.
6. Run the provided backend/HTTP/UI tests on the Windows machine before storing confidential content.

## API contracts

- `POST /api/projects` accepts `visibility: private|workspace` (default: `private`).
- `GET /api/projects/{id}/access` returns the visibility, creator, membership roster, and access audit.
- `PATCH /api/projects/{id}/access` changes visibility, with `{ "visibility":"private" }`.
- `POST /api/projects/{id}/members` grants or updates membership with `{ "user_id":"...", "permission":"view|edit" }`.
- `DELETE /api/projects/{id}/members/{user_id}` revokes access.
- `GET /api/team/directory` returns an active user directory without secrets.

Write operations require the existing authenticated cookie and `X-WFS-CSRF` header. Every grant/revoke/visibility change is authorized by project creator or Owner and saved in the local audit database.

## Security boundaries & production risks

**This is still a trusted-network, single-workspace local release candidate, not enterprise tenant separation or internet-ready production.** MFA/SSO is not implemented. Files are stored in the same SQLite/database and host filesystem and may be inspected by host administrators. A trusted host operator with direct database or Docker access is outside application-level RBAC. A shared project is readable by all signed-in users, including Viewers. The host-side preview runner can publish a separate localhost URL without its own authentication; treat that local preview URL as sensitive. Avoid exposing preview ports to untrusted networks, even if the dashboard uses private ACL.

Use HTTPS, secure cookies, hardened deployment, backup encryption, MFA, professional security review and real Docker acceptance tests before granting remote or external access. No project content or user credential should be assumed protected against compromise of the Windows host.
