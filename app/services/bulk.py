"""Pembuatan banyak perhiasan sekaligus (kode unik otomatis berdasarkan jenis, gramasi, dan jumlah pcs)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import JENIS
from ..db import tx
from ..validation import normalize_kadar
from . import audit
from .items import NewItem, create_item

KODE_JENIS = {"Cincin": "CIN", "Kalung": "KAL", "Gelang": "GEL", "Anting": "ANT", "Liontin": "LIO", "Lainnya": "LNY"}
MAKS_PER_BARIS = 200
MAKS_TOTAL = 500
MAKS_BARIS = 30
_AWALAN = re.compile(r"^[A-Z0-9]{0,6}$")


@dataclass
class BatchRow:
    jenis: str
    kadar: str
    berat: float
    pcs: int
    nama: str = ""
    ongkos: int = 0


def kode_berat(berat: float) -> str:
    """3.5 -> '3G5', 10 -> '10G', 0.8 -> '0G8' (G menggantikan titik desimal)."""
    bulat, _, pecah = f"{float(berat):.3f}".partition(".")
    pecah = pecah.rstrip("0")
    return f"{int(bulat)}G{pecah}"


def _gram_teks(berat: float) -> str:
    bulat, _, pecah = f"{float(berat):.3f}".partition(".")
    pecah = pecah.rstrip("0")
    return bulat + ("," + pecah if pecah else "")


def _cek(rows: list[BatchRow], awalan: str) -> tuple[str, list[BatchRow]]:
    awalan = (awalan or "").strip().upper()
    if not _AWALAN.match(awalan):
        raise ValueError("Awalan kode hanya huruf/angka, maksimal 6 karakter")
    if not rows:
        raise ValueError("Isi minimal satu baris perhiasan")
    if len(rows) > MAKS_BARIS:
        raise ValueError(f"Maksimal {MAKS_BARIS} baris sekali buat")
    bersih, total = [], 0
    for n, r in enumerate(rows, start=1):
        if r.jenis not in JENIS:
            raise ValueError(f"Baris {n}: Jenis tidak valid")
        try:
            pcs = int(r.pcs)
        except (TypeError, ValueError):
            raise ValueError(f"Baris {n}: Jumlah pcs harus berupa angka") from None
        if not 1 <= pcs <= MAKS_PER_BARIS:
            raise ValueError(f"Baris {n}: Jumlah pcs harus 1 sampai {MAKS_PER_BARIS}")
        try:
            berat = round(float(r.berat), 3)
        except (TypeError, ValueError):
            raise ValueError(f"Baris {n}: Berat harus berupa angka") from None
        if berat <= 0:
            raise ValueError(f"Baris {n}: Berat harus lebih dari 0")
        try:
            kadar = normalize_kadar(r.kadar)
        except ValueError:
            raise ValueError(f"Baris {n}: Kadar tidak valid (contoh 22K)") from None
        ongkos = int(r.ongkos or 0)
        if ongkos < 0:
            raise ValueError(f"Baris {n}: Ongkos tidak boleh negatif")
        total += pcs
        bersih.append(BatchRow(r.jenis, kadar, berat, pcs, (r.nama or "").strip(), ongkos))
    if total > MAKS_TOTAL:
        raise ValueError(f"Total maksimal {MAKS_TOTAL} pcs sekali buat (sekarang {total})")
    return awalan, bersih


def _stem(awalan: str, jenis: str, berat: float) -> str:
    return "-".join(p for p in (awalan, KODE_JENIS[jenis], kode_berat(berat)) if p)


def _seq_terakhir(conn, stem: str) -> int:
    best = 0
    for (code,) in conn.execute("SELECT code FROM items WHERE code GLOB ?", (stem + "-[0-9]*",)):
        akhir = code[len(stem) + 1:]
        if akhir.isdigit():
            best = max(best, int(akhir))
    return best


def rencana_kode(conn, rows: list[BatchRow], awalan: str = "") -> list[dict]:
    """Daftar kode yang AKAN dibuat, per baris. Dipakai pratinjau dan pembuatan agar hasilnya selalu sama."""
    awalan, rows = _cek(rows, awalan)
    seq: dict[str, int] = {}
    hasil = []
    for r in rows:
        stem = _stem(awalan, r.jenis, r.berat)
        if stem not in seq:
            seq[stem] = _seq_terakhir(conn, stem)
        for _ in range(r.pcs):
            seq[stem] += 1
            hasil.append({"kode": f"{stem}-{seq[stem]:03d}", "baris": r})
    return hasil


def buat_massal(conn, rows: list[BatchRow], user_id, awalan: str = "") -> list[int]:
    """Buat semua perhiasan dalam satu transaksi: semua tersimpan atau tidak sama sekali."""
    with tx(conn):
        rencana = rencana_kode(conn, rows, awalan)
        ids = []
        for p in rencana:
            r: BatchRow = p["baris"]
            nama = r.nama or f"{r.jenis} {_gram_teks(r.berat)} g"
            ids.append(create_item(conn, NewItem(nama, r.jenis, r.kadar, r.berat, r.ongkos, None, p["kode"])))
        audit.log(conn, user_id, "buat_massal", {"jumlah": len(ids), "awal": rencana[0]["kode"], "akhir": rencana[-1]["kode"]})
    return ids
