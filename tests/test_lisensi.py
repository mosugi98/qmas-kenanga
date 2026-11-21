from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import lisensi
from app.config import Settings
from app.main import create_app
from app.services.users import create_user

HARI = date(2026, 11, 19)
DEV = lisensi.kode_perangkat("mesin-a")
PEM, PUB = lisensi.buat_pasangan()


def _key(sampai="2027-11-19", dev=DEV, pem=PEM):
    return lisensi.terbitkan(pem, "Toko Maju", dev, sampai, terbit=HARI)


def test_kode_perangkat_stabil_dan_berbeda():
    assert DEV == lisensi.kode_perangkat("mesin-a")
    assert DEV != lisensi.kode_perangkat("mesin-b")
    assert DEV.startswith("QM-") and len(DEV) == 22


def test_lisensi_aktif_dan_isi():
    st = lisensi.periksa(_key(), DEV, HARI, PUB)
    assert st.kode == "aktif" and st.boleh_pakai and st.toko == "Toko Maju" and st.sisa_hari == 365


def test_spasi_dan_baris_baru_diabaikan():
    k = _key()
    rusak = k[:40] + "\n  " + k[40:]
    assert lisensi.periksa(rusak, DEV, HARI, PUB).boleh_pakai


def test_tanpa_batas_waktu():
    st = lisensi.periksa(_key(sampai=None), DEV, date(2040, 1, 1), PUB)
    assert st.kode == "aktif" and st.boleh_pakai


def test_belum_ada_dan_rusak():
    assert lisensi.periksa("", DEV, HARI, PUB).kode == "belum_ada"
    assert lisensi.periksa("abc", DEV, HARI, PUB).kode == "tidak_valid"
    k = _key()
    assert lisensi.periksa(k[:-6], DEV, HARI, PUB).kode == "tidak_valid"   # terpotong


def test_diubah_isinya_ditolak():
    k = _key()
    lain = _key(sampai="2099-01-01")
    palsu = k.split(".")[0] + "." + lain.split(".")[1] + "." + k.split(".")[2]
    assert lisensi.periksa(palsu, DEV, HARI, PUB).kode == "tidak_valid"


def test_kunci_penerbit_lain_ditolak():
    pem2, _ = lisensi.buat_pasangan()
    assert lisensi.periksa(_key(pem=pem2), DEV, HARI, PUB).kode == "tidak_valid"


def test_salah_komputer():
    st = lisensi.periksa(_key(dev=lisensi.kode_perangkat("mesin-b")), DEV, HARI, PUB)
    assert st.kode == "salah_perangkat" and not st.boleh_pakai


@pytest.mark.parametrize("selisih,kode,boleh", [
    (30, "aktif", True), (14, "segera_habis", True), (0, "segera_habis", True),
    (-1, "masa_tenggang", True), (-7, "masa_tenggang", True), (-8, "kedaluwarsa", False),
])
def test_masa_berlaku(selisih, kode, boleh):
    k = _key(sampai=(HARI + timedelta(days=selisih)).isoformat())
    st = lisensi.periksa(k, DEV, HARI, PUB)
    assert (st.kode, st.boleh_pakai) == (kode, boleh)


def test_jam_mundur():
    st = lisensi.periksa(_key(), DEV, HARI, PUB, terakhir_terlihat=HARI + timedelta(days=30))
    assert st.kode == "jam_mundur" and not st.boleh_pakai
    assert lisensi.periksa(_key(), DEV, HARI, PUB, terakhir_terlihat=HARI + timedelta(days=1)).boleh_pakai


def test_terbitkan_validasi():
    with pytest.raises(lisensi.LisensiError):
        lisensi.terbitkan(PEM, "", DEV, None)
    with pytest.raises(lisensi.LisensiError):
        lisensi.terbitkan(PEM, "X", "bukan-kode", None)
    with pytest.raises(lisensi.LisensiError):
        lisensi.terbitkan(PEM, "X", DEV, "31/12/2027")


def test_kunci_publik_bawaan_valid():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(lisensi._unb64(lisensi.PUBLIC_KEY_B64))


# ---------- penjaga akses di aplikasi ----------
@pytest.fixture
def app_lisensi(tmp_path):
    s = Settings(data_dir=tmp_path / "data", lisensi_wajib=True, lisensi_pubkey=PUB)
    return create_app(s)


@pytest.fixture
def web(app_lisensi):
    return TestClient(app_lisensi, base_url="https://testserver")


def test_terkunci_tanpa_lisensi(web):
    r = web.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/lisensi"
    r = web.get("/api/items/kode-tersedia?kode=X", follow_redirects=False)
    assert r.status_code == 402
    assert web.get("/static/app.css").status_code == 200


def test_halaman_lisensi_tampilkan_kode_perangkat(web):
    r = web.get("/lisensi")
    assert r.status_code == 200 and lisensi.kode_perangkat() in r.text


def test_aktivasi_berhasil_membuka_aplikasi(web, app_lisensi):
    k = lisensi.terbitkan(PEM_APP, "Toko Maju", lisensi.kode_perangkat(), None)
    r = web.post("/lisensi", data={"kunci": k}, follow_redirects=False)
    assert r.status_code == 303
    assert app_lisensi.state.settings.lisensi_file.exists()
    assert web.get("/", follow_redirects=False).headers["location"] == "/login"   # tidak lagi dikunci


def test_aktivasi_gagal_pesan_jelas(web, app_lisensi):
    r = web.post("/lisensi", data={"kunci": "ngawur"})
    assert r.status_code == 400 and "Format kunci" in r.text
    assert not app_lisensi.state.settings.lisensi_file.exists()
    pem2, _ = lisensi.buat_pasangan()
    r = web.post("/lisensi", data={"kunci": lisensi.terbitkan(pem2, "T", lisensi.kode_perangkat(), None)})
    assert r.status_code == 400 and "tidak sah" in r.text


def test_kedaluwarsa_mengunci_tetapi_backup_tetap_bisa(web, app_lisensi):
    s = app_lisensi.state.settings
    conn_users = None
    from app.db import connect
    c = connect(s.db_path)
    create_user(c, "bos", "rahasia123", "pemilik")
    c.close()
    k = lisensi.terbitkan(PEM_APP, "T", lisensi.kode_perangkat(), "2020-01-01")
    lisensi.simpan_kunci(s, k)
    lisensi.reset_cache(app_lisensi)
    assert web.get("/transaksi", follow_redirects=False).headers["location"] == "/lisensi"
    r = web.post("/login", data={"username": "bos", "password": "rahasia123"}, follow_redirects=False)
    assert r.status_code == 303
    assert web.post("/backup").status_code == 200
    assert "habis" in web.get("/lisensi").text


def test_banner_peringatan_untuk_pemilik(web, app_lisensi):
    s = app_lisensi.state.settings
    from app.db import connect
    c = connect(s.db_path)
    create_user(c, "bos", "rahasia123", "pemilik")
    c.close()
    sampai = (date.today() + timedelta(days=5)).isoformat()
    lisensi.simpan_kunci(s, lisensi.terbitkan(PEM_APP, "T", lisensi.kode_perangkat(), sampai))
    lisensi.reset_cache(app_lisensi)
    web.post("/login", data={"username": "bos", "password": "rahasia123"})
    r = web.get("/")
    assert r.status_code == 200 and "Lisensi habis dalam 5 hari" in r.text


def test_aplikasi_asli_mewajibkan_lisensi(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKOEMAS_DATA", str(tmp_path))
    from app.config import load_settings
    assert load_settings().lisensi_wajib is True


PEM_APP = PEM
