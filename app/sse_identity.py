"""Local issuer and verification of short-lived SSE admission assertions.

Only the authority process holds the signing key. The API proves possession of
the session credential through private IPC. Project and tenant claims come from
one read-only authorization query, not from API attestations.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature

ISSUER = 'wfs-session-authority'
AUDIENCE = 'wfs-sse-admission'
ASSERTION_TTL = 8
HEX32 = re.compile(r'[a-f0-9]{32}')
HEX64 = re.compile(r'[a-f0-9]{64}')
IDENT = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
PROJECT = re.compile(r'[a-f0-9]{20}')


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _encode(claims):
    return json.dumps(claims, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


class SessionPolicy:
    def __init__(self, database):
        self.uri = Path(database).resolve(strict=True).as_uri() + '?mode=ro'

    def lookup(self, session, project):
        if not _matches(HEX64, session) or (project is not None and not _matches(PROJECT, project)):
            return None
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with closing(sqlite3.connect(self.uri, uri=True, timeout=0.25)) as cx:
            return cx.execute("""
                SELECT u.id,u.organization_id FROM sessions s
                JOIN users u ON u.id=s.user_id
                JOIN organizations o ON o.id=u.organization_id
                WHERE s.id_hash=? AND s.expires_at>? AND u.disabled=0
                  AND (o.mfa_required=0 OR COALESCE(u.mfa_secret,'')!='')
                  AND (? IS NULL OR EXISTS (
                    SELECT 1 FROM projects p
                    WHERE p.id=? AND p.organization_id=u.organization_id
                      AND (u.role='owner' OR p.created_by=u.id OR p.visibility='workspace'
                           OR EXISTS (SELECT 1 FROM project_members m
                                      WHERE m.project_id=p.id AND m.user_id=u.id))
                  ))
                """, (session, now, project, project)).fetchone()


class AssertionIssuer:
    def __init__(self, policy, signing_key):
        self.policy = policy
        self.signing_key = signing_key

    def issue(self, token, project):
        if not isinstance(token, str) or not 1 <= len(token) <= 256 or not token.isascii():
            return None
        session = hashlib.sha256(token.encode()).hexdigest()
        account = self.policy.lookup(session, project)
        if account is None:
            return None
        issued = int(time.time())
        claims = dict(iss=ISSUER, aud=AUDIENCE, sub=account[0], org=account[1],
                      sid=session, project=project, iat=issued, exp=issued+ASSERTION_TTL,
                      jti=secrets.token_hex(16))
        return {'claims': claims, 'signature': self.signing_key.sign(_encode(claims)).hex()}


class AssertionVerifier:
    def __init__(self, policy, public_key):
        self.policy = policy
        self.public_key = public_key

    def verify(self, assertion, at):
        if not isinstance(assertion, dict) or set(assertion) != {'claims', 'signature'}:
            return None
        claims, sig = assertion['claims'], assertion['signature']
        if (not isinstance(claims, dict)
                or set(claims) != {'iss','aud','sub','org','sid','project','iat','exp','jti'}
                or not isinstance(sig, str) or not re.fullmatch(r'[a-f0-9]{128}', sig)
                or claims['iss'] != ISSUER or claims['aud'] != AUDIENCE
                or not _matches(IDENT, claims['sub']) or not _matches(IDENT, claims['org'])
                or not _matches(HEX64, claims['sid']) or not _matches(HEX32, claims['jti'])
                or (claims['project'] is not None and not _matches(PROJECT, claims['project']))
                or type(claims['iat']) is not int or type(claims['exp']) is not int
                or not claims['iat'] <= at < claims['exp']
                or not 0 < claims['exp'] - claims['iat'] <= ASSERTION_TTL):
            return None
        try:
            self.public_key.verify(bytes.fromhex(sig), _encode(claims))
        except InvalidSignature:
            return None
        if self.policy.lookup(claims['sid'], claims['project']) != (claims['sub'], claims['org']):
            return None
        return claims
