from __future__ import annotations

from dataclasses import dataclass

from ..config import JENIS
from ..db import tx
import sqlite3

from ..validation import normalize_kadar, normalize_kode
from . import audit


@dataclass
class NewItem:
    name: str
    jenis: str
    kadar: str
    berat: float
    ongkos: int = 0
    foto: str | None = None
    code: str | None = None  # kosong = dibuat otomatis (GLD-000123)


class ItemNotAvailable(Exception):
    def __init__(self, code: str, tx_id: int | None = None):
        self.code = code
        self.tx_id = tx_id
        suffix = f" (transaksi #{tx_id})" if tx_id else ""
        super().__init__(f"{code} sudah tidak tersedia{suffix}")


def _clean(d: NewItem) -> NewItem:
    name = (d.name or "").strip()
    if not name:
        raise ValueError("Nama perhiasan wajib diisi")
    if d.jenis not in JENIS:
        raise ValueError("Jenis tidak valid")
    berat = float(d.berat)
    if berat <= 0:
        raise ValueError("Berat harus lebih dari 0")
    ongkos = int(d.ongkos)
    if ongkos < 0:
        raise ValueError("Ongkos tidak boleh negatif")
    kode = normalize_kode(d.code) if (d.code or "").strip() else None
    return NewItem(name, d.jenis, normalize_kadar(d.kadar), berat, ongkos, d.foto, kode)


def next_code(conn) -> str:
    n = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(code, 5) AS INTEGER)), 0) + 1 FROM items "
        "WHERE code GLOB 'GLD-[0-9][0-9][0-9][0-9][0-9][0-9]*'"
    ).fetchone()[0]
    return f"GLD-{n:06d}"


def pastikan_kode_unik(conn, kode: str, abaikan_id: int | None = None) -> None:
    row = conn.execute("SELECT id, name FROM items WHERE code=?", (kode,)).fetchone()
    if row is not None and row["id"] != abaikan_id:
        raise ValueError(f"Kode {kode} sudah dipakai oleh {row['name']}")


def create_item(conn, data: NewItem, created_by_tx: int | None = None) -> int:
    """Pemanggil harus sudah berada di dalam `tx(conn)`."""
    d = _clean(data)
    kode = d.code or next_code(conn)
    pastikan_kode_unik(conn, kode)
    try:
        cur = conn.execute(
            "INSERT INTO items(code, name, jenis, kadar, berat, ongkos, foto, created_by_tx) VALUES (?,?,?,?,?,?,?,?)",
            (kode, d.name, d.jenis, d.kadar, d.berat, d.ongkos, d.foto, created_by_tx),
        )
    except sqlite3.IntegrityError:
        raise ValueError(f"Kode {kode} sudah dipakai") from None
    return cur.lastrowid


def add_item(conn, data: NewItem, user_id) -> int:
    with tx(conn):
        item_id = create_item(conn, data)
        audit.log(conn, user_id, "item_baru", {"id": item_id})
    return item_id


def update_item(conn, item_id: int, data: NewItem, user_id) -> None:
    with tx(conn):
        row = conn.execute("SELECT status, foto, code FROM items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("Perhiasan tidak ditemukan")
        if row["status"] == "terjual":
            raise ValueError("Perhiasan yang sudah terjual tidak bisa diubah")
        d = _clean(data)
        kode = d.code or row["code"]
        if kode != row["code"]:
            pastikan_kode_unik(conn, kode, item_id)
        conn.execute(
            "UPDATE items SET code=?, name=?, jenis=?, kadar=?, berat=?, ongkos=?, foto=? WHERE id=?",
            (kode, d.name, d.jenis, d.kadar, d.berat, d.ongkos, d.foto or row["foto"], item_id),
        )
        detail = {"id": item_id}
        if kode != row["code"]:
            detail.update(kode_lama=row["code"], kode_baru=kode)
        audit.log(conn, user_id, "item_ubah", detail)


def get_item(conn, item_id: int):
    return conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()


def get_by_code(conn, code: str):
    return conn.execute("SELECT * FROM items WHERE code=?", ((code or "").strip().upper(),)).fetchone()


def search(conn, q: str = "", jenis: str = "", kadar: str = "", status: str = ""):
    sql, args = "SELECT * FROM items WHERE 1=1", []
    if q:
        sql += " AND (code LIKE ? OR name LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if jenis:
        sql += " AND jenis=?"
        args.append(jenis)
    if kadar:
        sql += " AND kadar=?"
        args.append(kadar.strip().upper())
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT 200"
    return conn.execute(sql, args).fetchall()


def item_payload(item, harga_jual: int | None) -> dict:
    """Bentuk JSON perhiasan untuk keranjang kasir (sama dengan hasil pencarian kode)."""
    return {
        "id": item["id"], "code": item["code"], "name": item["name"], "jenis": item["jenis"],
        "kadar": item["kadar"], "berat": item["berat"], "ongkos": item["ongkos"], "status": "tersedia",
        "foto_url": f"/foto/{item['foto']}" if item["foto"] else None,
        "harga_jual": harga_jual,
    }
