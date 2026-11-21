import json

import pytest

from app.services import stocktake as st
from app.services.transactions import LineIn, create_transaction
from tests.helpers import make_item


@pytest.fixture
def skenario(conn, owner_id):
    """5 perhiasan: E sudah terjual sebelum opname; A,B,C,D tersedia saat opname dimulai."""
    ids = {n: make_item(conn, f"Cincin {n}", "Cincin", "22K", berat) for n, berat in zip("ABCDE", (2.0, 3.0, 4.0, 5.0, 6.0))}
    create_transaction(conn, "jual", owner_id, "Lama", [LineIn(item_id=ids["E"], harga_per_gram=1_000_000)])
    kode = {n: conn.execute("SELECT code FROM items WHERE id=?", (i,)).fetchone()[0] for n, i in ids.items()}
    return ids, kode


def test_mulai_snapshot_stok_awal(conn, owner_id, skenario):
    ids, _ = skenario
    take = st.mulai(conn, owner_id, "Opname Uji")
    lap = st.laporan(conn, take)
    assert lap["awal"]["pcs"] == 4 and lap["awal"]["gram"] == 14.0     # A+B+C+D, E sudah terjual
    assert lap["status"] == "berjalan"


def test_hanya_satu_opname_berjalan(conn, owner_id, skenario):
    st.mulai(conn, owner_id, "Satu")
    with pytest.raises(ValueError, match="berjalan"):
        st.mulai(conn, owner_id, "Dua")


def test_hasil_scan_semua_kasus(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    assert st.scan(conn, take, owner_id, kode["A"])["hasil"] == "cocok"
    assert st.scan(conn, take, owner_id, kode["A"].lower() + "  ")["hasil"] == "duplikat"     # huruf kecil/spasi dinormalkan
    assert st.scan(conn, take, owner_id, "TIDAK-ADA-1")["hasil"] == "tidak_dikenal"
    assert st.scan(conn, take, owner_id, kode["E"])["hasil"] == "terjual_ada"              # tercatat terjual tapi ada fisik
    baru = make_item(conn, "Baru Masuk", "Kalung", "18K", 7.0)
    kb = conn.execute("SELECT code FROM items WHERE id=?", (baru,)).fetchone()[0]
    r = st.scan(conn, take, owner_id, kb)
    assert r["hasil"] == "baru_masuk" and r["item"]["code"] == kb
    assert r["ringkasan"]["cocok"]["pcs"] == 1


def test_laporan_terjual_ditemukan_hilang(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    st.scan(conn, take, owner_id, kode["A"])
    st.scan(conn, take, owner_id, kode["D"])
    create_transaction(conn, "jual", owner_id, "Budi", [LineIn(item_id=ids["B"], harga_per_gram=1_000_000)])   # terjual SETELAH opname mulai
    lap = st.laporan(conn, take)
    assert (lap["cocok"]["pcs"], lap["terjual"]["pcs"], lap["hilang"]["pcs"]) == (2, 1, 1)
    assert lap["hilang"]["gram"] == 4.0 and [x["code"] for x in lap["hilang"]["daftar"]] == [kode["C"]]
    assert lap["terjual"]["daftar"][0]["code"] == kode["B"] and lap["terjual"]["daftar"][0]["nota"] is not None
    assert lap["selisih_pcs"] == 1
    assert lap["awal"]["pcs"] == lap["cocok"]["pcs"] + lap["terjual"]["pcs"] + lap["hilang"]["pcs"] + lap["nonaktif"]["pcs"]


def test_semua_cocok_tidak_ada_kehilangan(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    for n in "ABCD":
        st.scan(conn, take, owner_id, kode[n])
    lap = st.laporan(conn, take)
    assert lap["hilang"]["pcs"] == 0 and lap["selisih_pcs"] == 0


def test_selesai_membekukan_laporan(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    st.scan(conn, take, owner_id, kode["A"])
    st.selesai(conn, take, owner_id, "catatan akhir")
    create_transaction(conn, "jual", owner_id, "Telat", [LineIn(item_id=ids["C"], harga_per_gram=1_000_000)])   # sesudah selesai
    lap = st.laporan(conn, take)
    assert lap["status"] == "selesai" and lap["hilang"]["pcs"] == 3 and lap["terjual"]["pcs"] == 0     # tidak berubah
    assert lap["catatan"] == "catatan akhir"
    with pytest.raises(ValueError, match="sudah selesai"):
        st.scan(conn, take, owner_id, kode["B"])
    with pytest.raises(ValueError):
        st.selesai(conn, take, owner_id, "")
    st.mulai(conn, owner_id, "Opname berikutnya")          # boleh mulai lagi setelah selesai


def test_nonaktif_bukan_hilang(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    conn.execute("UPDATE items SET status='nonaktif' WHERE id=?", (ids["C"],))
    lap = st.laporan(conn, take)
    assert lap["nonaktif"]["pcs"] == 1 and lap["hilang"]["pcs"] == 3


def test_jejak_barang(conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    st.scan(conn, take, owner_id, kode["A"])
    j = st.jejak(conn, kode["E"])
    assert j["item"]["status"] == "terjual" and j["transaksi"][0]["tipe"] == "jual" and j["transaksi"][0]["pihak"] == "Lama"
    ja = st.jejak(conn, kode["A"])
    assert ja["opname"][0]["nama"] == "Uji" and ja["opname"][0]["ditemukan"] is True
    assert st.jejak(conn, "NGAWUR") is None


# ---------- rute ----------
def test_rute_alur_scan_dan_laporan(kasir_client, conn, owner_id, skenario):
    ids, kode = skenario
    assert kasir_client.get("/opname").status_code == 200
    r = kasir_client.post("/opname/mulai", data={"nama": "Opname Pagi"}, follow_redirects=False)
    assert r.status_code == 303
    url = r.headers["location"]
    take = int(url.rstrip("/").split("/")[-1])
    page = kasir_client.get(url)
    assert page.status_code == 200 and 'id="scan-kode"' in page.text
    j = kasir_client.post(f"/opname/{take}/scan", json={"kode": kode["A"]}).json()
    assert j["hasil"] == "cocok" and j["ringkasan"]["cocok"]["pcs"] == 1 and j["ringkasan"]["awal"]["pcs"] == 4
    assert kasir_client.post(f"/opname/{take}/scan", json={"kode": "XXXXX"}).json()["hasil"] == "tidak_dikenal"
    lap = kasir_client.get(f"/opname/{take}/laporan")
    assert lap.status_code == 200 and "HILANG" in lap.text.upper()
    r = kasir_client.post(f"/opname/{take}/selesai", data={"catatan": "ok"}, follow_redirects=False)
    assert r.status_code == 303
    assert kasir_client.post(f"/opname/{take}/scan", json={"kode": kode["B"]}).status_code == 400


def test_ekspor_opname_hanya_pemilik(kasir_client, client, conn, owner_id, skenario):
    ids, kode = skenario
    take = st.mulai(conn, owner_id, "Uji")
    assert kasir_client.get(f"/opname/{take}/ekspor.csv").status_code == 403
    assert client.get(f"/opname/{take}/ekspor.csv", follow_redirects=False).status_code == 303


def test_api_lacak(kasir_client, conn, skenario):
    ids, kode = skenario
    r = kasir_client.get(f"/api/lacak?kode={kode['E']}")
    assert r.status_code == 200 and r.json()["item"]["status"] == "terjual"
    assert kasir_client.get("/api/lacak?kode=NGAWUR").status_code == 404
    hasil = kasir_client.get("/api/lacak?q=Cincin").json()
    assert len(hasil["daftar"]) == 5
    assert kasir_client.get("/lacak").status_code == 200
