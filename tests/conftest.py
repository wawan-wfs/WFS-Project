"""Mark unavailable host capabilities explicitly without relaxing app checks."""
import os
import socket
import pytest

UDS_MODULES={'test_v31_dynamic_broker.py','test_v38_broker_deadlines.py','test_v40_sse_admission.py'}
ROOT_GC_TESTS={'test_dry_run_only_returns_metadata_without_deleting','test_purge_requires_cooling_off_after_quarantine',
               'test_quarantine_retry_is_detectable_and_scoped','test_recent_attempt_not_eligible'}


def pytest_collection_modifyitems(items):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
            uds=True
    except (AttributeError,OSError):
        uds=False
    for item in items:
        file=item.path.name
        if not uds and (file in UDS_MODULES or (file=='test_v32_remote_authority.py' and
            ('DynamicPreviewV31' in item.nodeid or 'test_dynamic_gateway_works_without_local_database_copy' in item.nodeid))):
            item.add_marker(pytest.mark.skip(reason='Runtime does not permit AF_UNIX sockets'))
        if not hasattr(os,'geteuid') or os.geteuid()!=0:
            if file=='test_v35_admission_lock.py' or (file=='test_v35_runner_gc.py' and item.name in ROOT_GC_TESTS):
                item.add_marker(pytest.mark.skip(reason='Fixture needs a real UID 0-owned staging tree'))
