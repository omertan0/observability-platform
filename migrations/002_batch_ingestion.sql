-- Görevde kaç kayıt bulunduğunu takip eder; eski tekli görevler 1 olarak kalır.
ALTER TABLE processed_tasks ADD COLUMN IF NOT EXISTS record_count INTEGER NOT NULL DEFAULT 1;
-- Toplu görevde her kayıt ayrı alarm kaynağıdır; eski bildirimlerde sıra numarası 0 kalır.
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS source_record_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_rule_id_source_task_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_source_record
ON alerts (rule_id, source_task_id, source_record_index);
INSERT INTO schema_migrations (version) VALUES ('002_batch_ingestion') ON CONFLICT DO NOTHING;
