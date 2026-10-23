"""Örnek uygulama gibi güncel log ve metrik üretir; yalnızca HTTP API kullanır.

Çalıştırma: python scripts/simulate_telemetry.py --duration 60
Sürekli: python scripts/simulate_telemetry.py --duration 0 (Ctrl+C ile durur)
"""
import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from client_access import ingestion_headers, no_redirect_open as urlopen


class SimulatorError(Exception):
    pass


def make_cycle(rng, services, sequence, scenario, run_id, now=None):
    """Aynı turdaki metrikler ve log, aynı yük durumunu temsil eder."""
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    incident = scenario == 'incident' or (scenario == 'mixed' and sequence % 5 == 0)
    logs, metrics = [], []
    for service in services:
        tags = {'environment': 'simulation', 'source': 'telemetry-simulator', 'run_id': run_id,
                'sequence': sequence, 'scenario': 'incident' if incident else 'normal', 'host': 'simulator-1'}
        common = {'timestamp': timestamp, 'service': service, 'tags': tags}
        level = 'ERROR' if incident else rng.choices(['INFO', 'WARN'], weights=[9, 1])[0]
        message = ('Simülasyon: veritabanı bağlantısı zaman aşımına uğradı.' if incident else
                   'Simülasyon: istek normalden uzun sürdü.' if level == 'WARN' else
                   'Simülasyon: istek başarıyla tamamlandı.')
        trace = ('Traceback (simulated):\n  File "demo_service.py", line 24, in handle_request\n'
                 '    database.connect()\nTimeoutError: simulated database timeout') if incident else None
        logs.append({**common, 'level': level, 'message': message, 'stack_trace': trace})
        ranges = [(90, 99), (80, 96), (700, 1800)] if incident else [(15, 70), (25, 70), (30, 300)]
        for (name, unit), (low, high) in zip(
            [('cpu_usage', 'percent'), ('memory_usage', 'percent'), ('response_time', 'ms')], ranges,
        ):
            metrics.append({**common, 'name': name, 'unit': unit, 'value': round(rng.uniform(low, high), 2)})
    return logs, metrics


class ApiClient:
    def __init__(self, base_url, timeout=5):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def request(self, method, path, body=None):
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8') if body is not None else None
        try:
            headers = {'Content-Type': 'application/json', **ingestion_headers()}
        except ValueError:
            raise SimulatorError('INGEST_API_KEY hazır değil; scripts/setup_access.py çalıştırılmalı.') from None
        req = Request(self.base_url + path, data=data, method=method,
                      headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                result = json.load(response)
                if not isinstance(result, dict):
                    raise ValueError('object required')
                return response.status, result
        except HTTPError as exc:
            with exc:
                raise SimulatorError(f'{method} {path}: HTTP {exc.code}. Servisleri, API anahtarını ve gönderilen veriyi kontrol et.') from None
        except (URLError, OSError, ValueError):
            raise SimulatorError(f'{method} {path}: yanıt alınamadı veya okunamadı. POST sonucu belirsiz olabilir; otomatik tekrar yapılmadı.') from None

    def ready(self):
        code, body = self.request('GET', '/ready')
        if code != 200 or body.get('status') != 'ready':
            raise SimulatorError('API, Redis veya veritabanı hazır değil.')

    def submit(self, kind, records):
        code, body = self.request('POST', f'/{kind}/batch', records)
        try:
            task_id = str(UUID(body['task_id']))
            if code != 202 or body.get('status') != 'queued' or body.get('record_count') != len(records):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise SimulatorError('Kuyruğa kabul yanıtı doğrulanamadı. İstek kaydedilmiş olabilir; otomatik tekrar yapılmadı.') from None
        return task_id

    def task_state(self, task_id):
        code, body = self.request('GET', '/tasks/' + task_id)
        state = body.get('state')
        if code != 200 or body.get('task_id') != task_id or state not in ('PENDING', 'STARTED', 'RETRY', 'SUCCESS', 'FAILURE'):
            raise SimulatorError('Worker görev durumu doğrulanamadı.')
        return state


def wait_for_tasks(client, pending, stats, timeout, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while pending:
        for task_id, (kind, count) in list(pending.items()):
            state = client.task_state(task_id)
            if state == 'SUCCESS':
                stats['confirmed_' + kind] += count
                del pending[task_id]
            elif state == 'FAILURE':
                stats['failed_records'] += count
                del pending[task_id]
                raise SimulatorError(f'Worker görevi başarısız: {task_id}. Worker loglarını kontrol et.')
        if not pending:
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise SimulatorError('Worker bekleme süresi doldu. Kabul edilen işler hâlâ kuyrukta olabilir; simülatör durduruldu.')
        sleep(min(0.25, remaining))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Canlı panel için rastgele log ve metrik simülatörü.')
    parser.add_argument('--api-url', default='http://127.0.0.1:8000', help='FastAPI adresi')
    parser.add_argument('--services', nargs='+', default=['demo-payment'], help='Örnek servis adları (en fazla 10)')
    parser.add_argument('--duration', type=float, default=60, help='Saniye; 0 sürekli çalışır')
    parser.add_argument('--interval', type=float, default=2, help='Tamamlanan turlar arası bekleme, saniye')
    parser.add_argument('--scenario', choices=['normal', 'mixed', 'incident'], default='mixed', help='mixed: her beşinci tur hatalı')
    parser.add_argument('--seed', type=int, help='Aynı rastgele değerleri tekrar üretmek için sayı')
    parser.add_argument('--worker-timeout', type=float, default=30, help='Bir turun görevlerini bekleme süresi, saniye')
    parser.add_argument('--report', type=Path, help='İsteğe bağlı JSON çalışma özeti; var olan dosyanın üzerine yazılır')
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration) or not 0 <= args.duration <= 86400:
        parser.error('duration 0–86400 arasında olmalıdır; 0 sürekli çalışır.')
    if not math.isfinite(args.interval) or not 0.2 <= args.interval <= 60:
        parser.error('interval 0.2–60 arasında olmalıdır.')
    if not math.isfinite(args.worker_timeout) or not 1 <= args.worker_timeout <= 120:
        parser.error('worker-timeout 1–120 arasında olmalıdır.')
    args.services = [value.strip() for value in args.services]
    if not 1 <= len(args.services) <= 10 or len(set(args.services)) != len(args.services) or any(not value or len(value) > 200 for value in args.services):
        parser.error('1–10 farklı servis adı kullan; her biri 1–200 karakter olmalıdır.')
    try:
        address = urlsplit(args.api_url)
        valid = address.scheme in ('http', 'https') and address.hostname and address.port != 0
    except ValueError:
        parser.error('api-url geçerli bir HTTP(S) adresi olmalıdır.')
    if not valid or address.username or address.password or address.query or address.fragment:
        parser.error('api-url geçerli bir HTTP(S) adresi olmalıdır; kullanıcı/parola, query veya fragment içeremez.')
    return args


def main(argv=None):
    args = parse_args(argv)
    client = ApiClient(args.api_url)
    rng = random.Random(args.seed)
    started = time.monotonic()
    stats = {'run_id': uuid4().hex, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'services': args.services, 'scenario': args.scenario, 'seed': args.seed,
             'interval_seconds': args.interval, 'requested_duration_seconds': args.duration,
             'cycles_completed': 0, 'accepted_logs': 0, 'accepted_metrics': 0,
             'confirmed_logs': 0, 'confirmed_metrics': 0, 'failed_records': 0}
    pending = {}
    # Süresiz çalışmada belleğin büyümemesi için yalnızca son 20 kabulü tut.
    recent_task_ids = deque(maxlen=20)
    error = None
    interrupted = False
    print(f"Simülatör · servisler: {', '.join(args.services)} · senaryo: {args.scenario}", flush=True)
    print(f"run_id: {stats['run_id']} · durdurmak için Ctrl+C", flush=True)
    try:
        client.ready()
        deadline = time.monotonic() + args.duration if args.duration else math.inf
        while time.monotonic() < deadline:
            sequence = stats['cycles_completed'] + 1
            logs, metrics = make_cycle(rng, args.services, sequence, args.scenario, stats['run_id'])
            for kind, records in [('logs', logs), ('metrics', metrics)]:
                task_id = client.submit(kind, records)
                stats['accepted_' + kind] += len(records)
                pending[task_id] = (kind, len(records))
                recent_task_ids.append(task_id)
            wait_for_tasks(client, pending, stats, args.worker_timeout)
            stats['cycles_completed'] += 1
            print(f"Tur {sequence} · {logs[0]['tags']['scenario']} · worker onayı: "
                  f"{stats['confirmed_logs']} log, {stats['confirmed_metrics']} metrik", flush=True)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(args.interval, remaining))
    except KeyboardInterrupt:
        interrupted = True
        print('\nÜretim durduruldu. Kuyruğa alınmış işler sonradan tamamlanabilir.', flush=True)
    except SimulatorError as exc:
        error = str(exc)
        print('Hata: ' + error, file=sys.stderr, flush=True)
    stats.update({'finished_at_utc': datetime.now(timezone.utc).isoformat(),
                  'elapsed_seconds': round(time.monotonic() - started, 3),
                  'unconfirmed_records': sum(count for _, count in pending.values()),
                  'recent_task_ids': list(recent_task_ids), 'interrupted': interrupted, 'error': error,
                  'successful': error is None and not pending and not interrupted})
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except OSError:
            print('Çalışma özeti dosyaya yazılamadı.', file=sys.stderr)
            return 1
    return 130 if interrupted else 1 if error else 0


if __name__ == '__main__':
    sys.exit(main())
