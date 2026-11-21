"""Opname stok dengan scanner: mencocokkan stok awal, barang terjual, dan barang tersisa untuk mendeteksi kehilangan.

Cara kerja:
- mulai(): mengambil "foto" stok awal = semua perhiasan berstatus tersedia saat itu.
- scan(): tiap perhiasan yang discan ditandai ditemukan. Scan ganda, kode asing, dan barang yang
  tercatat terjual tetapi masih ada fisiknya dicatat sebagai temuan.
- laporan(): tiap barang stok awal masuk tepat satu kelompok:
    terjual   : status sekarang terjual (sesuai catatan penjualan)
    nonaktif  : dinonaktifkan (mis. pembelian dibatalkan)
    cocok     : ditemukan lewat scan dan masih tersedia
    hilang    : tidak ditemukan dan masih tercatat tersedia
- selesai(): membekukan laporan sehingga penjualan berikutnya tidak mengubah hasil opname itu.
"""
from __future__ import annotations

import json

from ..db import tx
from ..timeutil import now_str
from . import audit
from .items import get_by_code


def _aktif(conn):
    return conn.execute("SELECT * FROM stock_takes WHERE status='berjalan' ORDER BY id DESC LIMIT 1").fetchone()


def aktif(conn):
    return _aktif(conn)


def mulai(conn, user_id, nama: str) -> int:
    nama = (nama or "").strip()[:80] or f"Opname {now_str()[:10]}"
    with tx(conn):
        jalan = _aktif(conn)
        if jalan is not None:
            raise ValueError(f"Masih ada opname berjalan: {jalan['nama']}. Selesaikan dulu.")
        cur = conn.execute("INSERT INTO stock_takes(nama, mulai, dibuat_oleh) VALUES (?,?,?)", (nama, now_str(), user_id))
        take = cur.lastrowid
        conn.execute(
            "INSERT INTO stock_take_items(take_id, item_id) SELECT ?, id FROM items WHERE status='tersedia'", (take,)
        )
        n = conn.execute("SELECT COUNT(*) FROM stock_take_items WHERE take_id=?", (take,)).fetchone()[0]
        audit.log(conn, user_id, "opname_mulai", {"id": take, "nama": nama, "stok_awal": n})
    return take


def _take(conn, take_id: int):
    t = conn.execute("SELECT * FROM stock_takes WHERE id=?", (take_id,)).fetchone()
    if t is None:
        raise LookupError("Opname tidak ditemukan")
    return t


def _grup(rows) -> dict:
    return {"pcs": len(rows), "gram": round(sum(float(r["berat"]) for r in rows), 3)}


def _hitung(conn, take_id: int) -> dict:
    rows = conn.execute(
        "SELECT s.found_at, i.id AS item_id, i.code, i.name, i.jenis, i.kadar, i.berat, i.status "
        "FROM stock_take_items s JOIN items i ON i.id=s.item_id WHERE s.take_id=? ORDER BY i.code",
        (take_id,),
    ).fetchall()
    kel = {"terjual": [], "nonaktif": [], "cocok": [], "hilang": []}
    for r in rows:
        if r["status"] == "terjual":
            kel["terjual"].append(r)
        elif r["status"] == "nonaktif":
            kel["nonaktif"].append(r)
        elif r["found_at"]:
            kel["cocok"].append(r)
        else:
            kel["hilang"].append(r)

    def daftar(rs, tambah=None):
        out = []
        for r in rs:
            d = {k: r[k] for k in ("code", "name", "jenis", "kadar", "berat")}
            d["ditemukan"] = r["found_at"]
            if tambah:
                d.update(tambah(r))
            out.append(d)
        return out

    def nota(r):
        t = conn.execute(
            "SELECT t.id, t.tanggal, t.pihak FROM transaction_lines l JOIN transactions t ON t.id=l.transaction_id "
            "WHERE l.item_id=? AND t.tipe='jual' AND t.status='aktif' ORDER BY t.id DESC LIMIT 1", (r["item_id"],)
        ).fetchone()
        return {"nota": t["id"], "tanggal": t["tanggal"], "pihak": t["pihak"]} if t else {"nota": None, "tanggal": None, "pihak": ""}

    scans = conn.execute(
        "SELECT hasil, kode, item_id, MIN(waktu) AS waktu FROM stock_take_scans WHERE take_id=? "
        "AND hasil IN ('tidak_dikenal','terjual_ada','nonaktif_ada','baru_masuk') GROUP BY hasil, kode ORDER BY MIN(id)",
        (take_id,),
    ).fetchall()
    baru = [dict(s) for s in scans if s["hasil"] == "baru_masuk"]
    temuan = [dict(s) for s in scans if s["hasil"] != "baru_masuk"]
    baru_rows = conn.execute(
        "SELECT i.berat FROM items i WHERE i.id IN (SELECT item_id FROM stock_take_scans WHERE take_id=? AND hasil='baru_masuk')",
        (take_id,),
    ).fetchall()
    lap = {
        "awal": _grup(rows),
        "terjual": {**_grup(kel["terjual"]), "daftar": daftar(kel["terjual"], nota)},
        "nonaktif": {**_grup(kel["nonaktif"]), "daftar": daftar(kel["nonaktif"])},
        "cocok": {**_grup(kel["cocok"]), "daftar": daftar(kel["cocok"])},
        "hilang": {**_grup(kel["hilang"]), "daftar": daftar(kel["hilang"])},
        "baru_masuk": {**_grup(baru_rows), "kode": [b["kode"] for b in baru]},
        "temuan": temuan,
    }
    lap["selisih_pcs"] = lap["hilang"]["pcs"]
    lap["selisih_gram"] = lap["hilang"]["gram"]
    return lap


def laporan(conn, take_id: int) -> dict:
    t = _take(conn, take_id)
    if t["status"] == "selesai" and t["laporan_beku"]:
        lap = json.loads(t["laporan_beku"])
    else:
        lap = _hitung(conn, take_id)
    lap.update(id=t["id"], nama=t["nama"], mulai=t["mulai"], selesai=t["selesai"], status=t["status"], catatan=t["catatan"])
    return lap


def _ringkas(lap: dict) -> dict:
    return {k: {"pcs": lap[k]["pcs"], "gram": lap[k]["gram"]} for k in ("awal", "terjual", "nonaktif", "cocok", "hilang", "baru_masuk")}


def scan(conn, take_id: int, user_id, kode: str) -> dict:
    kode = (kode or "").strip().upper()
    if not kode:
        raise ValueError("Kode kosong")
    with tx(conn):
        t = _take(conn, take_id)
        if t["status"] != "berjalan":
            raise ValueError("Opname ini sudah selesai")
        item = get_by_code(conn, kode)
        item_id = item["id"] if item else None
        if item is None:
            hasil, pesan = "tidak_dikenal", f"Kode {kode} TIDAK TERDAFTAR di katalog"
        else:
            snap = conn.execute(
                "SELECT found_at FROM stock_take_items WHERE take_id=? AND item_id=?", (take_id, item["id"])
            ).fetchone()
            if snap is not None and snap["found_at"]:
                hasil, pesan = "duplikat", "Sudah discan sebelumnya"
            elif item["status"] == "terjual":
                hasil, pesan = "terjual_ada", "Tercatat TERJUAL tetapi barangnya ada. Periksa nota penjualan"
            elif item["status"] == "nonaktif":
                hasil, pesan = "nonaktif_ada", "Tercatat NONAKTIF tetapi barangnya ada. Periksa catatan"
            elif snap is None:
                hasil, pesan = "baru_masuk", "Barang baru (ditambahkan setelah opname dimulai)"
            else:
                conn.execute(
                    "UPDATE stock_take_items SET found_at=?, found_by=? WHERE take_id=? AND item_id=?",
                    (now_str(), user_id, take_id, item["id"]),
                )
                hasil, pesan = "cocok", "Cocok, barang ada"
        conn.execute(
            "INSERT INTO stock_take_scans(take_id, waktu, user_id, kode, item_id, hasil) VALUES (?,?,?,?,?,?)",
            (take_id, now_str(), user_id, kode, item_id, hasil),
        )
    lap = _hitung(conn, take_id)
    return {
        "hasil": hasil, "pesan": pesan, "kode": kode,
        "item": {k: item[k] for k in ("id", "code", "name", "jenis", "kadar", "berat", "status")} if item else None,
        "ringkasan": _ringkas(lap),
    }


def selesai(conn, take_id: int, user_id, catatan: str = "") -> None:
    with tx(conn):
        t = _take(conn, take_id)
        if t["status"] != "berjalan":
            raise ValueError("Opname ini sudah selesai")
        lap = _hitung(conn, take_id)
        conn.execute(
            "UPDATE stock_takes SET status='selesai', selesai=?, catatan=?, laporan_beku=? WHERE id=?",
            (now_str(), (catatan or "").strip()[:500], json.dumps(lap, ensure_ascii=False), take_id),
        )
        audit.log(conn, user_id, "opname_selesai", {"id": take_id, "hilang": lap["hilang"]["pcs"], "gram_hilang": lap["hilang"]["gram"]})


def daftar_opname(conn):
    return conn.execute(
        "SELECT s.*, u.username AS petugas, (SELECT COUNT(*) FROM stock_take_items i WHERE i.take_id=s.id) AS awal_pcs "
        "FROM stock_takes s LEFT JOIN users u ON u.id=s.dibuat_oleh ORDER BY s.id DESC LIMIT 100"
    ).fetchall()


def jejak(conn, kode: str):
    """Riwayat satu perhiasan: status, transaksi, dan hasil opname terakhir. None bila kode tidak ada."""
    item = get_by_code(conn, kode)
    if item is None:
        return None
    trx = conn.execute(
        "SELECT t.id, t.tipe, t.tanggal, t.pihak, t.status, u.username AS kasir, l.harga_per_gram, l.subtotal "
        "FROM transaction_lines l JOIN transactions t ON t.id=l.transaction_id JOIN users u ON u.id=t.kasir_id "
        "WHERE l.item_id=? ORDER BY t.id DESC",
        (item["id"],),
    ).fetchall()
    ops = conn.execute(
        "SELECT s.id, s.nama, s.mulai, i.found_at FROM stock_take_items i JOIN stock_takes s ON s.id=i.take_id "
        "WHERE i.item_id=? ORDER BY s.id DESC LIMIT 5",
        (item["id"],),
    ).fetchall()
    return {
        "item": {k: item[k] for k in ("id", "code", "name", "jenis", "kadar", "berat", "ongkos", "status")},
        "transaksi": [dict(r) for r in trx],
        "opname": [{"id": o["id"], "nama": o["nama"], "mulai": o["mulai"], "ditemukan": bool(o["found_at"])} for o in ops],
    }
