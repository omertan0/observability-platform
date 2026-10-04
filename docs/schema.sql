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
