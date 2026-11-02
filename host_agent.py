"""Read-only host telemetry sampler that sends metrics through the ingestion API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("host_agent")
PROC_ROOT = Path(os.getenv("HOST_PROC_ROOT", "/host/proc"))
SYS_ROOT = Path(os.getenv("HOST_SYS_ROOT", "/host/sys"))
DEFAULT_SERVICE = "artersoft-vm"
DEFAULT_INTERVAL = 30.0
SECTOR_BYTES = 512


def parse_cpu_counters(text: str) -> tuple[int, int]:
    """Return total and idle CPU ticks from the aggregate procfs cpu line."""
    line = next((item for item in text.splitlines() if item.startswith("cpu ")), None)
    if line is None:
        raise ValueError("/proc/stat içinde toplam cpu satırı bulunamadı")
    values = [int(value) for value in line.split()[1:]]
    if len(values) < 4:
        raise ValueError("/proc/stat cpu satırının alanları eksik")
    total = sum(values)
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return total, idle


def memory_counters(text: str) -> tuple[int, int]:
    """Return host MemTotal and MemAvailable values in kB."""
    fields: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in {"MemTotal:", "MemAvailable:"}:
            fields[parts[0]] = int(parts[1])
    total = fields.get("MemTotal:", 0)
    available = fields.get("MemAvailable:", -1)
    if total <= 0 or available < 0:
        raise ValueError("/proc/meminfo içinde MemTotal veya MemAvailable eksik")
    return total, min(total, available)


def memory_percent(text: str) -> float:
    total, available = memory_counters(text)
    return round((total - available) * 100 / total, 3)


def disk_counters(text: str, device_names: set[str]) -> tuple[int, int]:
    """Sum read/write sectors for host top-level block devices, excluding partitions."""
    read_sectors = 0
    written_sectors = 0
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10 or fields[2] not in device_names:
            continue
        try:
            read_sectors += int(fields[5])
            written_sectors += int(fields[9])
        except ValueError as exc:
            raise ValueError("/proc/diskstats içinde sayısal olmayan sayaç bulundu") from exc
    return read_sectors, written_sectors


def _host_disk_names(sys_root: Path = SYS_ROOT) -> set[str]:
    names = set()
    for entry in (sys_root / "block").iterdir():
        name = entry.name
        if name.startswith(("loop", "ram", "zram", "dm-", "sr", "fd")):
            continue
        names.add(name)
    return names


def read_snapshot(proc_root: Path = PROC_ROOT, sys_root: Path = SYS_ROOT):
    cpu = parse_cpu_counters((proc_root / "stat").read_text(encoding="ascii"))
    memory = memory_counters((proc_root / "meminfo").read_text(encoding="ascii"))
    disks = disk_counters((proc_root / "diskstats").read_text(encoding="ascii"), _host_disk_names(sys_root))
    return cpu, memory, disks


def _counter_delta(previous: int, current: int) -> int:
    # Kernel counters can reset after device changes/reboots. Never emit a negative rate.
    return max(0, current - previous)


def build_metrics(
    before,
    after,
    elapsed_seconds: float,
    service: str,
    host: str,
    timestamp: str,
    response_time_ms: float | None,
) -> list[dict[str, Any]]:
    if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0:
        raise ValueError("Ölçüm aralığı pozitif ve sonlu olmalıdır")
    if not service.strip() or not host.strip():
        raise ValueError("Servis ve makine adı boş olamaz")

    before_cpu, _, before_disk = before
    after_cpu, after_memory, after_disk = after
    total_delta = _counter_delta(before_cpu[0], after_cpu[0])
    idle_delta = _counter_delta(before_cpu[1], after_cpu[1])
    cpu_value = 0.0 if total_delta == 0 else round(max(0, total_delta - idle_delta) * 100 / total_delta, 3)
    memory_total, memory_available = after_memory
    if memory_total <= 0:
        raise ValueError("Toplam bellek sıfırdan büyük olmalıdır")
    memory_value = round((memory_total - min(memory_total, memory_available)) * 100 / memory_total, 3)
    read_rate = round(_counter_delta(before_disk[0], after_disk[0]) * SECTOR_BYTES / elapsed_seconds, 3)
    write_rate = round(_counter_delta(before_disk[1], after_disk[1]) * SECTOR_BYTES / elapsed_seconds, 3)

    tags = {"source": "host-agent", "host": host}
    values = [
        ("cpu_usage", cpu_value, "percent"),
        ("memory_usage", memory_value, "percent"),
        ("disk_read_bytes_per_second", read_rate, "bytes_per_second"),
        ("disk_write_bytes_per_second", write_rate, "bytes_per_second"),
    ]
    if response_time_ms is not None and math.isfinite(response_time_ms) and response_time_ms >= 0:
        values.append(("response_time", round(response_time_ms, 3), "ms"))
    return [
        {"timestamp": timestamp, "service": service, "name": name, "value": value, "unit": unit, "tags": tags}
        for name, value, unit in values
    ]


def measure_api_response_ms(api_url: str, timeout_seconds: float = 5.0) -> float:
    """Measure a small internal health request; this is API probe latency, not app-wide latency."""
    started = time.perf_counter()
    with urlopen(api_url.rstrip("/") + "/health", timeout=timeout_seconds) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("API sağlık kontrolü başarılı yanıt vermedi")
        response.read()
    return (time.perf_counter() - started) * 1000


def post_metrics(api_url: str, api_key: str, metrics: list[dict[str, Any]], timeout_seconds: float = 10.0) -> str:
    request = Request(
        api_url.rstrip("/") + "/metrics/batch",
        data=json.dumps(metrics, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 202:
                raise RuntimeError(f"Metrik API beklenmeyen HTTP {response.status} yanıtı verdi")
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Metrik API HTTP {exc.code} yanıtı verdi") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise RuntimeError("Metrik API yanıtı alınamadı veya geçersiz") from None
    if not isinstance(result, dict):
        raise RuntimeError("Metrik API görev makbuzu beklenen biçimde değil")
    task_id = result.get("task_id")
    record_count = result.get("record_count")
    if not isinstance(task_id, str) or record_count != len(metrics):
        raise RuntimeError("Metrik API görev makbuzu beklenen biçimde değil")
    return task_id


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Linux ana makine CPU/bellek/disk ölçümlerini Observability API'ye gönderir.")
    parser.add_argument("--api-url", default=os.getenv("HOST_AGENT_API_URL", "http://api:8000"))
    parser.add_argument("--api-key", default=os.getenv("INGEST_API_KEY", ""))
    parser.add_argument("--service", default=os.getenv("HOST_AGENT_SERVICE", DEFAULT_SERVICE))
    parser.add_argument("--host", default=os.getenv("HOST_AGENT_HOST", "azure-vm"))
    parser.add_argument("--interval", type=float, default=float(os.getenv("HOST_AGENT_INTERVAL_SECONDS", DEFAULT_INTERVAL)))
    args = parser.parse_args(argv)
    parsed = urlparse(args.api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        parser.error("--api-url HTTP(S) adresi olmalı; kullanıcı bilgisi içeremez")
    if not args.api_key:
        parser.error("INGEST_API_KEY ayarlanmalıdır")
    if not math.isfinite(args.interval) or not 5 <= args.interval <= 3600:
        parser.error("--interval 5 ile 3600 saniye arasında olmalıdır")
    if not args.service.strip() or len(args.service) > 200 or not args.host.strip() or len(args.host) > 200:
        parser.error("Servis ve makine adları 1-200 karakter olmalıdır")
    return args


def run(args) -> None:
    snapshot = read_snapshot()
    previous_at = time.monotonic()
    LOGGER.info("Host ölçümleri %s aralıkla %s servisine gönderilecek", args.interval, args.service)
    while True:
        time.sleep(args.interval)
        try:
            current = read_snapshot()
        except (OSError, ValueError) as exc:
            LOGGER.warning("Ana makine ölçümleri okunamadı: %s", exc)
            continue
        current_at = time.monotonic()
        elapsed = current_at - previous_at
        previous_at = current_at
        try:
            response_ms = measure_api_response_ms(args.api_url)
        except Exception as exc:
            LOGGER.warning("API yanıt süresi bu tur ölçülemedi: %s", type(exc).__name__)
            response_ms = None
        metrics = build_metrics(
            snapshot, current, elapsed, args.service, args.host,
            datetime.now(timezone.utc).isoformat(), response_ms,
        )
        snapshot = current
        try:
            task_id = post_metrics(args.api_url, args.api_key, metrics)
            LOGGER.info("Metrik paketi kuyruğa alındı: count=%s task_id=%s", len(metrics), task_id)
        except RuntimeError as exc:
            LOGGER.warning("Metrik paketi gönderilemedi: %s", exc)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
