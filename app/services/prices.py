from ..db import tx
from ..validation import normalize_kadar
from . import audit


class PriceMissing(ValueError):
    pass


def set_price(conn, user_id, tanggal: str, kadar: str, harga_jual: int, harga_beli: int) -> None:
    kadar = normalize_kadar(kadar)
    harga_jual, harga_beli = int(harga_jual), int(harga_beli)
    if harga_jual <= 0 or harga_beli <= 0:
        raise ValueError("Harga harus lebih dari 0")
    with tx(conn):
        old = conn.execute(
            "SELECT harga_jual, harga_beli FROM daily_prices WHERE tanggal=? AND kadar=?", (tanggal, kadar)
        ).fetchone()
        conn.execute(
            "INSERT INTO daily_prices(tanggal, kadar, harga_jual, harga_beli) VALUES (?,?,?,?) "
            "ON CONFLICT(tanggal, kadar) DO UPDATE SET harga_jual=excluded.harga_jual, harga_beli=excluded.harga_beli",
            (tanggal, kadar, harga_jual, harga_beli),
        )
        audit.log(
            conn,
            user_id,
            "harga",
            {
                "tanggal": tanggal,
                "kadar": kadar,
                "lama": [old["harga_jual"], old["harga_beli"]] if old else None,
                "baru": [harga_jual, harga_beli],
            },
        )


def get_prices(conn, tanggal: str) -> dict:
    rows = conn.execute(
        "SELECT kadar, harga_jual, harga_beli FROM daily_prices WHERE tanggal=?", (tanggal,)
    ).fetchall()
    return {r["kadar"]: {"jual": r["harga_jual"], "beli": r["harga_beli"]} for r in rows}


def require_price(conn, tanggal: str, kadar: str):
    row = conn.execute(
        "SELECT * FROM daily_prices WHERE tanggal=? AND kadar=?", (tanggal, kadar)
    ).fetchone()
    if row is None:
        raise PriceMissing(f"Harga harian {kadar} untuk {tanggal} belum diisi")
    return row


def latest_prices(conn, tanggal: str) -> dict:
    """Harga terbaru per kadar pada atau sebelum `tanggal` (untuk mengisi awal form harga harian)."""
    rows = conn.execute(
        "SELECT kadar, harga_jual, harga_beli, tanggal FROM daily_prices WHERE tanggal<=? ORDER BY tanggal DESC",
        (tanggal,),
    ).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r["kadar"], {"jual": r["harga_jual"], "beli": r["harga_beli"], "tanggal": r["tanggal"]})
    return out

