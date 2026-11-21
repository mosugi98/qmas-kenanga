from __future__ import annotations

import math
from datetime import date, timedelta

MAX_CHART_DAYS = 92
_RANGE = "t.status='aktif' AND date(t.tanggal) BETWEEN ? AND ?"


def preset_range(preset: str, today: date) -> tuple[str, str]:
    if preset == "minggu_ini":
        start = today - timedelta(days=today.weekday())
    elif preset == "bulan_ini":
        start = today.replace(day=1)
    else:
        start = today
    return start.isoformat(), today.isoformat()


def nice_scale(vmax: int) -> tuple[int, list[int]]:
    vmax = max(int(vmax), 1_000_000)
    raw = vmax / 4
    exp = 10 ** math.floor(math.log10(raw))
    step = next(m * exp for m in (1, 2, 5, 10) if m * exp >= raw)
    top = step * math.ceil(vmax / step)
    return int(top), [int(i * step) for i in range(int(top // step) + 1)]


def _scalar(conn, sql: str, *args):
    return conn.execute(sql, args).fetchone()[0]


def summary(conn, start: str, end: str) -> dict:
    def total(cond: str) -> int:
        return _scalar(conn, f"SELECT COALESCE(SUM(t.total),0) FROM transactions t WHERE {cond} AND {_RANGE}", start, end)

    def gram(cond: str) -> float:
        value = _scalar(
            conn,
            "SELECT COALESCE(SUM(l.berat),0) FROM transaction_lines l "
            f"JOIN transactions t ON t.id=l.transaction_id WHERE {cond} AND {_RANGE}",
            start, end,
        )
        return round(value, 3)

    def count(cond: str) -> int:
        return _scalar(conn, f"SELECT COUNT(*) FROM transactions t WHERE {cond} AND {_RANGE}", start, end)

    last = date.fromisoformat(end)
    first = max(date.fromisoformat(start), last - timedelta(days=MAX_CHART_DAYS - 1))
    rows = conn.execute(
        "SELECT date(t.tanggal) AS tgl, "
        "SUM(CASE WHEN t.tipe='jual' THEN t.total ELSE 0 END) AS penjualan, "
        "SUM(CASE WHEN t.tipe!='jual' THEN t.total ELSE 0 END) AS pembelian "
        f"FROM transactions t WHERE {_RANGE} GROUP BY date(t.tanggal)",
        (first.isoformat(), end),
    ).fetchall()
    per_day = {r["tgl"]: r for r in rows}
    series = []
    day = first
    while day <= last:
        r = per_day.get(day.isoformat())
        series.append(
            {"tgl": day.isoformat(), "penjualan": r["penjualan"] if r else 0, "pembelian": r["pembelian"] if r else 0}
        )
        day += timedelta(days=1)

    recent = conn.execute(
        "SELECT t.id, t.tipe, t.tanggal, t.pihak, t.total, t.status, u.username AS kasir "
        "FROM transactions t JOIN users u ON u.id=t.kasir_id ORDER BY t.id DESC LIMIT 10"
    ).fetchall()
    return {
        "penjualan": total("t.tipe='jual'"),
        "pembelian": total("t.tipe!='jual'"),
        "gram_jual": gram("t.tipe='jual'"),
        "gram_beli": gram("t.tipe!='jual'"),
        "n_jual": count("t.tipe='jual'"),
        "n_beli": count("t.tipe!='jual'"),
        "series": series,
        "recent": recent,
    }


def stock_summary(conn) -> dict:
    row = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(berat),0) AS g FROM items WHERE status='tersedia'").fetchone()
    return {"jumlah": row["n"], "gram": round(row["g"], 3)}


def _desc(tipe: str, lines) -> str:
    first = lines[0]
    nama = f"{first['name']} {first['kadar']}" if first["name"] else None
    more = f" +{len(lines) - 1} lainnya" if len(lines) > 1 else ""
    if tipe == "jual":
        return (nama or f"Emas curah {first['kadar']}") + more
    asal = "pelanggan" if tipe == "beli_pelanggan" else "supplier"
    return (nama or f"Emas {first['kadar']}") + more + f" dari {asal}"


def day_rows(conn, start: str, end: str, limit: int = 10) -> list[dict]:
    """Daftar transaksi terbaru untuk beranda; pasangan tukar tambah digabung jadi satu baris."""
    txs = conn.execute(
        "SELECT * FROM transactions WHERE date(tanggal) BETWEEN ? AND ? ORDER BY id DESC LIMIT 200", (start, end)
    ).fetchall()
    if not txs:
        return []
    ids = [t["id"] for t in txs]
    lines = conn.execute(
        "SELECT l.transaction_id, l.kadar, l.berat, i.name FROM transaction_lines l "
        f"LEFT JOIN items i ON i.id=l.item_id WHERE l.transaction_id IN ({','.join('?' * len(ids))}) ORDER BY l.id",
        ids,
    ).fetchall()
    by_tx: dict[int, list] = {}
    for ln in lines:
        by_tx.setdefault(ln["transaction_id"], []).append(ln)

    rows: list[dict] = []
    pairs: dict[str, dict] = {}
    for t in txs:
        ls = by_tx.get(t["id"], [])
        if not ls:
            continue
        berat = round(sum(x["berat"] for x in ls), 3)
        grup = t["grup_tukar_tambah"]
        if grup and grup in pairs:  # sisi kedua dari tukar tambah yang sama
            row = pairs[grup]
            if t["tipe"] == "jual":
                row.update(id=t["id"], desc=_desc("jual", ls) + row["desc"], berat=berat, nilai=t["total"] - row["nilai"])
            else:
                row.update(desc=row["desc"] + f" · tukar emas {ls[0]['kadar']}", nilai=row["nilai"] - t["total"])
            row["batal"] = row["batal"] or t["status"] == "batal"
            row["kembali"] = row["nilai"] < 0
            continue
        base = {
            "id": t["id"], "jam": t["tanggal"][11:16], "pihak": t["pihak"], "batal": t["status"] == "batal",
            "berat": berat, "nilai": t["total"], "kembali": False,
        }
        if grup:
            # sisi pertama yang ditemui (id terbesar = pembelian); nilai sementara = total sisi ini
            base.update(kind="tukar", label="Tukar", desc="" if t["tipe"] == "jual" else f" · tukar emas {ls[0]['kadar']}")
            if t["tipe"] == "jual":
                base["desc"] = _desc("jual", ls)
            pairs[grup] = base
        else:
            base.update(
                kind="jual" if t["tipe"] == "jual" else "beli",
                label="Jual" if t["tipe"] == "jual" else ("Beli" if t["tipe"] == "beli_pelanggan" else "Supplier"),
                desc=_desc(t["tipe"], ls),
            )
        rows.append(base)
    return rows[:limit]
