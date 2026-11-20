"""Offline transport/parser tests: no authenticated API call has been made."""
import importlib.util
import io
import json
import time
import unittest
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'scripts/provider-official-costs-v36.py'
spec=importlib.util.spec_from_file_location('v36_official_costs',FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

START=1762560000
END=START+86400


def page(*, amount='1.25', currency='usd', more=False, cursor=None):
    return {'object':'page','data':[{'object':'bucket','start_time':START,
        'end_time':END,'results':[{'object':'organization.costs.result',
        'amount':{'currency':currency,'value':amount}}]}],
        'has_more':more,'next_page':cursor}


class FakeResponse:
    def __init__(self,url,obj, *, response_url=None, content_type='application/json', status=200):
        self.url=url;self.response_url=response_url or url;self.raw=json.dumps(obj).encode()
        self.headers={'Content-Type':content_type};self.status=status
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return self.response_url
    def read(self,n):return self.raw[:n]


class FakeOpener:
    def __init__(self, pages):self.pages=iter(pages);self.requests=[]
    def open(self,req,timeout):
        self.requests.append(req)
        obj=next(self.pages)
        if isinstance(obj,FakeResponse):return obj
        return FakeResponse(req.full_url,obj)


class OfficialCostsReadOnlyV36(unittest.TestCase):
    def test_safe_two_page_aggregate_never_clears_unknown_charges(self):
        fake=FakeOpener([page(more=True,cursor='next:1'),page(amount='0.75')])
        result=mod.fetch_costs(START,END,'operator-test-token-'+('x'*40),opener=fake)
        self.assertEqual(result['aggregate_usd'],'2.00')
        self.assertEqual(result['page_count'],2)
        self.assertTrue(result['account_scoped_authorized_fetch'])
        self.assertFalse(result['reconciled'])
        self.assertFalse(result['billing_unknown_cleared'])
        self.assertFalse(result['provider_request_ids_available'])
        self.assertFalse(result['provider_hard_cap_verified'])
        self.assertIn('page=next%3A1',fake.requests[1].full_url)
        self.assertEqual({r.get_method() for r in fake.requests},{'GET'})
        self.assertTrue(all(r.full_url.startswith(mod.ENDPOINT+'?') for r in fake.requests))
        self.assertNotIn('operator-test-token',str(result))

    def test_bad_currency_and_nonfinite_amounts_rejected(self):
        for amount,currency in [('NaN','usd'),('-1','usd'),('Infinity','usd'),('1.00','eur')]:
            with self.subTest(amount=amount,currency=currency):
                with self.assertRaises(mod.BillingReadError):
                    mod.fetch_costs(START,END,'test-token-'+('a'*40),
                        opener=FakeOpener([page(amount=amount,currency=currency)]))

    def test_missing_or_bad_credentials_and_time_windows_fail_before_network(self):
        for start,end,key in [(START,END,''),(START,START,'a'*40),(START,START+32*86400,'a'*40)]:
            with self.assertRaises(mod.BillingReadError):
                mod.fetch_costs(start,end,key,opener=FakeOpener([]))

    def test_cursor_replay_refused(self):
        fake=FakeOpener([page(more=True,cursor='same'),page(more=True,cursor='same')])
        with self.assertRaisesRegex(mod.BillingReadError,'Repeated'):
            mod.fetch_costs(START,END,'a'*40,opener=fake)

    def test_redirect_and_html_refused(self):
        class RedirectOpener:
            def open(self,req,timeout):
                return FakeResponse(req.full_url,page(),response_url='https://evil.example/steal')
        with self.assertRaisesRegex(mod.BillingReadError,'Redirect'):
            mod.fetch_costs(START,END,'a'*40,opener=RedirectOpener())
        class HtmlOpener:
            def open(self,req,timeout):
                return FakeResponse(req.full_url,page(),content_type='text/html')
        with self.assertRaisesRegex(mod.BillingReadError,'Unexpected'):
            mod.fetch_costs(START,END,'a'*40,opener=HtmlOpener())

    def test_malformed_or_unbounded_buckets_rejected(self):
        for obj in [[], {'object':'page','data':[], 'has_more':True,'next_page':None},
                    {'object':'page','data':[{'object':'bucket','start_time':0,'end_time':END,'results':[]}],
                    'has_more':False,'next_page':None}]:
            with self.subTest(obj=str(obj)[:40]),self.assertRaises(mod.BillingReadError):
                mod.fetch_costs(START,END,'a'*40,opener=FakeOpener([obj]))

if __name__=='__main__':unittest.main()
