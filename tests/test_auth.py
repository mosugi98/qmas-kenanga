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
