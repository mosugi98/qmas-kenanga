"""Mode online (hosting): bisa diakses dari internet, jadi pengaturan awal dikunci, login dibatasi, dan ada header keamanan."""
import pytest
from fastapi.testclient import TestClient

from app import config, lisensi
from app.config import Settings, load_settings
from app.main import create_app
from app.services.users import create_user

INTERNET = ("8.8.8.8", 50000)   # alamat klien publik


def _app(tmp_path, **kw):
    return create_app(Settings(data_dir=tmp_path / "data", online=True, setup_token="rahasia-token", **kw))


def _web(app, ip=INTERNET):
    return TestClient(app, base_url="https://testserver", client=ip)


def test_load_settings_dari_lingkungan(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKOEMAS_DATA", str(tmp_path))
    monkeypatch.setenv("TOKOEMAS_ONLINE", "1")
    monkeypatch.setenv("TOKOEMAS_SETUP_TOKEN", "abc123")
    s = load_settings()
    assert s.online and s.setup_token == "abc123" and not s.lisensi_wajib      # lisensi per-komputer tidak berlaku di hosting
    monkeypatch.delenv("TOKOEMAS_ONLINE")
    assert load_settings().lisensi_wajib and not load_settings().online


def test_mode_lan_tetap_menolak_alamat_publik(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "d"))
    assert _web(app).get("/login", follow_redirects=False).status_code == 403


def test_mode_online_menerima_alamat_publik(tmp_path):
    app = _app(tmp_path)
    r = _web(_app(tmp_path / "x")).get("/login", follow_redirects=False)
    assert r.status_code in (200, 303)


# ---------- pengaturan awal dikunci ----------
def test_setup_butuh_token(tmp_path):
    app = _app(tmp_path)
    w = _web(app)
    assert "token" in w.get("/setup").text.lower()
    r = w.post("/setup", data={"username": "maling", "password": "sandi123", "token": "salah"}, follow_redirects=False)
    assert r.status_code == 403
    r = w.post("/setup", data={"username": "maling", "password": "sandi123"}, follow_redirects=False)
    assert r.status_code in (403, 422)
    from app.db import connect
    c = connect(app.state.settings.db_path)
    assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    r = w.post("/setup", data={"username": "pemilik", "password": "sandi123", "token": "rahasia-token"}, follow_redirects=False)
    assert r.status_code == 303
    assert c.execute("SELECT username FROM users").fetchone()[0] == "pemilik"


def test_setup_nonaktif_bila_token_tidak_diatur(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "d", online=True, setup_token=""))
    r = _web(app).post("/setup", data={"username": "a", "password": "sandi123", "token": ""}, follow_redirects=False)
    assert r.status_code == 403


def test_setup_lan_tanpa_token_tetap_jalan(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "d"))
    w = TestClient(app, base_url="https://testserver")
    assert w.post("/setup", data={"username": "pemilik", "password": "sandi123"}, follow_redirects=False).status_code == 303


# ---------- pembatasan login ----------
def test_login_dibatasi_setelah_gagal_berulang(tmp_path):
    app = _app(tmp_path)
    from app.db import connect
    c = connect(app.state.settings.db_path)
    create_user(c, "bu_pemilik", "sandibenar1", "pemilik")
    w = _web(app)
    for _ in range(5):
        assert w.post("/login", data={"username": "bu_pemilik", "password": "salah"}).status_code == 401
    r = w.post("/login", data={"username": "bu_pemilik", "password": "sandibenar1"}, follow_redirects=False)
    assert r.status_code == 429 and "coba lagi" in r.text.lower()
    # pengguna lain dari alamat berbeda tidak ikut terkunci
    w2 = _web(app, ("9.9.9.9", 1))
    assert w2.post("/login", data={"username": "bu_pemilik", "password": "sandibenar1"}, follow_redirects=False).status_code == 303


def test_pembatasan_dilepas_setelah_waktu_lewat(tmp_path):
    app = _app(tmp_path)
    from app.db import connect
    create_user(connect(app.state.settings.db_path), "bu", "sandibenar1", "pemilik")
    w = _web(app)
    for _ in range(5):
        w.post("/login", data={"username": "bu", "password": "salah"})
    assert w.post("/login", data={"username": "bu", "password": "sandibenar1"}).status_code == 429
    app.state.throttle.geser_waktu(16 * 60)
    assert w.post("/login", data={"username": "bu", "password": "sandibenar1"}, follow_redirects=False).status_code == 303


def test_login_berhasil_mereset_hitungan(tmp_path):
    app = _app(tmp_path)
    from app.db import connect
    create_user(connect(app.state.settings.db_path), "bu", "sandibenar1", "pemilik")
    w = _web(app)
    for _ in range(4):
        w.post("/login", data={"username": "bu", "password": "salah"})
    assert w.post("/login", data={"username": "bu", "password": "sandibenar1"}, follow_redirects=False).status_code == 303
    w.post("/logout")
    for _ in range(4):
        assert w.post("/login", data={"username": "bu", "password": "salah"}).status_code == 401


# ---------- header keamanan dan kesehatan ----------
def test_header_keamanan(tmp_path):
    r = _web(_app(tmp_path)).get("/login", follow_redirects=True)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "max-age" in r.headers["strict-transport-security"]
    lan = TestClient(create_app(Settings(data_dir=tmp_path / "lan")), base_url="https://testserver")
    assert "strict-transport-security" not in lan.get("/login", follow_redirects=True).headers


def test_healthz_terbuka(tmp_path):
    app = _app(tmp_path)
    r = _web(app).get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_kode_perangkat_bisa_dipatok_lewat_lingkungan(monkeypatch):
    monkeypatch.setenv("QMAS_MACHINE_ID", "instans-hosting-1")
    assert lisensi.machine_id() == "instans-hosting-1"
    assert lisensi.kode_perangkat() == lisensi.kode_perangkat("instans-hosting-1")


def test_berkas_penyebaran_ada():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for f in ("Dockerfile", "docker-compose.yml", "Caddyfile", ".env.example", "render.yaml", ".dockerignore",
              ".github/workflows/docker.yml"):
        assert (root / f).exists(), f
    assert "TOKOEMAS_ONLINE" in (root / "Dockerfile").read_text()
    assert ".env" not in [p.name for p in root.iterdir() if p.is_file() and p.name == ".env"]   # rahasia tidak ikut repo
