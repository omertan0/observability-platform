"""Yeni kayıt işlendiğinde kuralları değerlendirip sistem içi bildirim oluşturur."""
from datetime import timedelta
from operator import gt, ge, lt, le

from psycopg.rows import dict_row

OPERATORS = {"gt": gt, "gte": ge, "lt": lt, "lte": le}
SYMBOLS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def load_rules(conn, kind: str, records: list[dict]):
    # Aynı kuralı değerlendiren worker'lar sırayla ilerler; çift alarm önlenir.
    with conn.cursor(row_factory=dict_row) as cur:
        if kind == "metric":
            cur.execute(
                """SELECT * FROM alert_rules
                   WHERE enabled AND kind = 'metric_threshold'
                     AND (service IS NULL OR service = ANY(%s))
                     AND metric_name = ANY(%s) AND metric_unit = ANY(%s)
                   ORDER BY id FOR UPDATE""",
                ([r["service"] for r in records], [r["name"] for r in records], [r["unit"] for r in records]),
            )
        else:
            cur.execute(
                """SELECT * FROM alert_rules
                   WHERE enabled AND kind = 'log_count'
                     AND (service IS NULL OR service = ANY(%s)) AND level = ANY(%s)
                   ORDER BY id FOR UPDATE""",
                ([r["service"] for r in records], [r["level"] for r in records]),
            )
        return cur.fetchall()


def evaluate_alerts(conn, kind: str, record: dict, task_id: str, record_index=0, rules=None, now=None):
    if rules is None:
        rules = load_rules(conn, kind, [record])
    if not rules:
        return
    with conn.cursor(row_factory=dict_row) as cur:
        if now is None:
            cur.execute("SELECT clock_timestamp() AS now")
            now = cur.fetchone()["now"]
        for rule in rules:
            if rule["service"] is not None and rule["service"] != record["service"]:
                continue
            if kind == "metric" and (rule["metric_name"] != record["name"] or rule["metric_unit"] != record["unit"]):
                continue
            if kind == "log" and rule["level"] != record["level"]:
                continue
            if kind == "metric":
                observed = record["value"]
            else:
                cur.execute(
                    """SELECT count(*) AS count FROM logs
                       WHERE service = %s AND level = %s
                         AND received_at > %s AND received_at <= %s""",
                    (record["service"], rule["level"],
                     now - timedelta(seconds=rule["window_seconds"]), now),
                )
                observed = cur.fetchone()["count"]
            if not OPERATORS[rule["operator"]](observed, rule["threshold"]):
                continue

            cur.execute(
                "SELECT last_triggered_at FROM alert_states WHERE rule_id = %s AND service = %s",
                (rule["id"], record["service"]),
            )
            state = cur.fetchone()
            if state and now < state["last_triggered_at"] + timedelta(seconds=rule["cooldown_seconds"]):
                continue

            description = (f"{record['name']} ({record['unit']})" if kind == "metric"
                           else f"Son {rule['window_seconds']} saniyedeki {rule['level']} sayısı")
            message = (f"{record['service']}: {description} = {observed:g}; "
                       f"eşik {SYMBOLS[rule['operator']]} {rule['threshold']:g}.")
            cur.execute(
                """INSERT INTO alerts
                   (rule_id, rule_name, kind, service, message, observed_value,
                    threshold, operator, source_task_id, triggered_at, source_record_index)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (rule["id"], rule["name"], rule["kind"], record["service"], message,
                 observed, rule["threshold"], rule["operator"], task_id, now, record_index),
            )
            cur.execute(
                """INSERT INTO alert_states (rule_id, service, last_triggered_at)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (rule_id, service)
                   DO UPDATE SET last_triggered_at = EXCLUDED.last_triggered_at""",
                (rule["id"], record["service"], now),
            )
