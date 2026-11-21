from app.services.transactions import LineIn, create_transaction
from app.timeutil import today
from tests.helpers import make_item


def _jual_hari_ini(conn, kasir_id):
    conn.execute(
        "INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)", (today(), "22K", 1_200_000, 1_100_000)
    )
    item = make_item(conn)
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)])


def test_pemilik_melihat_nominal_dan_grafik(owner_client, conn, kasir_id):
    _jual_hari_ini(conn, kasir_id)
    html = owner_client.get("/").text
    for teks in ("Penjualan hari ini", "Pembelian hari ini", "Stok tersedia", "Rp 3.050.000", "Harga emas hari ini", "Tren harian", "Lihat sebagai tabel"):
        assert teks in html


def test_kasir_tanpa_nominal(kasir_client, conn, kasir_id):
    _jual_hari_ini(conn, kasir_id)
    html = kasir_client.get("/").text
    assert "Gramasi jual hari ini" in html and "Gramasi beli hari ini" in html and "Cincin A 22K" in html
    assert "3.050.000" not in html and "Tren harian" not in html


def test_preset_dan_rentang(owner_client):
    assert owner_client.get("/?preset=bulan_ini").status_code == 200
    r = owner_client.get("/?start=2026-11-01&end=2026-11-19")
    assert r.status_code == 200 and "2026-11-01" in r.text


def test_rentang_tidak_valid_tidak_error(owner_client):
    r = owner_client.get("/?start=ngawur&end=2026-11-19")
    assert r.status_code == 200 and "Rentang tanggal tidak valid" in r.text
    r = owner_client.get("/?start=2026-11-19&end=2026-11-01")
    assert r.status_code == 200 and "Rentang tanggal tidak valid" in r.text


def test_dashboard_butuh_login(client, conn):
    assert client.get("/", follow_redirects=False).status_code == 303
