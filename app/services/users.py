import sqlite3

from ..security import hash_password, verify_password

ROLES = ("pemilik", "kasir")


def _check_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("Kata sandi minimal 6 karakter")


def create_user(conn, username: str, password: str, role: str) -> int:
    username = (username or "").strip()
    if not username:
        raise ValueError("Nama pengguna wajib diisi")
    _check_password(password)
    if role not in ROLES:
        raise ValueError("Peran tidak valid")
    try:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, role) VALUES (?,?,?)",
            (username, hash_password(password), role),
        )
    except sqlite3.IntegrityError:
        raise ValueError("Nama pengguna sudah dipakai") from None
    return cur.lastrowid


def authenticate(conn, username: str, password: str):
    row = conn.execute(
        "SELECT id, username, role, password_hash FROM users WHERE username=?", ((username or "").strip(),)
    ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return row


def count_users(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_users(conn):
    return conn.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()


def set_password(conn, user_id: int, password: str) -> None:
    _check_password(password)
    cur = conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), user_id))
    if cur.rowcount == 0:
        raise ValueError("Pengguna tidak ditemukan")
