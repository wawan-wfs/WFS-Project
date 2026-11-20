#!/usr/bin/env python3
"""Operator-only READ-ONLY fetch of OpenAI organization aggregate costs.

Requires an explicitly supplied operator admin credential and confirmation.
Never clears billing_unknown, assigns cost to WFS tenants, or approves invoices.
No network request occurs by importing this module or running --help.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://api.openai.com/v1/organization/costs'
MAX_PAGES = 50
MAX_PAGE_BYTES = 1024 * 1024
MAX_WINDOW = 31 * 24 * 3600
CONFIRM = 'READ_ONLY_OFFICIAL_COSTS'


class BillingReadError(ValueError):
    pass


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BillingReadError('Redirect refused for authenticated billing')


def _usd(value) -> Decimal:
    # Boolean, negative, NaN and infinity must not enter an audit record.
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise BillingReadError('Invalid provider USD amount')
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise BillingReadError('Invalid provider USD amount') from None
    if not amount.is_finite() or amount < 0 or amount > 100_000_000:
        raise BillingReadError('Invalid provider USD amount')
    return amount


def _validate_page(data: object, start: int, end: int) -> tuple[Decimal, int, str | None]:
    if not isinstance(data, dict) or data.get('object') != 'page':
        raise BillingReadError('Malformed provider page')
    buckets = data.get('data')
    if not isinstance(buckets, list) or len(buckets) > 100:
        raise BillingReadError('Unbounded or invalid provider buckets')
    subtotal = Decimal('0')
    for bucket in buckets:
        if not isinstance(bucket, dict) or bucket.get('object') != 'bucket':
            raise BillingReadError('Malformed provider cost bucket')
        begin, finish = bucket.get('start_time'), bucket.get('end_time')
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (begin, finish)):
            raise BillingReadError('Invalid provider bucket dates')
        if begin < start or finish > end or not begin < finish:
            raise BillingReadError('Provider bucket outside requested range')
        rows = bucket.get('results')
        if not isinstance(rows, list) or len(rows) > 1000:
            raise BillingReadError('Malformed provider cost entries')
        for row in rows:
            if not isinstance(row, dict) or row.get('object') != 'organization.costs.result':
                raise BillingReadError('Unexpected provider cost record')
            amount = row.get('amount')
            if not isinstance(amount, dict) or amount.get('currency') != 'usd':
                raise BillingReadError('Provider currency not USD')
            subtotal += _usd(amount.get('value'))
    more = data.get('has_more')
    if not isinstance(more, bool):
        raise BillingReadError('Invalid provider pagination marker')
    next_page = data.get('next_page')
    if more and (not isinstance(next_page, str) or len(next_page) > 1024 or not next_page):
        raise BillingReadError('Missing/unsafe provider page cursor')
    if not more and next_page is not None:
        raise BillingReadError('Unexpected terminal page cursor')
    return subtotal, len(buckets), next_page


def fetch_costs(start: int, end: int, admin_key: str, *, opener=None) -> dict:
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)):
        raise BillingReadError('Invalid requested interval')
    if start <= 0 or end <= start or end-start > MAX_WINDOW or end > int(datetime.now(timezone.utc).timestamp()) + 86400:
        raise BillingReadError('Interval must be valid and at most 31 days')
    if not isinstance(admin_key, str) or not (20 <= len(admin_key) <= 512) or '\n' in admin_key or '\r' in admin_key:
        raise BillingReadError('Operator admin credential missing or invalid')
    opener = opener or urllib.request.build_opener(NoRedirects())
    seen = set()
    cursor = None
    total = Decimal('0')
    page_count = bucket_count = 0
    raw_digests = []
    for _ in range(MAX_PAGES):
        args = {'start_time': str(start), 'end_time': str(end), 'limit': '100'}
        if cursor is not None:
            args['page'] = cursor
        url = ENDPOINT + '?' + urllib.parse.urlencode(args)
        req = urllib.request.Request(url, headers={
            'Authorization': 'Bearer ' + admin_key, 'Accept': 'application/json',
            'User-Agent': 'WFS-PROJECT-operator-read-only/3.6'}, method='GET')
        # Caller tests can supply an in-memory opener. Production uses validated HTTPS.
        try:
            with opener.open(req, timeout=15) as response:
                if response.geturl() != url:
                    raise BillingReadError('Redirect or alternate billing host refused')
                if response.status != 200 or not response.headers.get('Content-Type', '').lower().startswith('application/json'):
                    raise BillingReadError('Unexpected provider response')
                raw = response.read(MAX_PAGE_BYTES+1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BillingReadError('Provider billing request failed (details withheld)') from None
        if len(raw) > MAX_PAGE_BYTES:
            raise BillingReadError('Oversized provider page')
        try:
            page = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise BillingReadError('Malformed provider JSON') from None
        page_total, count, next_cursor = _validate_page(page, start, end)
        raw_digests.append(hashlib.sha256(raw).hexdigest())
        total += page_total
        bucket_count += count
        page_count += 1
        if not page['has_more']:
            return {
                'classification':'AUTHENTICATED AGGREGATE PROVIDER COST READ; NOT PER-RESPONSE RECONCILIATION',
                'source_endpoint':ENDPOINT,
                'read_only':True,
                'account_scoped_authorized_fetch':True,
                'provider_request_ids_available':False,
                'billing_unknown_cleared':False,
                'reconciled':False,
                'provider_hard_cap_verified':False,
                'interval_start':start, 'interval_end':end,
                'page_count':page_count, 'bucket_count':bucket_count,
                'aggregate_usd':str(total), 'page_sha256':raw_digests,
                'fetched_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
        if next_cursor in seen:
            raise BillingReadError('Repeated provider pagination cursor')
        seen.add(next_cursor)
        cursor = next_cursor
    raise BillingReadError('Provider page count exceeded safe bound')


def main() -> int:
    parser=argparse.ArgumentParser(description='Operator-only official aggregate provider costs (read-only).')
    parser.add_argument('--start-epoch',type=int,required=True)
    parser.add_argument('--end-epoch',type=int,required=True)
    parser.add_argument('--confirm',default='',help='Explicit operator confirmation for authenticated read')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.confirm != CONFIRM:
        parser.error('Explicit --confirm READ_ONLY_OFFICIAL_COSTS is required')
    key=os.environ.get('WFS_OPENAI_ADMIN_KEY','')
    try:
        data=fetch_costs(args.start_epoch,args.end_epoch,key)
        # Exclusive creation, no symlink following, private local output.
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(data,out,indent=2);out.write('\n')
        print(json.dumps({'report':str(args.output),'read_only':True,'reconciled':False,
                          'aggregate_provider_billing':True}))
        return 0
    except (BillingReadError, OSError) as exc:
        print('DENIED: official billing read/report failed (no credential or provider details printed)',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
