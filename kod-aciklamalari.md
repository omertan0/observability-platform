# Alarm aşamasına kadar kod açıklamaları

**11 Ekim 2026.** Satır numaraları bu sürümdeki dosyalara aittir. Boş satırlar yalnızca okunabilirlik içindir.

## Önce akışı hatırla

`POST → doğrulama → Redis → worker → kayıt → kural kontrolü → bildirim`

`GET → filtreli SELECT → JSON cevap`

Örnek: CPU 90 gelir. Worker ölçümü kaydeder, 90 > 85 koşulunu görür. Son 300 saniyede bu kural/servis için alarm yoksa alerts tablosuna bildirim ekler. GET /alerts bildirimi getirir.

Transaction bir işlemler paketidir: görev kimliği, ölçüm ve alarm hep birlikte onaylanır. Ortasında hata varsa hiçbiri kalmaz. Cooldown aynı alarmı tekrar üretmeden önce beklenen süredir.

Bu belgede uygulama kodları satır satır açıklanır. Docker ve eski şemada yalnızca değiştirilen satırlar gösterilir. React ve SSE henüz yapılmadı.

## database.py

Arşivin kapısını açan yardımcıdır. Yeni eklediğimiz zaman sınırları, sorun olduğunda sonsuza kadar beklememeyi sağlar.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/database.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `import os` | Ortam ayarlarını okumak için os modülünü getirir. |
| 2 | `import psycopg` | PostgreSQL ile konuşan Psycopg paketini getirir. |
| 5 | `def get_connection():` | Bağlantı açma işini tek fonksiyonda toplar. |
| 6 | `return psycopg.connect(` | Yeni bir veritabanı bağlantısı açıp çağırana verir. |
| 7 | `host=os.getenv("DB_HOST", "127.0.0.1"),` | Docker worker için db adresini, Windows API için varsayılan 127.0.0.1 adresini kullanır. |
| 8 | `port=os.getenv("DB_PORT", "5432"),` | Veritabanının portunu okur; belirtilmemişse 5432 kullanır. |
| 9 | `dbname=os.environ["POSTGRES_DB"],` | Bağlanılacak veritabanının adını ortamdan alır. |
| 10 | `user=os.environ["POSTGRES_USER"],` | Veritabanı kullanıcısını ortamdan alır. |
| 11 | `password=os.environ["POSTGRES_PASSWORD"],` | Parolayı ortamdan alır; kaynak koda yazmaz. |
| 12 | `connect_timeout=5,` | Bağlantı kurmak için en fazla 5 saniye bekler. |
| 13 | `options="-c statement_timeout=10000 -c lock_timeout=5000",` | Sorguyu 10 saniye, kilit beklemeyi 5 saniye ile sınırlar. Süreler milisaniyedir. |
| 14 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |

## celery_app.py

İş emirlerinin nasıl taşınacağını belirleyen ayar dosyasıdır. API'nin gönderme hatası ile worker'ın işleme tekrarı ayrı şeylerdir.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/celery_app.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `import os` | Ortam değişkenlerini okumak için os modülünü getirir. |
| 2 | `from celery import Celery` | Görev kuyruğu uygulamasını oluşturacak Celery sınıfını getirir. |
| 4 | `redis_url = os.getenv(` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 5 | `"REDIS_URL",` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 6 | `"redis://127.0.0.1:6379/0"` | REDIS_URL ayarını okur; yoksa bu bilgisayardaki Redis ve 0 numaralı veritabanı kullanılır. |
| 7 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 9 | `celery_app = Celery("observability", broker=redis_url)` | observability adında Celery uygulaması oluşturur; broker yani görev taşıyıcısı Redis'tir. |
| 10 | `celery_app.conf.update(` | Celery ayarlarını birlikte günceller. |
| 11 | `task_serializer="json",` | Görev paketlerini JSON biçiminde gönderir. |
| 12 | `accept_content=["json"],` | Yalnızca JSON görev paketlerini kabul eder. |
| 13 | `task_ignore_result=True,` | Görev dönüş değerini ayrıca bir sonuç deposunda saklamaz; kayıtlar PostgreSQL'dedir. |
| 14 | `task_publish_retry=False,` | API'nin kuyruğa gönderme işlemini otomatik tekrarlarla uzatmaz. |
| 15 | `broker_connection_timeout=3,` | Broker bağlantısının zaman sınırını 3 saniye olarak ayarlar. |
| 16 | `broker_connection_retry_on_startup=True,` | Worker açılırken Redis hazır değilse bağlanmayı yeniden dener. |
| 17 | `broker_transport_options={` | Redis taşıyıcısına özel ayar grubunu açar. |
| 18 | `"socket_connect_timeout": 3,` | Redis ağ bağlantısının kurulmasını 3 saniye ile sınırlar. |
| 19 | `"socket_timeout": 3,` | Redis ağ okuma/yazma beklemesini 3 saniye ile sınırlar. |
| 20 | `"retry_on_timeout": False,` | Redis istemcisinin zaman aşımında otomatik tekrarını kapatır. |
| 21 | `"visibility_timeout": 3600,` | Onaylanmamış mesajın Redis tarafından yeniden teslim edilebileceği süreyi 3600 saniye yapar; bu alarm bekleme süresi değildir. |
| 22 | `},` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 23 | `worker_prefetch_multiplier=1,` | Worker'ın önceden ayırdığı görev sayısını azaltır; bir çalışan çok sayıda işi üzerine toplamaz. |
| 24 | `timezone="UTC",` | Görev zamanlarını UTC üzerinden işler. |
| 25 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |

## models.py

Danışmadaki form kontrolüdür: verinin doğru alanlarla, doğru türlerle geldiğini denetler. Alarm kuralı da ayrı bir formdur.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/models.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from typing import Literal` | Literal, yalnızca belirlediğimiz seçeneklerin kabul edilmesini sağlar. |
| 2 | `import math` | Sayıların sonlu olup olmadığını kontrol etmek için math modülünü getirir. |
| 3 | `from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator` | Pydantic şablonlarını, alan kurallarını ve doğrulama araçlarını getirir. AwareDatetime saat dilimi ister; JsonValue JSON değerlerini tanımlar. |
| 5 | `# tanımladığımız modele göre gelen veriyi kontrol eder` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 8 | `class TelemetryInput(BaseModel):` | Log ve metriğin ortak alanlarını taşıyan şablonu oluşturur. |
| 9 | `model_config = ConfigDict(extra="forbid", allow_inf_nan=False)` | Bilinmeyen ek alanları ve sonlu olmayan sayıları reddetme ayarını yapar. |
| 11 | `timestamp: AwareDatetime` | timestamp zorunludur ve saat dilimi içermelidir. |
| 12 | `service: str = Field(min_length=1, max_length=200, pattern=r"\S")` | service en fazla 200 karakter olur; en az bir boşluk dışı karakter içermelidir. |
| 13 | `tags: dict[str, JsonValue] = Field(default_factory=dict)` | tags bir JSON sözlüğüdür. Gönderilmezse her kayıt için yeni bir boş sözlük oluşturulur. |
| 15 | `@field_validator("timestamp", mode="before")` | timestamp, Pydantic tarafından tarihe dönüştürülmeden önce aşağıdaki kontrolü çalıştırır. |
| 16 | `@classmethod` | Fonksiyonu sınıfa bağlı yapar; cls şablon sınıfını temsil eder. |
| 17 | `def require_iso_timestamp(cls, value):` | Gelen zaman değerini denetleyen fonksiyonu tanımlar. |
| 18 | `if not isinstance(value, str):` | Zamanın metin olarak gönderilip gönderilmediğini kontrol eder. |
| 19 | `raise ValueError("timestamp saat dilimi içeren ISO 8601 metni olmalıdır")` | Sayı gibi bir zaman girdisini doğrulama hatasıyla reddeder. |
| 20 | `return value` | Metni Pydantic'e verir; ISO biçimi ve saat dilimi bundan sonra doğrulanır. |
| 22 | `@field_validator("tags")` | tags alanı oluşturulduktan sonra özel sayı kontrolünü çalıştırır. |
| 23 | `@classmethod` | Doğrulama fonksiyonunu sınıfa bağlı yapar. |
| 24 | `def require_finite_tags(cls, value):` | Etiketlerin içindeki bütün seviyeleri tarayan fonksiyonu tanımlar. |
| 25 | `pending = [value]` | Kontrol edilecek değerleri bir listeye koyar. |
| 26 | `while pending:` | Kontrol edilecek değer kaldığı sürece döngüyü sürdürür. |
| 27 | `item = pending.pop()` | Listenin son değerini çıkarıp incelemeye alır. |
| 28 | `if isinstance(item, dict):` | Değer bir sözlük mü diye bakar. |
| 29 | `pending.extend(item.values())` | Sözlüğün içindeki değerleri de kontrol listesine ekler. |
| 30 | `elif isinstance(item, list):` | Değer bir liste mi diye bakar. |
| 31 | `pending.extend(item)` | Listenin elemanlarını da kontrol listesine ekler. |
| 32 | `elif isinstance(item, float) and not math.isfinite(item):` | Ondalıklı sayı Infinity veya NaN mı diye kontrol eder. |
| 33 | `raise ValueError("tags içindeki sayılar sonlu olmalıdır")` | Geçersiz sayıyı reddeder; veritabanına ulaşmasını engeller. |
| 34 | `return value` | Geçerli etiket sözlüğünü geri verir. |
| 37 | `class LogInput(TelemetryInput): # LogInput adinda log sablonu olusturduk` | Log şablonu ortak timestamp, service ve tags alanlarını TelemetryInput'tan alır. |
| 38 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"]` | Yalnızca INFO, WARN, ERROR ve FATAL seviyelerini kabul eder. |
| 39 | `message: str = Field(min_length=1, max_length=16000, pattern=r"\S")` | Log mesajına boş olmama ve 16000 karakter sınırı koyar. |
| 40 | `stack_trace: str \| None = Field(default=None, max_length=64000)` | stack_trace isteğe bağlıdır; metin verilirse en fazla 64000 karakter olur. |
| 42 | `class MetricInput(TelemetryInput):` | Metrik şablonu da ortak alanları TelemetryInput'tan alır. |
| 43 | `name: str = Field(min_length=1, max_length=200, pattern=r"\S")` | Ölçüm adını zorunlu yapar; örneğin cpu_usage. |
| 44 | `value: float = Field(strict=True, allow_inf_nan=False)  # allow_inf_nan=False sossuzluk ve NaN gibi degerleri reddeder` | Ölçüm değeri sonlu bir sayı olmalıdır. strict=True metin olarak gelen sayıyı reddeder. |
| 45 | `unit: str = Field(min_length=1, max_length=50, pattern=r"\S")` | Ölçüm birimini zorunlu yapar; örneğin percent veya ms. |
| 47 | `@model_validator(mode="after")` | Bütün metrik alanları doğrulandıktan sonra CPU kontrolünü çalıştırır. |
| 48 | `def check_cpu_percent(self):` | Doğrulanmış metriği self üzerinden inceleyen fonksiyonu tanımlar. |
| 49 | `if self.name == "cpu_usage" and self.unit == "percent" and not 0 <= self.value <= 100:` | Ölçüm CPU yüzdesiyse 0-100 aralığını kontrol eder; başka metriklere aynı aralığı dayatmaz. |
| 50 | `raise ValueError("cpu_usage percent değeri 0 ile 100 arasında olmalıdır")` | Geçersiz CPU yüzdesini reddeder. |
| 51 | `return self` | Geçerli metrik nesnesini döndürür. |
| 54 | `class AlertRuleInput(BaseModel):` | Kullanıcının göndereceği alarm kuralı şablonunu oluşturur. |
| 55 | `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)` | Bilinmeyen alanları reddeder ve kural metinlerinin başındaki/sonundaki boşlukları temizler. |
| 57 | `name: str = Field(min_length=1, max_length=200)` | Kuralın kullanıcıya görünen adını zorunlu yapar. |
| 58 | `kind: Literal["metric_threshold", "log_count"]` | Kural türünü metrik eşiği veya log sayısı olarak sınırlar. |
| 59 | `service: str \| None = Field(default=None, min_length=1, max_length=200)` | Servis adı isteğe bağlıdır. null ise her servis ayrı ayrı değerlendirilir. |
| 60 | `metric_name: str \| None = Field(default=None, min_length=1, max_length=200)` | Metrik kuralının hangi ölçümü izleyeceğini belirtir. |
| 61 | `metric_unit: str \| None = Field(default=None, min_length=1, max_length=50)` | Metrik kuralının birimini belirtir; farklı birimler karıştırılmaz. |
| 62 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"] \| None = None` | Log sayısı kuralının hangi seviyeyi sayacağını belirtir. |
| 63 | `operator: Literal["gt", "gte", "lt", "lte"] = "gt"` | Karşılaştırma türünü belirler; gt büyüktür, gte büyük/eşit, lt küçüktür, lte küçük/eşittir. |
| 64 | `threshold: float = Field(strict=True, allow_inf_nan=False)` | Karşılaştırılacak sonlu eşik sayısını zorunlu yapar. |
| 65 | `window_seconds: int = Field(default=300, ge=1, le=86400, description="Log sayısı kuralının zaman penceresi; metrik eşiğinde kullanılmaz.")` | Log sayımı için son kaç saniyeye bakılacağını belirler; varsayılan 300, üst sınır 86400 saniye. |
| 66 | `cooldown_seconds: int = Field(default=300, ge=0, le=86400, description="Aynı kural ve servis için iki bildirim arasındaki en kısa süre.")` | Aynı kural ve servisin yeniden alarm üretmeden önce bekleyeceği süreyi belirler. 0 beklemeyi kaldırır. |
| 67 | `enabled: bool = True` | Yeni kural varsayılan olarak açıktır. |
| 69 | `@model_validator(mode="after")` | Alanlar hazırlandıktan sonra kuralın bütün olarak tutarlı olup olmadığını denetler. |
| 70 | `def check_rule_fields(self):` | Kurala özel zorunlulukları kontrol eden fonksiyonu tanımlar. |
| 71 | `if self.kind == "metric_threshold":` | Metrik eşiği kurallarını ayrı ele alır. |
| 72 | `if not self.metric_name or not self.metric_unit:` | Metrik adı veya birim eksik mi diye bakar. |
| 73 | `raise ValueError("Metrik kuralında metric_name ve metric_unit zorunludur")` | Eksik metrik bilgisi olan kuralı reddeder. |
| 74 | `if self.level is not None:` | Metrik kuralına log seviyesi yazılmış mı diye bakar. |
| 75 | `raise ValueError("Metrik kuralında level kullanılmaz")` | Metrik kuralında gereksiz log seviyesini reddeder. |
| 76 | `else:` | Diğer tür olan log sayısı kurallarına geçer. |
| 77 | `if self.level is None:` | Log seviyesi eksik mi diye bakar. |
| 78 | `raise ValueError("Log kuralında level zorunludur")` | Hangi seviyeyi sayacağı bilinmeyen kuralı reddeder. |
| 79 | `if self.metric_name is not None or self.metric_unit is not None:` | Log kuralına metrik adı/birimi eklenmiş mi diye bakar. |
| 80 | `raise ValueError("Log kuralında metrik alanları kullanılmaz")` | Log kuralındaki metrik alanlarını reddeder. |
| 81 | `if self.threshold < 0 or not self.threshold.is_integer():` | Log eşiği negatif veya kesirli mi diye kontrol eder. |
| 82 | `raise ValueError("Log sayısı eşiği negatif olmayan tam sayı olmalıdır")` | Log sayısı eşiğini negatif olmayan tam sayıyla sınırlar. |
| 83 | `if self.operator not in ("gt", "gte"):` | Log sayısı karşılaştırmasının gt/gte olduğunu kontrol eder. |
| 84 | `raise ValueError("Log sayısı kuralında gt veya gte kullanılmalıdır")` | Log kuralında diğer karşılaştırmaları reddeder. |
| 85 | `return self` | Geçerli kuralı geri verir. |
| 88 | `class AlertRulePatch(AlertRuleInput):` | Kısmi düzenleme şablonunu mevcut kural şablonundan üretir. |
| 89 | `# PATCH: gönderilen alanlar mevcut kuralla birleştirilip tekrar doğrulanır.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 90 | `name: str \| None = Field(default=None, min_length=1, max_length=200)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 91 | `kind: Literal["metric_threshold", "log_count"] \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 92 | `operator: Literal["gt", "gte", "lt", "lte"] \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 93 | `threshold: float \| None = Field(default=None, strict=True, allow_inf_nan=False)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 94 | `window_seconds: int \| None = Field(default=None, ge=1, le=86400)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 95 | `cooldown_seconds: int \| None = Field(default=None, ge=0, le=86400)` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 96 | `enabled: bool \| None = None` | Bu alanı isteğe bağlı yapar: PATCH isteğinde yalnızca değiştirmek istediğimiz alanları gönderebiliriz. Gönderilen alan kendi tür/sınır kurallarına uymalıdır. |
| 98 | `@model_validator(mode="after")` | Kısmi şablonda aşağıdaki kontrolü kullanır; üst sınıftaki bütün kural kontrolünün yerini alır. |
| 99 | `def check_rule_fields(self):` | Kısmi kural kontrolünü tanımlar. |
| 100 | `return self` | Kısmi veriyi geçirir. main.py bunu eski kuralla birleştirip AlertRuleInput ile bütün olarak tekrar doğrular. |

## tasks.py

Çalışanın görev listesidir. Önce bu işi daha önce yaptım mı diye bakar, sonra evrakı kaydeder ve alarmı kontrol eder.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/tasks.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from uuid import uuid4` | Gerekirse benzersiz görev kimliği üretmek için uuid4 getirir. |
| 3 | `from celery.utils.log import get_task_logger` | Worker mesajlarını Celery'nin kayıt sistemine yazacak aracı getirir. |
| 4 | `from psycopg import OperationalError` | Geçici veritabanı bağlantı hatası türünü getirir. |
| 5 | `from psycopg.errors import DeadlockDetected, SerializationFailure, LockNotAvailable` | Çakışan kilitler ve transaction'lar için tekrar denenebilecek hata türlerini getirir. |
| 6 | `from psycopg.types.json import Jsonb` | Etiket sözlüğünü PostgreSQL JSONB biçimine gönderecek aracı getirir. |
| 8 | `from alerts import evaluate_alerts` | Alarm kurallarını değerlendiren kendi fonksiyonumuzu getirir. |
| 9 | `from celery_app import celery_app` | Celery uygulamamızı getirir. |
| 10 | `from database import get_connection` | Veritabanı bağlantı fonksiyonumuzu getirir. |
| 12 | `logger = get_task_logger(__name__)` | Bu dosya için worker logger'ını oluşturur. |
| 13 | `TASK_OPTIONS = dict(` | İki görevde ortak kullanılacak ayar sözlüğünü açar. |
| 14 | `bind=True,` | Görev fonksiyonuna self verir; böylece görev kimliğine erişebiliriz. |
| 15 | `acks_late=True,` | Görev başarılı dönünce kuyruk mesajını onaylar. |
| 16 | `reject_on_worker_lost=True,` | Çalışan süreç beklenmedik şekilde kaybolursa mesajın yeniden kuyruğa verilmesini ister. |
| 17 | `autoretry_for=(OperationalError, DeadlockDetected, SerializationFailure, LockNotAvailable),` | Listelenen geçici hatalarda görevin otomatik yeniden denenmesini sağlar. |
| 18 | `retry_backoff=True,` | Her tekrar arasında giderek büyüyen bekleme kullanır. |
| 19 | `retry_backoff_max=60,` | Tekrar beklemesini en fazla 60 saniye olarak sınırlar. |
| 20 | `retry_jitter=True,` | Birçok worker'ın aynı anda yeniden denemesini azaltmak için süreye rastgelelik ekler. |
| 21 | `max_retries=5,` | İlk denemeden sonra en fazla 5 tekrar yapılır. |
| 22 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 25 | `def save_record(kind: str, record: dict, task_id: str):` | Log ve metriğin ortak kayıt akışını tanımlar; kind tür, record veri, task_id görev kimliğidir. |
| 26 | `# Görev kimliği, kayıt ve alarm aynı transaction içinde tutulur.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 27 | `# İşlem yarıda kalırsa hepsi geri alınır; tekrar teslim çift kayıt üretmez.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 28 | `with get_connection() as conn:` | Transaction açar. Başarıda commit, hatada rollback yapılır ve bağlantı kapatılır. |
| 29 | `inserted = conn.execute(` | Görev kimliğini daha önce işlenmiş görevler tablosuna eklemeyi dener. |
| 30 | `"""INSERT INTO processed_tasks (task_id, kind) VALUES (%s, %s)` | Görev kimliği ve türü için INSERT sorgusunu başlatır. |
| 31 | `ON CONFLICT (task_id) DO NOTHING RETURNING task_id""",` | Aynı görev kimliği zaten varsa ekleme yapmaz; eklenen kimliği RETURNING ile geri verir. |
| 32 | `(task_id, kind),` | Görev kimliği ve türünü SQL'den ayrı parametreler olarak gönderir. |
| 33 | `).fetchone()` | INSERT sonucu olan tek satırı alır; ekleme olmadıysa None gelir. |
| 34 | `if inserted is None:` | Görevin daha önce işlendiğini fark eder. |
| 35 | `logger.info("Görev daha önce işlendi: %s", task_id)` | Tekrar teslim edildiğini worker kayıtlarına yazar. |
| 36 | `return` | Görevi tekrar işlemekten vazgeçer; ikinci log/metrik veya alarm oluşmaz. |
| 37 | `if kind == "log":` | Gelen veri log ise log tablosuna yazma kolunu seçer. |
| 38 | `conn.execute(` | Log INSERT sorgusunu çalıştırır. |
| 39 | `"""INSERT INTO logs` | Kayıt hedefinin logs tablosu olduğunu belirtir. |
| 40 | `(timestamp, received_at, service, level, message, stack_trace, tags)` | Doldurulacak log sütunlarını sıralar. |
| 41 | `VALUES (%s, %s, %s, %s, %s, %s, %s)""",` | Yedi sütun için yedi değer yeri ayırır. |
| 42 | `(record["timestamp"], record["received_at"], record["service"],` | Olay zamanı, API alım zamanı ve servis değerlerini aynı sırayla gönderir. |
| 43 | `record["level"], record["message"], record.get("stack_trace"),` | Seviye, mesaj ve isteğe bağlı stack_trace değerini gönderir; eksik stack_trace NULL olur. |
| 44 | `Jsonb(record.get("tags", {}))),` | Etiketleri JSONB olarak gönderir; eksikse boş sözlük kullanır. |
| 45 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 46 | `else:` | Metrik yazma kolunu seçer; bu fonksiyon yalnızca log/metric görevlerinden çağrılır. |
| 47 | `conn.execute(` | Metrik INSERT sorgusunu çalıştırır. |
| 48 | `"""INSERT INTO metrics` | Kayıt hedefinin metrics tablosu olduğunu belirtir. |
| 49 | `(timestamp, received_at, service, name, value, unit, tags)` | Doldurulacak metrik sütunlarını sıralar. |
| 50 | `VALUES (%s, %s, %s, %s, %s, %s, %s)""",` | Yedi metrik sütunu için yedi değer yeri ayırır. |
| 51 | `(record["timestamp"], record["received_at"], record["service"],` | Metrik zamanı, API alım zamanı ve servisi gönderir. |
| 52 | `record["name"], record["value"], record["unit"],` | Ölçüm adı, sayısı ve birimini gönderir. |
| 53 | `Jsonb(record.get("tags", {}))),` | Metrik etiketlerini JSONB olarak gönderir. |
| 54 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 55 | `evaluate_alerts(conn, kind, record, task_id)` | Aynı bağlantı/transaction içinde alarm kontrolünü yapar. Alarm kontrolü hata verirse kayıt da geri alınır. |
| 56 | `logger.info("%s kaydedildi ve alarm kuralları kontrol edildi: %s", kind, record["service"])` | with bloğu başarıyla kapandıktan, yani commit tamamlandıktan sonra başarı mesajı yazar. |
| 59 | `@celery_app.task(**TASK_OPTIONS)` | Fonksiyonu ortak TASK_OPTIONS ayarlarıyla Celery görevine dönüştürür; ** sözlüğü ayrı anahtar/değer ayarlarına açar. |
| 60 | `def process_log(self, record: dict):` | Worker'ın çalıştıracağı log görevini tanımlar. |
| 61 | `save_record("log", record, self.request.id or str(uuid4()))` | Ortak kayıt fonksiyonunu log türüyle ve Celery görev kimliğiyle çağırır; kimlik yoksa UUID üretir. |
| 64 | `@celery_app.task(**TASK_OPTIONS)` | Metrik fonksiyonunu da aynı ayarlarla Celery görevine dönüştürür. |
| 65 | `def process_metric(self, record: dict):` | Worker'ın çalıştıracağı metrik görevini tanımlar. |
| 66 | `save_record("metric", record, self.request.id or str(uuid4()))` | Ortak kayıt fonksiyonunu metric türüyle çağırır. |

## queries.py

Arşivde arama yaparken ortak kullanılan yardımcıdır. Koşullar SQL'e, kullanıcının değerleri ayrı parametrelere gider.

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
| 29 | `):` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
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
| 46 | `# sql/order/clauses yalnızca kod içindeki sabitlerden gelir.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 47 | `where = " WHERE " + " AND ".join(clauses) if clauses else ""` | Filtre varsa WHERE ekler ve koşulları AND ile birleştirir; yoksa WHERE eklemez. |
| 48 | `with get_connection() as conn:` | Sorgu için veritabanı bağlantısı açar. |
| 49 | `conn.row_factory = dict_row` | Her satırın sütun adlarıyla bir sözlük olarak gelmesini sağlar. |
| 50 | `rows = conn.execute(` | Liste sorgusunu çalıştırır. |
| 51 | `sql + where + " ORDER BY " + order + " LIMIT %s OFFSET %s",` | Kod içindeki sabit sorguya filtre, sıralama ve sayfalama parçalarını ekler. |
| 52 | `[*values, limit + 1, offset],` | Filtre değerlerini açar ve en sona limit/offset değerlerini ekler. Bir fazla kayıt, sonraki sayfa var mı diye bakmak içindir. |
| 53 | `).fetchall()` | Sorgunun sınırlandırılmış sonuçlarını liste olarak alır. |
| 54 | `has_more = len(rows) > limit` | Bir fazla satır varsa başka sayfa olduğunu belirler. |
| 55 | `return {"items": rows[:limit], "limit": limit, "offset": offset,` | İstenen sayıda satırı, limit ve offset bilgileriyle döndürür; fazladan satırı göstermez. |
| 56 | `"has_more": has_more, "next_offset": offset + limit if has_more else None}` | Sonraki sayfanın başlangıcını verir; başka sayfa yoksa null olur. |

## alerts.py

Kural defterini okuyan görevli: ölçüm/sayım ile eşik karşılaştırılır; süre uygunsa bildirim yazılır.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/alerts.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `"""Yeni kayıt işlendiğinde kuralları değerlendirip sistem içi bildirim oluşturur."""` | Dosyanın alarm kontrolü yaptığını açıklayan metindir. |
| 2 | `from datetime import timedelta` | Saniye cinsinden süreyi tarihe ekleyip çıkarmak için timedelta getirir. |
| 3 | `from operator import gt, ge, lt, le` | Büyüktür, büyük/eşit, küçüktür, küçük/eşit karşılaştırma fonksiyonlarını getirir. |
| 5 | `from psycopg.rows import dict_row` | Kural satırlarını sözlük olarak alacak ayarı getirir. |
| 7 | `OPERATORS = {"gt": gt, "gte": ge, "lt": lt, "lte": le}` | API'deki operator adını çalıştırılacak Python karşılaştırmasına eşler. |
| 8 | `SYMBOLS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}` | Aynı operator adlarını bildirimde okunacak simgelere eşler. |
| 11 | `def evaluate_alerts(conn, kind: str, record: dict, task_id: str):` | Bağlantıyı, kayıt türünü, veriyi ve görev kimliğini alarak alarm kontrolünü başlatır. |
| 12 | `# Aynı kuralı değerlendiren worker'lar sırayla ilerler; çift alarm önlenir.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 13 | `with conn.cursor(row_factory=dict_row) as cur:` | Mevcut bağlantı üzerinde sorgu aracı yani cursor açar. Ayrı bağlantı/transaction başlatmaz. |
| 14 | `if kind == "metric":` | Yeni gelen kayıt metrikse metrik kurallarını seçer. |
| 15 | `cur.execute(` | Uygun metrik kurallarının sorgusunu çalıştırır. |
| 16 | `"""SELECT * FROM alert_rules` | alert_rules tablosundan bütün kural alanlarını seçer. |
| 17 | `WHERE enabled AND kind = 'metric_threshold'` | Yalnızca açık metrik eşiği kurallarını alır. |
| 18 | `AND (service IS NULL OR service = %s)` | Tüm servisleri izleyen veya bu servise özel kuralları alır. |
| 19 | `AND metric_name = %s AND metric_unit = %s` | Metrik adı ve birimi aynı olan kuralları alır. |
| 20 | `ORDER BY id FOR UPDATE""",` | Kuralları aynı sırayla kilitler. Başka worker aynı kuralda bekler; bekleme süresini aynı anda aşamazlar. |
| 21 | `(record["service"], record["name"], record["unit"]),` | Servis, ölçüm adı ve birimini SQL'den ayrı gönderir. |
| 22 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 23 | `else:` | Log kaydı için log sayısı kurallarına geçer. |
| 24 | `cur.execute(` | Uygun log kurallarının sorgusunu çalıştırır. |
| 25 | `"""SELECT * FROM alert_rules` | Kural tablosundaki alanları seçer. |
| 26 | `WHERE enabled AND kind = 'log_count'` | Yalnızca açık log sayısı kurallarını alır. |
| 27 | `AND (service IS NULL OR service = %s) AND level = %s` | Servis kapsamını ve log seviyesini eşleştirir. |
| 28 | `ORDER BY id FOR UPDATE""",` | Kuralları aynı sırayla kilitler; eşzamanlı worker'ları sıraya koyar. |
| 29 | `(record["service"], record["level"]),` | Servis ve seviye parametrelerini ayrı gönderir. |
| 30 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 31 | `rules = cur.fetchall()` | Uygun bütün kuralları liste olarak alır. |
| 32 | `if not rules:` | Bu kayda uygun kural yok mu diye bakar. |
| 33 | `return` | Kural yoksa alarm kontrolünü bitirir; kayıt yine saklanır. |
| 34 | `cur.execute("SELECT clock_timestamp() AS now")` | Veritabanının o andaki saatini okur. |
| 35 | `now = cur.fetchone()["now"]` | Saat sonucunu now değişkenine koyar. |
| 36 | `for rule in rules:` | Uygun kuralları tek tek değerlendirir. |
| 37 | `if kind == "metric":` | Metrik kuralında gözlenen değer doğrudan yeni ölçümdür. |
| 38 | `observed = record["value"]` | Örneğin 87.5 değerini observed değişkenine koyar. |
| 39 | `else:` | Log kuralında gözlenen değer son penceredeki kayıt sayısıdır. |
| 40 | `cur.execute(` | Log sayma sorgusunu çalıştırır. |
| 41 | `"""SELECT count(*) AS count FROM logs` | count(*) ile kayıt sayısını hesaplar; sonucu count adıyla verir. |
| 42 | `WHERE service = %s AND level = %s` | Yalnızca aynı servis ve istenen seviyedeki logları sayar. |
| 43 | `AND received_at > %s AND received_at <= %s""",` | API alım zamanı pencerenin içinde kalan kayıtları sayar: başlangıç hariç, şimdi dahil. |
| 44 | `(record["service"], rule["level"],` | Servis ve log seviyesini parametre olarak verir. |
| 45 | `now - timedelta(seconds=rule["window_seconds"]), now),` | Pencerenin başlangıcını now eksi kuraldaki saniye olarak hesaplar; sonu now olur. |
| 46 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 47 | `observed = cur.fetchone()["count"]` | Hesaplanan log sayısını observed değişkenine koyar. |
| 48 | `if not OPERATORS[rule["operator"]](observed, rule["threshold"]):` | Kuralın karşılaştırma fonksiyonuyla gözlenen değer ve eşiği karşılaştırır. |
| 49 | `continue` | Koşul sağlanmıyorsa bu kuralı bırakıp sonraki kurala geçer. |
| 51 | `cur.execute(` | Son alarm zamanını okuyan sorguyu çalıştırır. |
| 52 | `"SELECT last_triggered_at FROM alert_states WHERE rule_id = %s AND service = %s",` | Bu kural ve bu servis için bekleme durumunu arar. |
| 53 | `(rule["id"], record["service"]),` | Kural kimliği ve servisi ayrı gönderir. |
| 54 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 55 | `state = cur.fetchone()` | Bulunan son alarm zamanını alır; önceki alarm yoksa None gelir. |
| 56 | `if state and now < state["last_triggered_at"] + timedelta(seconds=rule["cooldown_seconds"]):` | Son alarmdan sonra cooldown_seconds dolmuş mu diye kontrol eder. |
| 57 | `continue` | Süre dolmadıysa tekrar bildirim oluşturmaz; sonraki kurala geçer. |
| 59 | `description = (f"{record['name']} ({record['unit']})" if kind == "metric"` | Bildirimde metrik adını/birimini veya log sayma penceresini açıklayan metni hazırlar. |
| 60 | `else f"Son {rule['window_seconds']} saniyedeki {rule['level']} sayısı")` | Bildirimde metrik adını/birimini veya log sayma penceresini açıklayan metni hazırlar. |
| 61 | `message = (f"{record['service']}: {description} = {observed:g}; "` | Servis ve gözlenen değeri bildirim mesajına ekler. :g sayı biçimidir; gereksiz .0 yazmaz. |
| 62 | `f"eşik {SYMBOLS[rule['operator']]} {rule['threshold']:g}.")` | Karşılaştırma simgesini ve eşik sayısını mesajın devamına ekler. |
| 63 | `cur.execute(` | Yeni alarm kaydı ekleme sorgusunu çalıştırır. |
| 64 | `"""INSERT INTO alerts` | Bildirimi alerts tablosuna ekler. |
| 65 | `(rule_id, rule_name, kind, service, message, observed_value,` | Kuralın adını ve koşulunu da saklar; kural sonra değişse bile eski alarmın nedeni korunur. |
| 66 | `threshold, operator, source_task_id, triggered_at)` | Kuralın adını ve koşulunu da saklar; kural sonra değişse bile eski alarmın nedeni korunur. |
| 67 | `VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",` | On sütun için on parametre yeri açar. |
| 68 | `(rule["id"], rule["name"], rule["kind"], record["service"], message,` | Kural, servis, mesaj, gözlenen değer, eşik, görev ve zamanı aynı sırayla gönderir. |
| 69 | `observed, rule["threshold"], rule["operator"], task_id, now),` | Kural, servis, mesaj, gözlenen değer, eşik, görev ve zamanı aynı sırayla gönderir. |
| 70 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 71 | `cur.execute(` | Son alarm zamanını kaydetme sorgusunu çalıştırır. |
| 72 | `"""INSERT INTO alert_states (rule_id, service, last_triggered_at)` | Bekleme durumunu alert_states tablosuna yazar. |
| 73 | `VALUES (%s, %s, %s)` | Kural, servis ve alarm zamanını yerlerine koyar. |
| 74 | `ON CONFLICT (rule_id, service)` | Bu kural/servis durumu zaten var mı diye kontrol eder. |
| 75 | `DO UPDATE SET last_triggered_at = EXCLUDED.last_triggered_at""",` | Varsa zamanı günceller; EXCLUDED eklenmek istenen yeni satırı temsil eder. |
| 76 | `(rule["id"], record["service"], now),` | Durum için kural kimliğini, servisi ve şimdiki zamanı gönderir. |
| 77 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |

## main.py

Danışmadır. HTTP isteğini alır, doğrulatır, kuyruğa yollar veya arşivden okur ve cevap verir.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/main.py)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `from datetime import datetime, timezone` | UTC alım zamanı oluşturmak için tarih/saat araçlarını getirir. |
| 2 | `import logging` | API çalışma mesajları için logging modülünü getirir. |
| 3 | `from typing import Annotated, Literal` | Annotated alan doğrulama bilgisi ekler; Literal seçenekleri sınırlar. |
| 5 | `from dotenv import load_dotenv` | .env okuyucusunu getirir. |
| 6 | `from fastapi import FastAPI, HTTPException, Path, Query, Request` | API, HTTP hatası, adres/sorgu parametresi doğrulama ve istek araçlarını getirir. |
| 7 | `from fastapi.responses import JSONResponse` | HTTP kodunu belirterek JSON cevap üretme aracını getirir. |
| 8 | `from fastapi.exceptions import RequestValidationError` | Giriş doğrulama hatalarını yakalayacak türü getirir. |
| 9 | `from kombu.exceptions import OperationalError as BrokerError` | Kuyruk bağlantı hatasına BrokerError takma adı verir; veritabanı hatasıyla karışmaz. |
| 10 | `from psycopg import OperationalError` | Veritabanı bağlantı hata türünü getirir. |
| 11 | `from psycopg.errors import UniqueViolation, QueryCanceled, LockNotAvailable, UndefinedTable` | Kural adı çakışması, zaman aşımı, kilit ve eksik tablo hatalarını getirir. |
| 12 | `from psycopg.rows import dict_row` | Veritabanı satırlarını sözlük olarak alacak ayarı getirir. |
| 13 | `from pydantic import AwareDatetime, ValidationError` | Saat dilimli zaman türü ve birleşmiş kural doğrulama hatası türünü getirir. |
| 14 | `from redis import Redis` | Redis'e sağlık kontrolü göndermek için istemciyi getirir. |
| 15 | `from redis.exceptions import RedisError` | Redis bağlantı hatalarını yakalayacak türü getirir. |
| 17 | `# Ayarlar görev modülü içe alınmadan önce yüklenir.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 18 | `load_dotenv()` | Görev modülleri yüklenmeden önce .env içindeki ayarları okur. |
| 20 | `from celery_app import celery_app` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 21 | `from database import get_connection` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 22 | `from models import LogInput, MetricInput, AlertRuleInput, AlertRulePatch` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 23 | `from queries import page, telemetry_filters` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 24 | `from tasks import process_log, process_metric` | Projenin Celery, bağlantı, şablon, filtreleme ve görev fonksiyonlarını içe alır. |
| 26 | `logger = logging.getLogger(__name__)` | Bu dosyanın logger'ını oluşturur. |
| 27 | `app = FastAPI(title="Observability Platform", version="0.2.0",` | FastAPI uygulamasını adı, sürümü ve Swagger açıklamasıyla oluşturur. |
| 28 | `description="Log/metrik toplama, filtreleme ve sistem içi alarm API'si.")` | FastAPI uygulamasını adı, sürümü ve Swagger açıklamasıyla oluşturur. |
| 30 | `Limit = Annotated[int, Query(ge=1, le=200)]` | limit sorgu parametresi için ortak 1-200 doğrulamasını tanımlar. |
| 31 | `Offset = Annotated[int, Query(ge=0, le=100000)]` | offset için ortak 0-100000 doğrulamasını tanımlar. |
| 32 | `Service = Annotated[str \| None, Query(min_length=1, max_length=200, pattern=r"\S")]` | İsteğe bağlı servis filtresinin metin sınırlarını tanımlar. |
| 33 | `Time = Annotated[AwareDatetime \| None, Query()]` | İsteğe bağlı saat dilimli zaman filtresini tanımlar. |
| 34 | `RecordId = Annotated[int, Path(ge=1, le=9223372036854775807)]` | Adres içindeki kayıt kimliğini pozitif BIGINT aralığıyla sınırlar. |
| 37 | `@app.exception_handler(RequestValidationError)` | Doğrulama hatası oluştuğunda bu cevap fonksiyonunu kullan der. |
| 38 | `async def invalid_request(request: Request, exc: RequestValidationError):` | Doğrulama hatası cevap fonksiyonunu tanımlar. async burada FastAPI'nin hata işleyici biçimidir. |
| 39 | `# NaN/Infinity gibi geçersiz girdileri cevap JSON'una tekrar eklemeyiz.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 40 | `details = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}` | Her hatadan alanın yerini, açıklamasını ve türünü alır; geçersiz girdi değerini cevapta tekrar yazmaz. |
| 41 | `for error in exc.errors()]` | Bu sade hata sözlüğünü bütün hatalar için oluşturur. |
| 42 | `return JSONResponse(status_code=422, content={"detail": details})` | Hata listesini 422 cevabıyla döndürür. |
| 45 | `@app.exception_handler(OperationalError)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 46 | `@app.exception_handler(QueryCanceled)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 47 | `@app.exception_handler(LockNotAvailable)` | Bu üç veritabanı hata türünü aynı cevap fonksiyonuna bağlar. |
| 48 | `async def database_unavailable(request: Request, exc: Exception):` | Veritabanı erişim sorunu cevap fonksiyonunu tanımlar. |
| 49 | `logger.warning("Veritabanı işlemi tamamlanamadı: %s", type(exc).__name__)` | Ayrıntılı bağlantı bilgisi/parola yerine yalnızca hata türünü loglar. |
| 50 | `return JSONResponse(status_code=503, content={"detail": "Veritabanı geçici olarak erişilemiyor; tekrar deneyin."})` | Kullanıcıya açıklamalı 503 cevabı gönderir. |
| 53 | `@app.get("/health", tags=["Sağlık"])` | GET /health adresini oluşturur; tags Swagger'daki bölüm adıdır. |
| 54 | `def health():` | API süreç kontrolü fonksiyonunu tanımlar. |
| 55 | `return {"status": "ok"}` | API'nin cevap verebildiğini belirtir; bağımlılıkları kontrol etmez. |
| 58 | `@app.get("/ready", tags=["Sağlık"])` | GET /ready adresini oluşturur. |
| 59 | `def ready():` | Veritabanı ve kuyruk hazırlık kontrolünü tanımlar. |
| 60 | `checks = {"database": False, "redis": False}` | İki kontrolü başlangıçta başarısız kabul eder. |
| 61 | `try:` | Veritabanı kontrolünü hata yakalama bloğunda başlatır. |
| 62 | `with get_connection() as conn:` | Veritabanı bağlantısı açar. |
| 63 | `conn.execute("SELECT 1 FROM alert_rules LIMIT 1")` | Alarm tablosuna küçük bir sorgu atar; bağlantıyı ve tablonun varlığını kontrol eder. |
| 64 | `checks["database"] = True` | Veritabanı kontrolü başarılıysa True yazar. |
| 65 | `except (OperationalError, UndefinedTable, QueryCanceled, LockNotAvailable):` | Bağlantı, şema veya süre sorununu yakalar. |
| 66 | `pass` | Hata olduğunda kontrol False kalır; diğer kontrol de yapılır. |
| 67 | `try:` | Redis kontrolünü ayrı hata yakalama bloğunda başlatır. |
| 68 | `with Redis.from_url(celery_app.conf.broker_url, socket_connect_timeout=2, socket_timeout=2) as client:` | Redis istemcisi açar; bağlantı ve ağ işlemlerinde 2 saniye sınır kullanır. |
| 69 | `checks["redis"] = bool(client.ping())` | PING gönderir ve başarılı yanıtı True olarak kaydeder. |
| 70 | `except RedisError:` | Redis sorunu varsa yakalar. |
| 71 | `pass` | Redis kontrolü False kalır. |
| 72 | `ok = all(checks.values())` | İki kontrol de True ise uygulamayı hazır kabul eder. |
| 73 | `return JSONResponse(status_code=200 if ok else 503,` | Hazırsa 200, değilse 503 döndürür ve hangi bağımlılığın çalıştığını gösterir. Worker kontrolü burada yoktur. |
| 74 | `content={"status": "ready" if ok else "unavailable", "checks": checks})` | Hazırsa 200, değilse 503 döndürür ve hangi bağımlılığın çalıştığını gösterir. Worker kontrolü burada yoktur. |
| 77 | `def enqueue(task, payload):` | Log ve metriğin ortak kuyruğa gönderme fonksiyonunu tanımlar. |
| 78 | `record = payload.model_dump(mode="json")` | Doğrulanmış modeli JSON'a uygun değerleri olan sözlüğe çevirir; bu henüz JSON metni değildir. |
| 79 | `record["received_at"] = datetime.now(timezone.utc).isoformat()` | API'nin aldığı zamanı UTC olarak ekler. |
| 80 | `try:` | Kuyruğa gönderme hatalarını yakalamak için try açar. |
| 81 | `result = task.apply_async(args=[record], retry=False)` | Worker'a iş emri gönderir; bu fonksiyon görevi API içinde çalıştırmaz. args görev argümanlarıdır. |
| 82 | `except (BrokerError, RedisError, OSError):` | Kuyruk veya ağ bağlantı hatalarını yakalar. |
| 83 | `raise HTTPException(503, "Veri kuyruğa alınamadı; Redis bağlantısını kontrol edip tekrar deneyin.")` | Kuyruğa alınamayan kayıt için 503 gönderir. |
| 84 | `return {"status": "queued", "task_id": result.id}` | Kuyruğa alınma durumunu ve takip için görev kimliğini döndürür. |
| 87 | `@app.post("/logs", status_code=202, tags=["Loglar"])` | POST /logs adresini oluşturur; kabul edilince 202 döndürür. |
| 88 | `def receive_log(log: LogInput):` | Gövdeyi LogInput ile doğrulatır ve fonksiyona alır. |
| 89 | `return enqueue(process_log, log)` | Logu process_log görevine gönderir. |
| 92 | `@app.post("/metrics", status_code=202, tags=["Metrikler"])` | POST /metrics adresini oluşturur. |
| 93 | `def receive_metric(metric: MetricInput):` | Gövdeyi MetricInput ile doğrulatır. |
| 94 | `return enqueue(process_metric, metric)` | Metriği process_metric görevine gönderir. |
| 97 | `@app.get("/logs", tags=["Loglar"])` | GET /logs adresini oluşturur. |
| 98 | `def list_logs(service: Service = None,` | Log listeleme fonksiyonunu isteğe bağlı servis filtresiyle tanımlar. |
| 99 | `level: Literal["INFO", "WARN", "ERROR", "FATAL"] \| None = None,` | İsteğe bağlı seviyeyi dört seçenekle sınırlar. |
| 100 | `q: Annotated[str \| None, Query(min_length=1, max_length=500, pattern=r"\S")] = None,` | Kelime arama metnini sınırlar; yalnızca boşluk kabul etmez. |
| 101 | `tags: Annotated[str \| None, Query(max_length=4000)] = None,` | JSON etiket filtresinin metin uzunluğunu sınırlar. |
| 102 | `start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):` | Zaman aralığı ve sayfalama parametrelerini ekler; varsayılan 20 kayıt, başlangıç 0. |
| 103 | `clauses, values = telemetry_filters(service, start, end, tags)` | Ortak servis/zaman/etiket koşullarını hazırlatır. |
| 104 | `if level is not None:` | Seviye filtresi gönderilmiş mi diye kontrol eder. |
| 105 | `clauses.append("level = %s")` | Seviye eşitliği koşulunu ekler. |
| 106 | `values.append(level)` | Seviye değerini ayrı parametre listesine koyar. |
| 107 | `if q is not None:` | Kelime araması istenmiş mi diye kontrol eder. |
| 108 | `clauses.append("to_tsvector('simple', message) @@ websearch_to_tsquery('simple', %s)")` | Mesajı kelime dizinine çevirip websearch sorgusuyla eşleştirir; hazırladığımız GIN indeksinin ifadesiyle aynıdır. |
| 109 | `values.append(q)` | Kullanıcının arama metnini ayrı parametre olarak verir. |
| 110 | `return page("SELECT id, timestamp, received_at, service, level, message, stack_trace, tags FROM logs",` | Log alanlarını en yeni olay önce olacak şekilde ortak sayfalama fonksiyonundan getirir. |
| 111 | `clauses, values, "timestamp DESC, id DESC", limit, offset)` | Log alanlarını en yeni olay önce olacak şekilde ortak sayfalama fonksiyonundan getirir. |
| 114 | `@app.get("/metrics", tags=["Metrikler"])` | GET /metrics adresini oluşturur. |
| 115 | `def list_metrics(service: Service = None,` | Metrik listeleme fonksiyonunu servis filtresiyle tanımlar. |
| 116 | `name: Annotated[str \| None, Query(min_length=1, max_length=200)] = None,` | İsteğe bağlı ölçüm adı filtresini ekler. |
| 117 | `unit: Annotated[str \| None, Query(min_length=1, max_length=50)] = None,` | İsteğe bağlı birim filtresini ekler. |
| 118 | `tags: Annotated[str \| None, Query(max_length=4000)] = None,` | Etiket filtresini ekler. |
| 119 | `start: Time = None, end: Time = None, limit: Limit = 20, offset: Offset = 0):` | Zaman aralığı ve sayfalama parametrelerini ekler. |
| 120 | `clauses, values = telemetry_filters(service, start, end, tags)` | Ortak filtreleri hazırlatır. |
| 121 | `for column, value in (("name", name), ("unit", unit)):` | Ölçüm adı ve birim filtrelerini sırayla dolaşır. |
| 122 | `if value is not None:` | Gönderilmiş filtreyi işleme alır. |
| 123 | `clauses.append(f"{column} = %s")` | Kodda sabit olan name/unit sütununa eşitlik koşulu ekler; değer SQL'e yapıştırılmaz. |
| 124 | `values.append(value)` | Filtre değerini parametre listesine ekler. |
| 125 | `return page("SELECT id, timestamp, received_at, service, name, value, unit, tags FROM metrics",` | Metrik alanlarını olay zamanına göre sıralayıp sayfalı getirir. |
| 126 | `clauses, values, "timestamp DESC, id DESC", limit, offset)` | Metrik alanlarını olay zamanına göre sıralayıp sayfalı getirir. |
| 129 | `RULE_FIELDS = ("name", "kind", "service", "metric_name", "metric_unit", "level", "operator",` | Kural ekleme/düzenlemede kullanılacak izinli sütun adlarını sabit listede tutar. |
| 130 | `"threshold", "window_seconds", "cooldown_seconds", "enabled")` | Kural ekleme/düzenlemede kullanılacak izinli sütun adlarını sabit listede tutar. |
| 133 | `@app.get("/alert-rules", tags=["Alarm kuralları"])` | GET /alert-rules adresini oluşturur. |
| 134 | `def list_rules(enabled: bool \| None = None, limit: Limit = 20, offset: Offset = 0):` | Kuralları açık/kapalı filtresi ve sayfalamayla listeleyen fonksiyonu tanımlar. |
| 135 | `clauses, values = (["enabled = %s"], [enabled]) if enabled is not None else ([], [])` | enabled gönderilmişse filtre kurar; False da geçerli bir filtre olduğu için is not None kullanır. |
| 136 | `return page("SELECT * FROM alert_rules", clauses, values, "id ASC", limit, offset)` | Kuralları kimlik sırasıyla sayfalı getirir. |
| 139 | `@app.post("/alert-rules", status_code=201, tags=["Alarm kuralları"])` | POST /alert-rules adresini oluşturur; yeni kayıt için 201 döndürür. |
| 140 | `def create_rule(rule: AlertRuleInput):` | Gelen kuralı AlertRuleInput ile doğrulatır. |
| 141 | `data = rule.model_dump()` | Kural modelini Python sözlüğüne çevirir. |
| 142 | `try:` | Aynı isim hatasını yakalamak için try açar. |
| 143 | `with get_connection() as conn:` | Kural ekleme transaction'ını açar. |
| 144 | `conn.row_factory = dict_row` | Dönen satırı sözlük olarak alır. |
| 145 | `result = conn.execute(` | Kural INSERT sorgusunu çalıştırır. |
| 146 | `"INSERT INTO alert_rules (" + ", ".join(RULE_FIELDS) + ") VALUES ("` | İzinli sabit sütun adlarını virgülle birleştirip INSERT oluşturur. |
| 147 | `+ ", ".join(["%s"] * len(RULE_FIELDS)) + ") RETURNING *",` | Her sütun için %s oluşturur; RETURNING * eklenen kaydı geri getirir. |
| 148 | `[data[field] for field in RULE_FIELDS],` | Kural değerlerini sabit sütun sırasıyla ayrı parametreler olarak gönderir. |
| 149 | `).fetchone()` | Eklenen tek kuralı alır. |
| 150 | `except UniqueViolation:` | Veritabanındaki UNIQUE isim kontrolüne takılan hatayı yakalar. |
| 151 | `raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")` | İsim çakışmasını 409 cevabıyla bildirir. |
| 152 | `return result` | Yeni kuralı JSON cevabı olarak döndürür. |
| 155 | `@app.patch("/alert-rules/{rule_id}", tags=["Alarm kuralları"])` | Kural kimliği içeren PATCH adresini oluşturur. |
| 156 | `def update_rule(rule_id: RecordId, patch: AlertRulePatch):` | Kimliği ve değiştirilecek alanları doğrulatarak fonksiyona alır. |
| 157 | `changes = patch.model_dump(exclude_unset=True)` | Sadece istekte açıkça gönderilen alanları alır; gönderilmeyen varsayılanlarla eski değerleri ezmez. |
| 158 | `try:` | İsim çakışması hatasını yakalamak için try açar. |
| 159 | `with get_connection() as conn:` | Düzenleme transaction'ını açar. |
| 160 | `conn.row_factory = dict_row` | Sorgu sonucunu sözlük yapar. |
| 161 | `existing = conn.execute("SELECT * FROM alert_rules WHERE id = %s FOR UPDATE", (rule_id,)).fetchone()` | Eski kuralı okur ve kilitler; worker aynı anda o kuralı değişmiş haliyle değerlendiremez. |
| 162 | `if existing is None:` | Kural bulunmadı mı diye kontrol eder. |
| 163 | `raise HTTPException(404, "Alarm kuralı bulunamadı")` | Bulunmayan kimliğe 404 döndürür. |
| 164 | `if not changes:` | Değiştirilecek alan var mı diye bakar. |
| 165 | `return existing` | Boş PATCH gelmişse mevcut kuralı döndürür. |
| 166 | `merged = {field: existing[field] for field in RULE_FIELDS}` | Mevcut kuralın izinli alanlarını yeni sözlüğe alır. |
| 167 | `merged.update(changes)` | Gönderilen değişiklikleri bu sözlüğe uygular. |
| 168 | `try:` | Birleşmiş kuralın doğrulama hatalarını yakalamak için try açar. |
| 169 | `validated = AlertRuleInput.model_validate(merged).model_dump()` | Tam kural şablonuyla tekrar kontrol eder. Örneğin threshold:null burada reddedilir. |
| 170 | `except ValidationError as exc:` | Birleşmiş kural geçersizse hatayı yakalar. |
| 171 | `raise HTTPException(422, exc.errors(include_context=False, include_input=False))` | Geçersiz kuralın hata ayrıntılarını 422 ile gönderir; hatalı girdiyi cevapta tekrar taşımaz. |
| 172 | `result = conn.execute(` | Kuralı güncelleyen sorguyu çalıştırır. |
| 173 | `"UPDATE alert_rules SET " + ", ".join(field + " = %s" for field in RULE_FIELDS)` | İzinli sütunların her biri için parametreli SET ifadesi oluşturur. |
| 174 | `+ ", updated_at = clock_timestamp() WHERE id = %s RETURNING *",` | Güncelleme zamanını DB saatiyle yazar ve yalnızca istenen kimliği günceller. |
| 175 | `[validated[field] for field in RULE_FIELDS] + [rule_id],` | Doğrulanmış yeni değerleri ve en son kimliği parametre olarak gönderir. |
| 176 | `).fetchone()` | Güncellenmiş kuralı alır. |
| 177 | `# Düzenlenen kuralın yeni ayarları sonraki kayıtta hemen uygulanır.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 178 | `conn.execute("DELETE FROM alert_states WHERE rule_id = %s", (rule_id,))` | Bu kuralın eski bekleme durumunu temizler; yeni ayarlar sonraki kayıtta hemen uygulanır. |
| 179 | `except UniqueViolation:` | Yeni ad başka bir kuralla çakışırsa hatayı yakalar. |
| 180 | `raise HTTPException(409, "Bu isimde bir alarm kuralı zaten var")` | İsim çakışmasına 409 verir; transaction geri alınır. |
| 181 | `return result` | Güncellenmiş kuralı döndürür. |
| 184 | `@app.get("/alerts", tags=["Alarmlar"])` | GET /alerts adresini oluşturur. |
| 185 | `def list_alerts(service: Service = None, status: Literal["open", "acknowledged"] \| None = None,` | Servis ve open/acknowledged durum filtrelerini tanımlar. |
| 186 | `rule_id: Annotated[int \| None, Query(ge=1, le=9223372036854775807)] = None,` | İsteğe bağlı kural kimliği filtresini pozitif BIGINT aralığıyla sınırlar. |
| 187 | `limit: Limit = 20, offset: Offset = 0):` | Bildirimlerin sayfalama parametrelerini ekler. |
| 188 | `clauses, values = [], []` | Filtre koşulları ve değerleri için ayrı listeler açar. |
| 189 | `for column, value in (("service", service), ("status", status), ("rule_id", rule_id)):` | İzinli servis, durum ve kural kimliği filtrelerini dolaşır. |
| 190 | `if value is not None:` | Gönderilen filtreyi seçer. |
| 191 | `clauses.append(f"{column} = %s")` | Sabit sütun için eşitlik koşulu ekler. |
| 192 | `values.append(value)` | Filtre değerini ayrı parametre listesine koyar. |
| 193 | `return page("SELECT * FROM alerts", clauses, values, "triggered_at DESC, id DESC", limit, offset)` | Bildirimleri tetikleme zamanı en yeni önce olacak şekilde sayfalı getirir. |
| 196 | `@app.patch("/alerts/{alert_id}/acknowledge", tags=["Alarmlar"])` | Bildirimi görüldü olarak işaretleyen PATCH adresini oluşturur. |
| 197 | `def acknowledge_alert(alert_id: RecordId):` | Bildirimin kimliğini doğrulatarak alır. |
| 198 | `with get_connection() as conn:` | Görüldü işlemi için transaction açar. |
| 199 | `conn.row_factory = dict_row` | Sonucu sözlük olarak alır. |
| 200 | `result = conn.execute(` | Bildirim güncelleme sorgusunu çalıştırır. |
| 201 | `"""UPDATE alerts SET status = 'acknowledged',` | Durumu acknowledged yapar; bu kullanıcı gördü anlamındadır. |
| 202 | `acknowledged_at = COALESCE(acknowledged_at, clock_timestamp())` | COALESCE eski görülme zamanı varsa onu korur, yoksa şimdiki zamanı yazar. |
| 203 | `WHERE id = %s RETURNING *""", (alert_id,),` | Yalnızca bu kimliği günceller ve güncellenmiş satırı döndürür. |
| 204 | `).fetchone()` | Güncellemenin tek satırlık sonucunu alır. |
| 205 | `if result is None:` | Böyle bir bildirim yok mu diye kontrol eder. |
| 206 | `raise HTTPException(404, "Alarm bulunamadı")` | Bulunmayan bildirime 404 verir. |
| 207 | `return result` | Güncellenmiş bildirimi döndürür. |

## compose.yaml

Docker odalarının kurulma sırasıdır. Burada yalnızca yeni db-init bağımlılığını ve servisinin satırlarını açıklıyoruz.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/compose.yaml)

| Satır | Kod | Anlamı |
|---|---|---|
| 29 | `db-init:` | Worker'ın bekleyeceği servisler arasına db-init eklenir. |
| 30 | `condition: service_completed_successfully` | Tablo kurulumunun başarıyla bitmesini bekler; db-init sürekli açık kalmak zorunda değildir. |
| 32 | `db-init:` | Veritabanı kurulum servisini tanımlar. |
| 33 | `image: timescale/timescaledb:latest-pg17` | psql içeren TimescaleDB image'ını kullanır. |
| 34 | `environment:` | Kurulum istemcisinin ortam ayarlarını açar. |
| 35 | `PGHOST: db` | psql, Docker ağındaki db servisine bağlanır. |
| 36 | `PGUSER: ${POSTGRES_USER}` | .env içindeki kullanıcı adını psql ayarına verir. |
| 37 | `PGDATABASE: ${POSTGRES_DB}` | .env içindeki veritabanı adını psql ayarına verir. |
| 38 | `PGPASSWORD: ${POSTGRES_PASSWORD}` | .env içindeki parolayı psql ortamına verir; komut satırına yazmaz. |
| 39 | `volumes:` | Kurulum dosyalarının bağlanacağı volume listesini açar. |
| 40 | `- ./schema.sql:/schema.sql:ro` | Şemayı konteynerde salt okunur dosya olarak sunar; ro salt okunur demektir. |
| 41 | `- ./migrations:/migrations:ro` | Migration klasörünü salt okunur olarak konteynere bağlar. |
| 42 | `command: ["psql", "-v", "ON_ERROR_STOP=1", "--single-transaction", "-f", "/schema.sql", "-f", "/migrations/001_alerting.sql"]` | İki SQL dosyasını psql ile tek transaction içinde çalıştırır; hata varsa durur ve değişiklikler geri alınır. |
| 43 | `depends_on:` | Kurulum servisinin bekleyeceği bağımlılıkları tanımlar. |
| 44 | `db:` | Kurulum db servisini bekler. |
| 45 | `condition: service_healthy` | Veritabanı sağlık kontrolü başarılı olduktan sonra kurulum başlar. |

## Dockerfile

Worker odasının nasıl hazırlanacağını belirtir. Burada dosya kopyalama ve normal kullanıcı değişikliklerini açıklıyoruz.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/Dockerfile)

| Satır | Kod | Anlamı |
|---|---|---|
| 14 | `COPY main.py models.py celery_app.py tasks.py database.py alerts.py queries.py ./` | API, worker, alarm ve sorgu dosyalarını image içine kopyalar; yalnızca bu açıkça yazılan dosyalar kopyalanır. |
| 17 | `RUN useradd --uid 10001 --create-home appuser` | Linux image içinde 10001 numaralı normal kullanıcıyı oluşturur. |
| 18 | `USER appuser` | Sonraki çalıştırmanın bu kullanıcıyla yapılmasını sağlar; worker root olmaz. |

## schema.sql

Eski tablo/indeks tasarımını değiştirmedik; kurulum tekrar çalışınca hata vermemesi için eklenen satırlar burada açıklanıyor.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/schema.sql)

| Satır | Kod | Anlamı |
|---|---|---|
| 5 | `CREATE TABLE IF NOT EXISTS logs (` | logs tablosu yoksa oluşturur; varsa korur. Var olan tablonun yapısını değiştirmez. |
| 19 | `CREATE TABLE IF NOT EXISTS metrics (` | metrics tablosu yoksa oluşturur; varsa korur. |
| 37 | `by_range('timestamp',INTERVAL'1 day'), -- Her parça bir günlük zaman aralığı kapsar.` | Günlük zaman parçasını tanımlar; ardından yeni seçenek geleceği için virgül eklendi. |
| 38 | `if_not_exists => TRUE` | Tablo zaten hypertable ise yeniden dönüştürmeye çalışmaz. |
| 44 | `by_range('timestamp', INTERVAL '1 day'),` | Metriklerin günlük zaman parçasını tanımlar. |
| 45 | `if_not_exists => TRUE` | Metrik tablosu zaten hypertable ise onu korur. |
| 49 | `CREATE INDEX IF NOT EXISTS idx_logs_service_timestamp` | Servis/zaman indeksi yoksa oluşturur; varsa hata vermez. |
| 53 | `CREATE INDEX IF NOT EXISTS idx_logs_level_timestamp` | Seviye/zaman indeksi yoksa oluşturur. |
| 57 | `CREATE INDEX IF NOT EXISTS idx_metrics_service_name_timestamp` | Metrik servis/ad/zaman indeksi yoksa oluşturur. |
| 61 | `CREATE INDEX IF NOT EXISTS idx_logs_message_search` | Log kelime arama indeksi yoksa oluşturur. |
| 65 | `CREATE INDEX IF NOT EXISTS idx_logs_tags` | Log etiket indeksi yoksa oluşturur. |
| 69 | `CREATE INDEX IF NOT EXISTS idx_metrics_tags` | Metrik etiket indeksi yoksa oluşturur. |

## migrations/001_alerting.sql

Mevcut verileri koruyarak yeni alarm dolaplarını açan SQL dosyasıdır. Kural defteri, son alarm zamanı ve bildirimler ayrı tablolarda tutulur.

[Dosyayı aç](C:/Users/omer3/Desktop/artersoft/migrations/001_alerting.sql)

| Satır | Kod | Anlamı |
|---|---|---|
| 1 | `-- Mevcut log ve metrik kayıtlarını koruyarak alarm tablolarını ekler.` | Yorum satırıdır; kodun neden yazıldığını açıklar, işlem çalıştırmaz. |
| 2 | `CREATE TABLE IF NOT EXISTS schema_migrations (` | Hangi kurulum sürümünün uygulandığını tutar; başlangıç kuralları her açılışta yeniden eklenmez. |
| 3 | `version TEXT PRIMARY KEY,` | Uygulanan migration sürümünü benzersiz olarak saklar. |
| 4 | `applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` | Kurulumun veritabanındaki zamanını otomatik yazar. |
| 5 | `);` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 7 | `CREATE TABLE IF NOT EXISTS processed_tasks (` | İşlenmiş görev kimliklerini tutar; tekrar teslim edilen görevi tanımamızı sağlar. |
| 8 | `task_id UUID PRIMARY KEY,` | Görev kimliğini UUID türünde benzersiz tutar; aynı kimlik ikinci kez eklenemez. |
| 9 | `kind TEXT NOT NULL CHECK (kind IN ('log', 'metric')),` | Kayıt/kural türünü saklar; CHECK varsa izinli türleri sınırlar. |
| 10 | `processed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` | Görevin işlenme zamanını otomatik tutar. |
| 11 | `);` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
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
| 24 | `),` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
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
| 37 | `)` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 38 | `);` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
| 40 | `CREATE TABLE IF NOT EXISTS alert_states (` | Kural ve servis için en son bildirim zamanını tutar; bekleme süresi buradan hesaplanır. |
| 41 | `rule_id BIGINT NOT NULL REFERENCES alert_rules(id),` | İlgili kuralı başka tablodaki id ile ilişkilendirir; var olmayan kurala işaret edilemez. |
| 42 | `service TEXT NOT NULL,` | Servis kapsamını veya bildirimin ait olduğu servisi saklar; kuraldaki null tüm servisler demektir. |
| 43 | `last_triggered_at TIMESTAMPTZ NOT NULL,` | Bu kural/servisin son bildirim zamanını tutar. |
| 44 | `PRIMARY KEY (rule_id, service)` | Kural ve servis birleşimini benzersiz yapar; her servis için ayrı bekleme durumu vardır. |
| 45 | `);` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
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
| 62 | `);` | Önceki çok satırlı çağrıyı, sözlüğü veya SQL tanımını kapatır. |
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

## Test ve rapor dosyaları

tests/test_backend.py gerçek servislere istek gönderir, kaydın worker tarafından işlendiğini bekler ve beklenen sonuçla karşılaştırır. 12 senaryo ilerleme raporunda listelenmiştir. qa- ile başlayan benzersiz servislerle çalışır; yalnızca kendi verilerini temizler.

scripts/verify_backend.py testleri çalıştırıp gerçek sonucu test-results/backend-checks.json içine yazar. scripts/verify_outages.py yerel Redis/veritabanını kısa süre kapatır; API'nin 503 verdiğini kontrol eder ve finally bloğunda servisleri yeniden açar.

README.md kurulum ve kullanım rehberidir. api-contract.md istek/yanıt sözleşmesidir. .env.example yalnızca ayar örneğidir; gerçek parola .env içinde kalır.

## Öğrenirken izlenecek sıra

Önce database.py ve models.py; sonra tasks.py; ardından alerts.py; en son queries.py ve main.py. Docker değişiklikleri bu akışın nerede çalıştığını anlatır. Her dosyayı beraber açıklayıp anlaşılmayan satırda durabiliriz.
