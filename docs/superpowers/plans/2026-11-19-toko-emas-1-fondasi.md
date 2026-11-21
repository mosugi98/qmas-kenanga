# Toko Emas — Rencana 1: Fondasi dan Logika Inti

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun fondasi aplikasi toko emas: proyek Python, database, login dua peran, harga harian, katalog perhiasan (foto, kode unik, label QR/barcode), dan logika transaksi (jual, beli, tukar tambah, pembatalan) dengan API JSON yang teruji.

**Architecture:** Satu aplikasi FastAPI dengan SQLite (modul `sqlite3` bawaan, tanpa ORM). Logika bisnis ada di `app/services/*` sebagai fungsi murni yang menerima koneksi SQLite; route tipis hanya memanggil service. Halaman HTML dirender server (Jinja2), JavaScript hanya seperlunya. Setiap perubahan data dibungkus satu transaksi database (`BEGIN IMMEDIATE`).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, python-multipart, itsdangerous (sesi), qrcode, python-barcode, SQLite. Tes: pytest + httpx (TestClient).

**Rencana lanjutan:** `2026-11-19-toko-emas-2-layar-dan-rilis.md` (dashboard, scan, layar transaksi, pengguna/backup, HTTPS, `.exe`). Kerjakan rencana ini sampai tuntas lebih dulu.

## Global Constraints

Disalin dari spesifikasi `docs/superpowers/specs/2026-11-19-toko-emas-design.md`:

- Aplikasi web untuk satu toko, diakses lewat WiFi/LAN lokal; server di 1 PC Windows, 2–5 perangkat.
- Stack: Python (FastAPI) + SQLite + halaman web ringan, dibungkus `.exe` Windows.
- HTTPS pada port 8443.
- Data: satu file SQLite; foto di folder `foto/` di samping database.
- Jenis transaksi: `jual`, `beli_pelanggan`, `beli_supplier`. Tukar tambah = satu `jual` + satu `beli_pelanggan` dengan `grup_tukar_tambah` yang sama.
- Status transaksi: `aktif` / `batal`. Status perhiasan: `tersedia` / `terjual` / `nonaktif`.
- Peran: `pemilik` (semua fitur) dan `kasir` (scan, katalog, transaksi).
- Subtotal baris = berat × harga per gram + ongkos. Uang disimpan sebagai bilangan bulat rupiah.
- Total/gramasi dashboard hanya menghitung transaksi `aktif`. Transaksi tidak pernah dihapus, hanya dibatalkan dengan alasan.
- Stok emas curah tidak dilacak. Hanya perhiasan berkode yang punya status stok.
- Kode unik berformat `GLD-000123`; isi barcode/QR hanya kode, tanpa harga.
- Kata sandi disimpan dalam bentuk hash; sesi habis otomatis; pembatalan dan perubahan harga dicatat di log audit.
- Harga harian belum diisi → transaksi diblokir.
- Pembatalan transaksi beli ditolak jika perhiasan yang dibuatnya sudah terjual.

Keputusan yang melengkapi spesifikasi (dibuat saat menyusun rencana):

- Harga harian dianggap terisi jika ada baris `daily_prices` dengan tanggal transaksi yang sama persis dan kadar yang sama.
- Hanya pemilik yang boleh mengisi harga harian dan membatalkan transaksi.
- Perhiasan baru dari transaksi beli dibuat tanpa foto; foto ditambahkan lewat halaman ubah katalog.
- Pengguna pertama dibuat lewat halaman `/setup` (hanya aktif selama belum ada pengguna).

## Struktur File

```
toko-emas/
  requirements.txt            requirements-dev.txt     pytest.ini     .gitignore
  app/
    __init__.py
    config.py                 # Settings, daftar jenis & kadar
    db.py                     # skema, connect(), init_db(), tx()
    security.py               # hash_password / verify_password
    timeutil.py               # now_str(), today()
    validation.py             # normalize_kadar()
    pricing.py                # line_subtotal()
    auth.py                   # get_db, current_user, require_user, require_owner
    web.py                    # templates + render()
    main.py                   # create_app()
    services/
      __init__.py
      audit.py  users.py  prices.py  items.py  photos.py  labels.py  transactions.py
    routes/
      __init__.py
      auth_routes.py  dashboard_routes.py  prices_routes.py  items_routes.py  transactions_routes.py
    templates/  base.html setup.html login.html home.html harga.html katalog.html item_form.html label.html
    static/     app.css
  tests/
    __init__.py  conftest.py  helpers.py
    test_security.py test_db.py test_validation.py test_auth.py test_prices.py
    test_items.py test_pricing.py test_transactions.py test_transactions_api.py
```

---

### Task 1: Kerangka proyek, database, keamanan dasar

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`
- Create: `app/__init__.py`, `app/config.py`, `app/db.py`, `app/security.py`, `app/timeutil.py`, `app/validation.py`, `app/services/__init__.py`, `app/routes/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_security.py`, `tests/test_db.py`, `tests/test_validation.py`

**Interfaces:**
- Produces:
  - `app.config.Settings(data_dir: Path, https_only: bool = True)` dengan properti `db_path`, `photo_dir`, `backup_dir`, `cert_dir`, `secret_file`, dan metode `ensure_dirs()`; `load_settings() -> Settings`; konstanta `JENIS`, `KADAR_UMUM`, `PORT`.
  - `app.db.connect(path) -> sqlite3.Connection` (row_factory `Row`, autocommit, foreign keys ON); `init_db(path)`; `tx(conn)` (context manager `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`).
  - `app.security.hash_password(str) -> str`, `verify_password(str, str) -> bool`.
  - `app.timeutil.now_str() -> "YYYY-MM-DD HH:MM:SS"`, `today() -> "YYYY-MM-DD"`.
  - `app.validation.normalize_kadar(str) -> str` (mis. `"22k"` → `"22K"`, `ValueError` jika tidak valid).
  - Fixture pytest `settings`, `conn`.

- [ ] **Step 1: Siapkan lingkungan dan file konfigurasi**

`requirements.txt`:
```
fastapi>=0.110
uvicorn>=0.29
jinja2>=3.1
python-multipart>=0.0.9
itsdangerous>=2.1
qrcode>=7.4
python-barcode>=0.15
cryptography>=42
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
httpx>=0.27
```

`pytest.ini`:
```
[pytest]
pythonpath = .
testpaths = tests
```

`.gitignore`:
```
__pycache__/
.pytest_cache/
.venv/
data/
build/
dist/
*.spec.bak
```

Jalankan (Windows: ganti baris aktivasi dengan `.venv\Scripts\activate`):
```bash
cd /home/claude/toko-emas
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
```
Expected: instalasi selesai tanpa error.

- [ ] **Step 2: Tulis tes yang gagal**

`tests/__init__.py` dan `app/__init__.py`, `app/services/__init__.py`, `app/routes/__init__.py`: file kosong.

`tests/conftest.py`:
```python
import pytest

from app.config import Settings
from app.db import connect, init_db


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def conn(settings):
    settings.ensure_dirs()
    init_db(settings.db_path)
    c = connect(settings.db_path)
    yield c
    c.close()
```

`tests/test_security.py`:
```python
from app.security import hash_password, verify_password


def test_hash_dan_verifikasi():
    h = hash_password("rahasia123")
    assert h != "rahasia123"
    assert verify_password("rahasia123", h)
    assert not verify_password("salah", h)


def test_hash_berbeda_tiap_kali():
    assert hash_password("abc123") != hash_password("abc123")


def test_format_rusak_ditolak():
    assert not verify_password("x", "bukan-hash")
```

`tests/test_db.py`:
```python
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
```

`tests/test_validation.py`:
```python
import pytest

from app.validation import normalize_kadar


@pytest.mark.parametrize("raw,expected", [("22k", "22K"), (" 24K ", "24K"), ("9K", "9K")])
def test_kadar_valid(raw, expected):
    assert normalize_kadar(raw) == expected


@pytest.mark.parametrize("raw", ["", "K", "abc", "22", "240K"])
def test_kadar_tidak_valid(raw):
    with pytest.raises(ValueError):
        normalize_kadar(raw)
```

- [ ] **Step 3: Jalankan tes, pastikan gagal**

Run: `pytest -q`
Expected: error `ModuleNotFoundError: No module named 'app.config'` (atau sejenisnya).

- [ ] **Step 4: Tulis implementasi**

`app/config.py`:
```python
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

JENIS = ["Cincin", "Kalung", "Gelang", "Anting", "Liontin", "Lainnya"]
KADAR_UMUM = ["24K", "22K", "18K", "16K", "9K"]
PORT = 8443


def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    https_only: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tokoemas.db"

    @property
    def photo_dir(self) -> Path:
        return self.data_dir / "foto"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backup"

    @property
    def cert_dir(self) -> Path:
        return self.data_dir / "cert"

    @property
    def secret_file(self) -> Path:
        return self.data_dir / "secret.key"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.photo_dir, self.backup_dir, self.cert_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    return Settings(data_dir=Path(os.environ.get("TOKOEMAS_DATA") or _default_data_dir()))
```

`app/db.py`:
```python
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
    grup_tukar_tambah TEXT
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
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    waktu TEXT NOT NULL,
    user_id INTEGER,
    aksi TEXT NOT NULL,
    detail TEXT NOT NULL
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


def init_db(path: Path | str) -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
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
```

`app/security.py`:
```python
import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P)
    except ValueError:
        return False
    return hmac.compare_digest(dk.hex(), dk_hex)
```

`app/timeutil.py`:
```python
from datetime import date, datetime


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return date.today().isoformat()
```

`app/validation.py`:
```python
import re

_KADAR = re.compile(r"^\d{1,2}K$")


def normalize_kadar(value: str) -> str:
    v = (value or "").strip().upper()
    if not _KADAR.match(v):
        raise ValueError("Kadar tidak valid (contoh: 24K, 22K, 18K)")
    return v
```

- [ ] **Step 5: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua tes lulus (`10 passed` atau lebih).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: kerangka proyek, skema database, hash kata sandi, validasi kadar"
```

---

### Task 2: Aplikasi FastAPI, login, setup pemilik pertama

**Files:**
- Create: `app/auth.py`, `app/web.py`, `app/main.py`, `app/services/audit.py`, `app/services/users.py`
- Create: `app/routes/auth_routes.py`, `app/routes/dashboard_routes.py`
- Create: `app/templates/base.html`, `setup.html`, `login.html`, `home.html`; `app/static/app.css`
- Modify: `tests/conftest.py` (tambah fixture)
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Settings`, `connect`, `init_db`, `verify_password`, `hash_password` dari Task 1.
- Produces:
  - `app.main.create_app(settings: Settings | None = None) -> FastAPI`
  - `app.auth`: `get_db(request)` (dependency, yield `sqlite3.Connection`), `current_user(...) -> Row | None`, `require_user(...) -> Row`, `require_owner(...) -> Row`, exception `NotLoggedIn`, `Forbidden`. Baris user punya kunci `id`, `username`, `role`.
  - `app.web.render(request, name, user, status_code=200, **ctx) -> TemplateResponse`; filter Jinja `rupiah` dan `gram`.
  - `app.services.users`: `create_user(conn, username, password, role) -> int` (`ValueError` jika tidak valid), `authenticate(conn, username, password) -> Row | None`, `count_users(conn) -> int`, `list_users(conn) -> list[Row]`, `set_password(conn, user_id, password)`.
  - `app.services.audit.log(conn, user_id, aksi, detail: dict)`.
  - Daftar router di `app/main.py`: `ROUTERS = [...]` (tugas berikutnya menambah isinya).
  - Fixture: `app`, `client`, `owner_client`, `kasir_client` (sudah login; HTTPS base_url).

- [ ] **Step 1: Tulis tes yang gagal**

Tambahkan ke akhir `tests/conftest.py`:
```python
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.users import create_user


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app, base_url="https://testserver")


def _login(client, username, password):
    r = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return client


@pytest.fixture
def owner_client(app, conn):
    create_user(conn, "pemilik1", "rahasia123", "pemilik")
    return _login(TestClient(app, base_url="https://testserver"), "pemilik1", "rahasia123")


@pytest.fixture
def kasir_client(app, conn):
    create_user(conn, "kasir1", "rahasia123", "kasir")
    return _login(TestClient(app, base_url="https://testserver"), "kasir1", "rahasia123")
```

`tests/test_auth.py`:
```python
from app.services.users import authenticate, count_users, create_user
import pytest


def test_create_dan_authenticate(conn):
    uid = create_user(conn, "budi", "rahasia123", "kasir")
    u = authenticate(conn, "budi", "rahasia123")
    assert u["id"] == uid and u["role"] == "kasir"
    assert authenticate(conn, "budi", "salah") is None
    assert authenticate(conn, "tidakada", "rahasia123") is None


def test_create_user_validasi(conn):
    with pytest.raises(ValueError):
        create_user(conn, "", "rahasia123", "kasir")
    with pytest.raises(ValueError):
        create_user(conn, "budi", "123", "kasir")
    with pytest.raises(ValueError):
        create_user(conn, "budi", "rahasia123", "admin")
    create_user(conn, "budi", "rahasia123", "kasir")
    with pytest.raises(ValueError):
        create_user(conn, "budi", "rahasia123", "kasir")
    assert count_users(conn) == 1


def test_belum_ada_pengguna_login_ke_setup(client):
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/setup"


def test_setup_membuat_pemilik_lalu_terkunci(client):
    r = client.post("/setup", data={"username": "bos", "password": "rahasia123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client.get("/").status_code == 200
    r2 = client.get("/setup", follow_redirects=False)
    assert r2.status_code == 303 and r2.headers["location"] == "/login"


def test_setup_kata_sandi_pendek_ditolak(client):
    r = client.post("/setup", data={"username": "bos", "password": "123"})
    assert r.status_code == 400 and "minimal" in r.text


def test_halaman_butuh_login(client, conn):
    create_user(conn, "bos", "rahasia123", "pemilik")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_login_salah_dan_benar(client, conn):
    create_user(conn, "bos", "rahasia123", "pemilik")
    r = client.post("/login", data={"username": "bos", "password": "salah"})
    assert r.status_code == 401 and "salah" in r.text
    r = client.post("/login", data={"username": "bos", "password": "rahasia123"}, follow_redirects=False)
    assert r.status_code == 303
    assert client.get("/").status_code == 200


def test_logout(owner_client):
    assert owner_client.post("/logout", follow_redirects=False).status_code == 303
    assert owner_client.get("/", follow_redirects=False).status_code == 303
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_auth.py -q`
Expected: gagal dengan `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Tulis implementasi**

`app/services/audit.py`:
```python
import json

from ..timeutil import now_str


def log(conn, user_id, aksi: str, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log(waktu, user_id, aksi, detail) VALUES (?,?,?,?)",
        (now_str(), user_id, aksi, json.dumps(detail, ensure_ascii=False)),
    )
```

`app/services/users.py`:
```python
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
```

`app/auth.py`:
```python
from fastapi import Depends, Request

from .db import connect


class NotLoggedIn(Exception):
    pass


class Forbidden(Exception):
    pass


def get_db(request: Request):
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def current_user(request: Request, db=Depends(get_db)):
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.execute("SELECT id, username, role FROM users WHERE id=?", (uid,)).fetchone()


def require_user(user=Depends(current_user)):
    if user is None:
        raise NotLoggedIn()
    return user


def require_owner(user=Depends(require_user)):
    if user["role"] != "pemilik":
        raise Forbidden()
    return user
```

`app/web.py`:
```python
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _rupiah(v) -> str:
    if v is None:
        return "—"
    return "Rp " + f"{int(v):,}".replace(",", ".")


def _gram(v) -> str:
    if v is None:
        return "—"
    return f"{float(v):.3f}".rstrip("0").rstrip(".") + " g"


templates.env.filters["rupiah"] = _rupiah
templates.env.filters["gram"] = _gram


def render(request: Request, name: str, user, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx}, status_code=status_code)
```

`app/main.py`:
```python
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import Forbidden, NotLoggedIn
from .config import Settings, load_settings
from .db import init_db
from .routes import auth_routes, dashboard_routes

BASE = Path(__file__).resolve().parent

ROUTERS = [auth_routes.router, dashboard_routes.router]


def _secret(settings: Settings) -> str:
    if settings.secret_file.exists():
        return settings.secret_file.read_text().strip()
    value = secrets.token_hex(32)
    settings.secret_file.write_text(value)
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)

    app = FastAPI(title="Toko Emas")
    app.state.settings = settings
    app.add_middleware(
        SessionMiddleware,
        secret_key=_secret(settings),
        max_age=8 * 3600,
        same_site="lax",
        https_only=settings.https_only,
    )
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.exception_handler(NotLoggedIn)
    async def _not_logged_in(request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Silakan login"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(Forbidden)
    async def _forbidden(request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Tidak diizinkan"}, status_code=403)
        return HTMLResponse("<h1>Tidak diizinkan</h1><a href='/'>Kembali</a>", status_code=403)

    for router in ROUTERS:
        app.include_router(router)
    return app
```

`app/routes/auth_routes.py`:
```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..auth import get_db
from ..services.users import authenticate, count_users, create_user
from ..web import render

router = APIRouter()


@router.get("/setup")
def setup_form(request: Request, db=Depends(get_db)):
    if count_users(db) > 0:
        return RedirectResponse("/login", status_code=303)
    return render(request, "setup.html", None)


@router.post("/setup")
def setup(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    if count_users(db) > 0:
        return RedirectResponse("/login", status_code=303)
    try:
        uid = create_user(db, username, password, "pemilik")
    except ValueError as e:
        return render(request, "setup.html", None, status_code=400, error=str(e))
    request.session["uid"] = uid
    return RedirectResponse("/", status_code=303)


@router.get("/login")
def login_form(request: Request, db=Depends(get_db)):
    if count_users(db) == 0:
        return RedirectResponse("/setup", status_code=303)
    return render(request, "login.html", None)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    user = authenticate(db, username, password)
    if user is None:
        return render(request, "login.html", None, status_code=401, error="Nama pengguna atau kata sandi salah")
    request.session["uid"] = user["id"]
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
```

`app/routes/dashboard_routes.py` (sementara; diganti penuh di Rencana 2, Task 6):
```python
from fastapi import APIRouter, Depends, Request

from ..auth import require_user
from ..web import render

router = APIRouter()


@router.get("/")
def home(request: Request, user=Depends(require_user)):
    return render(request, "home.html", user)
```

`app/templates/base.html`:
```html
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}Toko Emas{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
{% if user %}
<nav class="nav">
  <a href="/">Dashboard</a>
  <a href="/scan">Scan</a>
  <a href="/katalog">Katalog</a>
  <a href="/transaksi/baru">Transaksi</a>
  <a href="/transaksi">Riwayat</a>
  {% if user.role == 'pemilik' %}<a href="/harga">Harga</a><a href="/pengguna">Pengguna</a>{% endif %}
  <form method="post" action="/logout" class="inline"><button class="link">Keluar ({{ user.username }})</button></form>
</nav>
{% endif %}
<main>{% block content %}{% endblock %}</main>
{% block scripts %}{% endblock %}
</body>
</html>
```

`app/templates/setup.html`:
```html
{% extends "base.html" %}
{% block title %}Pengaturan awal{% endblock %}
{% block content %}
<h1>Pengaturan awal</h1>
<p>Buat akun pemilik pertama.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post" class="card">
  <p><label>Nama pengguna<br><input name="username" required autofocus></label></p>
  <p><label>Kata sandi (minimal 6 karakter)<br><input name="password" type="password" required></label></p>
  <p><button>Buat akun</button></p>
</form>
{% endblock %}
```

`app/templates/login.html`:
```html
{% extends "base.html" %}
{% block title %}Masuk{% endblock %}
{% block content %}
<h1>Masuk</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post" class="card">
  <p><label>Nama pengguna<br><input name="username" required autofocus></label></p>
  <p><label>Kata sandi<br><input name="password" type="password" required></label></p>
  <p><button>Masuk</button></p>
</form>
{% endblock %}
```

`app/templates/home.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>Dashboard</h1>
<p>Halo, {{ user.username }}.</p>
{% endblock %}
```

`app/static/app.css`:
```css
:root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e4e3df;--accent:#2a78d6;--danger:#c0392b;--s1:#2a78d6;--s2:#eb6834}
@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#33322f;--accent:#3987e5;--danger:#e66767;--s1:#3987e5;--s2:#d95926}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.4 system-ui,sans-serif;background:var(--surface);color:var(--ink)}
main{max-width:960px;margin:0 auto;padding:12px}
.nav{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}
.nav a{color:var(--ink);text-decoration:none;padding:6px 0}
form.inline{display:inline;margin-left:auto}
input,select,button,textarea{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);max-width:100%}
button{cursor:pointer;background:var(--accent);color:#fff;border-color:var(--accent)}
button.link{background:none;color:var(--ink);border:none}
button:disabled{opacity:.5;cursor:default}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:8px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}
.error{color:var(--danger)}
.muted{color:var(--ink2)}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.thumb{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px;background:var(--line);display:block}
@media print{.nav,.noprint{display:none}}
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: aplikasi FastAPI, login dua peran, setup pemilik pertama"
```

---

### Task 3: Harga harian

**Files:**
- Create: `app/services/prices.py`, `app/routes/prices_routes.py`, `app/templates/harga.html`
- Modify: `app/main.py` (daftarkan router), `tests/conftest.py` (fixture `owner_id`)
- Test: `tests/test_prices.py`

**Interfaces:**
- Consumes: `tx`, `normalize_kadar`, `audit.log`, `require_owner`, `require_user`, `get_db`, `render`, `today`, `KADAR_UMUM`.
- Produces:
  - `app.services.prices`: `class PriceMissing(ValueError)`; `set_price(conn, user_id, tanggal, kadar, harga_jual, harga_beli) -> None`; `get_prices(conn, tanggal) -> dict[str, {"jual": int, "beli": int}]`; `require_price(conn, tanggal: "YYYY-MM-DD", kadar) -> Row` (raise `PriceMissing`).
  - Route: `GET/POST /harga` (pemilik), `GET /api/harga` (login; `{"tanggal": str, "harga": {kadar: {"jual", "beli"}}}`).
  - Fixture `owner_id`.

- [ ] **Step 1: Tulis tes yang gagal**

Tambahkan ke `tests/conftest.py`:
```python
@pytest.fixture
def owner_id(conn):
    return create_user(conn, "pemilik0", "rahasia123", "pemilik")
```

`tests/test_prices.py`:
```python
import json

import pytest

from app.services.prices import PriceMissing, get_prices, require_price, set_price
from app.timeutil import today

TGL = "2026-11-19"


def test_set_price_baru_dan_ubah_tercatat_audit(conn, owner_id):
    set_price(conn, owner_id, TGL, "22k", 1_200_000, 1_100_000)
    assert get_prices(conn, TGL) == {"22K": {"jual": 1_200_000, "beli": 1_100_000}}
    set_price(conn, owner_id, TGL, "22K", 1_250_000, 1_150_000)
    assert get_prices(conn, TGL)["22K"]["jual"] == 1_250_000
    rows = conn.execute("SELECT detail FROM audit_log WHERE aksi='harga' ORDER BY id").fetchall()
    assert json.loads(rows[0]["detail"])["lama"] is None
    assert json.loads(rows[1]["detail"])["lama"] == [1_200_000, 1_100_000]


def test_harga_harus_positif(conn, owner_id):
    with pytest.raises(ValueError):
        set_price(conn, owner_id, TGL, "22K", 0, 1_100_000)


def test_require_price(conn, owner_id):
    with pytest.raises(PriceMissing) as e:
        require_price(conn, TGL, "22K")
    assert "22K" in str(e.value)
    set_price(conn, owner_id, TGL, "22K", 1, 1)
    assert require_price(conn, TGL, "22K")["harga_jual"] == 1


def test_kasir_tidak_boleh_buka_halaman_harga(kasir_client):
    assert kasir_client.get("/harga").status_code == 403


def test_pemilik_simpan_harga_dan_api(owner_client, kasir_client):
    r = owner_client.post(
        "/harga",
        data={"jual_24K": "1300000", "beli_24K": "1200000", "jual_22K": "", "beli_22K": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    api = kasir_client.get("/api/harga").json()
    assert api["tanggal"] == today()
    assert api["harga"]["24K"] == {"jual": 1_300_000, "beli": 1_200_000}
    assert "22K" not in api["harga"]


def test_harga_setengah_terisi_ditolak(owner_client):
    r = owner_client.post("/harga", data={"jual_24K": "1300000", "beli_24K": ""})
    assert r.status_code == 400 and "24K" in r.text
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_prices.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.services.prices'`.

- [ ] **Step 3: Tulis implementasi**

`app/services/prices.py`:
```python
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
```

`app/routes/prices_routes.py`:
```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from ..auth import get_db, require_owner, require_user
from ..config import KADAR_UMUM
from ..services.prices import get_prices, set_price
from ..timeutil import today
from ..web import render

router = APIRouter()


def _page(request, user, db, status_code=200, **extra):
    return render(
        request,
        "harga.html",
        user,
        status_code=status_code,
        tanggal=today(),
        prices=get_prices(db, today()),
        kadar_list=KADAR_UMUM,
        **extra,
    )


@router.get("/harga")
def harga(request: Request, saved: int = 0, user=Depends(require_owner), db=Depends(get_db)):
    return _page(request, user, db, saved=bool(saved))


@router.post("/harga")
async def harga_simpan(request: Request, user=Depends(require_owner), db=Depends(get_db)):
    form = await request.form()
    try:
        for k in KADAR_UMUM:
            jual = str(form.get(f"jual_{k}", "")).strip()
            beli = str(form.get(f"beli_{k}", "")).strip()
            if not jual and not beli:
                continue
            if not jual or not beli:
                raise ValueError(f"Isi harga jual dan harga beli untuk {k}")
            set_price(db, user["id"], today(), k, int(jual), int(beli))
    except ValueError as e:
        return _page(request, user, db, status_code=400, saved=False, error=str(e))
    return RedirectResponse("/harga?saved=1", status_code=303)


@router.get("/api/harga")
def api_harga(user=Depends(require_user), db=Depends(get_db)):
    return {"tanggal": today(), "harga": get_prices(db, today())}
```

`app/templates/harga.html`:
```html
{% extends "base.html" %}
{% block title %}Harga harian{% endblock %}
{% block content %}
<h1>Harga harian — {{ tanggal }}</h1>
{% if saved %}<p>Harga tersimpan.</p>{% endif %}
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post" action="/harga">
<table>
<tr><th>Kadar</th><th>Harga jual / gram (Rp)</th><th>Harga beli / gram (Rp)</th></tr>
{% for k in kadar_list %}
<tr>
  <td>{{ k }}</td>
  <td><input name="jual_{{ k }}" type="number" min="1" step="1" value="{{ prices.get(k, {}).get('jual', '') }}"></td>
  <td><input name="beli_{{ k }}" type="number" min="1" step="1" value="{{ prices.get(k, {}).get('beli', '') }}"></td>
</tr>
{% endfor %}
</table>
<p><button>Simpan</button></p>
</form>
{% endblock %}
```

Modifikasi `app/main.py`: ganti dua baris
```python
from .routes import auth_routes, dashboard_routes
```
```python
ROUTERS = [auth_routes.router, dashboard_routes.router]
```
menjadi
```python
from .routes import auth_routes, dashboard_routes, prices_routes
```
```python
ROUTERS = [auth_routes.router, dashboard_routes.router, prices_routes.router]
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: harga harian per kadar dengan audit"
```

---

### Task 4: Katalog perhiasan, foto, kode unik, label QR/barcode

**Files:**
- Create: `app/services/items.py`, `app/services/photos.py`, `app/services/labels.py`
- Create: `app/routes/items_routes.py`
- Create: `app/templates/katalog.html`, `item_form.html`, `label.html`
- Modify: `app/main.py` (daftarkan router)
- Test: `tests/helpers.py`, `tests/test_items.py`

**Interfaces:**
- Consumes: `tx`, `normalize_kadar`, `audit.log`, `JENIS`, `Settings.photo_dir`, `require_user`, `get_db`, `render`, `today`.
- Produces:
  - `app.services.items`: `@dataclass NewItem(name: str, jenis: str, kadar: str, berat: float, ongkos: int = 0, foto: str | None = None)`; `class ItemNotAvailable(Exception)` dengan atribut `code: str`, `tx_id: int | None`; `next_code(conn) -> str`; `create_item(conn, data: NewItem, created_by_tx: int | None = None) -> int` (**pemanggil sudah di dalam `tx`**); `add_item(conn, data, user_id) -> int`; `update_item(conn, item_id, data, user_id) -> None`; `get_item(conn, item_id) -> Row | None`; `get_by_code(conn, code) -> Row | None`; `search(conn, q="", jenis="", kadar="", status="") -> list[Row]`.
  - `app.services.photos.save_photo(settings, data: bytes) -> str` (nama file).
  - `app.services.labels`: `qr_svg(code) -> bytes`, `code128_svg(code) -> bytes`.
  - Route: `/katalog`, `/katalog/baru`, `/katalog/{id}/edit`, `/foto/{name}`, `/api/items/by-code/{code}` (JSON: `id, code, name, jenis, kadar, berat, ongkos, status, foto_url, harga_jual`), `/label/{id}`, `/kode/{code}/qr.svg`, `/kode/{code}/barcode.svg`.
  - `tests.helpers.make_item(conn, name="Cincin A", jenis="Cincin", kadar="22K", berat=2.5, ongkos=50_000) -> int`.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/helpers.py`:
```python
from app.db import tx
from app.services.items import NewItem, create_item


def make_item(conn, name="Cincin A", jenis="Cincin", kadar="22K", berat=2.5, ongkos=50_000) -> int:
    with tx(conn):
        return create_item(conn, NewItem(name, jenis, kadar, berat, ongkos))
```

`tests/test_items.py`:
```python
import pytest

from app.services.items import NewItem, add_item, get_by_code, get_item, next_code, search, update_item
from app.services.photos import save_photo
from tests.helpers import make_item

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def test_kode_berurutan(conn, owner_id):
    assert next_code(conn) == "GLD-000001"
    make_item(conn)
    make_item(conn, name="B")
    assert next_code(conn) == "GLD-000003"
    assert get_by_code(conn, "gld-000002")["name"] == "B"


def test_add_item_validasi(conn, owner_id):
    with pytest.raises(ValueError):
        add_item(conn, NewItem("", "Cincin", "22K", 2.0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Mobil", "22K", 2.0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Cincin", "22K", 0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Cincin", "xx", 1.0), owner_id)
    iid = add_item(conn, NewItem("A", "cincin".title(), "22k", 2.0, 10_000), owner_id)
    row = get_item(conn, iid)
    assert row["kadar"] == "22K" and row["status"] == "tersedia"


def test_update_item_dan_terjual_terkunci(conn, owner_id):
    iid = make_item(conn)
    update_item(conn, iid, NewItem("Baru", "Kalung", "24K", 3.0, 0), owner_id)
    assert get_item(conn, iid)["name"] == "Baru"
    conn.execute("UPDATE items SET status='terjual' WHERE id=?", (iid,))
    with pytest.raises(ValueError):
        update_item(conn, iid, NewItem("X", "Kalung", "24K", 3.0, 0), owner_id)


def test_update_item_foto_lama_dipertahankan(conn, owner_id):
    iid = add_item(conn, NewItem("A", "Cincin", "22K", 2.0, 0, foto="a.png"), owner_id)
    update_item(conn, iid, NewItem("A2", "Cincin", "22K", 2.0, 0, foto=None), owner_id)
    assert get_item(conn, iid)["foto"] == "a.png"


def test_search(conn):
    make_item(conn, name="Cincin Mawar")
    make_item(conn, name="Kalung Naga", jenis="Kalung", kadar="24K")
    assert [r["name"] for r in search(conn, q="mawar")] == ["Cincin Mawar"]
    assert [r["name"] for r in search(conn, jenis="Kalung")] == ["Kalung Naga"]
    assert [r["name"] for r in search(conn, kadar="24k")] == ["Kalung Naga"]
    assert len(search(conn)) == 2


def test_save_photo(settings):
    settings.ensure_dirs()
    name = save_photo(settings, PNG)
    assert name.endswith(".png") and (settings.photo_dir / name).read_bytes() == PNG
    with pytest.raises(ValueError):
        save_photo(settings, b"bukan gambar")
    with pytest.raises(ValueError):
        save_photo(settings, PNG + b"0" * (8 * 1024 * 1024))


def test_halaman_katalog_dan_tambah_item(kasir_client, conn):
    assert kasir_client.get("/katalog").status_code == 200
    assert kasir_client.get("/katalog/baru").status_code == 200
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Cincin Z", "jenis": "Cincin", "kadar": "22K", "berat": "2.5", "ongkos": "50000"},
        files={"foto": ("a.png", PNG, "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    row = get_by_code(conn, "GLD-000001")
    assert row["name"] == "Cincin Z" and row["foto"].endswith(".png")
    assert kasir_client.get(f"/foto/{row['foto']}").status_code == 200
    assert "Cincin Z" in kasir_client.get("/katalog").text


def test_tambah_item_tanpa_foto_dan_error(kasir_client, conn):
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Tanpa Foto", "jenis": "Cincin", "kadar": "22K", "berat": "1", "ongkos": "0"},
        files={"foto": ("", b"", "application/octet-stream")},
        follow_redirects=False,
    )
    assert r.status_code == 303 and get_by_code(conn, "GLD-000001")["foto"] is None
    r = kasir_client.post(
        "/katalog/baru", data={"name": "X", "jenis": "Cincin", "kadar": "salah", "berat": "1", "ongkos": "0"}
    )
    assert r.status_code == 400 and "Kadar tidak valid" in r.text


def test_edit_item_lewat_route(kasir_client, conn):
    iid = make_item(conn)
    assert kasir_client.get(f"/katalog/{iid}/edit").status_code == 200
    r = kasir_client.post(
        f"/katalog/{iid}/edit",
        data={"name": "Ganti", "jenis": "Gelang", "kadar": "18K", "berat": "4", "ongkos": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and get_item(conn, iid)["name"] == "Ganti"


def test_api_by_code(kasir_client, conn, owner_id):
    from app.services.prices import set_price
    from app.timeutil import today

    make_item(conn)
    r = kasir_client.get("/api/items/by-code/GLD-000001")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "GLD-000001" and body["status"] == "tersedia" and body["harga_jual"] is None
    set_price(conn, owner_id, today(), "22K", 1_200_000, 1_100_000)
    assert kasir_client.get("/api/items/by-code/gld-000001").json()["harga_jual"] == 1_200_000
    assert kasir_client.get("/api/items/by-code/GLD-999999").status_code == 404


def test_label_dan_svg(kasir_client, conn):
    iid = make_item(conn)
    assert "GLD-000001" in kasir_client.get(f"/label/{iid}").text
    for jenis in ("qr", "barcode"):
        r = kasir_client.get(f"/kode/GLD-000001/{jenis}.svg")
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in r.content
    assert kasir_client.get("/kode/ngawur/qr.svg").status_code == 404


def test_item_butuh_login(client, conn):
    assert client.get("/katalog", follow_redirects=False).status_code == 303
    assert client.get("/api/items/by-code/GLD-000001").status_code == 401
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_items.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.services.items'`.

- [ ] **Step 3: Tulis implementasi**

`app/services/items.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from ..config import JENIS
from ..db import tx
from ..validation import normalize_kadar
from . import audit


@dataclass
class NewItem:
    name: str
    jenis: str
    kadar: str
    berat: float
    ongkos: int = 0
    foto: str | None = None


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
    return NewItem(name, d.jenis, normalize_kadar(d.kadar), berat, ongkos, d.foto)


def next_code(conn) -> str:
    n = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(code, 5) AS INTEGER)), 0) + 1 FROM items"
    ).fetchone()[0]
    return f"GLD-{n:06d}"


def create_item(conn, data: NewItem, created_by_tx: int | None = None) -> int:
    """Pemanggil harus sudah berada di dalam `tx(conn)`."""
    d = _clean(data)
    cur = conn.execute(
        "INSERT INTO items(code, name, jenis, kadar, berat, ongkos, foto, created_by_tx) VALUES (?,?,?,?,?,?,?,?)",
        (next_code(conn), d.name, d.jenis, d.kadar, d.berat, d.ongkos, d.foto, created_by_tx),
    )
    return cur.lastrowid


def add_item(conn, data: NewItem, user_id) -> int:
    with tx(conn):
        item_id = create_item(conn, data)
        audit.log(conn, user_id, "item_baru", {"id": item_id})
    return item_id


def update_item(conn, item_id: int, data: NewItem, user_id) -> None:
    with tx(conn):
        row = conn.execute("SELECT status, foto FROM items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("Perhiasan tidak ditemukan")
        if row["status"] == "terjual":
            raise ValueError("Perhiasan yang sudah terjual tidak bisa diubah")
        d = _clean(data)
        conn.execute(
            "UPDATE items SET name=?, jenis=?, kadar=?, berat=?, ongkos=?, foto=? WHERE id=?",
            (d.name, d.jenis, d.kadar, d.berat, d.ongkos, d.foto or row["foto"], item_id),
        )
        audit.log(conn, user_id, "item_ubah", {"id": item_id})


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
```

`app/services/photos.py`:
```python
import uuid

MAX_BYTES = 8 * 1024 * 1024


def _ext(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_photo(settings, data: bytes) -> str:
    ext = _ext(data)
    if ext is None:
        raise ValueError("Foto harus berformat JPEG, PNG, atau WebP")
    if len(data) > MAX_BYTES:
        raise ValueError("Foto terlalu besar (maksimal 8 MB)")
    name = uuid.uuid4().hex + ext
    (settings.photo_dir / name).write_bytes(data)
    return name
```

`app/services/labels.py`:
```python
import io

import barcode
import qrcode
import qrcode.image.svg
from barcode.writer import SVGWriter


def qr_svg(code: str) -> bytes:
    img = qrcode.make(code, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def code128_svg(code: str) -> bytes:
    buf = io.BytesIO()
    barcode.get("code128", code, writer=SVGWriter()).write(
        buf, options={"write_text": False, "module_height": 8.0, "quiet_zone": 2.0}
    )
    return buf.getvalue()
```

`app/routes/items_routes.py`:
```python
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response

from ..auth import get_db, require_user
from ..config import JENIS
from ..services import labels
from ..services.items import NewItem, add_item, get_by_code, get_item, search, update_item
from ..services.photos import save_photo
from ..timeutil import today
from ..web import render

router = APIRouter()
CODE_RE = re.compile(r"^[A-Z]{3}-\d{6}$")


async def _upload_name(request: Request, foto: UploadFile | None):
    if foto is None or not foto.filename:
        return None
    return save_photo(request.app.state.settings, await foto.read())


def _form_page(request, user, item, f, error=None, status_code=200):
    return render(request, "item_form.html", user, status_code=status_code, item=item, f=f, JENIS=JENIS, error=error)


@router.get("/katalog")
def katalog(
    request: Request, q: str = "", jenis: str = "", kadar: str = "", status: str = "",
    user=Depends(require_user), db=Depends(get_db),
):
    return render(
        request, "katalog.html", user,
        items=search(db, q, jenis, kadar, status), q=q, jenis=jenis, kadar=kadar, status=status, JENIS=JENIS,
    )


@router.get("/katalog/baru")
def baru_form(request: Request, user=Depends(require_user)):
    return _form_page(request, user, None, {"name": "", "jenis": "Cincin", "kadar": "22K", "berat": "", "ongkos": 0})


@router.post("/katalog/baru")
async def baru(
    request: Request, name: str = Form(...), jenis: str = Form(...), kadar: str = Form(...),
    berat: float = Form(...), ongkos: int = Form(0), foto: UploadFile | None = File(None),
    user=Depends(require_user), db=Depends(get_db),
):
    f = {"name": name, "jenis": jenis, "kadar": kadar, "berat": berat, "ongkos": ongkos}
    try:
        add_item(db, NewItem(name, jenis, kadar, berat, ongkos, await _upload_name(request, foto)), user["id"])
    except ValueError as e:
        return _form_page(request, user, None, f, str(e), 400)
    return RedirectResponse("/katalog", status_code=303)


@router.get("/katalog/{item_id}/edit")
def edit_form(item_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    return _form_page(request, user, item, dict(item))


@router.post("/katalog/{item_id}/edit")
async def edit(
    item_id: int, request: Request, name: str = Form(...), jenis: str = Form(...), kadar: str = Form(...),
    berat: float = Form(...), ongkos: int = Form(0), foto: UploadFile | None = File(None),
    user=Depends(require_user), db=Depends(get_db),
):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    f = {"name": name, "jenis": jenis, "kadar": kadar, "berat": berat, "ongkos": ongkos}
    try:
        update_item(db, item_id, NewItem(name, jenis, kadar, berat, ongkos, await _upload_name(request, foto)), user["id"])
    except ValueError as e:
        return _form_page(request, user, item, f, str(e), 400)
    return RedirectResponse("/katalog", status_code=303)


@router.get("/foto/{name}")
def foto_file(name: str, request: Request, user=Depends(require_user)):
    path = request.app.state.settings.photo_dir / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "Foto tidak ditemukan")
    return FileResponse(path)


@router.get("/api/items/by-code/{code}")
def by_code(code: str, user=Depends(require_user), db=Depends(get_db)):
    item = get_by_code(db, code)
    if item is None:
        raise HTTPException(404, "Kode tidak terdaftar")
    price = db.execute(
        "SELECT harga_jual FROM daily_prices WHERE tanggal=? AND kadar=?", (today(), item["kadar"])
    ).fetchone()
    return {
        "id": item["id"], "code": item["code"], "name": item["name"], "jenis": item["jenis"],
        "kadar": item["kadar"], "berat": item["berat"], "ongkos": item["ongkos"], "status": item["status"],
        "foto_url": f"/foto/{item['foto']}" if item["foto"] else None,
        "harga_jual": price["harga_jual"] if price else None,
    }


@router.get("/label/{item_id}")
def label(item_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    return render(request, "label.html", user, item=item)


def _check_code(code: str) -> str:
    if not CODE_RE.match(code):
        raise HTTPException(404, "Kode tidak valid")
    return code


@router.get("/kode/{code}/qr.svg")
def qr(code: str, user=Depends(require_user)):
    return Response(labels.qr_svg(_check_code(code)), media_type="image/svg+xml")


@router.get("/kode/{code}/barcode.svg")
def barcode_svg(code: str, user=Depends(require_user)):
    return Response(labels.code128_svg(_check_code(code)), media_type="image/svg+xml")
```

`app/templates/katalog.html`:
```html
{% extends "base.html" %}
{% block title %}Katalog{% endblock %}
{% block content %}
<h1>Katalog perhiasan</h1>
<form class="row" method="get">
  <input name="q" value="{{ q }}" placeholder="Cari kode / nama">
  <select name="jenis"><option value="">Semua jenis</option>{% for j in JENIS %}<option {{ 'selected' if j == jenis }}>{{ j }}</option>{% endfor %}</select>
  <input name="kadar" value="{{ kadar }}" placeholder="Kadar (22K)" size="8">
  <select name="status"><option value="">Semua status</option>{% for s in ['tersedia','terjual','nonaktif'] %}<option {{ 'selected' if s == status }}>{{ s }}</option>{% endfor %}</select>
  <button>Cari</button>
  <a href="/katalog/baru">+ Perhiasan baru</a>
</form>
<div class="grid">
{% for it in items %}
  <div class="card">
    {% if it.foto %}<img class="thumb" src="/foto/{{ it.foto }}" alt="{{ it.name }}">{% else %}<div class="thumb"></div>{% endif %}
    <b>{{ it.code }}</b><br>{{ it.name }} · {{ it.jenis }}<br>
    {{ it.kadar }} · {{ it.berat|gram }} · {{ it.status }}<br>
    <a href="/katalog/{{ it.id }}/edit">Ubah</a> · <a href="/label/{{ it.id }}">Label</a>
  </div>
{% else %}
  <p class="muted">Belum ada perhiasan.</p>
{% endfor %}
</div>
{% endblock %}
```

`app/templates/item_form.html`:
```html
{% extends "base.html" %}
{% block title %}{{ 'Ubah perhiasan' if item else 'Perhiasan baru' }}{% endblock %}
{% block content %}
<h1>{{ ('Ubah ' ~ item.code) if item else 'Perhiasan baru' }}</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post" enctype="multipart/form-data" class="card">
  <p><label>Nama<br><input name="name" required value="{{ f.name }}"></label></p>
  <p><label>Jenis<br><select name="jenis">{% for j in JENIS %}<option {{ 'selected' if j == f.jenis }}>{{ j }}</option>{% endfor %}</select></label></p>
  <p><label>Kadar<br><input name="kadar" required placeholder="22K" value="{{ f.kadar }}"></label></p>
  <p><label>Berat (gram)<br><input name="berat" type="number" step="0.001" min="0.001" required value="{{ f.berat }}"></label></p>
  <p><label>Ongkos (Rp)<br><input name="ongkos" type="number" step="1" min="0" value="{{ f.ongkos }}"></label></p>
  <p><label>Foto<br><input name="foto" type="file" accept="image/*"></label></p>
  {% if item and item.foto %}<img class="thumb" style="max-width:200px" src="/foto/{{ item.foto }}" alt="">{% endif %}
  <p><button>Simpan</button> <a href="/katalog">Batal</a></p>
</form>
{% endblock %}
```

`app/templates/label.html`:
```html
{% extends "base.html" %}
{% block title %}Label {{ item.code }}{% endblock %}
{% block content %}
<div class="card" style="width:260px;text-align:center">
  <img src="/kode/{{ item.code }}/qr.svg" alt="QR" width="120">
  <img src="/kode/{{ item.code }}/barcode.svg" alt="Barcode" style="width:100%">
  <div><b>{{ item.code }}</b></div>
  <div>{{ item.kadar }} · {{ item.berat|gram }}</div>
</div>
<p class="noprint"><button onclick="window.print()">Cetak</button> <a href="/katalog">Kembali</a></p>
{% endblock %}
```

Modifikasi `app/main.py`: ganti
```python
from .routes import auth_routes, dashboard_routes, prices_routes
```
```python
ROUTERS = [auth_routes.router, dashboard_routes.router, prices_routes.router]
```
menjadi
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes
```
```python
ROUTERS = [auth_routes.router, dashboard_routes.router, prices_routes.router, items_routes.router]
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus. Jika `test_label_dan_svg` gagal karena keluaran library barcode (bukan logika aplikasi), cetak `r.content[:200]` dan sesuaikan `code128_svg` agar menghasilkan SVG berisi `<svg`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: katalog perhiasan, foto, kode unik, label QR dan barcode"
```

---

### Task 5: Logika transaksi (jual, beli, tukar tambah, pembatalan) dan API

**Files:**
- Create: `app/pricing.py`, `app/services/transactions.py`, `app/routes/transactions_routes.py`
- Modify: `app/main.py` (daftarkan router), `tests/conftest.py` (fixture `kasir_id`, `prices`)
- Test: `tests/test_pricing.py`, `tests/test_transactions.py`, `tests/test_transactions_api.py`

**Interfaces:**
- Consumes: `tx`, `normalize_kadar`, `audit.log`, `prices.require_price`, `items.create_item`/`NewItem`/`ItemNotAvailable`, `require_user`, `get_db`, `now_str`.
- Produces:
  - `app.pricing.line_subtotal(berat: float, harga_per_gram: int, ongkos: int = 0) -> int` (pembulatan setengah ke atas pada hasil berat × harga).
  - `app.services.transactions`: `TIPE`; `class TransactionError(ValueError)`; `class CannotCancel(TransactionError)`; `@dataclass LineIn(kadar: str = "", berat: float = 0, harga_per_gram: int = 0, ongkos: int = 0, item_id: int | None = None, nama: str | None = None, jenis: str | None = None)`; `create_transaction(conn, tipe, kasir_id, pihak, lines, tanggal=None) -> int`; `@dataclass TukarTambahResult(jual_id, beli_id, total_jual, total_beli, selisih)`; `create_tukar_tambah(conn, kasir_id, pihak, jual_lines, beli_lines, tanggal=None) -> TukarTambahResult`; `cancel_transaction(conn, tx_id, user_id, alasan) -> None`.
  - Aturan `LineIn`: pada `jual` dengan `item_id`, kadar/berat diambil dari perhiasan (nilai input diabaikan); tanpa `item_id` = emas curah. Pada `beli_*`, `item_id` ditolak; isi `nama` (dan `jenis`, default `"Lainnya"`) untuk membuat perhiasan baru berstatus `tersedia`; tanpa `nama` = emas curah. `tanggal` berformat `"YYYY-MM-DD HH:MM:SS"`; harga harian dicek untuk 10 karakter pertamanya.
  - API: `POST /api/transaksi` body `{"tipe", "pihak", "lines": [...]}` → `{"id"}`; `POST /api/transaksi/tukar-tambah` body `{"pihak", "jual_lines", "beli_lines"}` → `{"jual_id", "beli_id", "total_jual", "total_beli", "selisih"}`. Galat: 409 (perhiasan tidak tersedia), 400 (lainnya), 401 (belum login).
  - Fixture `kasir_id`, `prices` (harga 2026-11-19: 24K 1.300.000/1.200.000, 22K 1.200.000/1.100.000, 18K 1.000.000/900.000 — jual/beli).

- [ ] **Step 1: Tulis tes yang gagal**

Tambahkan ke `tests/conftest.py`:
```python
@pytest.fixture
def kasir_id(conn):
    return create_user(conn, "kasir0", "rahasia123", "kasir")


@pytest.fixture
def prices(conn):
    for kadar, jual, beli in (("24K", 1_300_000, 1_200_000), ("22K", 1_200_000, 1_100_000), ("18K", 1_000_000, 900_000)):
        conn.execute(
            "INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES ('2026-11-19',?,?,?)",
            (kadar, jual, beli),
        )
```

`tests/test_pricing.py`:
```python
from app.pricing import line_subtotal


def test_subtotal_dasar():
    assert line_subtotal(2.5, 1_200_000, 50_000) == 3_050_000


def test_subtotal_tanpa_ongkos():
    assert line_subtotal(10, 1_200_000) == 12_000_000


def test_pembulatan_setengah_ke_atas():
    assert line_subtotal(0.0005, 1000) == 1
    assert line_subtotal(0.0004, 1000) == 0
```

`tests/test_transactions.py`:
```python
import pytest

from app.services.items import ItemNotAvailable, get_item
from app.services.prices import PriceMissing
from app.services.transactions import (
    CannotCancel, LineIn, TransactionError, cancel_transaction, create_transaction, create_tukar_tambah,
)
from tests.helpers import make_item

TGL = "2026-11-19 10:00:00"


def _count(conn, table="transactions"):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _status(conn, item_id):
    return get_item(conn, item_id)["status"]


def _jual(conn, kasir_id, item_id, harga=1_200_000, ongkos=50_000):
    return create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item_id, harga_per_gram=harga, ongkos=ongkos)], TGL)


def test_jual_menandai_terjual_dan_menghitung_total(conn, prices, kasir_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item)
    t = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    assert t["total"] == 3_050_000 and t["status"] == "aktif" and t["pihak"] == "Budi"
    assert _status(conn, item) == "terjual"
    line = conn.execute("SELECT * FROM transaction_lines WHERE transaction_id=?", (tid,)).fetchone()
    assert line["berat"] == 2.5 and line["kadar"] == "22K" and line["subtotal"] == 3_050_000


def test_jual_harga_boleh_diubah_kasir(conn, prices, kasir_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item, harga=1_100_000, ongkos=0)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 2_750_000


def test_jual_item_sama_dua_kali_ditolak_dan_rollback(conn, prices, kasir_id):
    item = make_item(conn)
    _jual(conn, kasir_id, item)
    with pytest.raises(ItemNotAvailable) as e:
        _jual(conn, kasir_id, item)
    assert e.value.code == "GLD-000001" and e.value.tx_id == 1
    assert _count(conn) == 1 and _count(conn, "transaction_lines") == 1


def test_item_sama_dua_baris_dalam_satu_transaksi_ditolak(conn, prices, kasir_id):
    item = make_item(conn)
    lines = [LineIn(item_id=item, harga_per_gram=1_200_000), LineIn(item_id=item, harga_per_gram=1_200_000)]
    with pytest.raises(ItemNotAvailable):
        create_transaction(conn, "jual", kasir_id, "", lines, TGL)
    assert _status(conn, item) == "tersedia" and _count(conn) == 0


def test_harga_harian_belum_diisi_memblokir(conn, kasir_id):
    item = make_item(conn)
    with pytest.raises(PriceMissing):
        _jual(conn, kasir_id, item)
    assert _count(conn) == 0 and _status(conn, item) == "tersedia"


def test_harga_nol_ditolak(conn, prices, kasir_id):
    item = make_item(conn)
    with pytest.raises(TransactionError):
        _jual(conn, kasir_id, item, harga=0)


def test_transaksi_kosong_ditolak(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "jual", kasir_id, "", [], TGL)


def test_tipe_tidak_dikenal(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "hibah", kasir_id, "", [LineIn(kadar="22K", berat=1, harga_per_gram=1)], TGL)


def test_beli_supplier_membuat_perhiasan_baru(conn, prices, kasir_id):
    lines = [LineIn(kadar="24K", berat=10, harga_per_gram=1_200_000, nama="Kalung Naga", jenis="Kalung")]
    tid = create_transaction(conn, "beli_supplier", kasir_id, "PT Emas", lines, TGL)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 12_000_000
    item = conn.execute("SELECT * FROM items").fetchone()
    assert item["code"] == "GLD-000001" and item["status"] == "tersedia"
    assert item["created_by_tx"] == tid and item["kadar"] == "24K" and item["berat"] == 10


def test_beli_pelanggan_emas_curah(conn, prices, kasir_id):
    tid = create_transaction(conn, "beli_pelanggan", kasir_id, "Ani", [LineIn(kadar="18K", berat=3.2, harga_per_gram=900_000)], TGL)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 2_880_000
    assert _count(conn, "items") == 0
    assert conn.execute("SELECT item_id FROM transaction_lines").fetchone()[0] is None


def test_beli_tidak_boleh_pilih_perhiasan_ada(conn, prices, kasir_id):
    item = make_item(conn)
    with pytest.raises(TransactionError):
        create_transaction(conn, "beli_pelanggan", kasir_id, "", [LineIn(item_id=item, harga_per_gram=900_000)], TGL)


def test_jual_tidak_boleh_buat_perhiasan_baru(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "jual", kasir_id, "", [LineIn(kadar="22K", berat=1, harga_per_gram=1, nama="X")], TGL)


def test_tukar_tambah(conn, prices, kasir_id):
    item = make_item(conn)
    res = create_tukar_tambah(
        conn, kasir_id, "Budi",
        jual_lines=[LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)],
        beli_lines=[LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
        tanggal=TGL,
    )
    assert (res.total_jual, res.total_beli, res.selisih) == (3_050_000, 2_750_000, 300_000)
    rows = conn.execute("SELECT * FROM transactions ORDER BY id").fetchall()
    assert [r["tipe"] for r in rows] == ["jual", "beli_pelanggan"]
    assert rows[0]["grup_tukar_tambah"] == rows[1]["grup_tukar_tambah"] is not None
    assert (rows[0]["id"], rows[1]["id"]) == (res.jual_id, res.beli_id)


def test_tukar_tambah_gagal_membatalkan_semuanya(conn, prices, kasir_id):
    item = make_item(conn)
    _jual(conn, kasir_id, item)
    with pytest.raises(ItemNotAvailable):
        create_tukar_tambah(
            conn, kasir_id, "Budi",
            jual_lines=[LineIn(item_id=item, harga_per_gram=1_200_000)],
            beli_lines=[LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
            tanggal=TGL,
        )
    assert _count(conn) == 1


def test_batal_jual_mengembalikan_perhiasan(conn, prices, kasir_id, owner_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item)
    cancel_transaction(conn, tid, owner_id, "salah input")
    t = conn.execute("SELECT status, alasan_batal FROM transactions WHERE id=?", (tid,)).fetchone()
    assert (t["status"], t["alasan_batal"]) == ("batal", "salah input")
    assert _status(conn, item) == "tersedia"
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE aksi='batal'").fetchone()[0] == 1


def test_batal_wajib_alasan_dan_tidak_dua_kali(conn, prices, kasir_id, owner_id):
    tid = _jual(conn, kasir_id, make_item(conn))
    with pytest.raises(TransactionError):
        cancel_transaction(conn, tid, owner_id, "  ")
    cancel_transaction(conn, tid, owner_id, "x")
    with pytest.raises(TransactionError):
        cancel_transaction(conn, tid, owner_id, "x")
    with pytest.raises(TransactionError):
        cancel_transaction(conn, 999, owner_id, "x")


def test_batal_beli_ditolak_jika_perhiasan_terjual(conn, prices, kasir_id, owner_id):
    beli = create_transaction(
        conn, "beli_supplier", kasir_id, "PT",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin", jenis="Cincin")], TGL,
    )
    item = conn.execute("SELECT id FROM items").fetchone()[0]
    jual = _jual(conn, kasir_id, item)
    with pytest.raises(CannotCancel) as e:
        cancel_transaction(conn, beli, owner_id, "salah")
    assert "GLD-000001" in str(e.value)
    cancel_transaction(conn, jual, owner_id, "batal jual")
    cancel_transaction(conn, beli, owner_id, "batal beli")
    assert _status(conn, item) == "nonaktif"
```

`tests/test_transactions_api.py`:
```python
from app.timeutil import today
from tests.helpers import make_item


def _harga_hari_ini(conn):
    conn.execute("INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)", (today(), "22K", 1_200_000, 1_100_000))


def test_api_butuh_login(client, conn):
    assert client.post("/api/transaksi", json={"tipe": "jual", "lines": []}).status_code == 401


def test_api_jual_lalu_konflik(kasir_client, conn):
    _harga_hari_ini(conn)
    item = make_item(conn)
    body = {"tipe": "jual", "pihak": "Budi", "lines": [{"item_id": item, "harga_per_gram": 1_200_000, "ongkos": 50_000}]}
    r = kasir_client.post("/api/transaksi", json=body)
    assert r.status_code == 200 and isinstance(r.json()["id"], int)
    r2 = kasir_client.post("/api/transaksi", json=body)
    assert r2.status_code == 409 and "GLD-000001" in r2.json()["detail"]


def test_api_harga_belum_diisi(kasir_client, conn):
    item = make_item(conn)
    body = {"tipe": "jual", "lines": [{"item_id": item, "harga_per_gram": 1_200_000}]}
    r = kasir_client.post("/api/transaksi", json=body)
    assert r.status_code == 400 and "belum diisi" in r.json()["detail"]


def test_api_beli_curah(kasir_client, conn):
    _harga_hari_ini(conn)
    body = {"tipe": "beli_pelanggan", "pihak": "Ani", "lines": [{"kadar": "22K", "berat": 2, "harga_per_gram": 1_100_000}]}
    assert kasir_client.post("/api/transaksi", json=body).status_code == 200


def test_api_tukar_tambah(kasir_client, conn):
    _harga_hari_ini(conn)
    item = make_item(conn)
    body = {
        "pihak": "Budi",
        "jual_lines": [{"item_id": item, "harga_per_gram": 1_200_000, "ongkos": 50_000}],
        "beli_lines": [{"kadar": "22K", "berat": 2.5, "harga_per_gram": 1_100_000}],
    }
    r = kasir_client.post("/api/transaksi/tukar-tambah", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["selisih"] == 300_000 and data["jual_id"] != data["beli_id"]
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_pricing.py tests/test_transactions.py tests/test_transactions_api.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.pricing'`.

- [ ] **Step 3: Tulis implementasi**

`app/pricing.py`:
```python
from decimal import ROUND_HALF_UP, Decimal


def line_subtotal(berat: float, harga_per_gram: int, ongkos: int = 0) -> int:
    emas = (Decimal(str(berat)) * Decimal(int(harga_per_gram))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(emas) + int(ongkos)
```

`app/services/transactions.py`:
```python
from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..db import tx
from ..pricing import line_subtotal
from ..timeutil import now_str
from ..validation import normalize_kadar
from . import audit, prices
from .items import ItemNotAvailable, NewItem, create_item

TIPE = ("jual", "beli_pelanggan", "beli_supplier")


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


def _insert_transaction(conn, tipe, kasir_id, pihak, lines, tanggal, grup=None) -> int:
    """Pemanggil harus sudah berada di dalam `tx(conn)`."""
    if tipe not in TIPE:
        raise TransactionError("Tipe transaksi tidak dikenal")
    if not lines:
        raise TransactionError("Transaksi harus punya minimal satu baris")
    cur = conn.execute(
        "INSERT INTO transactions(tipe, tanggal, pihak, total, kasir_id, grup_tukar_tambah) VALUES (?,?,?,?,?,?)",
        (tipe, tanggal, (pihak or "").strip(), 0, kasir_id, grup),
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
        prices.require_price(conn, tanggal[:10], kadar)
        subtotal = line_subtotal(berat, harga, ongkos)
        conn.execute(
            "INSERT INTO transaction_lines(transaction_id, item_id, kadar, berat, harga_per_gram, ongkos, subtotal) "
            "VALUES (?,?,?,?,?,?,?)",
            (tx_id, item_id, kadar, berat, harga, ongkos, subtotal),
        )
        total += subtotal
    conn.execute("UPDATE transactions SET total=? WHERE id=?", (total, tx_id))
    return tx_id


def create_transaction(conn, tipe, kasir_id, pihak, lines, tanggal=None) -> int:
    tanggal = tanggal or now_str()
    with tx(conn):
        tx_id = _insert_transaction(conn, tipe, kasir_id, pihak, lines, tanggal)
        audit.log(conn, kasir_id, "transaksi", {"id": tx_id, "tipe": tipe})
    return tx_id


def create_tukar_tambah(conn, kasir_id, pihak, jual_lines, beli_lines, tanggal=None) -> TukarTambahResult:
    tanggal = tanggal or now_str()
    grup = uuid.uuid4().hex
    with tx(conn):
        jual_id = _insert_transaction(conn, "jual", kasir_id, pihak, jual_lines, tanggal, grup)
        beli_id = _insert_transaction(conn, "beli_pelanggan", kasir_id, pihak, beli_lines, tanggal, grup)
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
```

`app/routes/transactions_routes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_db, require_user
from ..services.items import ItemNotAvailable
from ..services.transactions import LineIn, create_transaction, create_tukar_tambah

router = APIRouter()


class LineBody(BaseModel):
    kadar: str = ""
    berat: float = 0
    harga_per_gram: int
    ongkos: int = 0
    item_id: int | None = None
    nama: str | None = None
    jenis: str | None = None


class TransaksiBody(BaseModel):
    tipe: str
    pihak: str = ""
    lines: list[LineBody]


class TukarTambahBody(BaseModel):
    pihak: str = ""
    jual_lines: list[LineBody]
    beli_lines: list[LineBody]


def _lines(items: list[LineBody]) -> list[LineIn]:
    return [LineIn(**i.model_dump()) for i in items]


@router.post("/api/transaksi")
def api_buat(body: TransaksiBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        tx_id = create_transaction(db, body.tipe, user["id"], body.pihak, _lines(body.lines))
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"id": tx_id}


@router.post("/api/transaksi/tukar-tambah")
def api_tukar_tambah(body: TukarTambahBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        r = create_tukar_tambah(db, user["id"], body.pihak, _lines(body.jual_lines), _lines(body.beli_lines))
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {
        "jual_id": r.jual_id, "beli_id": r.beli_id,
        "total_jual": r.total_jual, "total_beli": r.total_beli, "selisih": r.selisih,
    }
```

Modifikasi `app/main.py`: ganti
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes
```
```python
ROUTERS = [auth_routes.router, dashboard_routes.router, prices_routes.router, items_routes.router]
```
menjadi
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes, transactions_routes
```
```python
ROUTERS = [
    auth_routes.router,
    dashboard_routes.router,
    prices_routes.router,
    items_routes.router,
    transactions_routes.router,
]
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus (seluruh suite, termasuk Task 1–4).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: logika transaksi jual, beli, tukar tambah, pembatalan, dan API JSON"
```

---

## Self-Review (Rencana 1)

**Cakupan spesifikasi:** model data (§4) → Task 1, 3, 4, 5; aturan perhitungan dan tukar tambah → Task 5; kode unik, label QR/barcode (§7) → Task 4; error handling inti (§8: kode tidak ditemukan, item terjual dijual lagi, harga belum diisi, atomik) → Task 4, 5; keamanan (§9: login, hash, peran, audit) → Task 2, 3, 5. Layar dashboard, scan, transaksi, riwayat, pengguna, backup, pembatasan jaringan lokal, HTTPS, dan `.exe` ada di Rencana 2.

**Konsistensi tipe:** `LineIn`, `NewItem`, `create_item`, `ItemNotAvailable(code, tx_id)`, `require_price(conn, tanggal10, kadar)`, `render(request, name, user, status_code, **ctx)`, dan daftar `ROUTERS` dipakai dengan nama dan tanda tangan yang sama di semua tugas.

**Akhir Rencana 1:** `pytest -q` seluruhnya hijau; API sudah bisa dipakai lewat `POST /api/transaksi`.
