from fastapi import FastAPI
from models import LogInput

app = FastAPI(title="Observability Platform")


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/logs")  #Bu adrese gönderilen POST isteklerini karşılar.
def receive_log(log: LogInput): #Gönderilen JSON, LogInput kurallarına göre kontrol edilir. Hatalıysa FastAPI otomatik olarak 422 döndürür.
    return {
        "status": "validated",
        "log": log.model_dump(mode="json") #Kontrol edilmiş veriyi JSON’a uygun bir sözlüğe dönüştürür; cevapta geri gösteriyoruz
    }