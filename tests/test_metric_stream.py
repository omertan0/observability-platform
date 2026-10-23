"""Grafikle aynı metrik filtresi/penceresi ve gerçek worker sonrası SSE kontrolü."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4

from test_backend import BASE_URL, request, wait_for, admin_client
urlopen = admin_client.open
from test_stream import next_event
from celery_app import celery_app
from database import get_connection
from queries import metric_filters
from streams import metrics_revision
from tasks import insert_record


class MetricStreamChecks(unittest.TestCase):
    def setUp(self):
        self.service = 'qa-metric-stream-' + uuid4().hex
        self.task_ids = []
        self.params = {'service': self.service, 'name': 'cpu_usage', 'unit': 'percent', 'limit': 100}

    def tearDown(self):
        with get_connection() as conn:
            conn.execute('DELETE FROM alerts WHERE service = %s', (self.service,))
            conn.execute('DELETE FROM alert_states WHERE service = %s', (self.service,))
            conn.execute('DELETE FROM metrics WHERE service = %s', (self.service,))
            if self.task_ids:
                conn.execute('DELETE FROM processed_tasks WHERE task_id = ANY(%s::uuid[])', (self.task_ids,))
        for task_id in self.task_ids:
            celery_app.AsyncResult(task_id).forget()

    def body(self):
        return {'timestamp': datetime.now(timezone.utc).isoformat(), 'service': self.service,
                'name': 'cpu_usage', 'unit': 'percent', 'value': 40.0, 'tags': {'test': 'metric-stream'}}

    def test_01_commit_filters_queue_and_reconnect(self):
        query = '?' + urlencode(self.params)
        with urlopen(BASE_URL + '/stream/metrics' + query, timeout=12) as response, ThreadPoolExecutor(max_workers=1) as executor:
            self.assertTrue(response.headers['Content-Type'].startswith('text/event-stream'))
            initial = next_event(response)
            self.assertEqual(initial['event'], 'metrics_changed')
            with get_connection() as conn:
                # Başka metrik adı ve aynı ada sahip farklı birim grafiği değiştirmez.
                for change in ({'name': 'latency', 'unit': 'ms'}, {'unit': 'ratio'}):
                    insert_record(conn, 'metric', {**self.body(), **change, 'received_at': datetime.now(timezone.utc).isoformat()})
            pending = executor.submit(next_event, response)
            with self.assertRaises(TimeoutError):
                pending.result(timeout=2.6)
            with get_connection() as conn:
                insert_record(conn, 'metric', {**self.body(), 'received_at': datetime.now(timezone.utc).isoformat()})
                # Doğru filtreye uysa bile commit öncesi bildirim yok.
                with self.assertRaises(TimeoutError):
                    pending.result(timeout=2.6)
            committed = pending.result(timeout=8)
            self.assertNotEqual(committed['id'], initial['id'])
            code, queued = request('POST', '/metrics', {**self.body(), 'value': 42.0})
            self.assertEqual(code, 202)
            self.task_ids.append(queued['task_id'])
            worker_event = next_event(response)
            self.assertNotEqual(worker_event['id'], committed['id'])
            _, page = request('GET', '/metrics', params=self.params)
            self.assertEqual([item['value'] for item in page['items']], [42.0, 40.0])
            wait_for(lambda: request('GET', '/tasks/' + queued['task_id'])[1]['successful'])
        with urlopen(BASE_URL + '/stream/metrics' + query, timeout=12) as response:
            self.assertEqual(next_event(response)['id'], worker_event['id'])

    def test_02_window_matches_chart_and_older_rows_do_not_change_it(self):
        clauses, values = metric_filters(self.service, 'cpu_usage', 'percent')
        now = datetime.now(timezone.utc)
        with get_connection() as conn:
            for index in range(100):
                insert_record(conn, 'metric', {**self.body(), 'timestamp': (now - timedelta(seconds=index)).isoformat(), 'received_at': now.isoformat()})
        before = metrics_revision(clauses, values, 100)
        _, page_before = request('GET', '/metrics', params=self.params)
        self.assertFalse(page_before['has_more'])
        with get_connection() as conn:
            insert_record(conn, 'metric', {**self.body(), 'timestamp': (now - timedelta(hours=1)).isoformat(), 'received_at': now.isoformat()})
        after = metrics_revision(clauses, values, 100)
        self.assertNotEqual(before, after)
        _, page_after = request('GET', '/metrics', params=self.params)
        self.assertEqual(page_before['items'], page_after['items'])
        self.assertTrue(page_after['has_more'])
        with get_connection() as conn:
            insert_record(conn, 'metric', {**self.body(), 'timestamp': (now - timedelta(hours=2)).isoformat(), 'received_at': now.isoformat()})
        self.assertEqual(metrics_revision(clauses, values, 100), after)

    def test_03_validation_before_stream_headers(self):
        for params in ({'limit': 0}, {'limit': 201}, {'name': ''}, {'unit': ''}, {'service': ' '},
                       {'tags': '[]'}, {'start': '2026-10-18T14:00:00'},
                       {'start': '2026-10-18T15:00:00Z', 'end': '2026-10-18T14:00:00Z'}):
            with self.subTest(params=params):
                self.assertEqual(request('GET', '/stream/metrics', params=params)[0], 422)
