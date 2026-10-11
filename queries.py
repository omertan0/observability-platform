"""Liste sorgularını parametrelerle oluşturur; kullanıcı verisi SQL'e eklenmez."""
import json
import math

from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from database import get_connection


def reject_json_constant(value):
    raise ValueError(f"Geçersiz JSON sayısı: {value}")


def finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON sayısı sonlu olmalıdır")
    return number


def telemetry_filters(service, start, end, tags):
    clauses, values = [], []
    if start and end and start > end:
        raise HTTPException(422, "start, end zamanından sonra olamaz")
    for column, value, comparison in (
        ("service", service, "="), ("timestamp", start, ">="), ("timestamp", end, "<="),
    ):
        if value is not None:
            clauses.append(f"{column} {comparison} %s")
            values.append(value)
    if tags is not None:
        try:
            parsed = json.loads(tags, parse_constant=reject_json_constant, parse_float=finite_json_float)
            if not isinstance(parsed, dict):
                raise ValueError("object required")
        except (ValueError, TypeError):
            raise HTTPException(422, 'tags JSON nesnesi olmalıdır; örnek: {"environment":"test"}')
        clauses.append("tags @> %s")
        values.append(Jsonb(parsed))
    return clauses, values


def page(sql, clauses, values, order, limit, offset):
    # sql/order/clauses yalnızca kod içindeki sabitlerden gelir.
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with get_connection() as conn:
        conn.row_factory = dict_row
        rows = conn.execute(
            sql + where + " ORDER BY " + order + " LIMIT %s OFFSET %s",
            [*values, limit + 1, offset],
        ).fetchall()
    has_more = len(rows) > limit
    return {"items": rows[:limit], "limit": limit, "offset": offset,
            "has_more": has_more, "next_offset": offset + limit if has_more else None}
