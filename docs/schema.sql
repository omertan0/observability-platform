-- Veritabanında TimescaleDB özelliklerini etkinleştirir.
CREATE EXTENSION IF NOT EXISTS timescaledb;

--Uygylamadan gelen loglari saklar
CREATE TABLE logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    service TEXT NOT NULL CHECK(length (btrim(service)) > 0 ),
    level TEXT NOT NULL CHECK( level IN ('INFO' , 'WARN' , 'ERROR' , 'FATAL')),
    message TEXT NOT NULL CHECK(length(btrim(message)) > 0),
    stack_trace TEXT,
    tags JSONB NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(tags) = 'object'),

    PRIMARY KEY (timestamp, id)
);

--onceki olcumleri saklar ve korur
CREATE TABLE metrics (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    service TEXT NOT NULL CHECK (length(btrim(service))>0),
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL CHECK (length(btrim(unit)) > 0),
    tags JSONB NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(tags) = 'object'),

    PRIMARY KEY (timestamp, id)
);

--simdi timescaleDB nin zaman gore boldugu tablolari hypertable yapisini donusturcez

--Log kayitlarini olay zamanina gore gunluk parcalara ayirir
SELECT create_hypertable(
    'logs',
    by_range('timestamp',INTERVAL'1 day') -- INTEVRAL her parcani gunluk zaman araligi kapsamasini ister
);

-- Metrik kayıtlarını ölçüm zamanına göre bir günlük parçalara ayırır.
SELECT create_hypertable(
    'metrics',
    by_range('timestamp', INTERVAL '1 day')
);

--servisin loglarini zaman gore hizli bulabilmesini saglar
CREATE INDEX idx_logs_service_timestamp
ON logs (service, timestamp DESC);

-- Log seviyesine ve zamana gore aramayi destekler.
CREATE INDEX idx_logs_level_timestamp
ON logs (level, timestamp DESC);

-- Bir servisin belirli metrigini zamana gore aramayi destekler.
CREATE INDEX idx_metrics_service_name_timestamp
ON metrics (service, name, timestamp DESC);

-- Log mesajlarinda kelime aramayi destekler.
CREATE INDEX idx_logs_message_search
ON logs USING GIN (to_tsvector('simple', message)); --USING GIN kullanacagimiz index turunu belirtir simplke kelimeri kucuk harfe cevirir

-- Log etiketlerine gore filtrelemeyi destekler.
CREATE INDEX idx_logs_tags
ON logs USING GIN (tags);

-- Metrik etiketlerine gore filtrelemeyi destekler.
CREATE INDEX idx_metrics_tags
ON metrics USING GIN (tags);