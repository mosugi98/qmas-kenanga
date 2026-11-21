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


def test_api_tanpa_harga_harian_tetap_bisa(kasir_client, conn):
    item = make_item(conn)
    body = {"tipe": "jual", "lines": [{"item_id": item, "harga_per_gram": 1_200_000}]}
    r = kasir_client.post("/api/transaksi", json=body)
    assert r.status_code == 200


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
