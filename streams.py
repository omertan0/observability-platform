"""Log ve metrik görünümlerindeki değişiklikleri SSE üzerinden bildirir."""
import asyncio
from hashlib import sha256
import json
import logging
from time import monotonic

import anyio
from psycopg import OperationalError
from psycopg.errors import LockNotAvailable, QueryCanceled, UndefinedTable
from psycopg_pool import PoolTimeout, TooManyRequests

from database import get_connection
from security import stream_access_valid
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)
POLL_SECONDS = 2
HEARTBEAT_SECONDS = 15
DATABASE_ERRORS = (OperationalError, LockNotAvailable, QueryCanceled, UndefinedTable,
                   PoolTimeout, TooManyRequests)


def logs_revision(clauses=(), values=()):
    # Tabloyla aynı sıralama. Henüz commit edilmemiş satırlar görünmez.
    # Kimlikler commit sırasıyla gelmeyebilir; yalnızca max(id) izlemeyiz.
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT timestamp, id FROM logs" + where + " ORDER BY timestamp DESC, id DESC LIMIT 21",
            values,
        ).fetchall()
    signature = "|".join(f"{timestamp.isoformat()}:{record_id}" for timestamp, record_id in rows)
    return sha256(signature.encode()).hexdigest()


def metrics_revision(clauses=(), values=(), limit=100):
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT timestamp, id FROM metrics" + where
            + " ORDER BY timestamp DESC, id DESC LIMIT %s",
            [*values, limit + 1],
        ).fetchall()
    signature = "|".join(f"{timestamp.isoformat()}:{record_id}" for timestamp, record_id in rows)
    return sha256(signature.encode()).hexdigest()


def sse_event(name, data, event_id=None):
    identifier = f"id: {event_id}\n" if event_id is not None else ""
    return f"{identifier}event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def log_events(request, clauses=(), values=()):
    async for event in revision_events(request, logs_revision, "logs_changed", clauses, values):
        yield event


async def metric_events(request, clauses=(), values=(), limit=100):
    async for event in revision_events(request, metrics_revision, "metrics_changed", clauses, values, limit):
        yield event


async def revision_events(request, revision_function, event_name, *arguments):
    previous = None
    unavailable = False
    heartbeat_at = monotonic()
    yield "retry: 3000\n\n"
    while not await request.is_disconnected():
        try:
            authorized = await stream_access_valid(request)
        except RedisError:
            yield sse_event('stream_status', {'status': 'unavailable'})
            await asyncio.sleep(POLL_SECONDS)
            continue
        if not authorized:
            yield sse_event('auth_expired', {'status': 'unauthorized'})
            return
        try:
            # Senkron DB sorgusu, API'nin async döngüsünü durdurmaz.
            revision = await anyio.to_thread.run_sync(revision_function, *arguments)
        except DATABASE_ERRORS:
            if not unavailable:
                logger.warning("Canlı akış veritabanına erişemiyor: %s", event_name)
                yield sse_event("stream_status", {"status": "unavailable"})
            unavailable = True
        else:
            # Her bağlantıda ve DB kurtarmasında yeniden eşitleme yapılır.
            if unavailable or revision != previous:
                yield sse_event(event_name, {"revision": revision}, revision)
                previous = revision
            unavailable = False
        if monotonic() - heartbeat_at >= HEARTBEAT_SECONDS:
            yield ": keepalive\n\n"
            heartbeat_at = monotonic()
        # Bağlantı açık kalır; beklerken DB bağlantısı havuzda kalır.
        await asyncio.sleep(POLL_SECONDS)
