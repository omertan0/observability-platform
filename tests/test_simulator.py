"""Simülatörün veri üretimi, sınırlı çalışma ve worker bekleme davranışı."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID

from models import LogInput, MetricInput
from scripts import simulate_telemetry as sim


class FakeClock:
    def __init__(self):
        self.value = 0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class SimulatorChecks(unittest.TestCase):
    def test_generated_records_match_api_models_and_selected_scenario(self):
        now = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)
        for mode in ('normal', 'mixed', 'incident'):
            rng = random.Random(42)
            for sequence in range(1, 11):
                logs, metrics = sim.make_cycle(rng, ['demo-payment', 'demo-orders'], sequence, mode, 'test-run', now)
                self.assertEqual(len(logs), 2)
                self.assertEqual(len(metrics), 6)
                incident = mode == 'incident' or (mode == 'mixed' and sequence % 5 == 0)
                for log in logs:
                    LogInput.model_validate(log)
                    self.assertEqual(log['level'] == 'ERROR', incident)
                    self.assertEqual(log['stack_trace'] is not None, incident)
                    self.assertEqual(log['timestamp'], now.isoformat())
                    self.assertEqual(log['tags']['run_id'], 'test-run')
                    self.assertEqual(log['tags']['sequence'], sequence)
                for metric in metrics:
                    MetricInput.model_validate(metric)
                    if metric['name'] == 'cpu_usage':
                        self.assertEqual(metric['value'] > 85, incident)
                self.assertEqual({(item['name'], item['unit']) for item in metrics},
                                 {('cpu_usage', 'percent'), ('memory_usage', 'percent'), ('response_time', 'ms')})

    def test_seed_reproduces_values_and_new_cycles_get_new_timestamps(self):
        first_time = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)
        next_time = datetime(2026, 10, 18, 21, 1, tzinfo=timezone.utc)
        first = sim.make_cycle(random.Random(7), ['demo'], 1, 'normal', 'run', first_time)
        self.assertEqual(first, sim.make_cycle(random.Random(7), ['demo'], 1, 'normal', 'run', first_time))
        next_cycle = sim.make_cycle(random.Random(7), ['demo'], 2, 'normal', 'run', next_time)
        self.assertNotEqual(first[1][0]['timestamp'], next_cycle[1][0]['timestamp'])

    def test_invalid_cli_limits_and_urls_are_rejected(self):
        invalid = [['--duration', 'nan'], ['--duration', '-1'], ['--interval', '0'],
                   ['--interval', 'inf'], ['--worker-timeout', '0'], ['--services', 'demo', ' demo '],
                   ['--services', ' '], ['--api-url', 'http://[bad'], ['--api-url', 'file:///tmp/api'],
                   ['--api-url', 'http://localhost:bad'], ['--api-url', 'http://user:secret@localhost']]
        for args in invalid:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                sim.parse_args(args)
        self.assertEqual(sim.parse_args(['--duration', '0']).duration, 0)

    def test_worker_success_is_distinct_from_queue_acceptance_and_timeout_is_bounded(self):
        clock = FakeClock()
        stats = {'confirmed_logs': 0, 'confirmed_metrics': 0, 'failed_records': 0}
        pending = {'task': ('logs', 2)}
        with patch.object(sim.ApiClient, 'task_state', return_value='PENDING'):
            with self.assertRaises(sim.SimulatorError):
                sim.wait_for_tasks(sim.ApiClient('http://localhost'), pending, stats, 1, clock.now, clock.sleep)
        self.assertEqual(stats['confirmed_logs'], 0)
        self.assertEqual(len(pending), 1)
        self.assertEqual(clock.value, 1)
        with patch.object(sim.ApiClient, 'task_state', return_value='SUCCESS'):
            sim.wait_for_tasks(sim.ApiClient('http://localhost'), pending, stats, 1, clock.now, clock.sleep)
        self.assertEqual(stats['confirmed_logs'], 2)
        self.assertFalse(pending)

    def test_unknown_post_response_is_not_retried(self):
        client = sim.ApiClient('http://localhost')
        with patch.object(client, 'request', return_value=(202, {'task_id': 'not-a-uuid'})) as request:
            with self.assertRaises(sim.SimulatorError):
                client.submit('logs', [{}])
            request.assert_called_once()

    def test_duration_run_counts_confirmed_records_and_writes_report(self):
        clock = FakeClock()
        with TemporaryDirectory() as directory, patch.object(sim, 'ApiClient') as client_type, \
                patch.object(sim.time, 'monotonic', clock.now), patch.object(sim.time, 'sleep', clock.sleep), redirect_stdout(io.StringIO()):
            client = client_type.return_value
            client.submit.side_effect = [str(UUID(int=index)) for index in range(1, 101)]
            client.task_state.return_value = 'SUCCESS'
            report = Path(directory) / 'summary.json'
            code = sim.main(['--duration', '1', '--interval', '0.2', '--report', str(report)])
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(code, 0)
            self.assertEqual(data['cycles_completed'], 5)
            self.assertEqual(data['confirmed_logs'], 5)
            self.assertEqual(data['confirmed_metrics'], 15)
            self.assertEqual(data['unconfirmed_records'], 0)
            self.assertTrue(data['successful'])
            self.assertEqual(client.submit.call_count, 10)

    def test_worker_failure_stops_production_and_keeps_unconfirmed_counts(self):
        with TemporaryDirectory() as directory, patch.object(sim, 'ApiClient') as client_type, \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            client = client_type.return_value
            client.submit.side_effect = ['log-task', 'metric-task']
            client.task_state.return_value = 'FAILURE'
            report = Path(directory) / 'summary.json'
            code = sim.main(['--duration', '60', '--report', str(report)])
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(code, 1)
            self.assertEqual(client.submit.call_count, 2)
            self.assertEqual(data['failed_records'], 1)
            self.assertEqual(data['unconfirmed_records'], 3)
            self.assertEqual(data['confirmed_logs'], 0)
            self.assertFalse(data['successful'])

    def test_ctrl_c_stops_without_resending_and_reports_pending_records(self):
        with TemporaryDirectory() as directory, patch.object(sim, 'ApiClient') as client_type, redirect_stdout(io.StringIO()):
            client = client_type.return_value
            client.submit.side_effect = ['log-task', 'metric-task']
            client.task_state.side_effect = KeyboardInterrupt
            report = Path(directory) / 'summary.json'
            code = sim.main(['--duration', '0', '--report', str(report)])
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(code, 130)
            self.assertTrue(data['interrupted'])
            self.assertIsNone(data['error'])
            self.assertEqual(data['unconfirmed_records'], 4)
            self.assertEqual(client.submit.call_count, 2)
