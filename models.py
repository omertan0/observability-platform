from typing import Literal
import math
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

MAX_BATCH_SIZE = 100

# tanımladığımız modele göre gelen veriyi kontrol eder


class TelemetryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    timestamp: AwareDatetime
    service: str = Field(min_length=1, max_length=200, pattern=r"\S")
    tags: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def require_iso_timestamp(cls, value):
        if not isinstance(value, str):
            raise ValueError("timestamp saat dilimi içeren ISO 8601 metni olmalıdır")
        return value

    @field_validator("tags")
    @classmethod
    def require_finite_tags(cls, value):
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("tags içindeki sayılar sonlu olmalıdır")
        return value


class LogInput(TelemetryInput): # LogInput adinda log sablonu olusturduk
    level: Literal["INFO", "WARN", "ERROR", "FATAL"]
    message: str = Field(min_length=1, max_length=16000, pattern=r"\S")
    stack_trace: str | None = Field(default=None, max_length=64000)

class MetricInput(TelemetryInput):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    value: float = Field(strict=True, allow_inf_nan=False)  # allow_inf_nan=False sossuzluk ve NaN gibi degerleri reddeder
    unit: str = Field(min_length=1, max_length=50, pattern=r"\S")

    @model_validator(mode="after")
    def check_cpu_percent(self):
        if self.name == "cpu_usage" and self.unit == "percent" and not 0 <= self.value <= 100:
            raise ValueError("cpu_usage percent değeri 0 ile 100 arasında olmalıdır")
        return self


class AlertRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    kind: Literal["metric_threshold", "log_count"]
    service: str | None = Field(default=None, min_length=1, max_length=200)
    metric_name: str | None = Field(default=None, min_length=1, max_length=200)
    metric_unit: str | None = Field(default=None, min_length=1, max_length=50)
    level: Literal["INFO", "WARN", "ERROR", "FATAL"] | None = None
    operator: Literal["gt", "gte", "lt", "lte"] = "gt"
    threshold: float = Field(strict=True, allow_inf_nan=False)
    window_seconds: int = Field(default=300, ge=1, le=86400, description="Log sayısı kuralının zaman penceresi; metrik eşiğinde kullanılmaz.")
    cooldown_seconds: int = Field(default=300, ge=0, le=86400, description="Aynı kural ve servis için iki bildirim arasındaki en kısa süre.")
    enabled: bool = True

    @model_validator(mode="after")
    def check_rule_fields(self):
        if self.kind == "metric_threshold":
            if not self.metric_name or not self.metric_unit:
                raise ValueError("Metrik kuralında metric_name ve metric_unit zorunludur")
            if self.level is not None:
                raise ValueError("Metrik kuralında level kullanılmaz")
        else:
            if self.level is None:
                raise ValueError("Log kuralında level zorunludur")
            if self.metric_name is not None or self.metric_unit is not None:
                raise ValueError("Log kuralında metrik alanları kullanılmaz")
            if self.threshold < 0 or not self.threshold.is_integer():
                raise ValueError("Log sayısı eşiği negatif olmayan tam sayı olmalıdır")
            if self.operator not in ("gt", "gte"):
                raise ValueError("Log sayısı kuralında gt veya gte kullanılmalıdır")
        return self


class AlertRulePatch(AlertRuleInput):
    # PATCH: gönderilen alanlar mevcut kuralla birleştirilip tekrar doğrulanır.
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["metric_threshold", "log_count"] | None = None
    operator: Literal["gt", "gte", "lt", "lte"] | None = None
    threshold: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    window_seconds: int | None = Field(default=None, ge=1, le=86400)
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    enabled: bool | None = None

    @model_validator(mode="after")
    def check_rule_fields(self):
        return self
