-- API access log and response-time samples are persisted as one idempotent task.
ALTER TABLE processed_tasks DROP CONSTRAINT IF EXISTS processed_tasks_kind_check;
ALTER TABLE processed_tasks
    ADD CONSTRAINT processed_tasks_kind_check
    CHECK (kind IN ('log', 'metric', 'api_request'));
INSERT INTO schema_migrations (version) VALUES ('003_api_request_tasks') ON CONFLICT DO NOTHING;
