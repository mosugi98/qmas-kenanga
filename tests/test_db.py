import pytest

from app.db import tx


def test_init_membuat_tabel(conn):
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "items", "daily_prices", "transactions", "transaction_lines", "audit_log"} <= names


def test_tx_commit(conn):
    with tx(conn):
        conn.execute("INSERT INTO users(username,password_hash,role) VALUES('a','x','kasir')")
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_tx_rollback_saat_error(conn):
    with pytest.raises(RuntimeError):
        with tx(conn):
            conn.execute("INSERT INTO users(username,password_hash,role) VALUES('a','x','kasir')")
            raise RuntimeError("gagal")
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_peran_tidak_valid_ditolak(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users(username,password_hash,role) VALUES('a','x','admin')")


def test_migrasi_menambah_kolom_metode(tmp_path):
    import sqlite3

    from app.db import init_db

    path = tmp_path / "lama.db"
    c = sqlite3.connect(path)
    c.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT);"
        "CREATE TABLE transactions (id INTEGER PRIMARY KEY, tipe TEXT NOT NULL, tanggal TEXT NOT NULL, pihak TEXT NOT NULL DEFAULT '',"
        " total INTEGER NOT NULL, kasir_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'aktif', alasan_batal TEXT, grup_tukar_tambah TEXT);"
        "INSERT INTO transactions(tipe,tanggal,total,kasir_id) VALUES ('jual','2026-11-19 09:00:00',100,1);"
    )
    c.commit()
    c.close()
    init_db(path)
    init_db(path)  # aman dijalankan berulang
    c = sqlite3.connect(path)
    assert c.execute("SELECT metode FROM transactions").fetchone()[0] == "Tunai"
    assert c.execute("SELECT name FROM sqlite_master WHERE name='cart_items'").fetchone()
