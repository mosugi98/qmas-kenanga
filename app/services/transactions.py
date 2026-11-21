from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..db import tx
from ..pricing import line_subtotal
from ..timeutil import now_str
from ..validation import normalize_kadar
from . import audit
from .items import ItemNotAvailable, NewItem, create_item

TIPE = ("jual", "beli_pelanggan", "beli_supplier")
METODE = ("Tunai", "Transfer", "QRIS")


class TransactionError(ValueError):
    pass


class CannotCancel(TransactionError):
    pass


@dataclass
class LineIn:
    kadar: str = ""
    berat: float = 0
    harga_per_gram: int = 0
    ongkos: int = 0
    item_id: int | None = None
    nama: str | None = None
    jenis: str | None = None


@dataclass
class TukarTambahResult:
    jual_id: int
    beli_id: int
    total_jual: int
    total_beli: int
    selisih: int


def _last_tx_for_item(conn, item_id: int):
    row = conn.execute(
        "SELECT transaction_id FROM transaction_lines WHERE item_id=? ORDER BY id DESC LIMIT 1", (item_id,)
    ).fetchone()
    return row[0] if row else None


def _insert_transaction(conn, tipe, kasir_id, pihak, lines, tanggal, grup=None, metode="Tunai") -> int:
    """Pemanggil harus sudah berada di dalam `tx(conn)`."""
    if tipe not in TIPE:
        raise TransactionError("Tipe transaksi tidak dikenal")
    if metode not in METODE:
        raise TransactionError("Metode pembayaran tidak dikenal")
    if not lines:
        raise TransactionError("Transaksi harus punya minimal satu baris")
    cur = conn.execute(
        "INSERT INTO transactions(tipe, tanggal, pihak, total, kasir_id, grup_tukar_tambah, metode) VALUES (?,?,?,?,?,?,?)",
        (tipe, tanggal, (pihak or "").strip(), 0, kasir_id, grup, metode),
    )
    tx_id = cur.lastrowid
    total = 0
    for ln in lines:
        item_id = None
        if ln.item_id is not None:
            if tipe != "jual":
                raise TransactionError("Hanya penjualan yang boleh memilih perhiasan yang sudah ada")
            item = conn.execute("SELECT * FROM items WHERE id=?", (ln.item_id,)).fetchone()
            if item is None:
                raise TransactionError("Perhiasan tidak ditemukan")
            if item["status"] != "tersedia":
                raise ItemNotAvailable(item["code"], _last_tx_for_item(conn, item["id"]))
            conn.execute("UPDATE items SET status='terjual' WHERE id=?", (item["id"],))
            conn.execute("DELETE FROM cart_items WHERE item_id=?", (item["id"],))
            item_id, kadar, berat = item["id"], item["kadar"], float(item["berat"])
        else:
            kadar = normalize_kadar(ln.kadar)
            berat = float(ln.berat)
            if berat <= 0:
                raise TransactionError("Berat harus lebih dari 0")
            if ln.nama:
                if tipe == "jual":
                    raise TransactionError("Penjualan tidak boleh membuat perhiasan baru")
                item_id = create_item(
                    conn, NewItem(ln.nama, ln.jenis or "Lainnya", kadar, berat, 0), created_by_tx=tx_id
                )
        harga, ongkos = int(ln.harga_per_gram), int(ln.ongkos)
        if harga <= 0:
            raise TransactionError("Harga per gram harus lebih dari 0")
        if ongkos < 0:
            raise TransactionError("Ongkos tidak boleh negatif")
        subtotal = line_subtotal(berat, harga, ongkos)
        conn.execute(
            "INSERT INTO transaction_lines(transaction_id, item_id, kadar, berat, harga_per_gram, ongkos, subtotal) "
            "VALUES (?,?,?,?,?,?,?)",
            (tx_id, item_id, kadar, berat, harga, ongkos, subtotal),
        )
        total += subtotal
    conn.execute("UPDATE transactions SET total=? WHERE id=?", (total, tx_id))
    return tx_id


def create_transaction(conn, tipe, kasir_id, pihak, lines, tanggal=None, metode="Tunai") -> int:
    tanggal = tanggal or now_str()
    with tx(conn):
        tx_id = _insert_transaction(conn, tipe, kasir_id, pihak, lines, tanggal, metode=metode)
        audit.log(conn, kasir_id, "transaksi", {"id": tx_id, "tipe": tipe})
    return tx_id


def create_tukar_tambah(conn, kasir_id, pihak, jual_lines, beli_lines, tanggal=None, metode="Tunai") -> TukarTambahResult:
    tanggal = tanggal or now_str()
    grup = uuid.uuid4().hex
    with tx(conn):
        jual_id = _insert_transaction(conn, "jual", kasir_id, pihak, jual_lines, tanggal, grup, metode)
        beli_id = _insert_transaction(conn, "beli_pelanggan", kasir_id, pihak, beli_lines, tanggal, grup, metode)
        total_jual = conn.execute("SELECT total FROM transactions WHERE id=?", (jual_id,)).fetchone()[0]
        total_beli = conn.execute("SELECT total FROM transactions WHERE id=?", (beli_id,)).fetchone()[0]
        audit.log(conn, kasir_id, "tukar_tambah", {"jual": jual_id, "beli": beli_id, "grup": grup})
    return TukarTambahResult(jual_id, beli_id, total_jual, total_beli, total_jual - total_beli)


def cancel_transaction(conn, tx_id: int, user_id, alasan: str) -> None:
    alasan = (alasan or "").strip()
    if not alasan:
        raise TransactionError("Alasan pembatalan wajib diisi")
    with tx(conn):
        t = conn.execute("SELECT tipe, status FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if t is None:
            raise TransactionError("Transaksi tidak ditemukan")
        if t["status"] != "aktif":
            raise TransactionError("Transaksi sudah dibatalkan")
        if t["tipe"] == "jual":
            conn.execute(
                "UPDATE items SET status='tersedia' WHERE status='terjual' AND id IN "
                "(SELECT item_id FROM transaction_lines WHERE transaction_id=? AND item_id IS NOT NULL)",
                (tx_id,),
            )
        else:
            sold = [
                r[0]
                for r in conn.execute(
                    "SELECT code FROM items WHERE created_by_tx=? AND status='terjual' ORDER BY id", (tx_id,)
                )
            ]
            if sold:
                raise CannotCancel(f"Perhiasan {', '.join(sold)} sudah terjual; batalkan penjualannya dulu")
            conn.execute("UPDATE items SET status='nonaktif' WHERE created_by_tx=?", (tx_id,))
        conn.execute("UPDATE transactions SET status='batal', alasan_batal=? WHERE id=?", (alasan, tx_id))
        audit.log(conn, user_id, "batal", {"id": tx_id, "alasan": alasan})


def list_transactions(conn, start: str, end: str, tipe: str = ""):
    sql = (
        "SELECT t.*, u.username AS kasir FROM transactions t JOIN users u ON u.id=t.kasir_id "
        "WHERE date(t.tanggal) BETWEEN ? AND ?"
    )
    args = [start, end]
    if tipe:
        sql += " AND t.tipe=?"
        args.append(tipe)
    return conn.execute(sql + " ORDER BY t.id DESC LIMIT 500", args).fetchall()


def get_transaction(conn, tx_id: int):
    t = conn.execute(
        "SELECT t.*, u.username AS kasir FROM transactions t JOIN users u ON u.id=t.kasir_id WHERE t.id=?",
        (tx_id,),
    ).fetchone()
    if t is None:
        return None
    lines = conn.execute(
        "SELECT l.*, i.code AS code, i.name AS nama, i.created_by_tx AS created_by_tx, i.id AS iid "
        "FROM transaction_lines l LEFT JOIN items i ON i.id=l.item_id WHERE l.transaction_id=? ORDER BY l.id",
        (tx_id,),
    ).fetchall()
    pair = None
    if t["grup_tukar_tambah"]:
        pair = conn.execute(
            "SELECT id, tipe FROM transactions WHERE grup_tukar_tambah=? AND id!=?", (t["grup_tukar_tambah"], tx_id)
        ).fetchone()
    return {"t": t, "lines": lines, "pair": pair}
