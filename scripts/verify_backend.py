"""İşlevsel testleri çalıştırır ve gerçek sonuçları JSON dosyasına kaydeder."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.checks = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.checks.append({"test": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.checks.append({"test": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.checks.append({"test": test.id(), "status": "error"})


started = time.monotonic()
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout, resultclass=RecordedResult).run(suite)
report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "duration_seconds": round(time.monotonic() - started, 2),
    "tests_run": result.testsRun,
    "successful": result.wasSuccessful(),
    "checks": result.checks,
}
output = ROOT / "test-results" / "backend-checks.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
sys.exit(0 if result.wasSuccessful() else 1)
