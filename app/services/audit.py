import json

from ..timeutil import now_str


def log(conn, user_id, aksi: str, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log(waktu, user_id, aksi, detail) VALUES (?,?,?,?)",
        (now_str(), user_id, aksi, json.dumps(detail, ensure_ascii=False)),
    )
