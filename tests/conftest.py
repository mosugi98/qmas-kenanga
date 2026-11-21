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


@pytest.fixture
def owner_id(conn):
    return create_user(conn, "pemilik0", "rahasia123", "pemilik")


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
