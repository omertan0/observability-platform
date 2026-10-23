# Faz 2 kodlarının satır açıklamaları

**12 Ekim 2026, API sürümü 0.3.0.** Satır numaraları bu sürümdeki dosyalara aittir.

## Akış ve son değişiklikler

`POST → doğrulama → Redis → worker → havuzdan bağlantı → kayıt ve alarm → commit → SUCCESS`

Bağlantı havuzu: arşiv kapısını her evrakta tekrar açmak yerine açık bağlantıyı ödünç alıp geri veririz. Toplu görev: en fazla 100 evrak tek iş emrinde, tek transaction içinde işlenir. Transaction işlemler paketidir; hata olursa tüm paket geri alınır.

Kurallar paket için bir kez okunup sırayla kilitlenir. Her kayıt sırayla eklenip değerlendirilir. Aynı paketteki farklı kaynakları ayırmak için görev kimliğinin yanında kayıt sıra numarası tutulur.

Boş satırlar yalnızca okunabilirlik içindir. Docker ve eski şemada yalnızca değişen satırlar gösterilir.

## database.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/database.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `import atexit` | Program kapanırken havuzu kapatma işini kaydetmek için getirir. |
| 2 | `from contextlib import contextmanager` | yield kullanan fonksiyonu with ile kullanılabilir yapar. |
| 3 | `import os` | Ortam ayarlarını okumak için os modülünü getirir. |
| 4 | `from threading import Lock` | Aynı anda iki havuz oluşturulmasını önleyecek kilidi getirir. |
| 6 | `from psycopg.rows import tuple_row` | Bağlantıyı varsayılan satır biçimine döndürmek için getirir. |
| 7 | `from psycopg_pool import ConnectionPool` | Hazır PostgreSQL bağlantılarını yöneten havuzu getirir. |
| 9 | `_pool = None` | Havuz referansı boş olur; ilk kullanımda oluşturulur. |
| 10 | `_pool_pid = None` | Havuzun kayıtlı süreç kimliğini boş yapar. |
| 11 | `_pool_lock = Lock()` | Havuz oluşturma kilidini hazırlar. |
| 14 | `def get_pool():` | Bu sürece ait havuzu veren fonksiyondur. |
| 15 | `global _pool, _pool_pid` | Dosya düzeyindeki havuz değişkenlerini güncelleyebilmesini sağlar. |
| 16 | `with _pool_lock:` | Havuz kontrolü aynı anda tek iş parçacığı tarafından yapılır. |
| 17 | `# Bağlantı import sırasında açılmaz; her Celery alt süreci kendi havuzunu kurar.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 18 | `if _pool is None or _pool_pid != os.getpid():` | Havuz yoksa veya başka sürece aitse yeni havuz kurar; Celery alt süreçleri bağlantı paylaşmaz. |
| 19 | `_pool = ConnectionPool(` | Yeni bağlantı havuzunu oluşturur. |
| 20 | `kwargs={` | Her yeni bağlantıya verilecek ayar sözlüğünü açar. |
| 21 | `"host": os.getenv("DB_HOST", "127.0.0.1"),` | Docker'da db, Windows'ta varsayılan localhost adresini kullanır. |
| 22 | `"port": os.getenv("DB_PORT", "5432"),` | Veritabanı portunu okur; varsayılan 5432. |
| 23 | `"dbname": os.environ["POSTGRES_DB"],` | Veritabanı adını ortamdan alır. |
| 24 | `"user": os.environ["POSTGRES_USER"],` | Kullanıcı adını ortamdan alır. |
| 25 | `"password": os.environ["POSTGRES_PASSWORD"],` | Parolayı ortamdan alır; kaynak koda koymaz. |
| 26 | `"connect_timeout": 5,` | Bağlantı denemesini 5 saniye ile sınırlar. |
| 27 | `"options": "-c statement_timeout=10000 -c lock_timeout=5000",` | Sorgu 10, kilit bekleme 5 saniye ile sınırlanır. |
| 28 | `},` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 29 | `min_size=1,` | En az bir hazır bağlantı tutmaya çalışır. |
| 30 | `max_size=int(os.getenv("DB_POOL_MAX", "8")),` | Süreç başına bağlantı sınırıdır: API varsayılan 8, worker ayarı 2. |
| 31 | `timeout=5,` | Havuzdan bağlantı almak için en fazla 5 saniye bekler. |
| 32 | `max_waiting=32,` | En fazla 32 istek havuz kuyruğunda bekler. |
| 33 | `check=ConnectionPool.check_connection,` | Ödünç vermeden önce bağlantının çalıştığını denetler. |
| 34 | `open=True,` | Havuz oluşturulduğunda bağlantıları arka planda hazırlamaya başlar. |
| 35 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 36 | `_pool_pid = os.getpid()` | Havuzun bu sürece ait olduğunu kaydeder. |
| 37 | `return _pool` | Hazırlanan havuzu verir. |
| 40 | `@contextmanager` | get_connection fonksiyonunu with içinde kullanılabilir yapar. |
| 41 | `def get_connection():` | Havuzdan bağlantı ödünç alma işini tek fonksiyonda toplar. |
| 42 | `with get_pool().connection() as conn:` | Havuzdan bağlantı ödünç alır; başarıda commit, hatada rollback yapılır ve bağlantı geri verilir. |
| 43 | `# Önceki kullanıcı dict_row seçmiş olabilir; yeni işlem temiz ayarla başlar.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 44 | `conn.row_factory = tuple_row` | Önceki kullanıcının dict_row ayarını temizler. |
| 45 | `yield conn` | Bağlantıyı çağıranın with bloğuna verir. Blok bitince fonksiyon devam eder. |
| 46 | `# Başarıda commit, hatada rollback; bağlantı kapatılmaz, havuza geri döner.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 49 | `def close_pool():` | Bu sürecin havuzunu kapatan fonksiyondur. |
| 50 | `global _pool, _pool_pid` | Dosya düzeyindeki havuz değişkenlerini güncelleyebilmesini sağlar. |
| 51 | `if _pool is not None and _pool_pid == os.getpid():` | Yalnızca bu sürece ait bir havuz varsa onu kapatır. |
| 52 | `_pool.close()` | Havuzun bağlantılarını ve arka plan kaynaklarını kapatır. |
| 53 | `_pool = None` | Havuz referansı boş olur; ilk kullanımda oluşturulur. |
| 54 | `_pool_pid = None` | Havuzun kayıtlı süreç kimliğini boş yapar. |
| 57 | `atexit.register(close_pool)` | Program kapanırken close_pool çalıştırılmasını kaydeder. |

## celery_app.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/celery_app.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `import os` | Ortam değişkenlerini okumak için os modülünü getirir. |
| 2 | `from celery import Celery` | Görev kuyruğu uygulamasını oluşturacak Celery sınıfını getirir. |
| 4 | `redis_url = os.getenv(` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 5 | `"REDIS_URL",` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 6 | `"redis://127.0.0.1:6379/0"` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 7 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 9 | `result_url = os.getenv("REDIS_RESULT_URL", redis_url.rsplit("/", 1)[0] + "/1")` | Sonuç deposu adresini okur; varsayılan aynı Redis sunucusunun 1 numaralı veritabanı. |
| 10 | `celery_app = Celery("observability", broker=redis_url, backend=result_url)` | Görev taşıma ve sonuç saklama adreslerini Celery'ye verir. |
| 11 | `celery_app.conf.update(` | Celery ayarlarını birlikte günceller. |
| 12 | `task_serializer="json",` | Görev paketlerini JSON biçiminde gönderir. |
| 13 | `accept_content=["json"],` | Yalnızca JSON görev paketlerini kabul eder. |
| 14 | `task_ignore_result=False,` | Görev sonuçlarını saklar. |
| 15 | `task_track_started=True,` | Görev başlayınca STARTED durumunu kaydeder. |
| 16 | `result_expires=86400,` | Sonuçları 24 saat sonra siler. |
| 17 | `redis_socket_connect_timeout=3,` | Sonuç deposuna bağlantı süresini 3 saniye ile sınırlar. |
| 18 | `redis_socket_timeout=3,` | Sonuç deposundaki ağ beklemesini 3 saniye ile sınırlar. |
| 19 | `result_backend_transport_options={"retry_policy": {"timeout": 3, "max_retries": 1}},` | Sonuç deposuna erişimde tekrar denemenin süresini ve sayısını sınırlar. |
| 20 | `task_publish_retry=False,` | API'nin kuyruğa gönderme işlemini otomatik tekrarlarla uzatmaz. |
| 21 | `broker_connection_timeout=3,` | Broker bağlantısının zaman sınırını 3 saniye olarak ayarlar. |
| 22 | `broker_connection_retry_on_startup=True,` | Worker açılırken Redis hazır değilse bağlanmayı yeniden dener. |
| 23 | `broker_transport_options={` | Redis taşıyıcısına özel ayar grubunu açar. |
| 24 | `"socket_connect_timeout": 3,` | Redis ağ bağlantısının kurulmasını 3 saniye ile sınırlar. |
| 25 | `"socket_timeout": 3,` | Redis ağ okuma/yazma beklemesini 3 saniye ile sınırlar. |
| 26 | `"retry_on_timeout": False,` | Redis istemcisinin zaman aşımında otomatik tekrarını kapatır. |
| 27 | `"visibility_timeout": 3600,` | Onaylanmamış mesajın Redis tarafından yeniden teslim edilebileceği süreyi 3600 saniye yapar; bu alarm bekleme süresi değildir. |
| 28 | `},` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 29 | `worker_prefetch_multiplier=1,` | Worker'ın önceden ayırdığı görev sayısını azaltır; bir çalışan çok sayıda işi üzerine toplamaz. |
| 30 | `timezone="UTC",` | Görev zamanlarını UTC üzerinden işler. |
| 31 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |

## models.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/models.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from typing import Literal` | Literal, yalnızca belirlediğimiz seçeneklerin kabul edilmesini sağlar. |
| 2 | `import math` | Sayıların sonlu olup olmadığını kontrol etmek için math modülünü getirir. |
| 3 | `from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator` | Pydantic şablonlarını, alan kurallarını ve doğrulama araçlarını getirir. AwareDatetime saat dilimi ister; JsonValue JSON değerlerini tanımlar. |
| 5 | `MAX_BATCH_SIZE = 100` | Tek istekte en fazla 100 kayıt kabul edilir; API ve worker aynı sınırı kullanır. |
| 7 | `# tanımladığımız modele göre gelen veriyi kontrol eder` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 10 | `class TelemetryInput(BaseModel):` | Log ve metriğin ortak alanlarını taşıyan şablonu oluşturur. |
| 11 | `model_config = ConfigDict(extra="forbid", allow_inf_nan=False)` | Bilinmeyen ek alanları ve sonlu olmayan sayıları reddetme ayarını yapar. |
| 13 | `timestamp: AwareDatetime` | timestamp zorunludur ve saat dilimi içermelidir. |
| 14 | `service: str = Field(min_length=1, max_length=200, pattern=r"\S")` | service en fazla 200 karakter olur; en az bir boşluk dışı karakter içermelidir. |
| 15 | `tags: dict[str, JsonValue] = Field(default_factory=dict)` | tags bir JSON sözlüğüdür. Gönderilmezse her kayıt için yeni bir boş sözlük oluşturulur. |
| 17 | `@field_validator("timestamp", mode="before")` | timestamp, Pydantic tarafından tarihe dönüştürülmeden önce aşağıdaki kontrolü çalıştırır. |
| 18 | `@classmethod` | Doğrulama fonksiyonunu sınıfa bağlı yapar. |
| 19 | `def require_iso_timestamp(cls, value):` | Gelen zaman değerini denetleyen fonksiyonu tanımlar. |
| 20 | `if not isinstance(value, str):` | Zamanın metin olarak gönderilip gönderilmediğini kontrol eder. |
| 21 | `raise ValueError("timestamp saat dilimi içeren ISO 8601 metni olmalıdır")` | Sayı gibi bir zaman girdisini doğrulama hatasıyla reddeder. |
| 22 | `return value` | Geçerli etiket sözlüğünü geri verir. |
| 24 | `@field_validator("tags")` | tags alanı oluşturulduktan sonra özel sayı kontrolünü çalıştırır. |
| 25 | `@classmethod` | Doğrulama fonksiyonunu sınıfa bağlı yapar. |
| 26 | `def require_finite_tags(cls, value):` | Etiketlerin içindeki bütün seviyeleri tarayan fonksiyonu tanımlar. |
| 27 | `pending = [value]` | Kontrol edilecek değerleri bir listeye koyar. |
| 28 | `while pending:` | Kontrol edilecek değer kaldığı sürece döngüyü sürdürür. |
| 29 | `item = pending.pop()` | Listenin son değerini çıkarıp incelemeye alır. |
| 30 | `if isinstance(item, dict):` | Değer bir sözlük mü diye bakar. |
| 31 | `pending.extend(item.values())` | Sözlüğün içindeki değerleri de kontrol listesine ekler. |
| 32 | `elif isinstance(item, list):` | Değer bir liste mi diye bakar. |
| 33 | `pending.extend(item)` | Listenin elemanlarını da kontrol listesine ekler. |
| 34 | `elif isinstance(item, float) and not math.isfinite(item):` | Ondalıklı sayı Infinity veya NaN mı diye kontrol eder. |
| 35 | `raise ValueError("tags içindeki sayılar sonlu olmalıdır")` | Geçersiz sayıyı reddeder; veritabanına ulaşmasını engeller. |
| 36 | `return value` | Geçerli etiket sözlüğünü geri verir. |
| 39 | `class LogInput(TelemetryInput): # LogInput adinda log sablonu olusturduk` | Log şablonu ortak timestamp, service ve tags alanlarını TelemetryInput'tan alır. |
| 40 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"]` | Yalnızca INFO, WARN, ERROR ve FATAL seviyelerini kabul eder. |
| 41 | `message: str = Field(min_length=1, max_length=16000, pattern=r"\S")` | Log mesajına boş olmama ve 16000 karakter sınırı koyar. |
| 42 | `stack_trace: str \| None = Field(default=None, max_length=64000)` | stack_trace isteğe bağlıdır; metin verilirse en fazla 64000 karakter olur. |
| 44 | `class MetricInput(TelemetryInput):` | Metrik şablonu da ortak alanları TelemetryInput'tan alır. |
| 45 | `name: str = Field(min_length=1, max_length=200, pattern=r"\S")` | Ölçüm adını zorunlu yapar; örneğin cpu_usage. |
| 46 | `value: float = Field(strict=True, allow_inf_nan=False)  # allow_inf_nan=False sossuzluk ve NaN gibi degerleri reddeder` | Ölçüm değeri sonlu bir sayı olmalıdır. strict=True metin olarak gelen sayıyı reddeder. |
| 47 | `unit: str = Field(min_length=1, max_length=50, pattern=r"\S")` | Ölçüm birimini zorunlu yapar; örneğin percent veya ms. |
| 49 | `@model_validator(mode="after")` | Kısmi şablonda aşağıdaki kontrolü kullanır; üst sınıftaki bütün kural kontrolünün yerini alır. |
| 50 | `def check_cpu_percent(self):` | Doğrulanmış metriği self üzerinden inceleyen fonksiyonu tanımlar. |
| 51 | `if self.name == "cpu_usage" and self.unit == "percent" and not 0 <= self.value <= 100:` | Ölçüm CPU yüzdesiyse 0-100 aralığını kontrol eder; başka metriklere aynı aralığı dayatmaz. |
| 52 | `raise ValueError("cpu_usage percent değeri 0 ile 100 arasında olmalıdır")` | Geçersiz CPU yüzdesini reddeder. |
| 53 | `return self` | Kısmi veriyi geçirir. main.py bunu eski kuralla birleştirip AlertRuleInput ile bütün olarak tekrar doğrular. |
| 56 | `class AlertRuleInput(BaseModel):` | Kullanıcının göndereceği alarm kuralı şablonunu oluşturur. |
| 57 | `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)` | Bilinmeyen alanları reddeder ve kural metinlerinin başındaki/sonundaki boşlukları temizler. |
| 59 | `name: str = Field(min_length=1, max_length=200)` | Kuralın kullanıcıya görünen adını zorunlu yapar. |
| 60 | `kind: Literal["metric_threshold", "log_count"]` | Kural türünü metrik eşiği veya log sayısı olarak sınırlar. |
| 61 | `service: str \| None = Field(default=None, min_length=1, max_length=200)` | Servis adı isteğe bağlıdır. null ise her servis ayrı ayrı değerlendirilir. |
| 62 | `metric_name: str \| None = Field(default=None, min_length=1, max_length=200)` | Metrik kuralının hangi ölçümü izleyeceğini belirtir. |
| 63 | `metric_unit: str \| None = Field(default=None, min_length=1, max_length=50)` | Metrik kuralının birimini belirtir; farklı birimler karıştırılmaz. |
| 64 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"] \| None = None` | Log sayısı kuralının hangi seviyeyi sayacağını belirtir. |
| 65 | `operator: Literal["gt", "gte", "lt", "lte"] = "gt"` | Karşılaştırma türünü belirler; gt büyüktür, gte büyük/eşit, lt küçüktür, lte küçük/eşittir. |
| 66 | `threshold: float = Field(strict=True, allow_inf_nan=False)` | Karşılaştırılacak sonlu eşik sayısını zorunlu yapar. |
| 67 | `window_seconds: int = Field(default=300, ge=1, le=86400, description="Log sayısı kuralının zaman penceresi; metrik eşiğinde kullanılmaz.")` | Log sayımı için son kaç saniyeye bakılacağını belirler; varsayılan 300, üst sınır 86400 saniye. |
| 68 | `cooldown_seconds: int = Field(default=300, ge=0, le=86400, description="Aynı kural ve servis için iki bildirim arasındaki en kısa süre.")` | Aynı kural ve servisin yeniden alarm üretmeden önce bekleyeceği süreyi belirler. 0 beklemeyi kaldırır. |
| 69 | `enabled: bool = True` | Yeni kural varsayılan olarak açıktır. |
| 71 | `@model_validator(mode="after")` | Kısmi şablonda aşağıdaki kontrolü kullanır; üst sınıftaki bütün kural kontrolünün yerini alır. |
| 72 | `def check_rule_fields(self):` | Kısmi kural kontrolünü tanımlar. |
| 73 | `if self.kind == "metric_threshold":` | Metrik eşiği kurallarını ayrı ele alır. |
| 74 | `if not self.metric_name or not self.metric_unit:` | Metrik adı veya birim eksik mi diye bakar. |
| 75 | `raise ValueError("Metrik kuralında metric_name ve metric_unit zorunludur")` | Eksik metrik bilgisi olan kuralı reddeder. |
| 76 | `if self.level is not None:` | Metrik kuralına log seviyesi yazılmış mı diye bakar. |
| 77 | `raise ValueError("Metrik kuralında level kullanılmaz")` | Metrik kuralında gereksiz log seviyesini reddeder. |
| 78 | `else:` | Diğer tür olan log sayısı kurallarına geçer. |
| 79 | `if self.level is None:` | Log seviyesi eksik mi diye bakar. |
| 80 | `raise ValueError("Log kuralında level zorunludur")` | Hangi seviyeyi sayacağı bilinmeyen kuralı reddeder. |
| 81 | `if self.metric_name is not None or self.metric_unit is not None:` | Log kuralına metrik adı/birimi eklenmiş mi diye bakar. |
| 82 | `raise ValueError("Log kuralında metrik alanları kullanılmaz")` | Log kuralındaki metrik alanlarını reddeder. |
| 83 | `if self.threshold < 0 or not self.threshold.is_integer():` | Log eşiği negatif veya kesirli mi diye kontrol eder. |
| 84 | `raise ValueError("Log sayısı eşiği negatif olmayan tam sayı olmalıdır")` | Log sayısı eşiğini negatif olmayan tam sayıyla sınırlar. |
| 85 | `if self.operator not in ("gt", "gte"):` | Log sayısı karşılaştırmasının gt/gte olduğunu kontrol eder. |
| 86 | `raise ValueError("Log sayısı kuralında gt veya gte kullanılmalıdır")` | Log kuralında diğer karşılaştırmaları reddeder. |
| 87 | `return self` | Kısmi veriyi geçirir. main.py bunu eski kuralla birleştirip AlertRuleInput ile bütün olarak tekrar doğrular. |
| 90 | `class AlertRulePatch(AlertRuleInput):` | Kısmi düzenleme şablonunu mevcut kural şablonundan üretir. |
| 91 | `# PATCH: gönderilen alanlar mevcut kuralla birleştirilip tekrar doğrulanır.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 92 | `name: str \| None = Field(default=None, min_length=1, max_length=200)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 93 | `kind: Literal["metric_threshold", "log_count"] \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 94 | `operator: Literal["gt", "gte", "lt", "lte"] \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 95 | `threshold: float \| None = Field(default=None, strict=True, allow_inf_nan=False)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 96 | `window_seconds: int \| None = Field(default=None, ge=1, le=86400)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 97 | `cooldown_seconds: int \| None = Field(default=None, ge=0, le=86400)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 98 | `enabled: bool \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 100 | `@model_validator(mode="after")` | Kısmi şablonda aşağıdaki kontrolü kullanır; üst sınıftaki bütün kural kontrolünün yerini alır. |
| 101 | `def check_rule_fields(self):` | Kısmi kural kontrolünü tanımlar. |
| 102 | `return self` | Kısmi veriyi geçirir. main.py bunu eski kuralla birleştirip AlertRuleInput ile bütün olarak tekrar doğrular. |

## tasks.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/tasks.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from uuid import uuid4` | Gerekirse benzersiz görev kimliği üretmek için uuid4 getirir. |
| 3 | `from celery.utils.log import get_task_logger` | Worker mesajlarını Celery'nin kayıt sistemine yazacak aracı getirir. |
| 4 | `from celery.signals import worker_process_shutdown` | Worker alt süreci kapanış sinyalini getirir. |
| 5 | `from psycopg import OperationalError` | Geçici veritabanı bağlantı hatası türünü getirir. |
| 6 | `from psycopg.errors import DeadlockDetected, SerializationFailure, LockNotAvailable, QueryCanceled` | Tekrar denenebilecek veritabanı/kilit/süre hatalarını getirir. |
| 7 | `from psycopg.types.json import Jsonb` | Etiket sözlüğünü PostgreSQL JSONB biçimine gönderecek aracı getirir. |
| 8 | `from psycopg_pool import PoolTimeout, TooManyRequests` | Havuz bekleme ve dolu kuyruk hatalarını getirir. |
| 10 | `from alerts import evaluate_alerts, load_rules` | Kuralları okuyan ve kayıtları değerlendiren yardımcıları getirir. |
| 11 | `from celery_app import celery_app` | Celery uygulamamızı getirir. |
| 12 | `from database import get_connection, close_pool` | Bağlantı alma ve havuz kapatma fonksiyonlarını getirir. |
| 13 | `from models import MAX_BATCH_SIZE` | API ile aynı paket sınırını getirir. |
| 15 | `logger = get_task_logger(__name__)` | Bu dosya için worker logger'ını oluşturur. |
| 16 | `TASK_OPTIONS = dict(` | İki görevde ortak kullanılacak ayar sözlüğünü açar. |
| 17 | `bind=True,` | Görev fonksiyonuna self verir; böylece görev kimliğine erişebiliriz. |
| 18 | `acks_late=True,` | Görev başarılı dönünce kuyruk mesajını onaylar. |
| 19 | `reject_on_worker_lost=True,` | Çalışan süreç beklenmedik şekilde kaybolursa mesajın yeniden kuyruğa verilmesini ister. |
| 20 | `autoretry_for=(OperationalError, DeadlockDetected, SerializationFailure, LockNotAvailable,` | Geçici veritabanı hatalarında yeniden deneme yapılır. |
| 21 | `QueryCanceled, PoolTimeout, TooManyRequests),` | Süre ve havuz hatalarını da yeniden denenebilir hatalara ekler. |
| 22 | `retry_backoff=True,` | Her tekrar arasında giderek büyüyen bekleme kullanır. |
| 23 | `retry_backoff_max=60,` | Tekrar beklemesini en fazla 60 saniye olarak sınırlar. |
| 24 | `retry_jitter=True,` | Birçok worker'ın aynı anda yeniden denemesini azaltmak için süreye rastgelelik ekler. |
| 25 | `max_retries=5,` | İlk denemeden sonra en fazla 5 tekrar yapılır. |
| 26 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 29 | `def save_records(kind: str, records: list[dict], task_id: str):` | Bir paketi tek görev ve transaction içinde kaydeden ortak fonksiyondur. |
| 30 | `if not 1 <= len(records) <= MAX_BATCH_SIZE:` | Worker'da da 1-100 kayıt sınırını denetler. |
| 31 | `raise ValueError("Bir görev 1-100 kayıt içermelidir")` | Sınır dışı görevi reddeder. |
| 32 | `# Görev kimliği, kayıt ve alarm aynı transaction içinde tutulur.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 33 | `# İşlem yarıda kalırsa hepsi geri alınır; tekrar teslim çift kayıt üretmez.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 34 | `with get_connection() as conn:` | Havuzdan bağlantı alır ve transaction başlatır. Başarıda commit, hatada rollback yapılır; bağlantı havuza geri verilir. |
| 35 | `inserted = conn.execute(` | Görev kimliğini daha önce işlenmiş görevler tablosuna eklemeyi dener. |
| 36 | `"""INSERT INTO processed_tasks (task_id, kind, record_count) VALUES (%s, %s, %s)` | Görev kimliği, türü ve kayıt sayısını aynı transaction içinde ekler. |
| 37 | `ON CONFLICT (task_id) DO NOTHING RETURNING task_id""",` | Aynı görev kimliği zaten varsa ekleme yapmaz; eklenen kimliği RETURNING ile geri verir. |
| 38 | `(task_id, kind, len(records)),` | Kimlik, tür ve kayıt sayısını ayrı SQL parametreleri verir. |
| 39 | `).fetchone()` | INSERT sonucu olan tek satırı alır; ekleme olmadıysa None gelir. |
| 40 | `if inserted is None:` | Görevin daha önce işlendiğini fark eder. |
| 41 | `logger.info("Görev daha önce işlendi: %s", task_id)` | Tekrar teslim edildiğini worker kayıtlarına yazar. |
| 42 | `return {"status": "already_processed"}` | Görev daha önce işlendiyse hiçbir kaydı tekrar eklemeden döner. |
| 43 | `# Kurallar her kayıt için yeniden okunmaz; toplu görevde bir kez sıralı kilitlenir.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 44 | `rules = load_rules(conn, kind, records)` | Uygun kuralları paket başına bir kez okur ve aynı sırayla kilitler. |
| 45 | `now = conn.execute("SELECT clock_timestamp()").fetchone()[0] if rules else None` | Kurallar varsa paket için değerlendirme zamanını bir kez DB'den alır. |
| 46 | `for index, record in enumerate(records):` | Kayıtları ve sıfırdan başlayan sıra numaralarını dolaşır. |
| 47 | `insert_record(conn, kind, record)` | Kaydı doğru tabloya ekler. |
| 48 | `evaluate_alerts(conn, kind, record, task_id, index, rules, now)` | Hazır kurallar/zaman ve kaynak sıra numarasıyla kaydın alarmını kontrol eder. |
| 49 | `logger.info("%s kaydı yazıldı ve alarm kuralları kontrol edildi: %s", len(records), kind)` | Commit tamamlandıktan sonra başarı mesajını yazar. |
| 50 | `return {"status": "saved", "record_count": len(records)}` | Celery sonuç deposuna yazılacak başarı özetini verir. |
| 53 | `def insert_record(conn, kind: str, record: dict):` | Yalnızca INSERT yapan yardımcıdır; ayrı transaction açmaz. |
| 54 | `if kind == "log":` | Gelen veri log ise log tablosuna yazma kolunu seçer. |
| 55 | `conn.execute(` | Metrik INSERT sorgusunu çalıştırır. |
| 56 | `"""INSERT INTO logs` | Kayıt hedefinin logs tablosu olduğunu belirtir. |
| 57 | `(timestamp, received_at, service, level, message, stack_trace, tags)` | Doldurulacak log sütunlarını sıralar. |
| 58 | `VALUES (%s, %s, %s, %s, %s, %s, %s)""",` | Yedi metrik sütunu için yedi değer yeri ayırır. |
| 59 | `(record["timestamp"], record["received_at"], record["service"],` | Metrik zamanı, API alım zamanı ve servisi gönderir. |
| 60 | `record["level"], record["message"], record.get("stack_trace"),` | Seviye, mesaj ve isteğe bağlı stack_trace değerini gönderir; eksik stack_trace NULL olur. |
| 61 | `Jsonb(record.get("tags", {}))),` | Metrik etiketlerini JSONB olarak gönderir. |
| 62 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 63 | `else:` | Metrik yazma kolunu seçer; bu fonksiyon yalnızca log/metric görevlerinden çağrılır. |
| 64 | `conn.execute(` | Metrik INSERT sorgusunu çalıştırır. |
| 65 | `"""INSERT INTO metrics` | Kayıt hedefinin metrics tablosu olduğunu belirtir. |
| 66 | `(timestamp, received_at, service, name, value, unit, tags)` | Doldurulacak metrik sütunlarını sıralar. |
| 67 | `VALUES (%s, %s, %s, %s, %s, %s, %s)""",` | Yedi metrik sütunu için yedi değer yeri ayırır. |
| 68 | `(record["timestamp"], record["received_at"], record["service"],` | Metrik zamanı, API alım zamanı ve servisi gönderir. |
| 69 | `record["name"], record["value"], record["unit"],` | Ölçüm adı, sayısı ve birimini gönderir. |
| 70 | `Jsonb(record.get("tags", {}))),` | Metrik etiketlerini JSONB olarak gönderir. |
| 71 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 73 | `def save_record(kind: str, record: dict, task_id: str):` | Log ve metriğin ortak kayıt akışını tanımlar; kind tür, record veri, task_id görev kimliğidir. |
| 74 | `return save_records(kind, [record], task_id)` | Tek kaydı bir elemanlı listeye çevirip ortak akışı kullanır. |
| 77 | `@celery_app.task(**TASK_OPTIONS)` | Metrik fonksiyonunu da aynı ayarlarla Celery görevine dönüştürür. |
| 78 | `def process_log(self, record: dict):` | Worker'ın çalıştıracağı log görevini tanımlar. |
| 79 | `return save_record("log", record, self.request.id or str(uuid4()))` | Tek log görevini işler ve sonucu Celery'ye döndürür. |
| 82 | `@celery_app.task(**TASK_OPTIONS)` | Metrik fonksiyonunu da aynı ayarlarla Celery görevine dönüştürür. |
| 83 | `def process_metric(self, record: dict):` | Worker'ın çalıştıracağı metrik görevini tanımlar. |
| 84 | `return save_record("metric", record, self.request.id or str(uuid4()))` | Tek metrik görevini işler ve sonucu Celery'ye döndürür. |
| 87 | `@celery_app.task(**TASK_OPTIONS)` | Metrik fonksiyonunu da aynı ayarlarla Celery görevine dönüştürür. |
| 88 | `def process_logs_batch(self, records: list[dict]):` | Toplu log görevini tanımlar. |
| 89 | `return save_records("log", records, self.request.id or str(uuid4()))` | Log paketini aynı görev kimliğiyle işler. |
| 92 | `@celery_app.task(**TASK_OPTIONS)` | Metrik fonksiyonunu da aynı ayarlarla Celery görevine dönüştürür. |
| 93 | `def process_metrics_batch(self, records: list[dict]):` | Toplu metrik görevini tanımlar. |
| 94 | `return save_records("metric", records, self.request.id or str(uuid4()))` | Metrik paketini aynı görev kimliğiyle işler. |
| 97 | `@worker_process_shutdown.connect` | Kapanış sinyalini aşağıdaki fonksiyona bağlar. |
| 98 | `def close_worker_connections(**kwargs):` | Kapanış sinyalinin bilgilerini kabul eden fonksiyondur. |
| 99 | `close_pool()` | Bu worker alt sürecinin bağlantı havuzunu kapatır. |

## queries.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/queries.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `"""Liste sorgularını parametrelerle oluşturur; kullanıcı verisi SQL'e eklenmez."""` | Dosyanın amacını açıklayan metindir; SQL koşulları ile kullanıcı değerleri ayrı tutulur. |
| 2 | `import json` | Etiket sorgu metnini Python sözlüğüne çevirmek için JSON aracını getirir. |
| 3 | `import math` | Sonlu sayı kontrolü için math modülünü getirir. |
| 5 | `from fastapi import HTTPException` | Geçersiz filtreye HTTP hata cevabı vermek için aracı getirir. |
| 6 | `from psycopg.rows import dict_row` | Sorgu satırlarını sözlük olarak alacak ayarı getirir. |
| 7 | `from psycopg.types.json import Jsonb` | Etiket filtrelerini JSONB parametresine çevirecek aracı getirir. |
| 9 | `from database import get_connection` | Kendi bağlantı fonksiyonumuzu getirir. |
| 12 | `def reject_json_constant(value):` | JSON okuyucusu NaN/Infinity görürse çağrılacak fonksiyonu tanımlar. |
| 13 | `raise ValueError(f"Geçersiz JSON sayısı: {value}")` | Bu özel sayı metinlerini reddeder. |
| 16 | `def finite_json_float(value):` | JSON içindeki ondalıklı sayıları okuyacak fonksiyonu tanımlar. |
| 17 | `number = float(value)` | Sayı metnini float yapar. |
| 18 | `if not math.isfinite(number):` | 1e999 gibi taşan bir sayının sonsuza dönüşüp dönüşmediğine bakar. |
| 19 | `raise ValueError("JSON sayısı sonlu olmalıdır")` | Sonlu olmayan sayıyı reddeder. |
| 20 | `return number` | Geçerli sayıyı JSON okuyucusuna geri verir. |
| 23 | `def telemetry_filters(service, start, end, tags):` | Log/metrik sorgularının ortak servis, zaman ve etiket filtrelerini hazırlar. |
| 24 | `clauses, values = [], []` | SQL koşulları ve onların değerleri için iki ayrı liste açar. |
| 25 | `if start and end and start > end:` | Zaman aralığının ters verilmiş olup olmadığını kontrol eder. |
| 26 | `raise HTTPException(422, "start, end zamanından sonra olamaz")` | Ters aralığı 422 ile reddeder. |
| 27 | `for column, value, comparison in (` | Ortak filtreleri sırayla dolaşır. |
| 28 | `("service", service, "="), ("timestamp", start, ">="), ("timestamp", end, "<="),` | Servis için eşitlik, başlangıç için büyük/eşit, bitiş için küçük/eşit koşullarını tanımlar. |
| 29 | `):` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 30 | `if value is not None:` | Bu filtre gerçekten gönderilmişse işleme alır. |
| 31 | `clauses.append(f"{column} {comparison} %s")` | Kodda sabit olan sütun/karşılaştırmayla SQL koşulu kurar; kullanıcı değeri %s yerine ayrı gönderilir. |
| 32 | `values.append(value)` | Filtre değerini koşulla aynı sırada değer listesine koyar. |
| 33 | `if tags is not None:` | Etiket filtresi gönderilmiş mi diye bakar. |
| 34 | `try:` | JSON dönüştürmesinde oluşabilecek hataları yakalamak için try açar. |
| 35 | `parsed = json.loads(tags, parse_constant=reject_json_constant, parse_float=finite_json_float)` | Etiket metnini JSON olarak okur; sonlu olmayan sayıları da denetler. |
| 36 | `if not isinstance(parsed, dict):` | Etiketin nesne/sözlük olduğunu kontrol eder; listeyi kabul etmez. |
| 37 | `raise ValueError("object required")` | Nesne olmayan etiketi hata koluna yönlendirir. |
| 38 | `except (ValueError, TypeError):` | Bozuk JSON ve yanlış tür hatalarını yakalar. |
| 39 | `raise HTTPException(422, 'tags JSON nesnesi olmalıdır; örnek: {"environment":"test"}')` | Filtreyi anlaşılır bir 422 cevabıyla reddeder. |
| 40 | `clauses.append("tags @> %s")` | JSONB içermeyi denetleyen @> koşulunu ekler; kayıt belirtilen etiketleri içermelidir. |
| 41 | `values.append(Jsonb(parsed))` | Etiket sözlüğünü ayrı JSONB parametresi olarak ekler. |
| 42 | `return clauses, values` | Hazırlanan koşulları ve değerleri çağırana döndürür. |
| 45 | `def page(sql, clauses, values, order, limit, offset):` | Ortak sayfalama fonksiyonunu tanımlar. |
| 46 | `# sql/order/clauses yalnızca kod içindeki sabitlerden gelir.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 47 | `where = " WHERE " + " AND ".join(clauses) if clauses else ""` | Filtre varsa WHERE ekler ve koşulları AND ile birleştirir; yoksa WHERE eklemez. |
| 48 | `with get_connection() as conn:` | Sorgu için havuzdan veritabanı bağlantısı ödünç alır. |
| 49 | `conn.row_factory = dict_row` | Her satırın sütun adlarıyla bir sözlük olarak gelmesini sağlar. |
| 50 | `rows = conn.execute(` | Liste sorgusunu çalıştırır. |
| 51 | `sql + where + " ORDER BY " + order + " LIMIT %s OFFSET %s",` | Kod içindeki sabit sorguya filtre, sıralama ve sayfalama parçalarını ekler. |
| 52 | `[*values, limit + 1, offset],` | Filtre değerlerini açar ve en sona limit/offset değerlerini ekler. Bir fazla kayıt, sonraki sayfa var mı diye bakmak içindir. |
| 53 | `).fetchall()` | Sorgunun sınırlandırılmış sonuçlarını liste olarak alır. |
| 54 | `has_more = len(rows) > limit` | Bir fazla satır varsa başka sayfa olduğunu belirler. |
| 55 | `return {"items": rows[:limit], "limit": limit, "offset": offset,` | İstenen sayıda satırı, limit ve offset bilgileriyle döndürür; fazladan satırı göstermez. |
| 56 | `"has_more": has_more, "next_offset": offset + limit if has_more else None}` | Sonraki sayfanın başlangıcını verir; başka sayfa yoksa null olur. |

## alerts.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/alerts.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `"""Yeni kayıt işlendiğinde kuralları değerlendirip sistem içi bildirim oluşturur."""` | Dosyanın alarm kontrolü yaptığını açıklayan metindir. |
| 2 | `from datetime import timedelta` | Saniye cinsinden süreyi tarihe ekleyip çıkarmak için timedelta getirir. |
| 3 | `from operator import gt, ge, lt, le` | Büyüktür, büyük/eşit, küçüktür, küçük/eşit karşılaştırma fonksiyonlarını getirir. |
| 5 | `from psycopg.rows import dict_row` | Kural satırlarını sözlük olarak alacak ayarı getirir. |
| 7 | `OPERATORS = {"gt": gt, "gte": ge, "lt": lt, "lte": le}` | API'deki operator adını çalıştırılacak Python karşılaştırmasına eşler. |
| 8 | `SYMBOLS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}` | Aynı operator adlarını bildirimde okunacak simgelere eşler. |
| 11 | `def load_rules(conn, kind: str, records: list[dict]):` | Paketteki kayıtlara uygun kuralları bir kez getirir. |
| 12 | `# Aynı kuralı değerlendiren worker'lar sırayla ilerler; çift alarm önlenir.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 13 | `with conn.cursor(row_factory=dict_row) as cur:` | Mevcut bağlantı üzerinde sorgu aracı yani cursor açar. Ayrı bağlantı/transaction başlatmaz. |
| 14 | `if kind == "metric":` | Metrik kuralında gözlenen değer doğrudan yeni ölçümdür. |
| 15 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 16 | `"""SELECT * FROM alert_rules` | Kural tablosundaki alanları seçer. |
| 17 | `WHERE enabled AND kind = 'metric_threshold'` | Yalnızca açık metrik eşiği kurallarını alır. |
| 18 | `AND (service IS NULL OR service = ANY(%s))` | Tüm servislerin veya paketteki servislerden birinin kurallarını seçer. |
| 19 | `AND metric_name = ANY(%s) AND metric_unit = ANY(%s)` | Paketin ölçüm adları ve birimlerine uygun aday kuralları seçer. |
| 20 | `ORDER BY id FOR UPDATE""",` | Kuralları aynı sırayla kilitler; eşzamanlı worker'ları sıraya koyar. |
| 21 | `([r["service"] for r in records], [r["name"] for r in records], [r["unit"] for r in records]),` | Paketten servis/ad/birim listelerini çıkarıp SQL'e ayrı parametre verir. |
| 22 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 23 | `else:` | Log kuralında gözlenen değer son penceredeki kayıt sayısıdır. |
| 24 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 25 | `"""SELECT * FROM alert_rules` | Kural tablosundaki alanları seçer. |
| 26 | `WHERE enabled AND kind = 'log_count'` | Yalnızca açık log sayısı kurallarını alır. |
| 27 | `AND (service IS NULL OR service = ANY(%s)) AND level = ANY(%s)` | Paketin servis ve log seviyelerine uygun kuralları seçer. |
| 28 | `ORDER BY id FOR UPDATE""",` | Kuralları aynı sırayla kilitler; eşzamanlı worker'ları sıraya koyar. |
| 29 | `([r["service"] for r in records], [r["level"] for r in records]),` | Paketin servis ve seviye listelerini parametre verir. |
| 30 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 31 | `return cur.fetchall()` | Uygun kural listesini döndürür. |
| 34 | `def evaluate_alerts(conn, kind: str, record: dict, task_id: str, record_index=0, rules=None, now=None):` | Bir kaydı değerlendirir; hazır kurallar/zaman verilmişse yeniden okumaz. |
| 35 | `if rules is None:` | Kurallar çağıran tarafından verilmiş mi diye bakar. |
| 36 | `rules = load_rules(conn, kind, [record])` | Hazır kural yoksa bu kayıt için okur. |
| 37 | `if not rules:` | Bu kayda uygun kural yok mu diye bakar. |
| 38 | `return` | Kural yoksa alarm kontrolünü bitirir; kayıt yine saklanır. |
| 39 | `with conn.cursor(row_factory=dict_row) as cur:` | Mevcut bağlantı üzerinde sorgu aracı yani cursor açar. Ayrı bağlantı/transaction başlatmaz. |
| 40 | `if now is None:` | Hazır değerlendirme zamanı verilmiş mi diye bakar. |
| 41 | `cur.execute("SELECT clock_timestamp() AS now")` | Veritabanının o andaki saatini okur. |
| 42 | `now = cur.fetchone()["now"]` | Saat sonucunu now değişkenine koyar. |
| 43 | `for rule in rules:` | Uygun kuralları tek tek değerlendirir. |
| 44 | `if rule["service"] is not None and rule["service"] != record["service"]:` | Aday kuralın bu kaydın servisine tam uyduğunu denetler. |
| 45 | `continue` | Bu kuralı bırakıp sonraki kurala geçer. |
| 46 | `if kind == "metric" and (rule["metric_name"] != record["name"] or rule["metric_unit"] != record["unit"]):` | Ölçüm adı ve birimi birlikte tam eşleşmelidir. |
| 47 | `continue` | Bu kuralı bırakıp sonraki kurala geçer. |
| 48 | `if kind == "log" and rule["level"] != record["level"]:` | Log seviyesi bu kuralla tam eşleşmelidir. |
| 49 | `continue` | Bu kuralı bırakıp sonraki kurala geçer. |
| 50 | `if kind == "metric":` | Metrik kuralında gözlenen değer doğrudan yeni ölçümdür. |
| 51 | `observed = record["value"]` | Örneğin 87.5 değerini observed değişkenine koyar. |
| 52 | `else:` | Log kuralında gözlenen değer son penceredeki kayıt sayısıdır. |
| 53 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 54 | `"""SELECT count(*) AS count FROM logs` | count(*) ile kayıt sayısını hesaplar; sonucu count adıyla verir. |
| 55 | `WHERE service = %s AND level = %s` | Yalnızca aynı servis ve istenen seviyedeki logları sayar. |
| 56 | `AND received_at > %s AND received_at <= %s""",` | API alım zamanı pencerenin içinde kalan kayıtları sayar: başlangıç hariç, şimdi dahil. |
| 57 | `(record["service"], rule["level"],` | Servis ve log seviyesini parametre olarak verir. |
| 58 | `now - timedelta(seconds=rule["window_seconds"]), now),` | Pencerenin başlangıcını now eksi kuraldaki saniye olarak hesaplar; sonu now olur. |
| 59 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 60 | `observed = cur.fetchone()["count"]` | Hesaplanan log sayısını observed değişkenine koyar. |
| 61 | `if not OPERATORS[rule["operator"]](observed, rule["threshold"]):` | Kuralın karşılaştırma fonksiyonuyla gözlenen değer ve eşiği karşılaştırır. |
| 62 | `continue` | Bu kuralı bırakıp sonraki kurala geçer. |
| 64 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 65 | `"SELECT last_triggered_at FROM alert_states WHERE rule_id = %s AND service = %s",` | Bu kural ve bu servis için bekleme durumunu arar. |
| 66 | `(rule["id"], record["service"]),` | Kural kimliği ve servisi ayrı gönderir. |
| 67 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 68 | `state = cur.fetchone()` | Bulunan son alarm zamanını alır; önceki alarm yoksa None gelir. |
| 69 | `if state and now < state["last_triggered_at"] + timedelta(seconds=rule["cooldown_seconds"]):` | Son alarmdan sonra cooldown_seconds dolmuş mu diye kontrol eder. |
| 70 | `continue` | Bu kuralı bırakıp sonraki kurala geçer. |
| 72 | `description = (f"{record['name']} ({record['unit']})" if kind == "metric"` | Bildirimde metrik adını/birimini veya log sayma penceresini açıklayan metni hazırlar. |
| 73 | `else f"Son {rule['window_seconds']} saniyedeki {rule['level']} sayısı")` | Bildirimde metrik adını/birimini veya log sayma penceresini açıklayan metni hazırlar. |
| 74 | `message = (f"{record['service']}: {description} = {observed:g}; "` | Servis ve gözlenen değeri bildirim mesajına ekler. :g sayı biçimidir; gereksiz .0 yazmaz. |
| 75 | `f"eşik {SYMBOLS[rule['operator']]} {rule['threshold']:g}.")` | Karşılaştırma simgesini ve eşik sayısını mesajın devamına ekler. |
| 76 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 77 | `"""INSERT INTO alerts` | Bildirimi alerts tablosuna ekler. |
| 78 | `(rule_id, rule_name, kind, service, message, observed_value,` | Kuralın adını ve koşulunu da saklar; kural sonra değişse bile eski alarmın nedeni korunur. |
| 79 | `threshold, operator, source_task_id, triggered_at, source_record_index)` | Bildirime paketteki kaynak kayıt sırasını da ekler. |
| 80 | `VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",` | On bir alarm alanı için on bir parametre yeri açar. |
| 81 | `(rule["id"], rule["name"], rule["kind"], record["service"], message,` | Kural, servis, mesaj, gözlenen değer, eşik, görev ve zamanı aynı sırayla gönderir. |
| 82 | `observed, rule["threshold"], rule["operator"], task_id, now, record_index),` | Gözlenen değer, eşik, görev kimliği, zaman ve kayıt sırasını verir. |
| 83 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 84 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 85 | `"""INSERT INTO alert_states (rule_id, service, last_triggered_at)` | Bekleme durumunu alert_states tablosuna yazar. |
| 86 | `VALUES (%s, %s, %s)` | Kural, servis ve alarm zamanını yerlerine koyar. |
| 87 | `ON CONFLICT (rule_id, service)` | Bu kural/servis durumu zaten var mı diye kontrol eder. |
| 88 | `DO UPDATE SET last_triggered_at = EXCLUDED.last_triggered_at""",` | Varsa zamanı günceller; EXCLUDED eklenmek istenen yeni satırı temsil eder. |
| 89 | `(rule["id"], record["service"], now),` | Durum için kural kimliğini, servisi ve şimdiki zamanı gönderir. |
| 90 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |

## main.py

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/main.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from datetime import datetime, timezone` | UTC alım zamanı oluşturmak için tarih/saat araçlarını getirir. |
| 2 | `import logging` | API çalışma mesajları için logging modülünü getirir. |
| 3 | `from typing import Annotated, Literal` | Annotated alan doğrulama bilgisi ekler; Literal seçenekleri sınırlar. |
| 4 | `from uuid import UUID` | Görev kimliğini UUID biçiminde doğrulatmak için getirir. |
| 6 | `from dotenv import load_dotenv` | .env okuyucusunu getirir. |
| 7 | `from fastapi import FastAPI, HTTPException, Path, Query, Request, Body` | JSON listesinin boyutunu sınırlamak için Body aracını da getirir. |
| 8 | `from fastapi.responses import JSONResponse` | HTTP kodunu belirterek JSON cevap üretme aracını getirir. |
| 9 | `from fastapi.exceptions import RequestValidationError` | Giriş doğrulama hatalarını yakalayacak türü getirir. |
| 10 | `from kombu.exceptions import OperationalError as BrokerError` | Kuyruk bağlantı hatasına BrokerError takma adı verir; veritabanı hatasıyla karışmaz. |
| 11 | `from psycopg import OperationalError` | Veritabanı bağlantı hata türünü getirir. |
| 12 | `from psycopg.errors import UniqueViolation, QueryCanceled, LockNotAvailable, UndefinedTable` | Kural adı çakışması, zaman aşımı, kilit ve eksik tablo hatalarını getirir. |
| 13 | `from psycopg.rows import dict_row` | Veritabanı satırlarını sözlük olarak alacak ayarı getirir. |
| 14 | `from pydantic import AwareDatetime, ValidationError` | Saat dilimli zaman türü ve birleşmiş kural doğrulama hatası türünü getirir. |
| 15 | `from redis import Redis` | Redis'e sağlık kontrolü göndermek için istemciyi getirir. |
| 16 | `from redis.exceptions import RedisError` | Redis bağlantı hatalarını yakalayacak türü getirir. |
| 17 | `from psycopg_pool import PoolTimeout, TooManyRequests` | Havuz sorunlarını 503 cevabıyla yönetmek için getirir. |
| 19 | `# Ayarlar görev modülü içe alınmadan önce yüklenir.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 20 | `load_dotenv()` | Görev modülleri yüklenmeden önce .env içindeki ayarları okur. |
| 22 | `from celery_app import celery_app` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 23 | `from database import get_connection` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 24 | `from models import LogInput, MetricInput, AlertRuleInput, AlertRulePatch, MAX_BATCH_SIZE` | Şablonlarla birlikte ortak paket sınırını getirir. |
| 25 | `from queries import page, telemetry_filters` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 26 | `from tasks import process_log, process_metric, process_logs_batch, process_metrics_batch` | Tekli ve toplu Celery görevlerini getirir. |
| 28 | `logger = logging.getLogger(__name__)` | Bu dosyanın logger'ını oluşturur. |
| 29 | `app = FastAPI(title="Observability Platform", version="0.3.0",` | API uygulamasını 0.3.0 sürümüyle oluşturur. |
| 30 | `description="Log/metrik toplama, filtreleme ve sistem içi alarm API'si.")` | FastAPI uygulamasını adı, sürümü ve Swagger açıklamasıyla oluşturur. |
| 32 | `Limit = Annotated[int, Query(ge=1, le=200)]` | limit sorgu parametresi için ortak 1-200 doğrulamasını tanımlar. |
| 33 | `Offset = Annotated[int, Query(ge=0, le=100000)]` | offset için ortak 0-100000 doğrulamasını tanımlar. |
| 34 | `Service = Annotated[str \| None, Query(min_length=1, max_length=200, pattern=r"\S")]` | İsteğe bağlı servis filtresinin metin sınırlarını tanımlar. |
| 35 | `Time = Annotated[AwareDatetime \| None, Query()]` | İsteğe bağlı saat dilimli zaman filtresini tanımlar. |
| 36 | `RecordId = Annotated[int, Path(ge=1, le=9223372036854775807)]` | Adres içindeki kayıt kimliğini pozitif BIGINT aralığıyla sınırlar. |
| 39 | `@app.exception_handler(RequestValidationError)` | Doğrulama hatası oluştuğunda bu cevap fonksiyonunu kullan der. |
| 40 | `async def invalid_request(request: Request, exc: RequestValidationError):` | Doğrulama hatası cevap fonksiyonunu tanımlar. async burada FastAPI'nin hata işleyici biçimidir. |
| 41 | `# NaN/Infinity gibi geçersiz girdileri cevap JSON'una tekrar eklemeyiz.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 42 | `details = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}` | Her hatadan alanın yerini, açıklamasını ve türünü alır; geçersiz girdi değerini cevapta tekrar yazmaz. |
| 43 | `for error in exc.errors()]` | Bu sade hata sözlüğünü bütün hatalar için oluşturur. |
| 44 | `return JSONResponse(status_code=422, content={"detail": details})` | Hata listesini 422 cevabıyla döndürür. |
| 47 | `@app.exception_handler(OperationalError)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 48 | `@app.exception_handler(QueryCanceled)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 49 | `@app.exception_handler(LockNotAvailable)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 50 | `@app.exception_handler(PoolTimeout)` | Havuzdan bağlantı alma süresi dolarsa ortak 503 işleyicisine yönlendirir. |
| 51 | `@app.exception_handler(TooManyRequests)` | Havuz kuyruğu doluysa ortak 503 işleyicisini kullanır. |
| 52 | `async def database_unavailable(request: Request, exc: Exception):` | Veritabanı erişim sorunu cevap fonksiyonunu tanımlar. |
| 53 | `logger.warning("Veritabanı işlemi tamamlanamadı: %s", type(exc).__name__)` | Ayrıntılı bağlantı bilgisi/parola yerine yalnızca hata türünü loglar. |
| 54 | `return JSONResponse(status_code=503, content={"detail": "Veritabanı geçici olarak erişilemiyor; tekrar deneyin."})` | Kullanıcıya açıklamalı 503 cevabı gönderir. |
| 57 | `@app.get("/health", tags=["Sağlık"])` | GET /health adresini oluşturur; tags Swagger'daki bölüm adıdır. |
| 58 | `def health():` | API süreç kontrolü fonksiyonunu tanımlar. |
| 59 | `return {"status": "ok"}` | API'nin cevap verebildiğini belirtir; bağımlılıkları kontrol etmez. |
| 62 | `@app.get("/ready", tags=["Sağlık"])` | GET /ready adresini oluşturur. |
| 63 | `def ready():` | Veritabanı ve kuyruk hazırlık kontrolünü tanımlar. |
| 64 | `checks = {"database": False, "redis": False}` | İki kontrolü başlangıçta başarısız kabul eder. |
| 65 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 66 | `with get_connection() as conn:` | Görüldü işlemi için transaction açar. |
| 67 | `conn.execute("SELECT 1 FROM alert_rules LIMIT 1")` | Alarm tablosuna küçük bir sorgu atar; bağlantıyı ve tablonun varlığını kontrol eder. |
| 68 | `checks["database"] = True` | Veritabanı kontrolü başarılıysa True yazar. |
| 69 | `except (OperationalError, UndefinedTable, QueryCanceled, LockNotAvailable, PoolTimeout, TooManyRequests):` | Hazırlık kontrolünde havuz hatalarını da erişilemiyor olarak ele alır. |
| 70 | `pass` | Redis kontrolü False kalır. |
| 71 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 72 | `with Redis.from_url(celery_app.conf.broker_url, socket_connect_timeout=2, socket_timeout=2) as client:` | Redis istemcisi açar; bağlantı ve ağ işlemlerinde 2 saniye sınır kullanır. |
| 73 | `checks["redis"] = bool(client.ping())` | PING gönderir ve başarılı yanıtı True olarak kaydeder. |
| 74 | `except RedisError:` | Redis sorunu varsa yakalar. |
| 75 | `pass` | Redis kontrolü False kalır. |
| 76 | `ok = all(checks.values())` | İki kontrol de True ise uygulamayı hazır kabul eder. |
| 77 | `return JSONResponse(status_code=200 if ok else 503,` | Hazırsa 200, değilse 503 döndürür ve hangi bağımlılığın çalıştığını gösterir. Worker kontrolü burada yoktur. |
| 78 | `content={"status": "ready" if ok else "unavailable", "checks": checks})` | Hazırsa 200, değilse 503 döndürür ve hangi bağımlılığın çalıştığını gösterir. Worker kontrolü burada yoktur. |
| 81 | `def enqueue(task, payload):` | Log ve metriğin ortak kuyruğa gönderme fonksiyonunu tanımlar. |
| 82 | `is_batch = isinstance(payload, list)` | Gövde tek model mi yoksa model listesi mi diye ayırır. |
| 83 | `items = payload if is_batch else [payload]` | Tek modeli de listeye çevirip ortak hazırlık akışını kullanır. |
| 84 | `received_at = datetime.now(timezone.utc).isoformat()` | İsteğin alındığı UTC zamanı bir kez üretir. |
| 85 | `records = [item.model_dump(mode="json") for item in items]` | Bütün modelleri JSON'a uygun sözlüklere çevirir. |
| 86 | `for record in records:` | Paketteki kayıtları dolaşır. |
| 87 | `record["received_at"] = received_at` | Kayıtlara aynı HTTP isteğinin alım zamanını ekler. |
| 88 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 89 | `result = task.apply_async(args=[records if is_batch else records[0]], retry=False)` | Toplu görev için listeyi, tekli görev için tek sözlüğü kuyruğa yollar. |
| 90 | `except (BrokerError, RedisError, OSError):` | Kuyruk veya ağ bağlantı hatalarını yakalar. |
| 91 | `raise HTTPException(503, "Veri kuyruğa alınamadı; Redis bağlantısını kontrol edip tekrar deneyin.")` | Kuyruğa alınamayan kayıt için 503 gönderir. |
| 92 | `response = {"status": "queued", "task_id": result.id}` | Kuyruğa kabul cevabını hazırlar. |
| 93 | `if is_batch:` | Toplu istekte ek cevap alanı hazırlar. |
| 94 | `response["record_count"] = len(records)` | Kabul edilen kayıt sayısını yanıta ekler. |
| 95 | `return response` | Hazırlanan cevabı döndürür. |
| 98 | `@app.post("/logs", status_code=202, tags=["Loglar"])` | POST /logs adresini oluşturur; kabul edilince 202 döndürür. |
| 99 | `def receive_log(log: LogInput):` | Gövdeyi LogInput ile doğrulatır ve fonksiyona alır. |
| 100 | `return enqueue(process_log, log)` | Logu process_log görevine gönderir. |
| 103 | `@app.post("/metrics", status_code=202, tags=["Metrikler"])` | POST /metrics adresini oluşturur. |
| 104 | `def receive_metric(metric: MetricInput):` | Gövdeyi MetricInput ile doğrulatır. |
| 105 | `return enqueue(process_metric, metric)` | Metriği process_metric görevine gönderir. |
| 108 | `@app.post("/logs/batch", status_code=202, tags=["Loglar"])` | Toplu log gönderme adresini oluşturur. |
| 109 | `def receive_logs_batch(logs: Annotated[list[LogInput], Body(min_length=1, max_length=MAX_BATCH_SIZE)]):` | 1-100 logdan oluşan JSON dizisini doğrulatır; bir kayıt hatalıysa tüm istek reddedilir. |
| 110 | `return enqueue(process_logs_batch, logs)` | Log listesini toplu göreve yollar. |
| 113 | `@app.post("/metrics/batch", status_code=202, tags=["Metrikler"])` | Toplu metrik gönderme adresini oluşturur. |
| 114 | `def receive_metrics_batch(metrics: Annotated[list[MetricInput], Body(min_length=1, max_length=MAX_BATCH_SIZE)]):` | 1-100 metrikten oluşan JSON dizisini doğrulatır. |
| 115 | `return enqueue(process_metrics_batch, metrics)` | Metrik listesini toplu göreve yollar. |
| 118 | `@app.get("/tasks/{task_id}", tags=["Görevler"])` | Görev durumu okuma adresini oluşturur. |
| 119 | `def task_status(task_id: UUID):` | UUID kimliğini doğrulayıp fonksiyona verir. |
| 120 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 121 | `result = celery_app.AsyncResult(str(task_id))` | Bu kimliğin sonuç nesnesini oluşturur; görevi yeniden çalıştırmaz. |
| 122 | `state = result.state` | Sonuç deposundan görev durumunu okur. |
| 123 | `except (BrokerError, RedisError, OSError):` | Kuyruk veya ağ bağlantı hatalarını yakalar. |
| 124 | `raise HTTPException(503, "Görev durumuna erişilemiyor; Redis bağlantısını kontrol edin.")` | Sonuç deposu erişilemiyorsa 503 döndürür. |
| 125 | `# PENDING, kimliğin varlığını kanıtlamaz; sonucu henüz yok veya süresi dolmuş olabilir.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 126 | `response = {"task_id": str(task_id), "state": state,` | Görev kimliği ve durumunu cevap sözlüğüne ekler. |
| 127 | `"completed": state in ("SUCCESS", "FAILURE"), "successful": state == "SUCCESS"}` | İş tamamlandı mı ve başarılı mı bilgisini ayrı verir. |
| 128 | `if state == "FAILURE":` | Görev başarısız mı diye kontrol eder. |
| 129 | `response["detail"] = "Görev başarısız oldu; worker loglarında bu kimliği arayın."` | Genel hata açıklaması verir; traceback API cevabına eklenmez. |
| 130 | `return response` | Hazırlanan cevabı döndürür. |
| 133 | `@app.get("/logs", tags=["Loglar"])` | GET /logs adresini oluşturur. |
| 134 | `def list_logs(service: Service = None,` | Log listeleme fonksiyonunu isteğe bağlı servis filtresiyle tanımlar. |
| 135 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"] \| None = None,` | İsteğe bağlı seviyeyi dört seçenekle sınırlar. |
| 136 | `q: Annotated[str \| None, Query(min_length=1, max_length=500, pattern=r"\S")] = None,` | Kelime arama metnini sınırlar; yalnızca boşluk kabul etmez. |
| 137 | `tags: Annotated[str \| None, Query(max_length=4000)] = None,` | Etiket filtresini ekler. |
| 138 | `start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):` | Zaman aralığı ve sayfalama parametrelerini ekler. |
| 139 | `clauses, values = telemetry_filters(service, start, end, tags)` | Ortak filtreleri hazırlatır. |
| 140 | `if level is not None:` | Seviye filtresi gönderilmiş mi diye kontrol eder. |
| 141 | `clauses.append("level = %s")` | Seviye eşitliği koşulunu ekler. |
| 142 | `values.append(level)` | Seviye değerini ayrı parametre listesine koyar. |
| 143 | `if q is not None:` | Kelime araması istenmiş mi diye kontrol eder. |
| 144 | `clauses.append("to_tsvector('simple', message) @@ websearch_to_tsquery('simple', %s)")` | Mesajı kelime dizinine çevirip websearch sorgusuyla eşleştirir; hazırladığımız GIN indeksinin ifadesiyle aynıdır. |
| 145 | `values.append(q)` | Kullanıcının arama metnini ayrı parametre olarak verir. |
| 146 | `return page("SELECT id, timestamp, received_at, service, level, message, stack_trace, tags FROM logs",` | Log alanlarını en yeni olay önce olacak şekilde ortak sayfalama fonksiyonundan getirir. |
| 147 | `clauses, values, "timestamp DESC, id DESC", limit, offset)` | Metrik alanlarını olay zamanına göre sıralayıp sayfalı getirir. |
| 150 | `@app.get("/metrics", tags=["Metrikler"])` | GET /metrics adresini oluşturur. |
| 151 | `def list_metrics(service: Service = None,` | Metrik listeleme fonksiyonunu servis filtresiyle tanımlar. |
| 152 | `name: Annotated[str \| None, Query(min_length=1, max_length=200)] = None,` | İsteğe bağlı ölçüm adı filtresini ekler. |
| 153 | `unit: Annotated[str \| None, Query(min_length=1, max_length=50)] = None,` | İsteğe bağlı birim filtresini ekler. |
| 154 | `tags: Annotated[str \| None, Query(max_length=4000)] = None,` | Etiket filtresini ekler. |
| 155 | `start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):` | Zaman aralığı ve sayfalama parametrelerini ekler. |
| 156 | `clauses, values = telemetry_filters(service, start, end, tags)` | Ortak filtreleri hazırlatır. |
| 157 | `for column, value in (("name", name), ("unit", unit)):` | Ölçüm adı ve birim filtrelerini sırayla dolaşır. |
| 158 | `if value is not None:` | Gönderilen filtreyi seçer. |
| 159 | `clauses.append(f"{column} = %s")` | Sabit sütun için eşitlik koşulu ekler. |
| 160 | `values.append(value)` | Filtre değerini ayrı parametre listesine koyar. |
| 161 | `return page("SELECT id, timestamp, received_at, service, name, value, unit, tags FROM metrics",` | Metrik alanlarını olay zamanına göre sıralayıp sayfalı getirir. |
| 162 | `clauses, values, "timestamp DESC, id DESC", limit, offset)` | Metrik alanlarını olay zamanına göre sıralayıp sayfalı getirir. |
| 165 | `RULE_FIELDS = ("name", "kind", "service", "metric_name", "metric_unit", "level", "operator",` | Kural ekleme/düzenlemede kullanılacak izinli sütun adlarını sabit listede tutar. |
| 166 | `"threshold", "window_seconds", "cooldown_seconds", "enabled")` | Kural ekleme/düzenlemede kullanılacak izinli sütun adlarını sabit listede tutar. |
| 169 | `@app.get("/alert-rules", tags=["Alarm kuralları"])` | GET /alert-rules adresini oluşturur. |
| 170 | `def list_rules(enabled: bool \| None = None, limit: Limit = 20, offset: Offset = 0):` | Kuralları açık/kapalı filtresi ve sayfalamayla listeleyen fonksiyonu tanımlar. |
| 171 | `clauses, values = (["enabled = %s"], [enabled]) if enabled is not None else ([], [])` | enabled gönderilmişse filtre kurar; False da geçerli bir filtre olduğu için is not None kullanır. |
| 172 | `return page("SELECT * FROM alert_rules", clauses, values, "id ASC", limit, offset)` | Kuralları kimlik sırasıyla sayfalı getirir. |
| 175 | `@app.post("/alert-rules", status_code=201, tags=["Alarm kuralları"])` | POST /alert-rules adresini oluşturur; yeni kayıt için 201 döndürür. |
| 176 | `def create_rule(rule: AlertRuleInput):` | Gelen kuralı AlertRuleInput ile doğrulatır. |
| 177 | `data = rule.model_dump()` | Kural modelini Python sözlüğüne çevirir. |
| 178 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 179 | `with get_connection() as conn:` | Görüldü işlemi için transaction açar. |
| 180 | `conn.row_factory = dict_row` | Sonucu sözlük olarak alır. |
| 181 | `result = conn.execute(` | Bildirim güncelleme sorgusunu çalıştırır. |
| 182 | `"INSERT INTO alert_rules (" + ", ".join(RULE_FIELDS) + ") VALUES ("` | İzinli sabit sütun adlarını virgülle birleştirip INSERT oluşturur. |
| 183 | `+ ", ".join(["%s"] * len(RULE_FIELDS)) + ") RETURNING *",` | Her sütun için %s oluşturur; RETURNING * eklenen kaydı geri getirir. |
| 184 | `[data[field] for field in RULE_FIELDS],` | Kural değerlerini sabit sütun sırasıyla ayrı parametreler olarak gönderir. |
| 185 | `).fetchone()` | Güncellemenin tek satırlık sonucunu alır. |
| 186 | `except UniqueViolation:` | Yeni ad başka bir kuralla çakışırsa hatayı yakalar. |
| 187 | `raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")` | İsim çakışmasına 409 verir; transaction geri alınır. |
| 188 | `return result` | Güncellenmiş bildirimi döndürür. |
| 191 | `@app.patch("/alert-rules/{rule_id}", tags=["Alarm kuralları"])` | Kural kimliği içeren PATCH adresini oluşturur. |
| 192 | `def update_rule(rule_id: RecordId, patch: AlertRulePatch):` | Kimliği ve değiştirilecek alanları doğrulatarak fonksiyona alır. |
| 193 | `changes = patch.model_dump(exclude_unset=True)` | Sadece istekte açıkça gönderilen alanları alır; gönderilmeyen varsayılanlarla eski değerleri ezmez. |
| 194 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 195 | `with get_connection() as conn:` | Görüldü işlemi için transaction açar. |
| 196 | `conn.row_factory = dict_row` | Sonucu sözlük olarak alır. |
| 197 | `existing = conn.execute("SELECT * FROM alert_rules WHERE id = %s FOR UPDATE", (rule_id,)).fetchone()` | Eski kuralı okur ve kilitler; worker aynı anda o kuralı değişmiş haliyle değerlendiremez. |
| 198 | `if existing is None:` | Kural bulunmadı mı diye kontrol eder. |
| 199 | `raise HTTPException(404, "Alarm kuralı bulunamadı")` | Bulunmayan kimliğe 404 döndürür. |
| 200 | `if not changes:` | Değiştirilecek alan var mı diye bakar. |
| 201 | `return existing` | Boş PATCH gelmişse mevcut kuralı döndürür. |
| 202 | `merged = {field: existing[field] for field in RULE_FIELDS}` | Mevcut kuralın izinli alanlarını yeni sözlüğe alır. |
| 203 | `merged.update(changes)` | Gönderilen değişiklikleri bu sözlüğe uygular. |
| 204 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 205 | `validated = AlertRuleInput.model_validate(merged).model_dump()` | Tam kural şablonuyla tekrar kontrol eder. Örneğin threshold:null burada reddedilir. |
| 206 | `except ValidationError as exc:` | Birleşmiş kural geçersizse hatayı yakalar. |
| 207 | `raise HTTPException(422, exc.errors(include_context=False, include_input=False))` | Geçersiz kuralın hata ayrıntılarını 422 ile gönderir; hatalı girdiyi cevapta tekrar taşımaz. |
| 208 | `result = conn.execute(` | Bildirim güncelleme sorgusunu çalıştırır. |
| 209 | `"UPDATE alert_rules SET " + ", ".join(field + " = %s" for field in RULE_FIELDS)` | İzinli sütunların her biri için parametreli SET ifadesi oluşturur. |
| 210 | `+ ", updated_at = clock_timestamp() WHERE id = %s RETURNING *",` | Güncelleme zamanını DB saatiyle yazar ve yalnızca istenen kimliği günceller. |
| 211 | `[validated[field] for field in RULE_FIELDS] + [rule_id],` | Doğrulanmış yeni değerleri ve en son kimliği parametre olarak gönderir. |
| 212 | `).fetchone()` | Güncellemenin tek satırlık sonucunu alır. |
| 213 | `# Düzenlenen kuralın yeni ayarları sonraki kayıtta hemen uygulanır.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 214 | `conn.execute("DELETE FROM alert_states WHERE rule_id = %s", (rule_id,))` | Bu kuralın eski bekleme durumunu temizler; yeni ayarlar sonraki kayıtta hemen uygulanır. |
| 215 | `except UniqueViolation:` | Yeni ad başka bir kuralla çakışırsa hatayı yakalar. |
| 216 | `raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")` | İsim çakışmasına 409 verir; transaction geri alınır. |
| 217 | `return result` | Güncellenmiş bildirimi döndürür. |
| 220 | `@app.get("/alerts", tags=["Alarmlar"])` | GET /alerts adresini oluşturur. |
| 221 | `def list_alerts(service: Service = None, status: Literal["open", "acknowledged"] \| None = None,` | Servis ve open/acknowledged durum filtrelerini tanımlar. |
| 222 | `rule_id: Annotated[int \| None, Query(ge=1, le=9223372036854775807)] = None,` | İsteğe bağlı kural kimliği filtresini pozitif BIGINT aralığıyla sınırlar. |
| 223 | `limit: Limit = 20, offset: Offset = 0):` | Bildirimlerin sayfalama parametrelerini ekler. |
| 224 | `clauses, values = [], []` | Filtre koşulları ve değerleri için ayrı listeler açar. |
| 225 | `for column, value in (("service", service), ("status", status), ("rule_id", rule_id)):` | İzinli servis, durum ve kural kimliği filtrelerini dolaşır. |
| 226 | `if value is not None:` | Gönderilen filtreyi seçer. |
| 227 | `clauses.append(f"{column} = %s")` | Sabit sütun için eşitlik koşulu ekler. |
| 228 | `values.append(value)` | Filtre değerini ayrı parametre listesine koyar. |
| 229 | `return page("SELECT * FROM alerts", clauses, values, "triggered_at DESC, id DESC", limit, offset)` | Bildirimleri tetikleme zamanı en yeni önce olacak şekilde sayfalı getirir. |
| 232 | `@app.patch("/alerts/{alert_id}/acknowledge", tags=["Alarmlar"])` | Bildirimi görüldü olarak işaretleyen PATCH adresini oluşturur. |
| 233 | `def acknowledge_alert(alert_id: RecordId):` | Bildirimin kimliğini doğrulatarak alır. |
| 234 | `with get_connection() as conn:` | Görüldü işlemi için transaction açar. |
| 235 | `conn.row_factory = dict_row` | Sonucu sözlük olarak alır. |
| 236 | `result = conn.execute(` | Bildirim güncelleme sorgusunu çalıştırır. |
| 237 | `"""UPDATE alerts SET status = 'acknowledged',` | Durumu acknowledged yapar; bu kullanıcı gördü anlamındadır. |
| 238 | `acknowledged_at = COALESCE(acknowledged_at, clock_timestamp())` | COALESCE eski görülme zamanı varsa onu korur, yoksa şimdiki zamanı yazar. |
| 239 | `WHERE id = %s RETURNING *""", (alert_id,),` | Yalnızca bu kimliği günceller ve güncellenmiş satırı döndürür. |
| 240 | `).fetchone()` | Güncellemenin tek satırlık sonucunu alır. |
| 241 | `if result is None:` | Böyle bir bildirim yok mu diye kontrol eder. |
| 242 | `raise HTTPException(404, "Alarm bulunamadı")` | Bulunmayan bildirime 404 verir. |
| 243 | `return result` | Güncellenmiş bildirimi döndürür. |

## compose.yaml

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/compose.yaml)

| Satır | Kod | Anlamı |
|---|---|---|
| 4 | `command: ["redis-server", "--appendonly", "yes"]` | Şemayı ve iki migration dosyasını tek transaction içinde uygular; hata olursa geri alır. |
| 7 | `volumes:` | Kurulum dosyalarının bağlanacağı volume listesini açar. |
| 17 | `environment:` | Kurulum istemcisinin ortam ayarlarını açar. |
| 19 | `REDIS_RESULT_URL: redis://redis:6379/1` | Görev sonuçlarını ayrı Redis veritabanında tutar. |
| 20 | `DB_POOL_MAX: "2"` | Her worker alt süreci en fazla iki DB bağlantısı açabilir. |
| 26 | `depends_on:` | Kurulum servisinin bekleyeceği bağımlılıkları tanımlar. |
| 28 | `condition: service_healthy` | Veritabanı sağlık kontrolü başarılı olduktan sonra kurulum başlar. |
| 29 | `db:` | Kurulum db servisini bekler. |
| 30 | `condition: service_healthy` | Veritabanı sağlık kontrolü başarılı olduktan sonra kurulum başlar. |
| 31 | `db-init:` | Veritabanı kurulum servisini tanımlar. |
| 32 | `condition: service_completed_successfully` | Tablo kurulumunun başarıyla bitmesini bekler; db-init sürekli açık kalmak zorunda değildir. |
| 34 | `db-init:` | Veritabanı kurulum servisini tanımlar. |
| 35 | `image: timescale/timescaledb:latest-pg17` | psql içeren TimescaleDB image'ını kullanır. |
| 36 | `environment:` | Kurulum istemcisinin ortam ayarlarını açar. |
| 37 | `PGHOST: db` | psql, Docker ağındaki db servisine bağlanır. |
| 38 | `PGUSER: ${POSTGRES_USER}` | .env içindeki kullanıcı adını psql ayarına verir. |
| 39 | `PGDATABASE: ${POSTGRES_DB}` | .env içindeki veritabanı adını psql ayarına verir. |
| 40 | `PGPASSWORD: ${POSTGRES_PASSWORD}` | .env içindeki parolayı psql ortamına verir; komut satırına yazmaz. |
| 41 | `volumes:` | Kurulum dosyalarının bağlanacağı volume listesini açar. |
| 42 | `- ./schema.sql:/schema.sql:ro` | Şemayı konteynerde salt okunur dosya olarak sunar; ro salt okunur demektir. |
| 43 | `- ./migrations:/migrations:ro` | Migration klasörünü salt okunur olarak konteynere bağlar. |
| 44 | `command: ["psql", "-v", "ON_ERROR_STOP=1", "--single-transaction", "-f", "/schema.sql", "-f", "/migrations/001_alerting.sql", "-f", "/migrations/002_batch_ingestion.sql"]` | Şemayı ve iki migration dosyasını tek transaction içinde uygular; hata olursa geri alır. |
| 45 | `depends_on:` | Kurulum servisinin bekleyeceği bağımlılıkları tanımlar. |
| 46 | `db:` | Kurulum db servisini bekler. |
| 47 | `condition: service_healthy` | Veritabanı sağlık kontrolü başarılı olduktan sonra kurulum başlar. |
| 49 | `db:` | Kurulum db servisini bekler. |
| 50 | `image: timescale/timescaledb:latest-pg17` | psql içeren TimescaleDB image'ını kullanır. |
| 51 | `environment:` | Kurulum istemcisinin ortam ayarlarını açar. |
| 57 | `volumes:` | Kurulum dosyalarının bağlanacağı volume listesini açar. |
| 65 | `volumes:` | Kurulum dosyalarının bağlanacağı volume listesini açar. |

## Dockerfile

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/Dockerfile)

| Satır | Kod | Anlamı |
|---|---|---|
| 14 | `COPY main.py models.py celery_app.py tasks.py database.py alerts.py queries.py ./` | API, worker, alarm ve sorgu dosyalarını image içine kopyalar; yalnızca bu açıkça yazılan dosyalar kopyalanır. |
| 17 | `RUN useradd --uid 10001 --create-home appuser` | Linux image içinde 10001 numaralı normal kullanıcıyı oluşturur. |
| 18 | `USER appuser` | Sonraki çalıştırmanın bu kullanıcıyla yapılmasını sağlar; worker root olmaz. |

## schema.sql

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/schema.sql)

| Satır | Kod | Anlamı |
|---|---|---|
| 5 | `CREATE TABLE IF NOT EXISTS logs (` | logs tablosu yoksa oluşturur; varsa korur. Var olan tablonun yapısını değiştirmez. |
| 19 | `CREATE TABLE IF NOT EXISTS metrics (` | metrics tablosu yoksa oluşturur; varsa korur. |
| 37 | `by_range('timestamp',INTERVAL'1 day'), -- Her parça bir günlük zaman aralığı kapsar.` | Günlük zaman parçasını tanımlar; ardından yeni seçenek geleceği için virgül eklendi. |
| 38 | `if_not_exists => TRUE` | Metrik tablosu zaten hypertable ise onu korur. |
| 44 | `by_range('timestamp', INTERVAL '1 day'),` | Metriklerin günlük zaman parçasını tanımlar. |
| 45 | `if_not_exists => TRUE` | Metrik tablosu zaten hypertable ise onu korur. |
| 49 | `CREATE INDEX IF NOT EXISTS idx_logs_service_timestamp` | Servis/zaman indeksi yoksa oluşturur; varsa hata vermez. |
| 53 | `CREATE INDEX IF NOT EXISTS idx_logs_level_timestamp` | Seviye/zaman indeksi yoksa oluşturur. |
| 57 | `CREATE INDEX IF NOT EXISTS idx_metrics_service_name_timestamp` | Metrik servis/ad/zaman indeksi yoksa oluşturur. |
| 61 | `CREATE INDEX IF NOT EXISTS idx_logs_message_search` | Log kelime arama indeksi yoksa oluşturur. |
| 65 | `CREATE INDEX IF NOT EXISTS idx_logs_tags` | Log etiket indeksi yoksa oluşturur. |
| 69 | `CREATE INDEX IF NOT EXISTS idx_metrics_tags` | Metrik etiket indeksi yoksa oluşturur. |

## migrations/001_alerting.sql

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/migrations/001_alerting.sql)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `-- Mevcut log ve metrik kayıtlarını koruyarak alarm tablolarını ekler.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 2 | `CREATE TABLE IF NOT EXISTS schema_migrations (` | Hangi kurulum sürümünün uygulandığını tutar; başlangıç kuralları her açılışta yeniden eklenmez. |
| 3 | `version TEXT PRIMARY KEY,` | Uygulanan migration sürümünü benzersiz olarak saklar. |
| 4 | `applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` | Kurulumun veritabanındaki zamanını otomatik yazar. |
| 5 | `);` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 7 | `CREATE TABLE IF NOT EXISTS processed_tasks (` | İşlenmiş görev kimliklerini tutar; tekrar teslim edilen görevi tanımamızı sağlar. |
| 8 | `task_id UUID PRIMARY KEY,` | Görev kimliğini UUID türünde benzersiz tutar; aynı kimlik ikinci kez eklenemez. |
| 9 | `kind TEXT NOT NULL CHECK (kind IN ('log', 'metric')),` | Kayıt/kural türünü saklar; CHECK varsa izinli türleri sınırlar. |
| 10 | `processed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` | Görevin işlenme zamanını otomatik tutar. |
| 11 | `);` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 13 | `CREATE TABLE IF NOT EXISTS alert_rules (` | Kullanıcının alarm kurallarını saklayan tabloyu oluşturur. |
| 14 | `id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,` | Kayıt numarasını veritabanı otomatik üretir ve benzersiz tutar. |
| 15 | `name TEXT NOT NULL UNIQUE CHECK (length(btrim(name)) > 0),` | Kural adı zorunlu, boş olmayan ve benzersiz metindir. |
| 16 | `kind TEXT NOT NULL CHECK (kind IN ('metric_threshold', 'log_count')),` | Kayıt/kural türünü saklar; CHECK varsa izinli türleri sınırlar. |
| 17 | `service TEXT CHECK (service IS NULL OR length(btrim(service)) > 0),` | Servis kapsamını veya bildirimin ait olduğu servisi saklar; kuraldaki null tüm servisler demektir. |
| 18 | `metric_name TEXT,` | Kuralın izleyeceği ölçüm adını tutar. |
| 19 | `metric_unit TEXT,` | Kuralın izleyeceği ölçüm birimini tutar. |
| 20 | `level TEXT CHECK (level IN ('INFO', 'WARN', 'ERROR', 'FATAL')),` | Sayılacak log seviyesini izinli seçeneklerle sınırlar. |
| 21 | `operator TEXT NOT NULL CHECK (operator IN ('gt', 'gte', 'lt', 'lte')),` | Karşılaştırma türünü tutar; kural tablosunda izinli seçenekler denetlenir. |
| 22 | `threshold DOUBLE PRECISION NOT NULL CHECK (` | Kuralın eşik sayısını veya tetiklenme anındaki eşik kopyasını saklar. |
| 23 | `threshold NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8)` | Kuralın eşik sayısını veya tetiklenme anındaki eşik kopyasını saklar. |
| 24 | `),` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 25 | `window_seconds INTEGER NOT NULL DEFAULT 300 CHECK (window_seconds BETWEEN 1 AND 86400),` | Log sayma penceresini saniye olarak tutar; 1-86400 arasında olmalıdır. |
| 26 | `cooldown_seconds INTEGER NOT NULL DEFAULT 300 CHECK (cooldown_seconds BETWEEN 0 AND 86400),` | Tekrar bildirim beklemesini saniye olarak tutar; 0-86400 arasında olmalıdır. |
| 27 | `enabled BOOLEAN NOT NULL DEFAULT TRUE,` | Kuralın açık/kapalı durumunu saklar; başlangıçta açık olur. |
| 28 | `created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),` | Kuralın oluşturulma zamanını otomatik tutar. |
| 29 | `updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),` | Kuralın son düzenlenme zamanını tutar. |
| 30 | `CHECK (` | Kural alanlarının birlikte tutarlı olmasını sağlayan veritabanı kontrolünü açar. |
| 31 | `(kind = 'metric_threshold' AND metric_name IS NOT NULL AND metric_unit IS NOT NULL` | Metrik kuralında metrik adı ve birimin var olmasını zorunlu tutar. |
| 32 | `AND length(btrim(metric_name)) > 0 AND length(btrim(metric_unit)) > 0 AND level IS NULL)` | Metrik adı/birimi boş olamaz ve metrik kuralında log seviyesi bulunamaz. |
| 33 | `OR` | İki izinli kural biçiminden birinin doğru olması yeterlidir. |
| 34 | `(kind = 'log_count' AND level IS NOT NULL AND metric_name IS NULL` | Log kuralında seviye zorunludur ve metrik adı boş olmalıdır. |
| 35 | `AND metric_unit IS NULL AND threshold >= 0` | Log kuralında metrik birimi olmaz; eşik negatif olamaz. |
| 36 | `AND threshold = floor(threshold) AND operator IN ('gt', 'gte'))` | Log sayısı eşiği tam sayı olmalı ve karşılaştırma gt/gte olmalıdır. |
| 37 | `)` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 38 | `);` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 40 | `CREATE TABLE IF NOT EXISTS alert_states (` | Kural ve servis için en son bildirim zamanını tutar; bekleme süresi buradan hesaplanır. |
| 41 | `rule_id BIGINT NOT NULL REFERENCES alert_rules(id),` | İlgili kuralı başka tablodaki id ile ilişkilendirir; var olmayan kurala işaret edilemez. |
| 42 | `service TEXT NOT NULL,` | Servis kapsamını veya bildirimin ait olduğu servisi saklar; kuraldaki null tüm servisler demektir. |
| 43 | `last_triggered_at TIMESTAMPTZ NOT NULL,` | Bu kural/servisin son bildirim zamanını tutar. |
| 44 | `PRIMARY KEY (rule_id, service)` | Kural ve servis birleşimini benzersiz yapar; her servis için ayrı bekleme durumu vardır. |
| 45 | `);` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 47 | `CREATE TABLE IF NOT EXISTS alerts (` | Oluşmuş sistem içi bildirimleri saklar. |
| 48 | `id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,` | Kayıt numarasını veritabanı otomatik üretir ve benzersiz tutar. |
| 49 | `rule_id BIGINT NOT NULL REFERENCES alert_rules(id),` | İlgili kuralı başka tablodaki id ile ilişkilendirir; var olmayan kurala işaret edilemez. |
| 50 | `rule_name TEXT NOT NULL,` | Tetikleme anındaki kural adını kopya olarak saklar; kural düzenlense de eski neden korunur. |
| 51 | `kind TEXT NOT NULL,` | Kayıt/kural türünü saklar; CHECK varsa izinli türleri sınırlar. |
| 52 | `service TEXT NOT NULL,` | Servis kapsamını veya bildirimin ait olduğu servisi saklar; kuraldaki null tüm servisler demektir. |
| 53 | `message TEXT NOT NULL,` | Kullanıcının okuyacağı bildirim metnini saklar. |
| 54 | `observed_value DOUBLE PRECISION NOT NULL,` | Alarmı tetikleyen ölçüm değerini veya log sayısını saklar. |
| 55 | `threshold DOUBLE PRECISION NOT NULL,` | Kuralın eşik sayısını veya tetiklenme anındaki eşik kopyasını saklar. |
| 56 | `operator TEXT NOT NULL,` | Karşılaştırma türünü tutar; kural tablosunda izinli seçenekler denetlenir. |
| 57 | `source_task_id UUID NOT NULL REFERENCES processed_tasks(task_id),` | Alarmı üreten işlenmiş göreve bağlar. |
| 58 | `triggered_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),` | Bildirimin oluşma zamanını saklar. |
| 59 | `status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged')),` | open veya acknowledged durumunu saklar; başlangıçta open olur. |
| 60 | `acknowledged_at TIMESTAMPTZ,` | Kullanıcının bildirimi gördüğü zamanı tutar; henüz görülmediyse NULL olur. |
| 61 | `UNIQUE (rule_id, source_task_id)` | Aynı kuralın aynı görev için ikinci bildirim üretmesini veritabanında da engeller. |
| 62 | `);` | Önceki çok satırlı çağrı, sözlük veya SQL tanımını kapatır. |
| 64 | `CREATE INDEX IF NOT EXISTS idx_logs_alert_window ON logs (service, level, received_at DESC);` | Sorgunun kullandığı sütunları indeksler; zaten varsa yeniden oluşturmaz. |
| 65 | `CREATE INDEX IF NOT EXISTS idx_alerts_service_time ON alerts (service, triggered_at DESC, id DESC);` | Sorgunun kullandığı sütunları indeksler; zaten varsa yeniden oluşturmaz. |
| 66 | `CREATE INDEX IF NOT EXISTS idx_alerts_status_time ON alerts (status, triggered_at DESC, id DESC);` | Sorgunun kullandığı sütunları indeksler; zaten varsa yeniden oluşturmaz. |
| 68 | `INSERT INTO alert_rules` | Başlangıç alarm kuralını ekleme sorgusunu başlatır. |
| 69 | `(name, kind, metric_name, metric_unit, operator, threshold, cooldown_seconds)` | Başlangıç kuralında doldurulacak sütunları sıralar. |
| 70 | `SELECT 'CPU kullanımı %85 üzerinde', 'metric_threshold', 'cpu_usage', 'percent', 'gt', 85, 300` | cpu_usage/percent için >85 eşiğini ve 300 saniye beklemeyi belirler. |
| 71 | `WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001_alerting')` | Başlangıç kurallarını yalnızca ilk kurulumda ekler; kullanıcı kuralı yeniden adlandırsa bile sonraki açılışta eski adla geri gelmez. |
| 72 | `ON CONFLICT (name) DO NOTHING;` | Aynı benzersiz ad/sürüm zaten varsa ikinci kayıt eklemez. |
| 74 | `INSERT INTO alert_rules` | Başlangıç alarm kuralını ekleme sorgusunu başlatır. |
| 75 | `(name, kind, level, operator, threshold, window_seconds, cooldown_seconds)` | Başlangıç kuralında doldurulacak sütunları sıralar. |
| 76 | `SELECT '5 dakikada 50 üzeri ERROR', 'log_count', 'ERROR', 'gt', 50, 300, 300` | ERROR sayısı için >50 eşiğini, 300 saniye pencereyi ve beklemeyi belirler. |
| 77 | `WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001_alerting')` | Başlangıç kurallarını yalnızca ilk kurulumda ekler; kullanıcı kuralı yeniden adlandırsa bile sonraki açılışta eski adla geri gelmez. |
| 78 | `ON CONFLICT (name) DO NOTHING;` | Aynı benzersiz ad/sürüm zaten varsa ikinci kayıt eklemez. |
| 80 | `INSERT INTO schema_migrations (version) VALUES ('001_alerting')` | Bu kurulum sürümünü uygulanmış olarak kaydeder. Dosyanın tamamı hata verirse transaction bunu da geri alır. |
| 81 | `ON CONFLICT (version) DO NOTHING;` | Aynı benzersiz ad/sürüm zaten varsa ikinci kayıt eklemez. |

## migrations/002_batch_ingestion.sql

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/migrations/002_batch_ingestion.sql)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `-- Görevde kaç kayıt bulunduğunu takip eder; eski tekli görevler 1 olarak kalır.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 2 | `ALTER TABLE processed_tasks ADD COLUMN IF NOT EXISTS record_count INTEGER NOT NULL DEFAULT 1;` | Görevdeki kayıt sayısını tutan alanı ekler; eski görevler 1 olur. |
| 3 | `-- Toplu görevde her kayıt ayrı alarm kaynağıdır; eski bildirimlerde sıra numarası 0 kalır.` | Yorum satırıdır; nedeni açıklar, komut çalıştırmaz. |
| 4 | `ALTER TABLE alerts ADD COLUMN IF NOT EXISTS source_record_index INTEGER NOT NULL DEFAULT 0;` | Alarmın paketteki kaynak sıra numarasını tutan alanı ekler. |
| 5 | `ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_rule_id_source_task_id_key;` | Toplu görevde birden çok alarmı engelleyen eski benzersizlik kısıtını kaldırır. |
| 6 | `CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_source_record` | Yeni kaynak kayıt benzersizlik indeksini oluşturur. |
| 7 | `ON alerts (rule_id, source_task_id, source_record_index);` | Aynı kural/görev/kayıt sırası ikinci kez alarm oluşturamaz; farklı kayıtlar ayrılır. |
| 8 | `INSERT INTO schema_migrations (version) VALUES ('002_batch_ingestion') ON CONFLICT DO NOTHING;` | Bu kurulum sürümünü uygulanmış olarak kaydeder. |

## Test betikleri

tests/test_backend.py 16 işlevsel senaryoyu kontrol eder. Yeni senaryolar toplu kayıt, farklı servis ve kaynak alarmları, paket geri alma, boyut sınırı, görev takibi ve havuz satır biçimi temizliğini denetler.

scripts/verify_recovery.py worker kapalıyken gönderim, DB kesintisi sonrası RETRY/SUCCESS, worker alt süreç kaybında yeniden teslim ve kalıcı hata durumunu gerçek servislerle dener.
scripts/load_backend.py sınırlı sayıda log/metrik gönderir; HTTP cevabını ve bütün kayıtlar yazılana kadar geçen süreyi ölçer. Sonuçları JSON'a yazar, kendi test verilerini temizler.


## Paket ve belge değişiklikleri

- requirements.txt içindeki psycopg-pool==3.3.3, bağlantı havuzunun kurulması için eklenmiştir. Bu dosya Docker içinde de aynı paketlerin kurulmasını sağlar.
- .env.example içindeki DB_POOL_MAX=8, bilgisayarda çalışan API havuzunun üst sınırıdır. Gerçek .env ayarları Git'e eklenmez.
- compose.yaml içindeki REDIS_RESULT_URL, sonuçların Redis'in 1 numaralı veritabanına yazılmasını sağlar. 0 numara görev kuyruğu için kullanılır.
- api-contract.md, yeni toplu uçların ve görev takibinin istek/cevap kurallarını açıklar.
- README.md, kurulumu ve deneme komutlarını bir araya getirir.
- ilerleme-raporu.md ve rapor.docx, tamamlanan Faz 2 işlerini ve ölçülen test sonuçlarını içerir.
- test-results içindeki JSON dosyaları ölçüm kanıtıdır; uygulamanın kaynak kodu değildir.

## Yeni testleri okuma sırası

### tests/test_backend.py

268. satırdaki test_13, üç ölçümlük paketin kaydedilmesini ve farklı kaynaklardan birden fazla alarm oluşturabilmesini denetler. Aynı görev kimliği tekrar kullanıldığında yeni kayıt oluşmadığını da kontrol eder.

287. satırdaki test_14, tek paketteki 51 ERROR kaydının eşiği aşmasını denetler. Ardından alarm kontrolünde bilerek hata çıkarır; bütün paketin ve görev makbuzunun geri alınmasını bekler.

304. satırdaki test_15, boş listeyi, 101 kayıtlık listeyi, içinde uygunsuz veri bulunan paketi ve geçersiz görev kimliğini 422 ile reddetmemizi denetler.

310. satırdaki test_16, bir işlem bağlantıyı dict_row biçiminde kullandıktan sonra sonraki işlemin tuple_row biçimiyle başlamasını denetler. Havuzda bağlantı yeniden kullanıldığı için bu sıfırlama gerekir.

### scripts/verify_recovery.py

- docker fonksiyonu, Docker komutunu çalıştırır ve komut hata verirse kontrolü başarısız sayar.
- request, gerçek API'ye HTTP isteği gönderir; hata yanıtlarını da durum koduyla okuyabilir.
- wait_for, beklenen koşul oluşana kadar sınırlı süre kontrol eder.
- state, GET /tasks üzerinden görevin durumunu okur.
- payload, diğer verilerle karışmayan benzersiz test servisi ve CPU ölçümü hazırlar.
- submit, POST /metrics cevabının 202 olduğunu doğrular ve görev kimliğini saklar.
- verify_saved, SUCCESS sonrasında veritabanında tam bir kayıt ve bir görev makbuzu arar.
- Birinci denemede worker durdurulur; kayıt kuyrukta kalmalı, worker açılınca yazılmalıdır.
- İkinci denemede DB durdurulur; RETRY görülmeli, DB açılınca SUCCESS olmalıdır.
- Üçüncü denemede tablo kilidiyle görev bekletilir; çalışan alt süreç bulunup sonlandırılır. Yeniden teslimde tek kayıt oluşmalıdır.
- Dördüncü denemede API doğrulaması test amacıyla atlanıp uygunsuz iç görev gönderilir. FAILURE görünmeli ve kayıt geri alınmalıdır.
- finally, hata olsa da servisleri yeniden açar. Sonuç JSON'a yazılır; bütün denemeler geçerse yalnızca bu testin verileri temizlenir.

### scripts/load_backend.py

- argparse, kayıt sayısı, eşzamanlılık ve paket boyutu gibi terminal seçeneklerini okur.
- percentile, ölçülen HTTP sürelerini sıralar ve seçilen yüzdelik dilimi bulur.
- monitor, Redis kuyruğunu 0,1 saniyelik aralıklarla örnekler. En yüksek örnek kesin kuyruk zirvesi değildir; çalışan veya önceden ayrılmış görevleri içermez.
- send, bir log/metrik veya kayıt listesi gönderir; 202 cevabını, görev kimliğini, süreyi ve hatayı toplar.
- Veri hazırlama döngüsü kayıtların yarısını log, yarısını CPU metriği olarak üretir. Aynı denemeye özel servis adı kullanır.
- jobs, verileri paket boyutuna göre böler. 1.000 kayıt 100'lük pakette 10 HTTP isteği olur.
- ThreadPoolExecutor, gönderimleri seçilen sayıda eşzamanlı yürütür.
- İlk ölçüm, bütün HTTP kabul yanıtlarının alınmasına kadar geçen süredir.
- Veritabanı sayım döngüsü, kabul edilen kayıtların tamamının yazılmasını en fazla 120 saniye bekler.
- İkinci ölçüm, ilk gönderimden bütün kayıtların veritabanında görülmesine kadar geçen süredir.
- report, kabul/yazılma sayısı, HTTP hataları, süreler, hız, p50/p95, kuyruk örnekleri ve alarm sayısını JSON'a yazar.
- finally, izleme iş parçacığını durdurur. Bekleyen görev yoksa yalnızca bu denemenin benzersiz servisine ait verileri ve görev makbuzlarını temizler.

## Öğrenme sırası

1. database.py: ödünç bağlantı, with ve yield.
2. main.py: bir JSON listesinden toplu görev oluşturma.
3. tasks.py: tek transaction, görev kimliği ve kayıt sırası.
4. alerts.py: bir kez kural okuma, her kaydı kontrol etme.
5. celery_app.py ve GET /tasks: görev durumları.
6. Test sonuçları: ölçülen sayıların anlamı.


# Faz 3 React panelinin başlangıcı

18 Ekim 2026. İlk adım servis bağlantılarını gösteren ekranı kurmaktır. Grafik, log listesi ve SSE sonraki adımlardır.

## Kullanılan araçlar

- React, ekranı bileşen denilen parçalardan oluşturur. App, ilk ekran bileşenimizdir.
- JavaScript tarayıcıda çalışan programlama dilidir. JSX, JavaScript içinde ekran öğelerini HTML'ye benzeyen bir yazımla tanımlamayı sağlar.
- Vite, geliştirirken kaynakları tarayıcıya sunar. Dosyayı kaydettiğimizde ekranın yenilenmesini sağlar.
- Node.js, bilgisayarda Vite gibi JavaScript araçlarını çalıştırır.
- npm, package.json içinde yazan paketleri kurar ve scripts bölümündeki komutları çalıştırır.
- package-lock.json, paketlerin kesin sürümlerini kaydeder. Başka bilgisayarda npm ci aynı kilit dosyasını kullanır.

## frontend/src/main.jsx satırları

| Satır | Kod | Açıklama |
|---|---|---|
| 1 | import { StrictMode } from 'react' | Geliştirme sırasında ek kontroller yapan React bileşenini getirir. |
| 2 | import { createRoot } from 'react-dom/client' | React ekranını tarayıcıdaki HTML'ye bağlayan fonksiyonu getirir. |
| 3 | import App from './App.jsx' | Asıl ekranımızın bulunduğu dosyadan App bileşenini getirir. |
| 4 | import './styles.css' | Görünüm kurallarını yükler. |
| 6 | createRoot(document.getElementById('root')).render( | index.html içindeki root alanını bulur ve React'in ekranı buraya çizmesini ister. |
| 7 | <StrictMode> | Ekranı geliştirme kontrolleriyle sarar. |
| 8 | <App /> | App fonksiyonunun tanımladığı ekranı yerleştirir. |
| 9 | </StrictMode>, | Kontrol sarmalayıcısını kapatır. |
| 10 | ) | render çağrısını tamamlar. |

## frontend/src/App.jsx akışı

useState, ekranda değişebilen bir değeri saklar. checking düğmenin bekleme durumunu; checks son servis yanıtını; message kullanıcıya gösterilecek açıklamayı tutar. Başlangıçta checks null olduğu için kartlarda Kontrol bekliyor yazılır.

checkConnection düğmeye tıklanınca çalışır. Önce bekleme durumunu açar, önceki sonucu temizler. fetch ile /api/ready adresine HTTP isteği gönderir. await, bu fonksiyon içinde yanıt gelmesini bekler; tarayıcı arayüzü çalışmaya devam eder. AbortSignal.timeout, yanıt beklemesini 15 saniyeyle sınırlar.

Yanıt JSON'a çevrilir ve beklenen alanları içerip içermediği kontrol edilir. API geçerli yanıt verdiyse api true olur; veritabanı ve Redis kendi durumlarıyla işaretlenir. 503 yanıtındaki kontrol sonuçları da gösterilir. Yanıt alınamazsa catch açıklayıcı hata mesajını yazar. finally her durumda düğmenin bekleme durumunu kapatır.

services.map, listedeki her servis için bir kart üretir. key, React'in her kartı ayırt etmesini sağlar. onClick, düğmeye tıklamayı fonksiyona bağlar. disabled, istek sürerken ikinci kez tıklamayı engeller. role=status, değişen mesajı ekran okuyucuya bildirir.

## frontend/vite.config.js akışı

plugins: [react()] React kaynaklarının Vite ile işlenmesini etkinleştirir. Geliştirme sunucusu yalnızca 127.0.0.1 adresinde, 5173 portunda açılır. strictPort, bu port doluysa başka porta sessizce geçmek yerine hata vermesini sağlar.

/api ile başlayan istekler 8000 portundaki FastAPI'ye iletilir. rewrite baştaki /api bölümünü kaldırır: panel /api/ready ister, FastAPI /ready alır. Bu yönlendirme geliştirme içindir; canlı ortamda ayrıca yapılandırılmalıdır. Veritabanı parolaları tarayıcıya aktarılmaz.

## Diğer dosyalar

index.html içindeki root, React ekranının yeridir. script etiketi src/main.jsx dosyasını başlatır. styles.css koyu temayı, kartları ve küçük ekran düzenini tanımlar. .gitignore node_modules, dist ve npm önbelleğini dışarıda tutar. .dockerignore frontend klasörünü Python worker imajına göndermez.


## Faz 3 gerçek logların tabloda gösterilmesi

Şemadaki yerimiz: PostgreSQL → GET /logs → Vite /api yönlendirmesi → React LogTable → tarayıcıdaki tablo.

App.jsx içindeki import LogTable, yeni bileşeni getirir. JSX içindeki <LogTable /> bu bileşenin ekranda görünmesini sağlar. Ayrı dosya, servis kartlarıyla log tablosunun kodunu ayırır.

### LogTable.jsx içindeki state değerleri

- logs ve setLogs: Veritabanından gelen kayıt listesi. Başlangıçta [] yani boş listedir.
- loading ve setLoading: İstek sürüyorsa yükleniyor mesajı gösterir, yenileme düğmesini kapatır.
- error ve setError: Son okuma hatasıdır. Boş metin hata olmadığını belirtir.
- lastUpdated ve setLastUpdated: Son başarılı okumanın zamanı.
- refreshKey ve setRefreshKey: Yenile düğmesi bu sayıyı artırır. Sayı değişince useEffect yeni okuma yapar.

### loadLogs fonksiyonunun sırası

1. setLoading(true): Ekranı bekleme durumuna geçirir.
2. setError(''): Önceki hatayı temizler.
3. fetch('/api/logs?limit=20', ...): Son 20 log için HTTP GET gönderir. Buradaki /api, geliştirme sunucusunda kaldırılarak FastAPI /logs adresine iletilir.
4. await: Yanıtı bu fonksiyon içinde bekler; sayfanın diğer işleri devam eder.
5. response.ok: HTTP yanıtının başarılı olup olmadığını kontrol eder. 503 gibi hatalarda anlaşılır açıklama gösterilir.
6. response.json(): HTTP gövdesini JavaScript verisine dönüştürür.
7. Array.isArray(data.items): items gerçekten bir liste mi kontrol eder.
8. setLogs(data.items): Gelen kayıtları React state'ine koyar. Ekran yeni listeye göre güncellenir.
9. setLastUpdated(new Date()): Başarılı okuma saatini saklar.
10. catch: Bağlantı, zaman aşımı veya uygunsuz yanıtı yakalar. Hata, boş kayıt listesiyle karıştırılmaz.
11. finally: Zaman aşımı sayacını kapatır ve yükleniyor durumunu bitirir.

### useEffect ve istek iptali

useEffect, bileşen ekrana geldiğinde ve refreshKey değiştiğinde okuma yapar. Sondaki [refreshKey] bu bağlılığı belirtir. Geliştirme StrictMode kontrol sırasında effect'i yeniden başlatabilir; temizleme kodu önceki isteği iptal eder.

AbortController bir isteği durdurabilmemizi sağlar. 15 saniyelik sayaç dolarsa istek iptal edilir. Effect'in döndürdüğü temizleme fonksiyonu, bileşen kaldırıldığında veya yeni okuma başladığında active değerini false yapar ve önceki isteği iptal eder. Böylece eski yanıt yeni listeyi değiştirmez.

### JSX tablosu

loading true ise yükleniyor mesajı gösterilir. İşlem bittiğinde error doluysa hata mesajı gösterilir. Hata yok ve logs boşsa kayıt olmadığı açıklanır. Kayıt varsa logs.map, her logu bir <tr> tablo satırına dönüştürür.

key, satırları ayırt etmek için timestamp ve id alanlarını birlikte kullanır; bu ikili backend tablosunun birincil anahtarıdır. Hücrelerde log.timestamp, log.service, log.level ve log.message gösterilir. Metinler React tarafından metin olarak çizilir; log mesajı HTML olarak çalıştırılmaz.

Intl.DateTimeFormat UTC zamanını tarayıcının yerel saatine göre okunabilir biçime çevirir. Başlıktaki kayıt sınırı 20'dir; bütün arşivin toplam kayıt sayısı değildir. Bu aşamada yeni kayıtlar otomatik gelmez; Logları yenile düğmesi yeniden GET isteği gönderir.


## Faz 3 SSE ile canlı log akışı

18 Ekim 2026, API 0.4.0. Akışımız: Worker commit → veritabanındaki son 20 kayıt değişir → SSE logs_changed → React refreshKey artar → GET /logs → tablo güncellenir.

### streams.py

POLL_SECONDS = 2, veritabanı kontrol aralığıdır. HEARTBEAT_SECONDS = 15, bağlantıyı açık tutmaya yardımcı olan yorumun aralığıdır. SSE tarayıcıya açık bağlantı üzerinden gönderilir; veritabanını iki saniyede bir kontrol eden taraf backend'dir.

logs_revision, tabloyla aynı sıradaki ilk 20 kaydın timestamp ve id alanlarını alır. Bu listenin SHA-256 özetini oluşturur. Aynı liste aynı özeti üretir; liste değişince özet değişir. Yalnızca en büyük id'yi kullanmayız: eşzamanlı işlemler farklı sırada commit edebilir. SELECT sorgusu commit edilmemiş satırları göremez.

sse_event, olayı SSE metin biçimine dönüştürür. id olayın özet kimliğini, event olay türünü, data ise JSON içeriğini belirtir. Boş satır bir olayın sonudur.

log_events, async generator'dür: yield ile bir parçayı tarayıcıya yollar, sonra bağlantıyı kapatmadan devam eder. retry: 3000, tarayıcıya bağlantı koparsa yaklaşık üç saniye sonra yeniden denemesini söyler.

request.is_disconnected, tarayıcının bağlantıyı kapatıp kapatmadığını kontrol eder. anyio.to_thread.run_sync, senkron PostgreSQL sorgusunu ayrı iş parçacığında çalıştırır; API'nin async döngüsü bu sorgu boyunca bloke edilmez. get_connection bağlamından çıkınca bağlantı havuza geri döner.

Özet önceki değerden farklıysa logs_changed gönderilir. DB hatası varsa stream_status gönderilir; DB geri geldiğinde liste aynı olsa da yeniden eşitleme bildirimi verilir. İlk bağlantıda da bir bildirim gönderilir. Kalıcı olay geçmişi tutulmaz.

: keepalive, EventSource'un uygulama olayı olarak işlemeyeceği yorumdur. await asyncio.sleep(2), bağlantıyı açık tutarak bekler; beklerken DB bağlantısı elde tutulmaz.

### main.py

GET /stream/logs, StreamingResponse döndürür. media_type='text/event-stream' tarayıcıya bunun olay akışı olduğunu söyler. Cache-Control: no-cache önbellekte eski akış tutulmasını, X-Accel-Buffering: no ise bunu destekleyen ters proxy'lerde olayların biriktirilmesini önlemeye yöneliktir.

### LogTable.jsx

streamStatus, canlı bağlantının ekranda gösterilen durumudur. EventSource('/api/stream/logs'), akışa bağlanır. Vite /api bölümünü kaldırıp FastAPI'ye iletir.

stream.addEventListener('logs_changed', ...) olay gelince refreshKey değerini artırır. Önceden yazdığımız log okuma useEffect'i bu değişiklik yüzünden yeniden çalışır. Yeni bir tablo sistemi kurmak yerine mevcut GET /logs okumasını kullanırız.

onerror, kesinti olduğunda yeniden bağlanma durumunu gösterir. EventSource, geçici bağlantı kesintilerinde kendisi yeniden bağlanmayı dener. stream_status geldiğinde DB'nin beklenmekte olduğu gösterilir. EventSource CLOSED durumuna girdiyse sayfanın yenilenmesi gerektiği açıklanır.

Effect'in temizleme fonksiyonundaki stream.close(), bileşen kaldırıldığında bağlantıyı kapatır. Yeni gelen bildirimin başlattığı GET tamamlanana kadar mevcut tablo görünür kalır. Son başarılı okuma saati aşağıda gösterilir.

### Testlerin anlamı

Yeni tests/test_stream.py; SSE biçimini, ilk bildirimi, commit öncesinde olay gelmemesini ve gerçek POST/kuyruk/worker yolundan sonra olay gelmesini kontrol eder. Yeniden bağlantıda güncel görünüm yeniden eşitlenir. DB hatasından toparlanma ve kopmuş istemcide sorgulamayı durdurma ayrı testlerde taklitlerle kontrol edilir. Beş yeni SSE kontrolü önceki 16 backend testiyle birlikte geçmiştir.


## Faz 3 filtreleme ve sayfalama

18 Ekim 2026, API 0.4.1. Akış: Formda taslak değerler → Uygula → sorgu parametreleri → GET /logs → filtreli tablo. İlk sayfada SSE aynı filtrelerle dinlenir.

### Taslak ile uygulanmış filtre farkı

draftFilters, kutulara yazdığımız değerlerdir. changeFilter, yalnızca bu taslağı günceller ve henüz uygulanmadı bilgisini açar. Bu sırada mevcut liste aynı sorguyu göstermeye devam eder.

applyFilters, formun varsayılan sayfa yenilemesini event.preventDefault ile engeller. buildLogFilters taslağı sorgu metnine çevirir. Başarılıysa view içine uygulanmış filtreler yazılır ve offset sıfırlanır. Form hatalıysa önceki görünüm korunur. clearFilters hem taslağı hem uygulanmış filtreleri temizler ve ilk sayfaya döner.

### logQuery.js

PAGE_SIZE = 20 her sayfadaki en fazla kayıt sayısıdır. MAX_OFFSET = 100000 API sınırıdır. EMPTY_FILTERS başlangıçtaki boş form değerlerini içerir.

buildLogFilters içinde URLSearchParams, sorgunun alanlarını güvenli URL yazımına çevirir. service, level ve q boş değilse eklenir; baş/son boşluklar temizlenir. Böylece boş q parametresi yüzünden 422 oluşmaz. Başlangıç/bitiş alanları new Date ile tarayıcının yerel saati olarak okunur; toISOString UTC zamanını Z son ekiyle verir. Başlangıç bitişten sonraysa hata fırlatılır ve istek gönderilmez.

buildLogPageQuery uygulanmış filtreleri korur; limit ve offset ekler. Negatif, sınırı aşan, kesirli veya 20'nin katı olmayan offset reddedilir.

### Sayfalama nasıl çalışıyor

limit=20, en fazla 20 kayıt getir der. offset=0 ilk sayfa, offset=20 ilk 20 kaydı atlayıp ikinci sayfayı getir demektir. Ekrandaki sayfa numarası offset / 20 + 1 ile bulunur.

Backend bir satır fazla okuyup has_more bayrağını hesaplar. Sonraki düğmesi yalnızca sonraki sayfa varsa açılır ve next_offset değerini kullanır. Önceki düğmesi offset'i 20 azaltır. Yeni filtre uygulamak offset'i sıfırlar. İlk sayfa/canlı düğmesi mevcut filtrelerle ilk sayfaya döner.

### Yanıtlar neden sorguyla birlikte saklanıyor

result içinde query ve items birlikte saklanır. Ekranın istediği pageQuery ile yanıtın query alanı aynı değilse eski satırlar gösterilmez. Yeni sorguda önceki istek iptal edilir. Böylece hızlıca filtre veya sayfa değiştirirken eski isteğin sonucu yeni sonuçları ezmez. Aynı sorgu arka planda yenilenirken mevcut tablo görünür kalır.

### Filtreli SSE

useEffect, view.filters ve view.offset değişince çalışır. İlk sayfadaysak EventSource URL'sine uygulanmış filtreler eklenir. İlk sayfa dışındaysak bağlantı kapatılır ve canlı yenileme duraklatılır. Böylece eski kayıtları okurken otomatik güncelleme satırları değiştirmez. Bu davranış offset sorgularını sabit bir veritabanı anlık görüntüsüne dönüştürmez; yeni kayıtlar sayfa sırasını yine etkileyebilir.

Backend'de liste ve SSE log_filters fonksiyonunu ortak kullanır. streams.logs_revision önce bu filtreleri uygular, sonra tarih/kimliğe göre ilk 21 satırı kontrol eder. Genel son kayıtların dışında kalan bir servise ait yeni log da kendi filtreli görünümünü değiştirebilir. 21. kayıt, ilk 20 satır aynı kalsa bile has_more değişikliğini bildirir.

### Doğrulama

24 backend/SSE testi ve dört Node sorgu testi başarılıdır. Node testleri bir tarayıcı testi değildir. Testler başlangıç/bitiş dönüşümünü, URL özel karakterlerini, sayfa sınırını ve filtreli canlı bildirimleri doğrular.


## Faz 3 log detayları

18 Ekim 2026. Şemadaki yerimiz: GET /logs yanıtı → React'te kayıt listesi → seçilen kayıt → detay penceresi. API yanıtında tam mesaj, tags ve stack_trace zaten bulunduğundan bu adım yeni HTTP isteği göndermez.

### LogTable.jsx

selectedLog, incelenmek üzere seçilen kayıt nesnesidir. Başlangıçtaki null, henüz kayıt seçilmediğini belirtir. Detay düğmesinin onClick işleyicisi openDetails(log, event.currentTarget) çağırır. log seçilen satırın verisidir; event.currentTarget tıklanan düğmedir.

setSelectedLog(log), bu kayıt nesnesini saklar. <LogDetails log={selectedLog} onClose={closeDetails} /> bu veriyi detay bileşenine aktarır. Bileşene bu şekilde verilen bilgilere props denir. Canlı liste yenilense de selectedLog aynı kayıt nesnesini tutar; başka bir satır yanlışlıkla detayın yerine geçmez.

useRef, HTML öğesine veya bir değere kalıcı referans tutar. detailOpenerRef, pencereyi açan düğmeyi hatırlar; kapanınca klavye odağı bu düğmeye döndürülür. Canlı liste o düğmeyi artık içermiyorsa headingRef ile tablo başlığına dönülür. Bu referansları değiştirmek, useState gibi tek başına ekranı yeniden çizdirmez.

### LogDetails.jsx

log ve onClose, bileşenin aldığı iki prop'tur. dialogRef, HTML'deki dialog öğesini gösterir. useEffect, seçilen log değiştiğinde çalışır. log varsa showModal pencereyi açar; log yok ve pencere açıksa close kapatır. Pencere açıkken body kaydırması durdurulur; effect temizliğinde eski değer geri konur.

Native dialog, açıldığında arka sayfayı etkileşime kapatır ve klavye odağını pencere içinde yönetir. Kapat düğmesi dialogRef.current.close() çağırır. Escape de tarayıcı üzerinden pencereyi kapatır. onClose olayı parent bileşendeki closeDetails fonksiyonunu çağırır; selectedLog null olur ve odak geri verilir.

DetailTime, zamanı yerel saatle okunabilir biçimde gösterir; altta API'den gelen saat dilimli metni de korur. timestamp olayın zamanı, received_at platformun kaydı aldığı zamandır.

<pre> içindeki log.message ve log.stack_trace satır sonlarını koruyarak gösterilir. Metinler JSX içinde metin olarak çizilir; HTML olarak çalıştırılmaz. JSON.stringify(tags, null, 2), etiket nesnesini iki boşluk girintili okunabilir metne çevirir.

Stack trace, hatanın oluşmasına kadar kodda hangi çağrılardan geçildiğini anlatan hata izidir. Bu alan null veya boşsa, bu kayıtla hata izi gönderilmediği açıklanır; bu açıklama uygulamada hata olmadığı anlamına gelmez.

Tablodaki üç satır sınırı yalnızca CSS önizlemesidir. Veri kesilmez; detay penceresine tam kayıt aktarılır.


## Faz 3 canlı CPU grafiği — adım adım

Şemadaki yerimiz: uygulama → POST /metrics → Redis → worker → veritabanı → GET /metrics ve SSE → React grafiği. Önceki kayıt akışını değiştirmedik; arşivdeki sayıları okunabilir bir grafiğe bağladık.

### 1. metricQuery.js: hangi kayıtları istiyoruz?

METRIC_LIMIT = 100, grafikte en fazla kaç kayıt gösterileceğidir. CPU_NAME = 'cpu_usage' ölçümün adı, CPU_UNIT = 'percent' birimidir. buildMetricQuery(service), servis adını trim ile baş/son boşluklardan temizler; boş veya çok uzun adı reddeder. URLSearchParams bu dört değeri HTTP sorgusuna çevirir. Örneğin service=payment-service&name=cpu_usage&unit=percent&limit=100 isteği, yalnızca o servisin CPU yüzdesi kayıtlarını ister.

metricPoints(data, service), API yanıtının beklenen sayfa olduğunu ve her kaydın aynı servis/ad/birime ait olduğunu kontrol eder. Date.parse(timestamp), zamanı milisaniye cinsinden bir sayıya çevirir; bu sayı X eksenine yerleştirilebilir. value yüzde değeridir ve 0–100 aralığında olmalıdır. API satırları yeni → eski döndürür; grafik eski → yeni sıralar. API yanıtı yerinde değiştirilmez. timeDomain, ilk ve son noktanın zamanını eksen sınırı yapar. Tek zaman varsa iki yana 30 saniyelik boşluk ekler; yeni veya sahte ölçüm üretmez.

### 2. MetricsPanel.jsx: ekrandaki bilgiyi saklamak

useState('payment-service'), başlangıçtaki örnek servis adını tutar. draftService kutuda yazılan değerdir; service grafikte uygulanmış servistir. Göster düğmesi applyService çağırır. event.preventDefault(), formun tüm sayfayı yenilemesini engeller. buildMetricQuery girdiyi doğrular; setService yeni servisi uygular. Sonuçlar query bilgisiyle birlikte saklanır; yeni servise geçince eski servisin grafiği görünmez.

result.points grafiğin noktalarıdır. loading istek sürdüğünü, error başarısızlığı, hasMore daha eski kayıtların bulunduğunu, updatedAt son başarılı GET zamanını tutar. latest = points.at(-1), olay zamanına göre son kayıt demektir. Sıfır yüzde de geçerli ölçümdür; boş sonuçla aynı değildir.

### 3. GET ile ölçümleri yüklemek

useEffect, query veya refreshKey değiştiğinde çalışır. fetch('/api/metrics?' + query), backend'den kayıtları ister. await response.json(), JSON yanıtını JavaScript nesnesine çevirir. metricPoints bunu grafik noktalarına dönüştürür. setResult bu noktaları React belleğine koyunca ekran yeniden çizilir.

AbortController, servis değiştiğinde önceki isteği iptal eder. 15 saniyelik setTimeout istek süresini sınırlar. active bayrağı kapanmış veya başka sorguya geçmiş bileşene eski yanıtın yazılmasını engeller. Aynı sorgu yenilenirken eldeki noktalar korunur; istek başarısızsa önceki verinin güncelliğinin doğrulanamadığı açıklanır.

### 4. SSE ile yeni kayıttan haberdar olmak

new EventSource('/api/stream/metrics?' + query), açık bildirim bağlantısını kurar. metrics_changed gelince setRefreshKey(value => value + 1) çağrılır. refreshKey değişikliği GET effect'ini yeniden çalıştırır. Bildirimin içinde tüm grafik yoktur; bildirim yeni veriyi istememizi sağlar. Servis değişince effect temizliği stream.close() ile eski bağlantıyı kapatır. DB erişim hatası veya yeniden bağlanma ekranda ayrıca gösterilir. Canlı bağlantının açık olması, uygulamanın o anda yeni CPU örneği gönderdiğini kanıtlamaz; ölçüm zamanına bakılmalıdır.

### 5. Recharts grafiği nasıl çiziyor?

ResponsiveContainer, grafiği içinde bulunduğu kutunun genişliğine uyarlar. LineChart data={points}, noktaları çizim bileşenine verir. XAxis dataKey='time' type='number' scale='time', her noktanın gerçek zamanını yatay konuma çevirir. Böylece iki dakika arayla gelen iki kayıt ile iki gün arayla gelen iki kayıt aynı aralığa yerleştirilmez.

YAxis domain={[0, 100]}, yüzde ölçeğini belirler. Line dataKey='value', noktanın CPU sayısını dikey konuma koyar; type='linear' noktaları düz çizgilerle birleştirir. isAnimationActive={false}, canlı güncellemelerde çizgi animasyonunu kapatır. Tooltip, noktanın zamanını, değerini ve servisini gösterir. Tek nokta da görünür. Çizgi, aradaki zamanlarda ölçüm varmış anlamına gelmez. Altındaki details/table aynı sayıları klavye ile okunabilir biçimde sunar. Kayıtlar hizmet düzeyinde filtrelenir; farklı host etiketlerine göre ayrı çizgi veya ortalama oluşturulmaz.

### 6. Backend: ortak filtre ve bildirim döngüsü

queries.metric_filters, servis/zaman/etiket filtrelerine name ve unit eşitliğini ekler. Hem GET /metrics hem GET /stream/metrics bu fonksiyonu çağırır. Kullanıcı değerleri SQL metnine eklenmez; sorgu parametresi olarak gönderilir.

streams.metrics_revision, filtreli son limit+1 satırın zaman ve kimliğinden özet çıkarır. Özet değişirse metrics_changed gönderilir. Fazladan kayıt, grafiğin dışında daha eski kayıt var mı bilgisini günceller. Kimlik/zaman listesinde bulunmayan eski bir kayıt mevcut pencereyi değiştirmez. Kayıtlar eklenerek işlendiği için değer değişiklikleri şu an ayrı izlenmez; gelecekte düzenleme API'si yapılırsa bu özet de genişletilmelidir.

revision_events, log ve metrik için ortak açık bağlantı döngüsüdür. İki saniyede bir kısa DB sorgusu yapar, özet değiştiyse haber verir, beklerken DB bağlantısını havuza geri bırakır. İlk bağlantıda ve DB kurtarmasında da güncel görüntüyü yeniden okutacak bildirim gönderir. Çok sayıda kullanıcı için ortak dağıtım sistemi henüz yoktur; her açık akış ayrı kontrol yapar.

### 7. App.jsx ve paketler

Recharts 3.10.1 package.json/package-lock.json dosyalarına eklendi. lazy(() => import('./MetricsPanel.jsx')), grafik kodunu ayrı JavaScript parçasında yükler. Suspense, bu dosya yüklenene kadar kısa bir hazırlanıyor mesajı gösterir. Üretim derlemesinde ana dosya yaklaşık 239 kB, grafik dosyası 359 kB'dir; bunlar sıkıştırma öncesi yaklaşık değerlerdir.

### 8. Neyi doğruladık?

27 backend/SSE testi, sekiz frontend testi ve derleme başarılıdır. Yeni metrik testleri gerçek API → kuyruk → worker → commit → SSE → GET zincirini, filtreleri ve pencere sınırlarını denetler. Node testleri seri karışmasını, geçersiz değerleri, sıfır yüzdesini, kronolojik sıralamayı ve tek zaman noktasını denetler. Tarayıcıdaki yerleşim ve etkileşim otomatik doğrulanmadı; kullanıcı grafiği açıp yeni ölçüm göndererek kontrol edecektir.

Kaynak: Recharts eksen açıklamaları: https://recharts.github.io/en-US/guide/domainAndTicks/ ve XAxis API: https://recharts.github.io/en-US/api/XAxis/ . Kullanılan paket sürümünün yerel tür tanımları da kontrol edildi.


### Grafik zaman görünümü düzeltmesi

Bir hafta önceki kayıtlarla bugün birkaç dakika arayla gelen kayıtları aynı gerçek zaman eksenine koyunca yeni noktalar birbirine çok yaklaşır. Bu yüzden kayıtları sırayla eşit aralığa dizmek yerine zaman penceresi seçimi ekledik; böylece gerçek zaman anlamı korunur.

METRIC_WINDOWS üç pencere tanımlar: 1h, 24h, all. windowKey seçili pencereyi useState içinde tutar; başlangıcı 1h'dir. metricWindow, points.at(-1).time ile kayıtlı son zamanı alır, seçilen süreyi çıkarır ve bu sınırdan önceki noktaları geçici olarak görünümden ayırır. Veritabanından silmez. shownPoints grafiğe ve tabloya birlikte verilir. Pencere mevcut son 100 kayda uygulanır; daha eski kayıtları ayrıca istemez.

ResponsiveContainer.onResize gerçek kutu genişliğini chartWidth içine yazar. metricTicks bu genişliğe göre 2–6 zaman etiketi seçer. MetricTimeTick saat ile tarihi iki SVG tspan satırında gösterir. metricTickLabel kısa zaman aralığında saniyeleri, 10 saniyeden kısa aralıkta milisaniyeleri ekler. Böylece farklı zamanlar yalnızca aynı dakika etiketiyle yazılmaz. Sayısal zaman ekseni korunur.

duplicateCount aynı olay zamanını taşıyan ek kayıtları sayar. Aynı zamandaki farklı değerlerin aynı dikey hizada görünmesi doğrudur; bunlara yapay saat eklemeyiz. MetricTooltip, o zamanla eşleşen shownPoints kayıtlarının hepsini listeler. Tüm kayıtlar görünümünde eski ve yeni zamanlar tekrar tek eksene alınacağı için yakın örneklerin sıkışması mümkündür; 1 saat seçimiyle yakınlaşılır.

Üç yeni test kullanıcının haftalık/dakikalık dağılımını, aynı zamanlı kayıtların korunmasını, pencerenin son ölçüme göre hesaplanmasını, dahil sınırları, dar ekran etiket sayısını ve saniye/milisaniye ayrımını doğrular. Toplam 11 frontend testi ve derleme başarılıdır; görsel tarayıcı doğrulaması yapılmamıştır.


## Faz 3 metrik seçimi — aynı grafik, farklı ölçümler

Şemadaki yerimiz yine veritabanı → API/SSE → React grafiği. Yeni veri depolama sistemi kurmadık; mevcut name ve unit alanlarıyla grafiğin hangi ölçümü isteyeceğini seçilebilir yaptık.

### 1. METRIC_TYPES

metricQuery.js içindeki METRIC_TYPES, ekranın tanıdığı üç ölçümün tanımıdır. key seçimi React içinde ayırt eder; label ekrandaki başlık, shortLabel kısa isim, name API'nin ölçüm adı, unit API'nin birimidir. percent, yüzde ölçeği gerekip gerekmediğini belirtir. CPU cpu_usage/percent, bellek memory_usage/percent, yanıt süresi response_time/ms kullanır. metricType(key) bu tanımı bulur; bilinmeyen seçim için hata verir.

### 2. Sorguyu ve veriyi seçime bağlamak

buildMetricQuery(service, metricKey), seçilen türün name/unit değerlerini URLSearchParams içine koyar. metricPoints(data, service, metricKey), gelen satırların tam bu servis/isim/birime ait olduğunu kontrol eder. Yüzdede 101 geçersizdir; yanıt süresinde 420.5 geçerlidir. Yanıt süresi negatif olamaz. Bunlar panelde çizdiğimiz fiziksel ölçümlerin beklentileridir; genel API farklı metrik adlarını da saklayabilir. formatMetricValue yüzde için %64,2, yanıt süresi için 420,5 ms üretir; sıfır da doğru bir değerdir.

### 3. Form ve React state

draftMetricKey açılır kutuda seçilen henüz uygulanmamış değerdir. metricKey grafikte uygulanmış türdür. select içindeki option öğeleri METRIC_TYPES üzerinden oluşturulur. onChange taslağı değiştirir. Göster düğmesinde setService ile servis, setMetricKey ile metrik birlikte uygulanır. query değişince önceki HTTP isteği ve SSE bağlantısı temizlenir; yeni seçimle yenileri açılır. Sonuçlar query ile saklandığından CPU yanıtı yanıt süresi başlığı altında görünmez.

### 4. Birim ve eksen

CPU ile bellek aynı yüzde ölçeğini kullanır: domain=[0,100]. Yanıt süresinde domain=[0,'auto'] kullanılır; üst sınırı grafik kütüphanesi gelen sayılardan hesaplar. Bu yüzden 420 ms değeri 100 sınırında kesilmez. YAxis birimi, Line ismi, Tooltip değerleri, özet kartı ve tablo aynı type tanımından gelir. Farklı birimler tek seride birleştirilmez veya kendiliğinden dönüştürülmez.

### 5. Veri gelmemesi

Yeni seçilen metrik hiç gönderilmemişse grafik yerine o servis için kayıt bulunmadığı ve beklenen name/unit çifti yazılır. Ekran bilgisayardan CPU, bellek veya süre ölçmez; POST /metrics ile gelen kayıtları gösterir. Kullanıcı örneğin response_time/ms türünde bir kayıt gönderince mevcut worker bunu kaydeder; metrik SSE bağlantısı haber verir ve grafik güncellenir.

### 6. Kontrol

14 frontend testi ve derleme başarılıdır. Seçimin doğru sorguyu üretmesi, birimlerin karışmaması, yanıt süresinin 100'den büyük olabilmesi, yüzde sınırları, sıfır ve birim biçimlendirmesi test edildi. Geçici kayıtlarla gerçek API → worker → SSE → Vite GET zinciri bellek ve yanıt süresi için kontrol edildi; deneme verileri temizlendi. Bu kontroller tarayıcıda görsel/tıklama testi değildir.


## Faz 3 alarm bildirimleri — adım adım

Şemadaki yerimiz: worker → alarm kuralını değerlendir → alerts tablosuna kaydet → GET /alerts → React listesi. Bu adım alarm motorunu yeniden yazmaz; daha önce oluşan bildirimleri kullanıcıya gösterir.

### 1. alertQuery.js

ALERT_PAGE_SIZE = 20, sayfa başına kayıt sınırıdır. EMPTY_ALERT_FILTERS içinde status='open' vardır; ilk görünüm incelenmemiş bildirimlerdir. API'deki open, sorunun kesinlikle sürmekte olduğunu ifade etmez. buildAlertFilters, servis adını temizleyip service/status alanlarını URLSearchParams içine ekler. Durum boşsa Tümü, open ise İncelenmeyenler, acknowledged ise Görüldü seçilmiştir.

buildAlertPageQuery aynı filtreleri korur; limit ve offset ekler. Örneğin limit=20&offset=20, ilk 20 kaydı atlayıp ikinci sayfayı ister. Geçersiz veya API sınırını aşan offset reddedilir. validateAlertPage, yanıtın beklenen sayfa olduğunu ve kayıtların geçerli zaman/durum alanlarını taşıdığını denetler. validateAcknowledgment, sunucunun tam istediğimiz alarm için acknowledged durumu ve bir görülme zamanı döndürdüğünü kontrol eder. Böylece düğmeye basmak tek başına başarı sayılmaz.

### 2. AlertsPanel.jsx state

draftFilters formdaki henüz uygulanmamış değerlerdir. view.filters uygulanmış filtre, view.offset mevcut sayfadır. Uygula ile filtreler doğrulanıp offset sıfırlanır. result içinde query ve gelen items birlikte tutulur. result.query mevcut query ile aynı değilse önceki satırlar yeni başlık/filtre altında gösterilmez. loading, error, hasMore, nextOffset ve updatedAt yükleme, hata, sayfalama ve son başarılı veri alımı içindir.

busyId, şu an görüldü işaretlenen alarm kimliğidir. notice başarı/hata mesajıdır. acknowledgmentRef etkin değişiklik isteğinin AbortController nesnesini tutar; bu referans hemen değiştiğinden çok hızlı çift tıklama da ikinci PATCH başlatmaz. noticeRef, işlem sonrası klavye odağını sonuç mesajına taşır.

### 3. Listeyi almak ve yenilemek

useEffect içinde fetch('/api/alerts?' + query), mevcut sayfayı ister. JSON yanıtı doğrulandıktan sonra setResult listeyi ekrana taşır. AbortController ve 15 saniyelik süre sınırı vardır. Filtre, sayfa veya manuel yenileme değiştiğinde önceki istek ve zamanlayıcı temizlenir.

İlk sayfada GET tamamlandıktan sonra setTimeout(loadAlerts,10000) yeni kontrolü planlar. Önceki istek tamamlanmadan sonraki başlatılmaz. Bu alarm bölümü periyodik GET kullanır; log ve metrik grafikleri SSE kullanmaya devam eder. Geçmiş sayfalarda otomatik zamanlayıcı kurulmaz. Ağ gecikmesi ve tarayıcının arka plan sınırlamaları nedeniyle süre tam 10 saniye garantisi değildir.

### 4. Görüldü işlemi

onClick, acknowledge(alert) çağırır. setBusyId(alert.id) işlem durumunu açar ve liste effect'i durdurulur; eski GET yanıtı yeni görülme bilgisini ezemez. fetch('/api/alerts/' + alert.id + '/acknowledge', {method:'PATCH', ...}) mevcut kaydı sunucuda işaretler. PATCH burada kaydın bir bölümünü güncelleme isteğidir. Body göndermiyoruz; uç noktanın adı hangi işlemi istediğimizi zaten belirtir.

Yanıt validateAcknowledgment ile doğrulanınca başarı mesajı yazılır. finally bölümünde busyId temizlenir ve refreshKey artırılır. Liste tekrar GET ile gelir; İncelenmeyenler filtresindeki satır artık çıkmış olur, sayfanın doluluğu ve Sonraki düğmesi de gerçek yanıta göre güncellenir. Görüldü filtresi alarmı ve sunucunun acknowledged_at zamanını gösterir. İkinci kez aynı isteğin gönderilmesi ilk görülme zamanını değiştirmez.

İletişim koparsa PATCH veritabanına kaydedilmiş, fakat yanıt istemciye ulaşmamış olabilir. Bu yüzden hata mesajı işlemin kesin yapılmadığını söylemez; listenin tekrar kontrol edilmesini ister. Bileşen kapanırsa açık istek iptal edilir. Mesajlara HTML değil JSX metni olarak yer verilir.

### 5. Alarm ne anlatıyor?

triggered_at alarmın üretildiği zamandır. rule_name ve message alarm oluştuğunda kaydedilmiştir; güncel kural değiştirilse de bu eski bildirimin açıklaması korunur. status='acknowledged', kullanıcının bildirimi incelediğini belirtir. Sistemin düzelip düzelmediğini ayrıca gözlemlememiz gerekir. Bu projede otomatik resolved durumu henüz yoktur.

### 6. Doğrulama

18 frontend testi ve derleme başarılıdır. Ayrı test servisi ve kuralla gerçek API → worker üzerinden 21 alarm oluşturuldu; Vite üzerinden 20+1 sayfa, doğru durum filtresi, görüldü PATCH'i, aynı zamanın korunması ve işaretleme sonrası has_more değişimi kontrol edildi. Tüm deneme verileri temizlendi; kullanıcının mevcut iki alarmı işaretlenmedi. Bu kontroller tarayıcıda görsel/tıklama testi değildir. Alarm kurallarını ekleme/düzenleme ekranı sonraki adımdır.


## Faz 3 alarm kurallarını yönetmek — adım adım

Şemadaki yerimiz: React kural formu → POST/PATCH API → alert_rules tablosu. Sonraki log veya metrik geldiğinde worker bu kuralları okuyarak alarm üretir. Kuralı kaydetmek tek başına eski kayıtları yeniden işleme sokmaz.

### 1. ruleForm.js: formu JSON'a dönüştürmek

EMPTY_RULE yeni formun taslağıdır. Eşik ve süreler burada metindir; HTML input alanlarından gelen değerler de metindir. buildRulePayload, metinleri kontrol edip sayısal alanları Number ile sayıya çevirir. Önce boş olup olmadığını kontrol eder; çünkü JavaScript'te Number('') sıfırdır ve boş eşik yanlışlıkla sıfır olmamalıdır.

Servis alanı boşsa service:null gönderilir. Bu tüm servisleri ayrı ayrı değerlendir demektir. Metrik kuralında metric_name/metric_unit gönderilir ve level:null yapılır. Log sayısı kuralında level gönderilir; metric_name ve metric_unit null yapılır. Böylece tür değiştirirken önceki türe ait alanlar API doğrulamasını bozmaz. Metrikte kullanılmayan window_seconds değeri 300 gönderilir.

Log sayısı negatif olmayan tam sayı eşik ve gt/gte karşılaştırmasını destekler. Metrik kuralında gt/gte/lt/lte ve sonlu sayısal eşik vardır. Log penceresi 1–86400, tekrar bekleme 0–86400 saniye aralığındadır. enabled gerçek boolean olarak kalır. ruleToDraft, mevcut kuraldaki sayıları String ile düzenlenebilir metne çevirir; sıfır ve false değerlerini korur.

### 2. Yanıtları doğrulamak

validateRule, API'den gelen kaydın kimlik, tarih, sayı, durum ve türe bağlı alanlarını denetler. validateRulePage, sayfa bilgilerini kontrol eder. validateRuleSave, dönen kimlik ve kaydedilen alanların gönderdiğimiz değerlerle eşleştiğini doğrular. Böylece HTTP isteğinin yanıt vermesi tek başına başarılı kayıt sayılmaz. describeRule, koşulu okunabilir metne çevirir; örneğin cpu_usage (percent) > 85 veya Son 300 saniyedeki ERROR sayısı > 50.

### 3. RuleEditor.jsx: koşula göre değişen form

RuleEditor, editor ve onChange/onSubmit/onCancel props'larını alır. editor.id null ise yeni kural, sayısal kimlik varsa mevcut kural düzenlenir. editor.draft kutularda görünen değerlerdir. Tür log_count ise seviye ve zaman penceresi, metric_threshold ise metrik adı ve birimi gösterilir. datalist yalnızca yazım önerisidir; özel metrik adı ve birimi yazılabilir. Açılır kutuda log kurallarına yalnızca gt/gte sunulur.

field(key), value ve onChange özelliklerini üretir; kullanıcının yazdığı metni parent bileşene aktarır. Checkbox için event.target.checked kullanılır; bu metin değil true/false döndürür. fieldset disabled, istek sürerken formun ikinci defa gönderilmesini önler.

### 4. RulesPanel.jsx: liste ve düzenleme state'i

offset sayfayı, result liste yanıtını, editor aktif formu, busy değişiklik isteğini, notice sonucu tutar. query ile result.query eşleşmeden başka sayfanın satırları gösterilmez. Liste GET /api/alert-rules?limit=20&offset=... ile alınır. Bu bölüm manuel yenilenir. İstek veya sayfa değiştiğinde eski GET iptal edilir; açık taslak GET yüzünden yeniden doldurulmaz.

openEditor(rule), mevcut kaydı ruleToDraft ile forma aktarır; parametresiz çağrı yeni taslak açar. Form başlığına odak verilir. Bir form açıkken başka kayıt açılmaz; Kaydet veya Vazgeç kullanılır. Log türüne geçerken lt/lte seçilmişse operator gt yapılır.

### 5. POST, PATCH ve JSON.stringify

submitRule önce buildRulePayload ile JSON nesnesini hazırlar. saveRule, yeni kayıtta POST /api/alert-rules, mevcut kayıtta PATCH /api/alert-rules/{id} gönderir. JSON.stringify(payload), JavaScript nesnesini ağ üzerinden gönderilecek JSON metnine çevirir; Content-Type:application/json bunu sunucuya bildirir.

Aç/Kapat düğmesi aynı saveRule fonksiyonuna yalnızca {enabled:true/false} gönderir. Backend bu alanı mevcut kuralla birleştirir; diğer ayarları korur. Değişiklik bekleme durumunu sıfırlar ve sonraki kayıtta uygulanır. Eski alarmlar ve açıklamaları korunur.

mutationRef, başlayan isteği anında hatırlar ve hızlı çift tıklamanın ikinci POST/PATCH başlatmasını engeller. busy, kontrolleri devre dışı bırakır ve GET effect'ini durdurur. Yanıt doğrulanınca liste yeniden alınır. Başarıda form kapanır; hatada taslak korunur. İstek süresi 15 saniyedir. Zaman aşımında kayıt sunucuda oluşmuş olabilir; POST otomatik tekrarlanmaz, listeyi kontrol etmek gerekir. 409 aynı isim, 422 geçersiz alan, 404 bulunmayan kural olarak açıklanır.

### 6. Kontrol ve kalan iş

25 frontend testi ve derleme başarılıdır. Gerçek API/worker kontrolü için doğrudan buildRulePayload çıktıları kullanıldı. Eşik düzenleme, kapatma/açma, log sayısı, tür değişimi, geçmiş alarm bilgisinin korunması ve hata kodları doğrulandı. Test verileri temizlendi; mevcut kurallar değiştirilmedi. Tarayıcıdaki görsel/tıklama doğrulaması otomatik yapılmadı. Yerel Faz 3 ekranlarının kodları eklendi; son görsel kontrol ve ardından Faz 4 simülatör/yük testi/yayınlama/teslim hazırlığı kalır.


## Faz 4 veri simülatörü — ne yaptık?

Şemadaki yerimiz: simülatör → POST batch API → Redis → Celery worker → DB → SSE/GET → React paneli. Simülatör, örnek verilerle çalışan bir uygulama rolünü üstlenir. Bilgisayarın gerçek CPU/belleğini okumaz; gerçek bir ödeme isteği de göndermez.

### 1. scripts/simulate_telemetry.py nasıl başlar?

Dosyanın en altındaki if __name__ == '__main__', dosya terminalden doğrudan çalıştırıldığında main fonksiyonunu çağırır. argparse, --duration, --interval, --services gibi terminal seçeneklerini okur. Varsayılan süre 60 saniye, servis demo-payment, turlar arası bekleme 2 saniyedir. --duration 0 süresiz üretimdir; Ctrl+C üretimi durdurur. Ana API ve Docker servisleri daha önceki gibi açık olmalıdır.

### 2. make_cycle: örnek kayıtları üretmek

random.Random(seed), rastgele sayı kaynağıdır. Aynı seed ve ayarlar sayıları tekrarlanabilir yapar; her gerçek çalışmada güncel zaman ve run_id farklıdır. datetime.now(timezone.utc).isoformat(), her turda saat dilimi içeren yeni zamanı üretir. Böylece her Execute için elle zaman değiştirmek gerekmez.

Her servise bir log ve üç metrik hazırlanır. CPU cpu_usage/percent, bellek memory_usage/percent, yanıt süresi response_time/ms kullanır. Metrikler panelin tanıdığı adlarla eşleşir. Normal değerler düşük aralıklardan, hatalı tur değerleri yüksek aralıklardan gelir. ERROR ile sentetik stack_trace gönderilir; detay ekranında görülebilir.

scenario normal ise normal turlar, incident ise hatalı turlar üretilir. mixed seçiliyken sequence % 5 == 0 ifadesi her beşinci turu seçer. Yüzde işareti burada kalan bulma operatörüdür: 5, 10, 15 sayıları beşe bölününce kalan sıfırdır. Aynı turdaki log ve metrikler aynı durumla ilişkilidir.

tags içindeki environment=simulation ve source=telemetry-simulator bu verilerin örnek olduğunu gösterir. run_id aynı çalışmanın kayıtlarını, sequence o çalışmanın kaçıncı turunu ayırır. Servis alanı farklı uygulamaları ayırır; varsayılan demo-payment, önceki payment-service örneklerinden ayrıdır.

### 3. ApiClient: JSON'u API'ye göndermek

json.dumps, Python sözlük/listesini JSON metnine çevirir. encode('utf-8') ağ üzerinden gidecek baytları üretir. urllib.request.Request, HTTP isteğini oluşturur; urlopen isteği gönderir. Yeni paket eklemek gerekmez; bunlar Python'un standart kütüphanesindedir.

POST /logs/batch log listesini, POST /metrics/batch üç metrik listesini gönderir. Birden çok servis seçilirse aynı turun kayıtları yine bu iki istekte gruplanır. 202 yanıtı yalnızca kuyruğa kabul demektir. Dönen task_id ve record_count doğrulanır. İstek başarısız veya yanıt belirsizse aynı POST otomatik tekrar edilmez; çünkü API yeni POST'u yeni görev olarak kabul eder.

### 4. wait_for_tasks: gerçekten işlendi mi?

pending sözlüğünde kabul edilen görevlerin kimliği, türü ve kayıt sayısı tutulur. GET /tasks/{id}, PENDING/STARTED/RETRY/SUCCESS/FAILURE bilgisini verir. SUCCESS görülürse confirmed sayacı artırılır ve görev pending'den çıkarılır. FAILURE üretimi durdurur. Görevler varsayılan 30 saniyelik beklemede bitmezse yeni tur başlamaz; böylece worker kapalıyken kuyruk sınırsız doldurulmaz.

accepted_logs/metrics, kimliği doğrulanmış kabul yanıtlarını sayar. confirmed_logs/metrics, worker SUCCESS görevlerine dayanır. unconfirmed_records, kimliği alınmış fakat tamamlandığı doğrulanamamış görevlerdeki sayıdır. Kaybolan POST yanıtı nedeniyle kimliği hiç alınamayan işler bu sayıya dahil edilemez; hata mesajı bu belirsizliği açıklar.

### 5. Döngü ve durdurma

while, süre dolana kadar yeni turlar üretir. Önce log ve metrik gönderilir, sonra worker beklenir, sayaçlar yazılır, time.sleep ile sonraki tur öncesinde beklenir. interval, tamamlanan turlar arasındaki beklemedir; ağ/worker süresi de toplam süreye eklenir. Bu program kapasiteyi ölçen yük testi değildir.

time.monotonic, bilgisayarın saat ayarındaki değişikliklerden bağımsız süre ölçer. Ekrana yazılan olay zamanı için UTC datetime kullanılır. Süre dolunca yeni tur başlamaz; başlamış turun doğrulaması tamamlanabilir. Ctrl+C, KeyboardInterrupt olarak yakalanır; üretim durur, kuyruktaki işler yine tamamlanabilir. Rapor interrupted=true yazar; planlı kesintisiz bitiş anlamındaki successful false ve çıkış kodu 130 olur.

### 6. Özet ve belleğin sınırlı kalması

--report verilirse JSON çalışma özeti yazılır. Süre, tur sayısı, kabul/onay sayıları, hata ve çalışma kimliği saklanır. deque(maxlen=20), yalnızca son 20 görev kimliğini tutar. Böylece süresiz çalışmada görev kimliği listesi bellekte sınırsız büyümez. Rapor tam bir görev geçmişi değildir. Üretilen normal demo verileri DB'de kalır; program bunları otomatik silmez.

### 7. Bugünkü gerçek deneme

Sekiz test geçti. Ayrı QA servisiyle gerçek batch API → worker → DB → Vite SSE/GET bağlantısı, üç metrik, ERROR/hata izi ve iki tür alarm doğrulandı; QA verileri temizlendi. Ardından demo-payment ile 20 saniyede 10 log ve 30 metrik kaydedildi. İki tur ERROR üretti; mevcut CPU kuralından bir alarm oluştu. Alarm tekrar beklemesi nedeniyle her yüksek ölçüm için tekrar bildirim beklememek gerekir. Bu demo kayıtları panelde inceleme için bırakıldı; süreç kapandı.

### 8. Sen nasıl çalıştıracaksın?

Proje kökünde ayrı terminalde:

    .\.venv\Scripts\python.exe scripts/simulate_telemetry.py --duration 60

Panelde metrik servis kutusuna demo-payment yazıp Göster'e bas. CPU/bellek/yanıt süresi arasında seçim yap. Log filtresine de demo-payment yazıp Uygula'ya basabilirsin. Yeni veriler geldikçe çizgi ve tablo değişir. Alarmlar bölümü yaklaşık 10 saniyede bir kontrol edilir. 60 saniye sonra üretim biter. Sürekli çalışması için --duration 0; durdurmak için Ctrl+C kullan.

Sonraki çalışma kapsamlı yük testi ve yayınlamadır; bugünkü hedef simülatöre kadar tamamlandı. Tarayıcıdaki son görsel/etkileşim kontrolü ayrıca bekliyor.


## 24 Ekim 2026 — yük testi nasıl çalışıyor?

Şemadaki yerimiz: **yük üreticisi → FastAPI → Redis → Celery → veritabanı ve alarm**. Bu adımda React ekranına özellik eklemedik; veriyi taşıyan hattı ölçtük.

Bir kargo merkezi düşün: API paketi teslim alan gişe, Redis bekleme bandı, Celery paketleri işleyen çalışan, veritabanı ise kayıt defteri. Gişenin “aldım” demesi, çalışanın işi bitirdiği anlamına gelmez. Bu yüzden üç zamanı ayrı tutuyoruz: kabul yanıtı, bütün kayıtların DB'de görülmesi ve worker'ın işi bitirdiğinin onayı.

### 1. parse_args — denemenin ayarları

`--records 12000` toplam kayıt sayısıdır. `--concurrency 8`, en fazla sekiz HTTP isteğinin aynı anda yanıt beklemesine izin verir; sekiz Celery worker açmaz. `--batch-size 100`, her istekte en fazla yüz kayıt gönderir. `--rate 200`, saniyede iki yüz kayıt hedefidir; her paketin yüz kayıt olduğu durumda yaklaşık yarım saniyede bir istek planlanır. `--label`, JSON sonuç dosyasının adını belirler. Aynı ad eski sonucu değiştirir; ayrı denemeler için ayrı ad kullanılır.

Ön kontrolde API, DB, Redis ve worker yanıtı kontrol edilir. Hazır değillerse üretim başlamaz. `uuid4()` her denemeye ayrı bir servis adı üretir; önceki demo ile bu denemenin sayıları karışmaz.

### 2. send — istek ile kayıt farklı şeyler

Tekli gönderimde bir kayıt, bir POST isteğidir. Paket gönderiminde yüz kayıt tek POST olabilir. Bu nedenle 1.000 kayıt tekli gönderimde 1.000 görev, yüzlük paketle 10 görev oluşturur. Log ve metrikler kendi uç noktalarına ayrı gönderilir. `json.dumps` sözlük/listeleri JSON'a çevirir; `urlopen` API'ye gönderir. 202, queued, görev kimliği ve paket kayıt sayısı doğrulanır. Yanıt belirsizse aynı POST yeniden gönderilmez.

### 3. run_jobs — kontrollü gönderim

`ThreadPoolExecutor` HTTP isteklerini paralel gönderir. `pending`, henüz sonucu alınmamış istekleri tutar. Sayı concurrency sınırına gelince `wait(..., FIRST_COMPLETED)` en az bir isteğin bitmesini bekler. Bitmiş sonuç okunur, sonra yeni istek gönderilebilir. Böylece tüm istekler baştan sınırsız bir yürütücü kuyruğuna eklenmez.

Hız hedefi verildiyse o ana kadar planlanan kayıt sayısı hedef hıza bölünür; yeni paketin gönderim zamanı bulunur. Gerekirse `sleep` ile beklenir. Bu bir hedeftir; ağın yavaşlaması hedefin altında kalmaya yol açabilir. HTTP hatası görüldüğünde yeni işler eklemeyi durdurur; zaten gönderilmiş isteklerin sonuçları toplanır. Redis'te bekleyen görevler HTTP concurrency sınırından ayrı olarak birikebilir.

### 4. DB ve worker kontrolü — paket gerçekten işlendi mi?

Gönderim bittikten sonra SQL ile o servisin log/metrik sayıları ve `processed_tasks` kayıtları okunur. Makbuz, görevin DB işleminde kaydedilmiş olduğunu gösterir. Makbuz sayısı yanında içerdiği toplam kayıt sayısı da kontrol edilir. Ardından her görev için Celery `SUCCESS` beklenir. Yalnızca HTTP 202 dönmesi testi başarılı yapmaz.

`total_seconds`, gönderim başlangıcından DB doğrulamasına kadardır. Kontrol gönderimden sonra yapıldığı için gerçek son yazma anından biraz geç olabilir. `worker_confirmed_seconds`, görev sonuçlarının ayrıca doğrulandığı zamandır. `queue_drain_seconds`, gönderim bitişinden DB doğrulamasına kadar geçen ek beklemedir; görev başına kuyruk süresi değildir.

### 5. percentile ve monitor — hangi sayıya bakıyoruz?

HTTP gecikmeleri küçükten büyüğe sıralanır. p95 için kayıtların %95'ine denk gelen sıra yukarı yuvarlanır ve o süre alınır. Bu, en yavaş tek isteğin süresinden daha temsil edici bir gecikme göstergesidir; kayıtların DB'ye yazılma süresi değildir. Yalnızca 10 istek varsa p95 ve p99 ikisi de en büyük örneğe denk gelebilir; az örnekle kesin kapasite sonucu çıkarılmaz.

Ayrı bir `Thread`, Redis kuyruğundaki bekleyen görevleri yarım saniyede bir sayar. Örnekler `deque(maxlen=7200)` ile sınırlandırılır; örneklenen en yüksek değer ayrıca saklanır. Bu sayı kayıt değil görev sayısıdır. Kısa bir sıçrama iki kontrol arasına denk gelirse görünmeyebilir. Çalışmakta olan görevler bu sayıya dahil değildir.

### 6. cleanup_test_data — deneme bittikten sonra

Tam kayıt sayıları ve bütün SUCCESS sonuçları doğrulanınca yalnızca bu aracın benzersiz test servisine ait veriler temizlenir. Kullanıcının payment-service veya demo-payment kayıtları bu adla eşleşmez. SQL sorgularındaki `%s`, değeri sorgu metnine birleştirmek yerine ayrı parametre olarak gönderir. Görev makbuzları ve ilgili Redis sonuçları da temizlenir. JSON ölçüm raporu dosyada kalır.

Başarısız veya tamamlanması belirsiz denemede veriler inceleme için korunur. Temizlik hatası da rapora yazılır; program başarı koduyla çıkmaz. Bu sayede “ölçüm bitti” ile “test verileri temizlendi” birbirine karışmaz.

### 7. Sonuçlar nerede?

`test-results/load-phase4-20261024-*.json` dosyaları her gerçek denemenin sayısal kanıtıdır. `test-results/load-summary-20261024.md` sonuçları ve yorum sınırlarını birlikte açıklar. Altı yeni birim testi hız hesabını, yüzdelikleri, concurrency sınırını, hata sonrası durmayı, geçersiz ayarları ve kullanıcı servislerini temizlemeyi reddetmeyi kontrol eder.
