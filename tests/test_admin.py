import io
import zipfile

from fastapi.testclient import TestClient


def test_pengguna_hanya_pemilik(kasir_client):
    assert kasir_client.get("/pengguna").status_code == 403
    assert kasir_client.post("/pengguna", data={"username": "x", "password": "rahasia123", "role": "kasir"}).status_code == 403
    assert kasir_client.post("/backup").status_code == 403


def test_tambah_pengguna_lalu_login(owner_client, app):
    r = owner_client.post("/pengguna", data={"username": "siti", "password": "rahasia123", "role": "kasir"}, follow_redirects=False)
    assert r.status_code == 303
    assert "siti" in owner_client.get("/pengguna").text
    baru = TestClient(app, base_url="https://testserver")
    r = baru.post("/login", data={"username": "siti", "password": "rahasia123"}, follow_redirects=False)
    assert r.status_code == 303


def test_tambah_pengguna_duplikat_dan_sandi_pendek(owner_client):
    r = owner_client.post("/pengguna", data={"username": "pemilik1", "password": "rahasia123", "role": "kasir"})
    assert r.status_code == 400 and "sudah dipakai" in r.text
    r = owner_client.post("/pengguna", data={"username": "baru", "password": "123", "role": "kasir"})
    assert r.status_code == 400 and "minimal" in r.text


def test_ganti_sandi(owner_client, app, conn):
    uid = conn.execute("SELECT id FROM users WHERE username='pemilik1'").fetchone()[0]
    r = owner_client.post(f"/pengguna/{uid}/sandi", data={"password": "sandibaru1"}, follow_redirects=False)
    assert r.status_code == 303
    c = TestClient(app, base_url="https://testserver")
    assert c.post("/login", data={"username": "pemilik1", "password": "rahasia123"}).status_code == 401
    assert c.post("/login", data={"username": "pemilik1", "password": "sandibaru1"}, follow_redirects=False).status_code == 303
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE aksi='ganti_sandi'").fetchone()[0] == 1


def test_unduh_backup(owner_client):
    r = owner_client.post("/backup")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert "tokoemas.db" in z.namelist()
