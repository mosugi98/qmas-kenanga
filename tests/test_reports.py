from datetime import date

from app.services.reports import nice_scale, preset_range, summary
from app.services.transactions import LineIn, cancel_transaction, create_transaction, create_tukar_tambah
from tests.helpers import make_item


def _harga(conn, tanggal):
    for kadar, jual, beli in (("22K", 1_200_000, 1_100_000), ("24K", 1_300_000, 1_200_000)):
        conn.execute(
            "INSERT OR REPLACE INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)",
            (tanggal, kadar, jual, beli),
        )


def _data(conn, kasir_id, owner_id):
    for d in ("2026-11-18", "2026-11-19"):
        _harga(conn, d)
    a, b = make_item(conn), make_item(conn, name="B")
    create_transaction(conn, "jual", kasir_id, "x", [LineIn(item_id=a, harga_per_gram=1_200_000, ongkos=50_000)], "2026-11-18 09:00:00")
    batal = create_transaction(conn, "jual", kasir_id, "x", [LineIn(item_id=b, harga_per_gram=1_200_000, ongkos=50_000)], "2026-11-19 09:00:00")
    create_transaction(conn, "beli_pelanggan", kasir_id, "y", [LineIn(kadar="22K", berat=4, harga_per_gram=1_100_000)], "2026-11-19 10:00:00")
    create_transaction(
        conn, "beli_supplier", kasir_id, "z",
        [LineIn(kadar="24K", berat=1.5, harga_per_gram=1_200_000, nama="K", jenis="Kalung")], "2026-11-19 11:00:00",
    )
    cancel_transaction(conn, batal, owner_id, "salah")


def test_summary_hanya_transaksi_aktif(conn, kasir_id, owner_id):
    _data(conn, kasir_id, owner_id)
    s = summary(conn, "2026-11-18", "2026-11-19")
    assert s["penjualan"] == 3_050_000
    assert s["pembelian"] == 6_200_000
    assert s["gram_jual"] == 2.5 and s["gram_beli"] == 5.5
    assert s["series"][0] == {"tgl": "2026-11-18", "penjualan": 3_050_000, "pembelian": 0}
    assert s["series"][1] == {"tgl": "2026-11-19", "penjualan": 0, "pembelian": 6_200_000}
    assert len(s["recent"]) == 4 and s["recent"][0]["kasir"] == "kasir0"


def test_summary_satu_hari_dan_hari_kosong(conn, kasir_id, owner_id):
    _data(conn, kasir_id, owner_id)
    s = summary(conn, "2026-11-19", "2026-11-19")
    assert s["penjualan"] == 0 and s["pembelian"] == 6_200_000 and len(s["series"]) == 1
    s = summary(conn, "2026-11-17", "2026-11-19")
    assert [p["tgl"] for p in s["series"]] == ["2026-11-17", "2026-11-18", "2026-11-19"]
    assert s["series"][0] == {"tgl": "2026-11-17", "penjualan": 0, "pembelian": 0}


def test_summary_tukar_tambah_masuk_dua_sisi(conn, kasir_id):
    _harga(conn, "2026-11-19")
    item = make_item(conn)
    create_tukar_tambah(
        conn, kasir_id, "Budi",
        [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)],
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
        "2026-11-19 10:00:00",
    )
    s = summary(conn, "2026-11-19", "2026-11-19")
    assert (s["penjualan"], s["pembelian"], s["gram_jual"], s["gram_beli"]) == (3_050_000, 2_750_000, 2.5, 2.5)


def test_series_dibatasi_92_hari(conn):
    s = summary(conn, "2026-01-01", "2026-11-19")
    assert len(s["series"]) == 92 and s["series"][-1]["tgl"] == "2026-11-19"


def test_preset_range():
    kamis = date(2026, 11, 19)
    assert preset_range("hari_ini", kamis) == ("2026-11-19", "2026-11-19")
    assert preset_range("minggu_ini", kamis) == ("2026-11-16", "2026-11-19")
    assert preset_range("bulan_ini", kamis) == ("2026-11-01", "2026-11-19")
    assert preset_range("ngawur", kamis) == ("2026-11-19", "2026-11-19")


def test_nice_scale():
    assert nice_scale(0) == (1_000_000, [0, 500_000, 1_000_000])
    assert nice_scale(3_050_000) == (4_000_000, [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000])
    assert nice_scale(7_300_000) == (8_000_000, [0, 2_000_000, 4_000_000, 6_000_000, 8_000_000])


def test_hitungan_transaksi_dan_stok(conn, kasir_id, owner_id):
    from app.services.reports import stock_summary

    _data(conn, kasir_id, owner_id)
    s = summary(conn, "2026-11-18", "2026-11-19")
    assert s["n_jual"] == 1 and s["n_beli"] == 2
    st = stock_summary(conn)
    # B kembali tersedia setelah penjualannya dibatalkan (2,5 g) + K baru dari supplier (1,5 g); A sudah terjual
    assert st == {"jumlah": 2, "gram": 4.0}


def test_baris_transaksi_gabung_tukar_tambah(conn, kasir_id):
    from app.services.reports import day_rows

    _harga(conn, "2026-11-19")
    a = make_item(conn, name="Cincin Polos")
    create_tukar_tambah(
        conn, kasir_id, "Bu Made",
        [LineIn(item_id=a, harga_per_gram=1_200_000, ongkos=95_000)],
        [LineIn(kadar="22K", berat=2, harga_per_gram=1_100_000)],
        "2026-11-19 10:40:00",
    )
    create_transaction(conn, "beli_pelanggan", kasir_id, "Pak Ketut", [LineIn(kadar="24K", berat=1.5, harga_per_gram=1_200_000)], "2026-11-19 11:20:00")
    rows = day_rows(conn, "2026-11-19", "2026-11-19")
    assert [r["kind"] for r in rows] == ["beli", "tukar"]
    assert rows[0]["desc"] == "Emas 24K dari pelanggan" and rows[0]["jam"] == "11:20"
    tukar = rows[1]
    assert tukar["desc"] == "Cincin Polos 22K · tukar emas 22K"
    assert tukar["nilai"] == (2.5 * 1_200_000 + 95_000) - 2 * 1_100_000 and tukar["kembali"] is False
    assert tukar["berat"] == 2.5
