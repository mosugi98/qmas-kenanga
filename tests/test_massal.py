import pytest

from app.services.bulk import BatchRow, buat_massal, kode_berat, rencana_kode
from tests.helpers import make_item


@pytest.mark.parametrize("berat,hasil", [(3.5, "3G5"), (10.0, "10G"), (0.8, "0G8"), (3.25, "3G25"), (3.125, "3G125"), (12.0, "12G")])
def test_kode_berat(berat, hasil):
    assert kode_berat(berat) == hasil


def _kode(conn, ids):
    return [conn.execute("SELECT code FROM items WHERE id=?", (i,)).fetchone()[0] for i in ids]


def test_buat_massal_jumlah_dan_urutan(conn, owner_id):
    ids = buat_massal(conn, [BatchRow("Cincin", "22k", 3.5, 10)], owner_id, awalan="KNG")
    assert len(ids) == 10
    kode = _kode(conn, ids)
    assert kode[0] == "KNG-CIN-3G5-001" and kode[-1] == "KNG-CIN-3G5-010" and len(set(kode)) == 10
    r = conn.execute("SELECT name, jenis, kadar, berat, status, foto, ongkos FROM items WHERE id=?", (ids[0],)).fetchone()
    assert tuple(r) == ("Cincin 3,5 g", "Cincin", "22K", 3.5, "tersedia", None, 0)


def test_lanjut_nomor_dan_beda_berat_terpisah(conn, owner_id):
    buat_massal(conn, [BatchRow("Cincin", "22K", 3.5, 3)], owner_id, awalan="KNG")
    ids = buat_massal(conn, [BatchRow("Cincin", "22K", 3.5, 2), BatchRow("Cincin", "22K", 2.0, 2), BatchRow("Kalung", "18K", 3.5, 1)], owner_id, awalan="KNG")
    assert _kode(conn, ids) == ["KNG-CIN-3G5-004", "KNG-CIN-3G5-005", "KNG-CIN-2G-001", "KNG-CIN-2G-002", "KNG-KAL-3G5-001"]


def test_dua_baris_stem_sama_dalam_satu_batch_tidak_bentrok(conn, owner_id):
    ids = buat_massal(conn, [BatchRow("Gelang", "22K", 5, 2), BatchRow("Gelang", "18K", 5, 2)], owner_id, awalan="KNG")
    assert _kode(conn, ids) == ["KNG-GEL-5G-001", "KNG-GEL-5G-002", "KNG-GEL-5G-003", "KNG-GEL-5G-004"]


def test_kode_manual_yang_sudah_ada_tidak_ditabrak(conn, owner_id):
    from app.db import tx
    from app.services.items import NewItem, create_item
    with tx(conn):
        create_item(conn, NewItem("Manual", "Cincin", "22K", 3.5, 0, None, "KNG-CIN-3G5-007"))
    ids = buat_massal(conn, [BatchRow("Cincin", "22K", 3.5, 2)], owner_id, awalan="KNG")
    assert _kode(conn, ids) == ["KNG-CIN-3G5-008", "KNG-CIN-3G5-009"]


def test_tanpa_awalan_dan_rencana_sama_dengan_hasil(conn, owner_id):
    rows = [BatchRow("Anting", "22K", 1.25, 3)]
    rencana = rencana_kode(conn, rows, "")
    ids = buat_massal(conn, rows, owner_id, awalan="")
    assert [r["kode"] for r in rencana] == _kode(conn, ids) == ["ANT-1G25-001", "ANT-1G25-002", "ANT-1G25-003"]


def test_nama_dan_ongkos_opsional(conn, owner_id):
    ids = buat_massal(conn, [BatchRow("Liontin", "24K", 1.0, 1, nama="Liontin Kenanga", ongkos=25000)], owner_id)
    r = conn.execute("SELECT name, ongkos FROM items WHERE id=?", ids).fetchone()
    assert tuple(r) == ("Liontin Kenanga", 25000)


@pytest.mark.parametrize("rows,awalan,pesan", [
    ([BatchRow("Cincin", "22K", 3.5, 0)], "", "Jumlah"),
    ([BatchRow("Cincin", "22K", 3.5, 201)], "", "Jumlah"),
    ([BatchRow("Cincin", "22K", 0, 5)], "", "Berat"),
    ([BatchRow("Cincin", "XX", 3.5, 5)], "", "Kadar"),
    ([BatchRow("Topi", "22K", 3.5, 5)], "", "Jenis"),
    ([BatchRow("Cincin", "22K", 3.5, 5)], "k n g!", "Awalan"),
    ([], "", "minimal satu"),
    ([BatchRow("Cincin", "22K", 3.5, 200)] * 3, "", "500"),
])
def test_validasi(conn, owner_id, rows, awalan, pesan):
    with pytest.raises(ValueError) as e:
        buat_massal(conn, rows, owner_id, awalan=awalan)
    assert pesan in str(e.value)
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0   # tidak ada yang tersimpan separuh


def test_route_form_dan_buat(kasir_client, conn):
    assert kasir_client.get("/katalog/massal").status_code == 200
    r = kasir_client.post("/katalog/massal", data={"awalan": "KNG", "jenis": ["Cincin", "Kalung"], "kadar": ["22K", "18K"],
                                                    "berat": ["3.5", "5"], "pcs": ["4", "2"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/label/cetak?baru=1&ids=")
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 6
    page = kasir_client.get(r.headers["location"])
    assert page.status_code == 200 and page.text.count('class="labelcard') == 6


def test_route_validasi_kembali_ke_form(kasir_client, conn):
    r = kasir_client.post("/katalog/massal", data={"awalan": "", "jenis": ["Cincin"], "kadar": ["22K"], "berat": ["3.5"], "pcs": ["0"]})
    assert r.status_code == 400 and "Jumlah" in r.text and 'value="3.5"' in r.text
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0


def test_pratinjau_api(kasir_client, conn):
    make_item(conn)
    r = kasir_client.post("/api/items/massal-pratinjau", json={"awalan": "KNG", "baris": [{"jenis": "Cincin", "kadar": "22K", "berat": 3.5, "pcs": 3}]})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3 and d["baris"][0]["awal"] == "KNG-CIN-3G5-001" and d["baris"][0]["akhir"] == "KNG-CIN-3G5-003"
    bad = kasir_client.post("/api/items/massal-pratinjau", json={"awalan": "", "baris": [{"jenis": "Cincin", "kadar": "22K", "berat": 3.5, "pcs": 0}]})
    assert bad.status_code == 400


def test_butuh_login(client):
    assert client.get("/katalog/massal", follow_redirects=False).status_code == 303
