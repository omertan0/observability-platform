"""Yük üreticisinin ölçüm, hız ve temizlik sınırları. Ağ bağlantısı açmaz."""
from contextlib import redirect_stderr
import io
from threading import Lock
import time
import unittest
from unittest.mock import patch

from scripts import load_backend as load


class LoadRunnerChecks(unittest.TestCase):
    def test_percentile_nearest_rank_and_empty_sample(self):
        self.assertIsNone(load.percentile([], 0.95))
        self.assertEqual(load.percentile([0.001, 0.002, 0.003], 0.95), 3)
        self.assertEqual(load.percentile([0.010], 0.5), 10)
        self.assertEqual(load.percentile([i / 1000 for i in range(1, 101)], 0.95), 95)

    def test_cli_rejects_path_traversal_and_invalid_limits(self):
        for args in [['--label', '../wrong'], ['--label', 'x/y'], ['--records', '0'],
                     ['--batch-size', '101'], ['--concurrency', '33'], ['--rate', 'nan'],
                     ['--rate', '0.1'], ['--wait-timeout', '0'], ['--metric-value', 'inf']]:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                load.parse_args(args)
        self.assertEqual(load.parse_args(['--records', '12000', '--rate', '200']).rate, 200)

    def test_pacing_uses_record_counts_not_request_counts(self):
        clock = [0.0]
        sleeps = []
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        jobs = [('logs', [0] * 100), ('metrics', [0] * 100), ('logs', [0] * 50)]
        def send(job):
            return ('task', 0.01, len(job[1]), None)
        results = list(load.run_jobs(jobs, send, 1, 200, lambda: clock[0], sleep))
        self.assertEqual(sum(row[2] for row in results), 250)
        self.assertEqual(sleeps, [0, 0.5, 0.5])

    def test_concurrency_is_bounded_and_all_success_results_are_collected(self):
        state = {'active': 0, 'peak': 0}
        lock = Lock()
        def send(job):
            with lock:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
            time.sleep(0.003)
            with lock:
                state['active'] -= 1
            return ('task', 0.003, len(job[1]), None)
        results = list(load.run_jobs([('logs', [0])] * 30, send, 3, 0))
        self.assertEqual(len(results), 30)
        self.assertLessEqual(state['peak'], 3)
        self.assertEqual(state['active'], 0)

    def test_failure_stops_new_submissions_and_preserves_error_result(self):
        calls = []
        def send(job):
            calls.append(job)
            return (None, 0.01, len(job[1]), 'HTTP 503')
        results = list(load.run_jobs([('logs', [0])] * 100, send, 1, 0))
        self.assertEqual(len(calls), 1)
        self.assertEqual(results[0][-1], 'HTTP 503')

    def test_cleanup_rejects_user_services_before_any_database_access(self):
        with patch.object(load, 'get_connection') as connection:
            for service in ['payment-service', 'demo-payment', 'qa-load-', "qa-load-' OR 1=1"]:
                with self.assertRaises(ValueError):
                    load.cleanup_test_data(service, [])
            connection.assert_not_called()
