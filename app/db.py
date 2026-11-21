from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('pemilik','kasir'))
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    jenis TEXT NOT NULL,
    kadar TEXT NOT NULL,
    berat REAL NOT NULL,
    ongkos INTEGER NOT NULL DEFAULT 0,
    foto TEXT,
    status TEXT NOT NULL DEFAULT 'tersedia' CHECK (status IN ('tersedia','terjual','nonaktif')),
    created_by_tx INTEGER
);
CREATE TABLE IF NOT EXISTS daily_prices (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    kadar TEXT NOT NULL,
    harga_jual INTEGER NOT NULL,
    harga_beli INTEGER NOT NULL,
    UNIQUE (tanggal, kadar)
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    tipe TEXT NOT NULL CHECK (tipe IN ('jual','beli_pelanggan','beli_supplier')),
    tanggal TEXT NOT NULL,
    pihak TEXT NOT NULL DEFAULT '',
    total INTEGER NOT NULL,
    kasir_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'aktif' CHECK (status IN ('aktif','batal')),
    alasan_batal TEXT,
    grup_tukar_tambah TEXT,
    metode TEXT NOT NULL DEFAULT 'Tunai' CHECK (metode IN ('Tunai','Transfer','QRIS'))
);
CREATE TABLE IF NOT EXISTS transaction_lines (
    id INTEGER PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    item_id INTEGER REFERENCES items(id),
    kadar TEXT NOT NULL,
    berat REAL NOT NULL,
    harga_per_gram INTEGER NOT NULL,
    ongkos INTEGER NOT NULL DEFAULT 0,
    subtotal INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cart_items (
    user_id INTEGER NOT NULL REFERENCES users(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    added TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    waktu TEXT NOT NULL,
    user_id INTEGER,
    aksi TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_takes (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL,
    mulai TEXT NOT NULL,
    selesai TEXT,
    status TEXT NOT NULL DEFAULT 'berjalan' CHECK (status IN ('berjalan','selesai')),
    dibuat_oleh INTEGER REFERENCES users(id),
    catatan TEXT NOT NULL DEFAULT '',
    laporan_beku TEXT
);
CREATE TABLE IF NOT EXISTS stock_take_items (
    take_id INTEGER NOT NULL REFERENCES stock_takes(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    found_at TEXT,
    found_by INTEGER,
    PRIMARY KEY (take_id, item_id)
);
CREATE TABLE IF NOT EXISTS stock_take_scans (
    id INTEGER PRIMARY KEY,
    take_id INTEGER NOT NULL REFERENCES stock_takes(id),
    waktu TEXT NOT NULL,
    user_id INTEGER,
    kode TEXT NOT NULL,
    item_id INTEGER,
    hasil TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_tanggal ON transactions(tanggal);
CREATE INDEX IF NOT EXISTS idx_lines_tx ON transaction_lines(transaction_id);
CREATE INDEX IF NOT EXISTS idx_lines_item ON transaction_lines(item_id);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Perbarui database lama yang dibuat sebelum kolom baru ada."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
    if "metode" not in cols:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN metode TEXT NOT NULL DEFAULT 'Tunai' "
            "CHECK (metode IN ('Tunai','Transfer','QRIS'))"
        )


def init_db(path: Path | str) -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection):
    """Satu transaksi database: semua tersimpan atau tidak sama sekali."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
