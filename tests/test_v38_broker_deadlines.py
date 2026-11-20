"""Local real Unix-socket slow-client tests. Not a public TLS or Docker test."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_system import PASSWORD  # initialize test-only environment before application modules
from app import dynamic_broker as broker

PID = 'a' * 20


class Request:
    method = 'GET'
    headers = {'accept': 'text/plain', 'cookie': 'private-session', 'authorization': 'secret'}
    scope = {'raw_path': b'/status'}
    url = SimpleNamespace(query='')
    async def stream(self):
        if False: yield b''


class SlowBrokerV38(unittest.IsolatedAsyncioTestCase):
    async def test_total_request_body_deadline_rejects_slow_trickle(self):
        class Slow(Request):
            async def stream(self):
                for _ in range(50):
                    await asyncio.sleep(.02)
                    yield b'x'
        with patch.object(broker, 'BODY_DEADLINE_SECONDS', .07):
            with self.assertRaisesRegex(broker.BrokerUnavailable, 'deadline'):
                await broker._request_body(Slow())

    async def test_real_unix_transport_and_strip_auth(self):
        got=[]
        async def handle(reader, writer):
            data=await reader.readuntil(b'\r\n\r\n')
            got.append(data)
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\nContent-Type: text/plain\r\n\r\nPASS')
            await writer.drain()
            writer.close()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'upstream.sock'
            server=await asyncio.start_unix_server(handle,str(path))
            try:
                with patch.object(broker,'project_socket',return_value=path), \
                     patch.dict(os.environ,{'WFS_PREVIEW_SOCKET_UID':str(os.getuid())}):
                    result=await broker.proxy(Request(),PID)
                self.assertEqual(result.body,b'PASS')
                self.assertEqual(result.status_code,200)
                data=got[0].lower()
                self.assertNotIn(b'cookie',data)
                self.assertNotIn(b'authorization',data)
                self.assertNotIn(b'x-forwarded-',data)
            finally:
                server.close();await server.wait_closed()
        self.assertEqual(broker.broker_limit._total,0)

    async def test_slow_upstream_aborted_and_slot_released(self):
        entered=asyncio.Event()
        done=asyncio.Event()
        async def handle(reader,writer):
            try:
                await reader.readuntil(b'\r\n\r\n')
                entered.set()
                writer.write(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n')
                await writer.drain()
                # Slow-trickle output must not extend the total deadline.
                for _ in range(50):
                    writer.write(b'1\r\nx\r\n')
                    await writer.drain()
                    await asyncio.sleep(.03)
            except (ConnectionError,OSError):pass
            finally:
                writer.close()
                done.set()
        limiter=broker.BrokerLimit(per_project=1,total=1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'slow.sock'
            server=await asyncio.start_unix_server(handle,str(path))
            try:
                with patch.object(broker,'project_socket',return_value=path), \
                     patch.object(broker,'broker_limit',limiter), \
                     patch.object(broker,'UPSTREAM_DEADLINE_SECONDS',.12), \
                     patch.dict(os.environ,{'WFS_PREVIEW_SOCKET_UID':str(os.getuid())}):
                    with self.assertRaisesRegex(broker.BrokerUnavailable,'deadline'):
                        await broker.proxy(Request(),PID)
                    self.assertTrue(entered.is_set())
                    self.assertEqual(limiter._total,0)
                    await asyncio.wait_for(done.wait(),1)
            finally:
                server.close();await server.wait_closed()

    async def test_cancelled_client_closes_socket_and_releases_slot(self):
        entered=asyncio.Event()
        disconnected=asyncio.Event()
        async def handle(reader,writer):
            await reader.readuntil(b'\r\n\r\n')
            entered.set()
            try:
                if await reader.read() == b'':
                    disconnected.set()
            finally: writer.close()
        limiter=broker.BrokerLimit(per_project=1,total=1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cancel.sock'
            server=await asyncio.start_unix_server(handle,str(path))
            try:
                with patch.object(broker,'project_socket',return_value=path), \
                     patch.object(broker,'broker_limit',limiter), \
                     patch.dict(os.environ,{'WFS_PREVIEW_SOCKET_UID':str(os.getuid())}):
                    task=asyncio.create_task(broker.proxy(Request(),PID))
                    await asyncio.wait_for(entered.wait(),1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):await task
                    self.assertEqual(limiter._total,0)
                    await asyncio.wait_for(disconnected.wait(),1)
            finally:
                server.close();await server.wait_closed()

if __name__ == '__main__':unittest.main()
