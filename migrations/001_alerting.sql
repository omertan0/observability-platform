-- Mevcut log ve metrik kayıtlarını koruyarak alarm tablolarını ekler.
CREATE TABLE IF NOT EXISTS processed_tasks (
    task_id UUID PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('log', 'metric')),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (length(btrim(name)) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('metric_threshold', 'log_count')),
    service TEXT CHECK (service IS NULL OR length(btrim(service)) > 0),
    metric_name TEXT,
    metric_unit TEXT,
    level TEXT CHECK (level IN ('INFO', 'WARN', 'ERROR', 'FATAL')),
    operator TEXT NOT NULL CHECK (operator IN ('gt', 'gte', 'lt', 'lte')),
    threshold DOUBLE PRECISION NOT NULL CHECK (
        threshold NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8)
    ),
    window_seconds INTEGER NOT NULL DEFAULT 300 CHECK (window_seconds BETWEEN 1 AND 86400),
    cooldown_seconds INTEGER NOT NULL DEFAULT 300 CHECK (cooldown_seconds BETWEEN 0 AND 86400),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (kind = 'metric_threshold' AND metric_name IS NOT NULL AND metric_unit IS NOT NULL
            AND length(btrim(metric_name)) > 0 AND length(btrim(metric_unit)) > 0 AND level IS NULL)
        OR
        (kind = 'log_count' AND level IS NOT NULL AND metric_name IS NULL
            AND metric_unit IS NULL AND threshold >= 0
            AND threshold = floor(threshold) AND operator IN ('gt', 'gte'))
    )
);

CREATE TABLE IF NOT EXISTS alert_states (
    rule_id BIGINT NOT NULL REFERENCES alert_rules(id),
    service TEXT NOT NULL,
    last_triggered_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (rule_id, service)
);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES alert_rules(id),
    rule_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    service TEXT NOT NULL,
    message TEXT NOT NULL,
    observed_value DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    operator TEXT NOT NULL,
    source_task_id UUID NOT NULL REFERENCES processed_tasks(task_id),
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged')),
    acknowledged_at TIMESTAMPTZ,
    UNIQUE (rule_id, source_task_id)
);

CREATE INDEX IF NOT EXISTS idx_logs_alert_window ON logs (service, level, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_service_time ON alerts (service, triggered_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status_time ON alerts (status, triggered_at DESC, id DESC);

INSERT INTO alert_rules
    (name, kind, metric_name, metric_unit, operator, threshold, cooldown_seconds)
VALUES ('CPU kullanımı %85 üzerinde', 'metric_threshold', 'cpu_usage', 'percent', 'gt', 85, 300)
ON CONFLICT (name) DO NOTHING;

INSERT INTO alert_rules
    (name, kind, level, operator, threshold, window_seconds, cooldown_seconds)
VALUES ('5 dakikada 50 üzeri ERROR', 'log_count', 'ERROR', 'gt', 50, 300, 300)
ON CONFLICT (name) DO NOTHING;
