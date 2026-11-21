import io
import zipfile
from datetime import date

import pytest
from openpyxl import load_workbook

from app.services import export
from app.services.transactions import LineIn, create_transaction
from tests.helpers import make_item


def _isi(conn, kasir_id):
    a = make_item(conn, "Cincin Polos", "Cincin", "22K", 3.5, 150000)
    make_item(conn, "=HYPERLINK(\"x\")", "Kalung", "18K", 5.0, 0)
    conn.execute("INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)",
                 (date.today().isoformat(), "22K", 1_200_000, 1_100_000))
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=a, harga_per_gram=1_200_000, ongkos=150000)])
    return a


def test_csv_bom_pemisah_dan_proteksi_rumus():
    data = export.to_csv(["A", "B"], [["=1+1", 2.5], ["x;y", "ok"]], pemisah=";")
    assert data.startswith(b"\xef\xbb\xbf")
    teks = data.decode("utf-8-sig")
    assert "'=1+1;2,5" in teks.replace("\r\n", "\n")   # angka desimal pakai koma saat pemisah ;
    assert '"x;y";ok' in teks


def test_csv_pemisah_koma_desimal_titik():
    teks = export.to_csv(["A"], [[2.5]], pemisah=",").decode("utf-8-sig")
    assert "2.5" in teks


def test_xlsx_terbaca_openpyxl():
    data = export.to_xlsx("Stok", ["Kode", "Berat"], [["GLD-1", 3.5], ["=x", 2]])
    ws = load_workbook(io.BytesIO(data)).active
    assert ws.title == "Stok"
    assert [c.value for c in ws[1]] == ["Kode", "Berat"]
    assert ws["B2"].value == 3.5 and ws["A3"].value == "=x"
    assert ws["A3"].data_type == "s"          # teks, bukan rumus


def test_stok_rows(conn, kasir_id):
    _isi(conn, kasir_id)
    header, rows = export.stok_rows(conn)
    assert header[:3] == ["Kode", "Nama", "Jenis"]
    assert len(rows) == 2


def test_transaksi_rows_rentang(conn, kasir_id):
    _isi(conn, kasir_id)
    hari = date.today().isoformat()
    header, rows = export.transaksi_rows(conn, hari, hari)
    assert len(rows) == 1 and "Budi" in rows[0]
    _, kosong = export.transaksi_rows(conn, "2000-01-01", "2000-01-02")
    assert kosong == []


def test_route_hanya_pemilik(kasir_client, client):
    assert kasir_client.get("/ekspor").status_code == 403
    assert kasir_client.get("/ekspor/stok.csv").status_code == 403
    assert client.get("/ekspor", follow_redirects=False).status_code == 303


def test_route_unduh(owner_client, conn, kasir_id):
    _isi(conn, kasir_id)
    assert owner_client.get("/ekspor").status_code == 200
    r = owner_client.get("/ekspor/stok.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert f"q-mas-stok-{date.today().isoformat()}.csv" in r.headers["content-disposition"]
    r = owner_client.get("/ekspor/stok.xlsx")
    assert zipfile.is_zipfile(io.BytesIO(r.content))
    hari = date.today().isoformat()
    r = owner_client.get(f"/ekspor/transaksi.xlsx?dari={hari}&sampai={hari}")
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.max_row == 2
    r = owner_client.get("/ekspor/transaksi.csv?dari=bukan&sampai=tanggal")
    assert r.status_code == 400
    assert owner_client.get("/ekspor/stok.pdf").status_code == 404
    n = conn.execute("SELECT COUNT(*) FROM audit_log WHERE aksi='ekspor'").fetchone()[0]
    assert n >= 3
