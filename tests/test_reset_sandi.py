"""Reset kata sandi hanya oleh penerbit (pemegang kunci privat) lewat kode tantangan bertanda tangan."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import lisensi
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.services.users import authenticate, create_user

PEM, PUB = lisensi.buat_pasangan()
PEM2, _ = lisensi.buat_pasangan()
DEV = lisensi.kode_perangkat("mesin-a")
HARI = date(2026, 11, 21)


# ---------- token ----------
def test_token_sah():
    t = lisensi.terbitkan_reset(PEM, DEV, "ABCD2345", hari_ini=HARI)
    assert t.startswith("QMRST1.")
    lisensi.periksa_reset(t, DEV, "ABCD2345", HARI, PUB)       # tidak melempar
    lisensi.periksa_reset(" " + t[:20] + "\n" + t[20:], DEV, "abcd2345", HARI, PUB)  # spasi dan huruf kecil dimaklumi


@pytest.mark.parametrize("dev,tantangan,hari,pub", [
    (lisensi.kode_perangkat("mesin-b"), "ABCD2345", HARI, PUB),   # komputer lain
    (DEV, "ZZZZ9999", HARI, PUB),                                 # tantangan lain
    (DEV, "ABCD2345", HARI + timedelta(days=3), PUB),             # kedaluwarsa
    (DEV, "ABCD2345", HARI, lisensi.buat_pasangan()[1]),          # penerbit lain
])
def test_token_ditolak(dev, tantangan, hari, pub):
    t = lisensi.terbitkan_reset(PEM, DEV, "ABCD2345", hari_ini=HARI)
    with pytest.raises(lisensi.LisensiError):
        lisensi.periksa_reset(t, dev, tantangan, hari, pub)


def test_kunci_lisensi_bukan_token_reset():
    k = lisensi.terbitkan(PEM, "Toko", DEV, None)
    with pytest.raises(lisensi.LisensiError):
        lisensi.periksa_reset(k, DEV, "ABCD2345", HARI, PUB)


# ---------- rute ----------
@pytest.fixture
def app_(tmp_path):
    return create_app(Settings(data_dir=tmp_path / "data", lisensi_pubkey=PUB))


@pytest.fixture
def web(app_):
    return TestClient(app_, base_url="https://testserver")


@pytest.fixture
def db(app_):
    c = connect(app_.state.settings.db_path)
    create_user(c, "bu_pemilik", "sandilama123", "pemilik")
    yield c
    c.close()


def _tantangan(web):
    r = web.get("/lupa-sandi")
    assert r.status_code == 200 and lisensi.kode_perangkat() in r.text
    import re
    m = re.search(r'id="tantangan">([A-Z2-9]{8})<', r.text)
    assert m, r.text
    return m.group(1)


def test_halaman_terbuka_tanpa_login_dan_tantangan_stabil(web, db):
    t1 = _tantangan(web)
    assert _tantangan(web) == t1          # dimuat ulang tidak mengganti kode yang sudah dikirim ke penerbit


def test_reset_berhasil_sekali_pakai(web, db):
    t = _tantangan(web)
    tok = lisensi.terbitkan_reset(PEM, lisensi.kode_perangkat(), t)
    r = web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": tok, "sandi": "sandibaru123"}, follow_redirects=False)
    assert r.status_code == 303
    assert authenticate(db, "bu_pemilik", "sandibaru123") is not None
    assert authenticate(db, "bu_pemilik", "sandilama123") is None
    # token yang sama tidak bisa dipakai lagi (tantangan sudah diganti)
    r = web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": tok, "sandi": "yanglain12345"}, follow_redirects=False)
    assert r.status_code == 400
    assert authenticate(db, "bu_pemilik", "sandibaru123") is not None
    assert _tantangan(web) != t


def test_token_palsu_ditolak(web, db):
    t = _tantangan(web)
    palsu = lisensi.terbitkan_reset(PEM2, lisensi.kode_perangkat(), t)     # ditandatangani pihak lain
    r = web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": palsu, "sandi": "sandibaru123"})
    assert r.status_code == 400
    r = web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": "asal", "sandi": "sandibaru123"})
    assert r.status_code == 400
    assert authenticate(db, "bu_pemilik", "sandilama123") is not None


def test_pengguna_tidak_ada_dan_sandi_pendek(web, db):
    t = _tantangan(web)
    tok = lisensi.terbitkan_reset(PEM, lisensi.kode_perangkat(), t)
    assert web.post("/lupa-sandi", data={"username": "hantu", "token": tok, "sandi": "sandibaru123"}).status_code == 400
    assert web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": tok, "sandi": "abc"}).status_code == 400
    assert authenticate(db, "bu_pemilik", "sandilama123") is not None
    # kegagalan tidak menghabiskan tantangan: token yang sah masih bisa dipakai
    assert web.post("/lupa-sandi", data={"username": "bu_pemilik", "token": tok, "sandi": "sandibaru123"}, follow_redirects=False).status_code == 303


def test_tetap_terbuka_saat_lisensi_terkunci(tmp_path):
    a = create_app(Settings(data_dir=tmp_path / "d", lisensi_wajib=True, lisensi_pubkey=PUB))
    w = TestClient(a, base_url="https://testserver")
    assert w.get("/lupa-sandi", follow_redirects=False).status_code == 200


def test_tautan_di_halaman_login(web, db):
    assert "/lupa-sandi" in web.get("/login").text
