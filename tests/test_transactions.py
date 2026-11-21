import pytest

from app.services.items import ItemNotAvailable, get_item
from app.services.transactions import (
    CannotCancel, LineIn, TransactionError, cancel_transaction, create_transaction, create_tukar_tambah,
)
from tests.helpers import make_item

TGL = "2026-11-19 10:00:00"


def _count(conn, table="transactions"):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _status(conn, item_id):
    return get_item(conn, item_id)["status"]


def _jual(conn, kasir_id, item_id, harga=1_200_000, ongkos=50_000):
    return create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item_id, harga_per_gram=harga, ongkos=ongkos)], TGL)


def test_jual_menandai_terjual_dan_menghitung_total(conn, prices, kasir_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item)
    t = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    assert t["total"] == 3_050_000 and t["status"] == "aktif" and t["pihak"] == "Budi"
    assert _status(conn, item) == "terjual"
    line = conn.execute("SELECT * FROM transaction_lines WHERE transaction_id=?", (tid,)).fetchone()
    assert line["berat"] == 2.5 and line["kadar"] == "22K" and line["subtotal"] == 3_050_000


def test_jual_harga_boleh_diubah_kasir(conn, prices, kasir_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item, harga=1_100_000, ongkos=0)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 2_750_000


def test_jual_item_sama_dua_kali_ditolak_dan_rollback(conn, prices, kasir_id):
    item = make_item(conn)
    _jual(conn, kasir_id, item)
    with pytest.raises(ItemNotAvailable) as e:
        _jual(conn, kasir_id, item)
    assert e.value.code == "GLD-000001" and e.value.tx_id == 1
    assert _count(conn) == 1 and _count(conn, "transaction_lines") == 1


def test_item_sama_dua_baris_dalam_satu_transaksi_ditolak(conn, prices, kasir_id):
    item = make_item(conn)
    lines = [LineIn(item_id=item, harga_per_gram=1_200_000), LineIn(item_id=item, harga_per_gram=1_200_000)]
    with pytest.raises(ItemNotAvailable):
        create_transaction(conn, "jual", kasir_id, "", lines, TGL)
    assert _status(conn, item) == "tersedia" and _count(conn) == 0


def test_harga_harian_tidak_wajib(conn, kasir_id):
    """Versi 2: harga dari kasir (manual) cukup; harga harian boleh kosong."""
    item = make_item(conn)
    _jual(conn, kasir_id, item)
    assert _count(conn) == 1 and _status(conn, item) == "terjual"


def test_harga_nol_ditolak(conn, prices, kasir_id):
    item = make_item(conn)
    with pytest.raises(TransactionError):
        _jual(conn, kasir_id, item, harga=0)


def test_transaksi_kosong_ditolak(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "jual", kasir_id, "", [], TGL)


def test_tipe_tidak_dikenal(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "hibah", kasir_id, "", [LineIn(kadar="22K", berat=1, harga_per_gram=1)], TGL)


def test_beli_supplier_membuat_perhiasan_baru(conn, prices, kasir_id):
    lines = [LineIn(kadar="24K", berat=10, harga_per_gram=1_200_000, nama="Kalung Naga", jenis="Kalung")]
    tid = create_transaction(conn, "beli_supplier", kasir_id, "PT Emas", lines, TGL)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 12_000_000
    item = conn.execute("SELECT * FROM items").fetchone()
    assert item["code"] == "GLD-000001" and item["status"] == "tersedia"
    assert item["created_by_tx"] == tid and item["kadar"] == "24K" and item["berat"] == 10


def test_beli_pelanggan_emas_curah(conn, prices, kasir_id):
    tid = create_transaction(conn, "beli_pelanggan", kasir_id, "Ani", [LineIn(kadar="18K", berat=3.2, harga_per_gram=900_000)], TGL)
    assert conn.execute("SELECT total FROM transactions WHERE id=?", (tid,)).fetchone()[0] == 2_880_000
    assert _count(conn, "items") == 0
    assert conn.execute("SELECT item_id FROM transaction_lines").fetchone()[0] is None


def test_beli_tidak_boleh_pilih_perhiasan_ada(conn, prices, kasir_id):
    item = make_item(conn)
    with pytest.raises(TransactionError):
        create_transaction(conn, "beli_pelanggan", kasir_id, "", [LineIn(item_id=item, harga_per_gram=900_000)], TGL)


def test_jual_tidak_boleh_buat_perhiasan_baru(conn, prices, kasir_id):
    with pytest.raises(TransactionError):
        create_transaction(conn, "jual", kasir_id, "", [LineIn(kadar="22K", berat=1, harga_per_gram=1, nama="X")], TGL)


def test_tukar_tambah(conn, prices, kasir_id):
    item = make_item(conn)
    res = create_tukar_tambah(
        conn, kasir_id, "Budi",
        jual_lines=[LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)],
        beli_lines=[LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
        tanggal=TGL,
    )
    assert (res.total_jual, res.total_beli, res.selisih) == (3_050_000, 2_750_000, 300_000)
    rows = conn.execute("SELECT * FROM transactions ORDER BY id").fetchall()
    assert [r["tipe"] for r in rows] == ["jual", "beli_pelanggan"]
    assert rows[0]["grup_tukar_tambah"] == rows[1]["grup_tukar_tambah"] is not None
    assert (rows[0]["id"], rows[1]["id"]) == (res.jual_id, res.beli_id)


def test_tukar_tambah_gagal_membatalkan_semuanya(conn, prices, kasir_id):
    item = make_item(conn)
    _jual(conn, kasir_id, item)
    with pytest.raises(ItemNotAvailable):
        create_tukar_tambah(
            conn, kasir_id, "Budi",
            jual_lines=[LineIn(item_id=item, harga_per_gram=1_200_000)],
            beli_lines=[LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
            tanggal=TGL,
        )
    assert _count(conn) == 1


def test_batal_jual_mengembalikan_perhiasan(conn, prices, kasir_id, owner_id):
    item = make_item(conn)
    tid = _jual(conn, kasir_id, item)
    cancel_transaction(conn, tid, owner_id, "salah input")
    t = conn.execute("SELECT status, alasan_batal FROM transactions WHERE id=?", (tid,)).fetchone()
    assert (t["status"], t["alasan_batal"]) == ("batal", "salah input")
    assert _status(conn, item) == "tersedia"
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE aksi='batal'").fetchone()[0] == 1


def test_batal_wajib_alasan_dan_tidak_dua_kali(conn, prices, kasir_id, owner_id):
    tid = _jual(conn, kasir_id, make_item(conn))
    with pytest.raises(TransactionError):
        cancel_transaction(conn, tid, owner_id, "  ")
    cancel_transaction(conn, tid, owner_id, "x")
    with pytest.raises(TransactionError):
        cancel_transaction(conn, tid, owner_id, "x")
    with pytest.raises(TransactionError):
        cancel_transaction(conn, 999, owner_id, "x")


def test_batal_beli_ditolak_jika_perhiasan_terjual(conn, prices, kasir_id, owner_id):
    beli = create_transaction(
        conn, "beli_supplier", kasir_id, "PT",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin", jenis="Cincin")], TGL,
    )
    item = conn.execute("SELECT id FROM items").fetchone()[0]
    jual = _jual(conn, kasir_id, item)
    with pytest.raises(CannotCancel) as e:
        cancel_transaction(conn, beli, owner_id, "salah")
    assert "GLD-000001" in str(e.value)
    cancel_transaction(conn, jual, owner_id, "batal jual")
    cancel_transaction(conn, beli, owner_id, "batal beli")
    assert _status(conn, item) == "nonaktif"


def test_metode_bayar_tersimpan_dan_divalidasi(conn, kasir_id, prices):
    from app.services.transactions import TransactionError
    import pytest

    t = create_transaction(conn, "beli_pelanggan", kasir_id, "x", [LineIn(kadar="22K", berat=1, harga_per_gram=1_100_000)], "2026-11-19 09:00:00")
    assert conn.execute("SELECT metode FROM transactions WHERE id=?", (t,)).fetchone()[0] == "Tunai"
    t = create_transaction(conn, "beli_pelanggan", kasir_id, "x", [LineIn(kadar="22K", berat=1, harga_per_gram=1_100_000)], "2026-11-19 09:00:00", metode="QRIS")
    assert conn.execute("SELECT metode FROM transactions WHERE id=?", (t,)).fetchone()[0] == "QRIS"
    with pytest.raises(TransactionError, match="Metode"):
        create_transaction(conn, "beli_pelanggan", kasir_id, "x", [LineIn(kadar="22K", berat=1, harga_per_gram=1_100_000)], "2026-11-19 09:00:00", metode="Kredit")
