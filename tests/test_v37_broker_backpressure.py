"""Local broker concurrency/URL negative tests; not external TLS acceptance."""
import asyncio
import unittest
from unittest.mock import patch
from types import SimpleNamespace
# Establish the isolated test environment before importing app.config.
from test_system import PASSWORD  # noqa: F401
from app import dynamic_broker


class BrokerPressureV37(unittest.IsolatedAsyncioTestCase):
    async def test_capacity_limited_per_project_and_global(self):
        limiter=dynamic_broker.BrokerLimit(per_project=2,total=3)
        ready=asyncio.Event()
        started=[]
        async def slow(request,pid):
            started.append(pid)
            await ready.wait()
            return pid
        with patch.object(dynamic_broker,'broker_limit',limiter), \
             patch.object(dynamic_broker,'_proxy_approved',side_effect=slow):
            tasks=[asyncio.create_task(dynamic_broker.proxy(None,'proj-A')) for _ in range(2)]
            await asyncio.sleep(0)
            self.assertEqual(limiter._projects,{'proj-A':2})
            with self.assertRaises(dynamic_broker.BrokerOverloaded):
                await dynamic_broker.proxy(None,'proj-A')
            third=asyncio.create_task(dynamic_broker.proxy(None,'proj-B'))
            await asyncio.sleep(0)
            with self.assertRaises(dynamic_broker.BrokerOverloaded):
                await dynamic_broker.proxy(None,'proj-C')
            ready.set()
            self.assertEqual(await asyncio.gather(*tasks,third),['proj-A','proj-A','proj-B'])
        self.assertEqual(limiter._total,0)
        self.assertEqual(limiter._projects,{})

    async def test_exception_releases_limit(self):
        limiter=dynamic_broker.BrokerLimit(per_project=1,total=1)
        async def fail(*a):
            raise dynamic_broker.BrokerUnavailable('bad backend')
        with patch.object(dynamic_broker,'broker_limit',limiter),patch.object(dynamic_broker,'_proxy_approved',side_effect=fail):
            for _ in range(2):
                with self.assertRaises(dynamic_broker.BrokerUnavailable):
                    await dynamic_broker.proxy(None,'proj-A')
            self.assertEqual(limiter._total,0)

    def test_encoded_control_characters_and_unsafe_paths_denied(self):
        cases=[('/%0dHeader:evil',''),('/%0a',''),('/%00',''),('/public','x=%0D%0Aevil'),
               ('/safe','x=%00'),('/%25%32e',''),('/%2Fetc',''),('/.config','')]
        for path,query in cases:
            with self.subTest(path=path,query=query):
                req=SimpleNamespace(scope={'raw_path':path.encode()},url=SimpleNamespace(query=query))
                with self.assertRaises(dynamic_broker.BrokerUnavailable):
                    dynamic_broker.safe_target(req)
        valid=SimpleNamespace(scope={'raw_path':b'/assets/index.html'},url=SimpleNamespace(query='v=2'))
        self.assertEqual(dynamic_broker.safe_target(valid),'/assets/index.html?v=2')

    def test_thread_safe_project_limit(self):
        from concurrent.futures import ThreadPoolExecutor
        limiter=dynamic_broker.BrokerLimit(per_project=3,total=100)
        with ThreadPoolExecutor(max_workers=30) as pool:
            results=list(pool.map(limiter.acquire,['same']*30))
        self.assertEqual(sum(results),3)
        for ok in results:
            if ok:limiter.release('same')
        self.assertEqual(limiter._total,0)

if __name__=='__main__':unittest.main()
