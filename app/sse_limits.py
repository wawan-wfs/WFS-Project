"""Local per-worker bounds for SSE subscriptions.

This protects an individual API worker, not a distributed cluster-wide quota.
No raw session token is retained. Production ingress needs a complementary
shared/edge limit; the SSE endpoint keeps its authorization checks per event.
"""
from __future__ import annotations
import asyncio
import hashlib
import threading

MAX_PER_SESSION = 2
MAX_PER_PROCESS = 64
MAX_EVENTS_PER_CONNECTION = 250


class StreamLimit:
    def __init__(self, *, per_session=MAX_PER_SESSION, total=MAX_PER_PROCESS):
        self.per_session = per_session
        self.total = total
        self._lock = threading.Lock()
        self._active = {}
        self._total = 0

    def acquire(self, token: str) -> str | None:
        # Keep a digest as the short-lived key, never a session secret.
        key = hashlib.sha256(token.encode('utf-8')).hexdigest()
        with self._lock:
            if self._total >= self.total or self._active.get(key, 0) >= self.per_session:
                return None
            self._active[key] = self._active.get(key, 0) + 1
            self._total += 1
        return key

    def release(self, key: str) -> None:
        with self._lock:
            count = self._active.get(key, 0)
            if not count:
                return
            if count == 1:
                del self._active[key]
            else:
                self._active[key] = count - 1
            self._total -= 1


stream_limit = StreamLimit()


class LeasedStream:
    """Releases a reserved SSE slot even if the body iterator never starts.

    Normal async-generator finally blocks do NOT run when a generator is
    closed before its first __anext__. That caused a silent admission leak
    behind custom middleware and abandoned pre-stream responses.
    """
    def __init__(self, inner, limiter: StreamLimit, lease: str):
        self.inner=inner
        self.limiter=limiter
        self.lease=lease
        self.released=False

    def _release(self):
        if not self.released:
            self.released=True
            self.limiter.release(self.lease)

    async def _release_async(self):
        if self.released:return
        async_release=getattr(self.limiter,'release_async',None)
        if async_release is None:self._release()
        else:
            self.released=True
            # A disconnect may already be cancelling the caller.
            task=asyncio.create_task(async_release(self.lease))
            await asyncio.shield(task)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.inner.__anext__()
        except BaseException:
            await self._release_async()
            raise

    async def aclose(self):
        try:
            await self.inner.aclose()
        finally:
            await self._release_async()

    def __del__(self):
        if not self.released and hasattr(self.limiter,'release_async'):
            try: loop=asyncio.get_running_loop()
            except RuntimeError: return  # Shared ledger TTL bounds abandonment at shutdown.
            self.released=True
            loop.run_in_executor(None,self.limiter.release,self.lease)
        else:self._release()
