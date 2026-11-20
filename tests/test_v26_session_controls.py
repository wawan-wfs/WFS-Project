"""v2.6 session inventory, device labels and targeted account revocation regressions."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_system import PASSWORD
from app import store
from app.main import app


class SessionControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();path=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'wfs.sqlite3'),
                      patch.object(store,'PROJECTS',path/'projects')]
        for patcher in self.patches:patcher.start()
        store.init_db()
        self.clients=[]

    def tearDown(self):
        for client in self.clients:client.__exit__(None,None,None)
        for patcher in reversed(self.patches):patcher.stop()
        self.tmp.cleanup()

    def login(self,user='admin',password=PASSWORD,ua='WFS Test Browser'):
        client=TestClient(app);client.__enter__();self.clients.append(client)
        response=client.post('/api/login',json={'username':user,'password':password},headers={'user-agent':ua})
        self.assertEqual(response.status_code,200,response.text)
        return client,{'X-WFS-CSRF':response.json()['csrf']}

    def test_other_session_revocation_and_no_secret_exposure(self):
        first,h1=self.login(ua='First Chromium')
        second,h2=self.login(ua='Second Edge')
        listing=first.get('/api/sessions')
        self.assertEqual(listing.status_code,200)
        sessions=listing.json()['sessions']
        self.assertEqual(len(sessions),2)
        self.assertEqual(sum(s['current'] for s in sessions),1)
        self.assertTrue(all(len(s['id'])==20 for s in sessions))
        self.assertNotIn('id_hash',listing.text)
        self.assertEqual(first.delete('/api/sessions/ffffffffffffffffffff').status_code,403)
        second_id=next(s['id'] for s in sessions if not s['current'])
        self.assertEqual(first.delete('/api/sessions/'+second_id,headers=h1).status_code,200)
        self.assertEqual(second.get('/api/session').json()['authenticated'],False)
        self.assertEqual(first.get('/api/session').json()['authenticated'],True)
        self.assertEqual(first.delete('/api/sessions/'+second_id,headers=h1).status_code,404)
        self.assertEqual(first.post('/api/sessions/revoke-others',headers=h1).json()['revoked_count'],0)

    def test_all_other_sessions_and_account_separation(self):
        first,h1=self.login()
        second,_=self.login()
        third,_=self.login()
        account=store.provision_organization('third-org','Third Organization','third_user',
                            __import__('app.auth',fromlist=['hash_password']).hash_password('Unique123456789!'))
        other,h_other=self.login('third_user','Unique123456789!')
        foreign=other.get('/api/sessions').json()['sessions'][0]['id']
        self.assertEqual(first.delete('/api/sessions/'+foreign,headers=h1).status_code,404)
        self.assertEqual(first.post('/api/sessions/revoke-others',headers=h1).json()['revoked_count'],2)
        self.assertFalse(second.get('/api/session').json()['authenticated'])
        self.assertFalse(third.get('/api/session').json()['authenticated'])
        self.assertTrue(other.get('/api/session').json()['authenticated'])
        self.assertEqual(first.get('/api/sessions').json()['sessions'][0]['current'],True)
        self.assertTrue(account)

    def test_policy_mfa_setup_session_can_review_and_revoke_sessions(self):
        first,h1=self.login()
        second,_=self.login()
        store.set_organization_mfa_policy('default',True)
        self.assertEqual(first.get('/api/projects').status_code,403)
        self.assertEqual(first.get('/api/sessions').status_code,200)
        self.assertEqual(first.post('/api/sessions/revoke-others',headers=h1).json()['revoked_count'],1)
        self.assertFalse(second.get('/api/session').json()['authenticated'])


if __name__=='__main__':unittest.main()
