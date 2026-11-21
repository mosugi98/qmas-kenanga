from app.services.items import get_item
from app.services.transactions import LineIn, create_transaction
from app.timeutil import today
from tests.helpers import make_item


def _harga(conn):
    conn.execute(
        "INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)", (today(), "22K", 1_200_000, 1_100_000)
    )


def test_halaman_transaksi_baru(kasir_client):
    r = kasir_client.get("/transaksi/baru")
    assert r.status_code == 200
    for teks in ('id="simpan"', "Selesaikan transaksi", "tukar_tambah", "Beli dari supplier", "lookup.js"):
        assert teks in r.text


def test_riwayat_dan_filter_tipe(kasir_client, conn, kasir_id):
    _harga(conn)
    item = make_item(conn)
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)])
    create_transaction(conn, "beli_pelanggan", kasir_id, "Ani", [LineIn(kadar="22K", berat=2, harga_per_gram=1_100_000)])
    html = kasir_client.get("/transaksi").text
    assert "Budi" in html and "Ani" in html
    html = kasir_client.get("/transaksi?tipe=jual").text
    assert "Budi" in html and "Ani" not in html
    assert kasir_client.get("/transaksi?start=ngawur").status_code == 200


def test_detail_dan_tautan_perhiasan_baru(kasir_client, conn, kasir_id):
    _harga(conn)
    tid = create_transaction(
        conn, "beli_supplier", kasir_id, "PT Emas",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin Baru", jenis="Cincin")],
    )
    html = kasir_client.get(f"/transaksi/{tid}").text
    for teks in ("GLD-000001", "Cincin Baru", "Rp 2.750.000", "/katalog/1/edit", "PT Emas"):
        assert teks in html


def test_detail_tidak_ada(kasir_client):
    assert kasir_client.get("/transaksi/999").status_code == 404


def test_batal_hanya_pemilik(kasir_client, owner_client, conn, kasir_id):
    _harga(conn)
    item = make_item(conn)
    tid = create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000)])
    r = kasir_client.post(f"/transaksi/{tid}/batal", data={"alasan": "salah"}, follow_redirects=False)
    assert r.status_code == 403
    r = owner_client.post(f"/transaksi/{tid}/batal", data={"alasan": ""})
    assert r.status_code == 400 and "wajib" in r.text
    r = owner_client.post(f"/transaksi/{tid}/batal", data={"alasan": "salah input"}, follow_redirects=False)
    assert r.status_code == 303
    html = owner_client.get(f"/transaksi/{tid}").text
    assert "DIBATALKAN" in html and "salah input" in html
    assert get_item(conn, item)["status"] == "tersedia"


def test_batal_beli_yang_perhiasannya_terjual_ditolak(owner_client, conn, kasir_id):
    _harga(conn)
    beli = create_transaction(
        conn, "beli_supplier", kasir_id, "PT",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin", jenis="Cincin")],
    )
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=1, harga_per_gram=1_200_000)])
    r = owner_client.post(f"/transaksi/{beli}/batal", data={"alasan": "salah"})
    assert r.status_code == 400 and "GLD-000001" in r.text
