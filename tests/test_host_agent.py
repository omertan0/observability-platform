import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch
from datetime import datetime, timezone

from host_agent import build_metrics, disk_counters, memory_percent, parse_cpu_counters, post_metrics, read_snapshot
from models import MetricInput


class HostMetricParsingTests(unittest.TestCase):
    def test_cpu_usage_is_calculated_from_counter_deltas(self):
        before = parse_cpu_counters('cpu 100 0 50 850 0 0 0 0 0 0')
        after = parse_cpu_counters('cpu 200 0 100 1600 0 0 0 0 0 0')
        metrics = build_metrics(
            before=(before, (1000, 250), (1000, 2000)),
            after=(after, (1000, 250), (1500, 2600)),
            elapsed_seconds=2,
            service='artersoft-vm',
            host='vm-test',
            timestamp='2026-11-02T10:00:00+00:00',
            response_time_ms=40.0,
        )
        cpu = next(item for item in metrics if item['name'] == 'cpu_usage')
        self.assertAlmostEqual(cpu['value'], 16.6666667, places=3)
        self.assertEqual(cpu['unit'], 'percent')

    def test_memory_percent_uses_memavailable(self):
        text = 'MemTotal: 1000 kB\nMemFree: 50 kB\nMemAvailable: 250 kB\n'
        self.assertEqual(memory_percent(text), 75.0)

    def test_disk_counters_include_only_top_level_host_devices(self):
        text = (
            '8 0 sda 100 0 1000 10 200 0 2000 20 0 30 30\n'
            '8 1 sda1 50 0 500 5 100 0 1000 10 0 15 15\n'
            '7 0 loop0 0 0 9999 0 0 0 9999 0 0 0 0\n'
        )
        self.assertEqual(disk_counters(text, {'sda'}), (1000, 2000))

    def test_build_metrics_emits_valid_tagged_metrics_with_real_units(self):
        before = (parse_cpu_counters('cpu 100 0 50 850 0 0 0 0 0 0'), (1000, 250), (1000, 2000))
        after = (parse_cpu_counters('cpu 200 0 100 1600 0 0 0 0 0 0'), (1000, 250), (1500, 2600))
        metrics = build_metrics(before, after, 2, 'artersoft-vm', 'vm-test', '2026-11-02T10:00:00+00:00', 40.0)
        self.assertEqual({(m['name'], m['unit']) for m in metrics}, {
            ('cpu_usage', 'percent'), ('memory_usage', 'percent'),
            ('disk_read_bytes_per_second', 'bytes_per_second'),
            ('disk_write_bytes_per_second', 'bytes_per_second'), ('response_time', 'ms'),
        })
        self.assertEqual(len(metrics), 5)
        for item in metrics:
            self.assertEqual(item['service'], 'artersoft-vm')
            self.assertEqual(item['tags'], {'source': 'host-agent', 'host': 'vm-test'})
            MetricInput.model_validate(item)

    def test_counter_reset_does_not_create_negative_cpu_or_disk_rates(self):
        before = (parse_cpu_counters('cpu 200 0 100 1600 0 0 0 0 0 0'), (1000, 250), (1500, 2600))
        after = (parse_cpu_counters('cpu 100 0 50 850 0 0 0 0 0 0'), (1000, 250), (100, 100))
        metrics = build_metrics(before, after, 2, 'artersoft-vm', 'vm-test', '2026-11-02T10:00:00+00:00', None)
        self.assertTrue(all(item['value'] >= 0 for item in metrics))

    def test_invalid_elapsed_time_is_rejected(self):
        with self.assertRaises(ValueError):
            build_metrics((None, (100, 50), (0, 0)), (None, (100, 50), (0, 0)), 0,
                          'artersoft-vm', 'vm-test', datetime.now(timezone.utc).isoformat(), None)

    def test_http_timeout_is_reported_without_leaking_the_ingest_key(self):
        secret = 'do-not-print-this-key'
        with patch('host_agent.urlopen', side_effect=TimeoutError(secret)):
            with self.assertRaises(RuntimeError) as caught:
                post_metrics('http://api:8000', secret, [])
        self.assertNotIn(secret, str(caught.exception))

    def test_snapshot_reads_only_the_mounted_host_roots(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc = root / 'proc'
            sys = root / 'sys'
            proc.mkdir()
            block = sys / 'block'
            block.mkdir(parents=True)
            (block / 'sda').mkdir()
            (block / 'loop0').mkdir()
            (proc / 'stat').write_text('cpu 100 0 50 850 0 0 0 0 0 0\n')
            (proc / 'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 250 kB\n')
            (proc / 'diskstats').write_text(
                '8 0 sda 100 0 1000 10 200 0 2000 20 0 30 30\n'
                '7 0 loop0 0 0 9999 0 0 0 9999 0 0 0 0\n')
            snapshot = read_snapshot(proc, sys)
        self.assertEqual(snapshot, ((1000, 850), (1000, 250), (1000, 2000)))

    def test_batch_post_uses_ingest_auth_and_validates_task_receipt(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received['path'] = self.path
                received['auth'] = self.headers.get('Authorization')
                received['content_type'] = self.headers.get('Content-Type')
                received['body'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                payload = json.dumps({'task_id': 'task-1', 'record_count': len(received['body'])}).encode()
                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.handle_request)
        thread.start()
        try:
            task_id = post_metrics(f'http://127.0.0.1:{server.server_port}', 'secret-key', [{'name': 'cpu_usage'}])
        finally:
            thread.join(timeout=2)
            server.server_close()
        self.assertEqual(task_id, 'task-1')
        self.assertEqual(received['path'], '/metrics/batch')
        self.assertEqual(received['auth'], 'Bearer secret-key')
        self.assertEqual(received['content_type'], 'application/json')
        self.assertEqual(received['body'], [{'name': 'cpu_usage'}])


if __name__ == '__main__':
    unittest.main()
