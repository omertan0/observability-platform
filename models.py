from typing import Literal
from pydantic import AwareDatetime, BaseModel , Field

# tanımladığımız modele göre gelen veriyi kontrol eder


class LogInput(BaseModel): # LogInput adinda log sablonu olusturduk
    timestamp: AwareDatetime
    service: str = Field(min_length=1, pattern=r"\S")
    level: Literal["INFO", "WARN", "ERROR", "FATAL"]
    message: str = Field(min_length=1, pattern=r"\S")
    stack_trace: str | None =None
    tags: dict = Field(default_factory=dict) #dict pythonda anahtar degerleri tutan sozluk