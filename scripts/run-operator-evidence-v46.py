#!/usr/bin/env python3
"""Collect local gate status and focused pytest case evidence without false passes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FOCUSED = ('tests/test_v40_sse_admission.py', 'tests/test_v38_broker_deadlines.py',
           'tests/test_v41_sse_identity.py')
GATES = {
    'manifest': ('scripts/verify-release.py',),
    'uds': ('scripts/sse-two-api-lab.py',),
    'focused': ('-m', 'pytest', '-q', '-rs', *FOCUSED),
    'http': ('scripts/http-e2e.py',),
    'workers': ('scripts/parallel-e2e.py',),
    'postgres-replica': ('scripts/postgres-replica-lab.py',),
    'postgres-scale': ('scripts/postgres-quota-lab.py',),
}
DEFAULT = ('manifest', 'uds', 'focused', 'http', 'workers')
UDS_CHECKS = ('cross_process_quota', 'disconnect_release', 'outage_fail_closed',
              'transport_secret_rotation', 'old_assertion_rejected', 'live_session_revocation')
# Node IDs are an explicit release contract. A filtered or renamed test must
# not make the collector silently count an incomplete run as a pass.
CASES = {
    'test_v40_sse_admission.AdmissionProcessV40': (
        'test_assertion_authority_real_uds_when_available',
        'test_authenticated_control_and_replay_deny',
        'test_crash_restart_ttl_and_fail_closed',
        'test_session_revocation_remains_required_inside_stream',
        'test_two_tenants_natted_sessions_concurrent_disconnect_replay',
    ),
    'test_v38_broker_deadlines.SlowBrokerV38': (
        'test_cancelled_client_closes_socket_and_releases_slot',
        'test_real_unix_transport_and_strip_auth',
        'test_slow_upstream_aborted_and_slot_released',
        'test_total_request_body_deadline_rejects_slow_trickle',
    ),
    'test_v41_sse_identity.LocalAssertions': (
        'test_claim_rechecks_revocation_and_mfa_before_quota_write',
        'test_forward_skew_nonce_cannot_replay_after_original_retention',
        'test_issuer_requires_real_bearer_and_live_tenant_grant',
        'test_replay_restart_ttl_and_two_independent_organization_caps',
        'test_signed_wrong_issuer_audience_expiry_and_tamper_are_rejected',
    ),
    'test_v41_sse_identity.SSECancellation': (
        'test_assertion_mode_misconfiguration_returns_503',
        'test_cancelled_admission_releases_a_late_reservation',
        'test_failed_send_releases_even_before_first_chunk',
    ),
}


def focused_result(report, rc):
    expected = {f'{group}.{name}' for group, names in CASES.items() for name in names}
    cases = {}
    unix_skip = set()
    invalid = False
    try:
        with report.open('rb') as stream:
            payload = stream.read(1_000_001)
        if len(payload) > 1_000_000:
            raise ValueError('JUnit report too large')
        xml = ET.fromstring(payload)
        if xml.tag not in ('testsuite', 'testsuites'):
            raise ValueError('Unexpected JUnit root')
        for case in xml.iter('testcase'):
            key = '.'.join((case.get('classname', '').removeprefix('tests.'), case.get('name', '')))
            if key not in expected or key in cases:
                invalid = True
                continue
            if case.find('failure') is not None or case.find('error') is not None:
                cases[key] = 'FAIL'
            elif (skipped := case.find('skipped')) is not None:
                cases[key] = 'SKIPPED'
                if skipped.get('message') == 'Runtime does not permit AF_UNIX sockets':
                    unix_skip.add(key)
            else:
                cases[key] = 'PASS'
    except (OSError, ValueError, ET.ParseError):
        invalid = True
    missing = expected - cases.keys()
    skipped_cases = {key for key, outcome in cases.items() if outcome == 'SKIPPED'}
    transport = {key for key in expected if not key.startswith('test_v41_')}
    if rc or invalid or missing or 'FAIL' in cases.values():
        status = 'FAIL'
    elif skipped_cases == unix_skip and unix_skip and unix_skip <= transport:
        status = 'BLOCKED_RUNTIME'
    elif skipped_cases:
        status = 'FAIL'
    else:
        status = 'PASS_LOCAL'
    return {'status': status, 'cases': {**cases, **dict.fromkeys(sorted(missing), 'NOT_RUN')}}


def uds_result(output, rc):
    try:
        evidence = json.loads(output)
    except (ValueError, TypeError):
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    cases = {f'two_api.{key}': 'NOT_RUN' for key in UDS_CHECKS}
    if rc == 77 and evidence.get('classification') == 'BLOCKED_RUNTIME':
        return {'status': 'BLOCKED_RUNTIME', 'cases': cases}
    if rc == 0 and evidence.get('classification') == 'PASS_LOCAL_UDS' and evidence.get('separate_api_processes') == 3:
        cases = {f'two_api.{key}': 'PASS' if evidence.get(key) is True else 'NOT_RUN' for key in UDS_CHECKS}
        if all(outcome == 'PASS' for outcome in cases.values()):
            return {'status': 'PASS_LOCAL', 'cases': cases}
    return {'status': 'FAIL', 'cases': cases}


def run(gates):
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join((str(ROOT), str(ROOT / 'tests')))}
    for key in ('OPENAI_API_KEY', 'PYTEST_ADDOPTS', 'PYTHONOPTIMIZE'):
        env.pop(key, None)
    records = {}
    with tempfile.TemporaryDirectory(prefix='wfs-evidence-') as tmp:
        report = Path(tmp) / 'focused.xml'
        for name in gates:
            start = time.monotonic()
            args = [sys.executable, *GATES[name]]
            if name == 'focused':
                args.append(f'--junitxml={report}')
            try:
                result = subprocess.run(args, cwd=ROOT, env=env, timeout=55,
                                        stdout=subprocess.PIPE if name == 'uds' else None)
                rc = result.returncode
                if name == 'focused':
                    record = focused_result(report, rc)
                elif name == 'uds':
                    record = uds_result(result.stdout, rc)
                else:
                    record = {'status': 'PASS_LOCAL' if rc == 0 else 'FAIL'}
            except subprocess.TimeoutExpired:
                rc = None
                record = {'status': 'TIMEOUT'}
            records[name] = dict(record, returncode=rc, elapsed_seconds=round(time.monotonic()-start, 3))
    return records


def exit_status(records):
    statuses = {result['status'] for result in records.values()}
    return 1 if statuses & {'FAIL', 'TIMEOUT'} else 77 if 'BLOCKED_RUNTIME' in statuses else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New report path, never overwritten')
    parser.add_argument('--gate', action='append', choices=GATES)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8') as out:
        results = run(tuple(dict.fromkeys(args.gate or DEFAULT)))
        json.dump({'classification': 'LOCAL_ONLY', 'production_admission': 'DENIED',
                   'utc': datetime.now(timezone.utc).isoformat(), 'gates': results}, out, indent=2)
        out.write('\n')
    return exit_status(results)


if __name__ == '__main__':
    raise SystemExit(main())
