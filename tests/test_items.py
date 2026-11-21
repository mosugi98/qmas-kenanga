import pytest

from app.services.items import NewItem, add_item, get_by_code, get_item, next_code, search, update_item
from app.services.photos import save_photo
from tests.helpers import make_item

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def test_kode_berurutan(conn, owner_id):
    assert next_code(conn) == "GLD-000001"
    make_item(conn)
    make_item(conn, name="B")
    assert next_code(conn) == "GLD-000003"
    assert get_by_code(conn, "gld-000002")["name"] == "B"


def test_add_item_validasi(conn, owner_id):
    with pytest.raises(ValueError):
        add_item(conn, NewItem("", "Cincin", "22K", 2.0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Mobil", "22K", 2.0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Cincin", "22K", 0), owner_id)
    with pytest.raises(ValueError):
        add_item(conn, NewItem("A", "Cincin", "xx", 1.0), owner_id)
    iid = add_item(conn, NewItem("A", "cincin".title(), "22k", 2.0, 10_000), owner_id)
    row = get_item(conn, iid)
    assert row["kadar"] == "22K" and row["status"] == "tersedia"


def test_update_item_dan_terjual_terkunci(conn, owner_id):
    iid = make_item(conn)
    update_item(conn, iid, NewItem("Baru", "Kalung", "24K", 3.0, 0), owner_id)
    assert get_item(conn, iid)["name"] == "Baru"
    conn.execute("UPDATE items SET status='terjual' WHERE id=?", (iid,))
    with pytest.raises(ValueError):
        update_item(conn, iid, NewItem("X", "Kalung", "24K", 3.0, 0), owner_id)


def test_update_item_foto_lama_dipertahankan(conn, owner_id):
    iid = add_item(conn, NewItem("A", "Cincin", "22K", 2.0, 0, foto="a.png"), owner_id)
    update_item(conn, iid, NewItem("A2", "Cincin", "22K", 2.0, 0, foto=None), owner_id)
    assert get_item(conn, iid)["foto"] == "a.png"


def test_search(conn):
    make_item(conn, name="Cincin Mawar")
    make_item(conn, name="Kalung Naga", jenis="Kalung", kadar="24K")
    assert [r["name"] for r in search(conn, q="mawar")] == ["Cincin Mawar"]
    assert [r["name"] for r in search(conn, jenis="Kalung")] == ["Kalung Naga"]
    assert [r["name"] for r in search(conn, kadar="24k")] == ["Kalung Naga"]
    assert len(search(conn)) == 2


def test_save_photo(settings):
    settings.ensure_dirs()
    name = save_photo(settings, PNG)
    assert name.endswith(".png") and (settings.photo_dir / name).read_bytes() == PNG
    with pytest.raises(ValueError):
        save_photo(settings, b"bukan gambar")
    with pytest.raises(ValueError):
        save_photo(settings, PNG + b"0" * (8 * 1024 * 1024))


def test_halaman_katalog_dan_tambah_item(kasir_client, conn):
    assert kasir_client.get("/katalog").status_code == 200
    assert kasir_client.get("/katalog/baru").status_code == 200
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Cincin Z", "jenis": "Cincin", "kadar": "22K", "berat": "2.5", "ongkos": "50000"},
        files={"foto": ("a.png", PNG, "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    row = get_by_code(conn, "GLD-000001")
    assert r.headers["location"] == f"/label/{row['id']}?baru=1"
    assert row["name"] == "Cincin Z" and row["foto"].endswith(".png")
    assert kasir_client.get(f"/foto/{row['foto']}").status_code == 200
    assert "Cincin Z" in kasir_client.get("/katalog").text


def test_tambah_item_tanpa_foto_dan_error(kasir_client, conn):
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Tanpa Foto", "jenis": "Cincin", "kadar": "22K", "berat": "1", "ongkos": "0"},
        files={"foto": ("", b"", "application/octet-stream")},
        follow_redirects=False,
    )
    assert r.status_code == 303 and get_by_code(conn, "GLD-000001")["foto"] is None
    r = kasir_client.post(
        "/katalog/baru", data={"name": "X", "jenis": "Cincin", "kadar": "salah", "berat": "1", "ongkos": "0"}
    )
    assert r.status_code == 400 and "Kadar tidak valid" in r.text


def test_edit_item_lewat_route(kasir_client, conn):
    iid = make_item(conn)
    assert kasir_client.get(f"/katalog/{iid}/edit").status_code == 200
    r = kasir_client.post(
        f"/katalog/{iid}/edit",
        data={"name": "Ganti", "jenis": "Gelang", "kadar": "18K", "berat": "4", "ongkos": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and get_item(conn, iid)["name"] == "Ganti"


def test_api_by_code(kasir_client, conn, owner_id):
    from app.services.prices import set_price
    from app.timeutil import today

    make_item(conn)
    r = kasir_client.get("/api/items/by-code/GLD-000001")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "GLD-000001" and body["status"] == "tersedia" and body["harga_jual"] is None
    set_price(conn, owner_id, today(), "22K", 1_200_000, 1_100_000)
    assert body["est"] is None
    ok = kasir_client.get("/api/items/by-code/gld-000001").json()
    assert ok["harga_jual"] == 1_200_000
    from app.pricing import line_subtotal
    assert ok["est"] == line_subtotal(ok["berat"], 1_200_000, ok["ongkos"])
    assert kasir_client.get("/api/items/by-code/GLD-999999").status_code == 404


def test_label_dan_svg(kasir_client, conn):
    iid = make_item(conn)
    assert "GLD-000001" in kasir_client.get(f"/label/{iid}").text
    for jenis in ("qr", "barcode"):
        r = kasir_client.get(f"/kode/GLD-000001/{jenis}.svg")
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in r.content
    assert kasir_client.get("/kode/ngawur/qr.svg").status_code == 404


def test_item_butuh_login(client, conn):
    assert client.get("/katalog", follow_redirects=False).status_code == 303
    assert client.get("/api/items/by-code/GLD-000001").status_code == 401


def test_katalog_default_tersedia_dan_filter_status(kasir_client, conn):
    from tests.helpers import make_item

    a = make_item(conn, name="Cincin Ada")
    b = make_item(conn, name="Cincin Laku")
    conn.execute("UPDATE items SET status='terjual' WHERE id=?", (b,))
    html = kasir_client.get("/katalog").text
    assert "Cincin Ada" in html and "Cincin Laku" not in html and "Tambah ke kasir" in html
    html = kasir_client.get("/katalog?status=semua").text
    assert "Cincin Ada" in html and "Cincin Laku" in html
    assert "Cincin Laku" in kasir_client.get("/katalog?status=terjual").text
    assert "Cincin Ada" not in kasir_client.get("/katalog?jenis=Kalung").text
    kasir_client.post("/api/keranjang", json={"item_id": a})
    assert "Sudah di kasir" in kasir_client.get("/katalog").text


def test_simpan_lalu_label_langsung_tampil(kasir_client, conn):
    r = kasir_client.post(
        "/katalog/baru", data={"name": "Gelang Uji", "jenis": "Gelang", "kadar": "22K", "berat": "3", "ongkos": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    for teks in ("Perhiasan tersimpan", "GLD-000001", "/kode/GLD-000001/qr.svg", "/kode/GLD-000001/barcode.svg", "Gelang Uji"):
        assert teks in r.text


def test_simpan_dan_tambah_lagi(kasir_client, conn):
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Anting Uji", "jenis": "Anting", "kadar": "18K", "berat": "1", "ongkos": "0", "aksi": "lagi"},
        follow_redirects=False,
    )
    iid = get_by_code(conn, "GLD-000001")["id"]
    assert r.headers["location"] == f"/katalog/baru?ok={iid}"
    page = kasir_client.get(r.headers["location"]).text
    assert "Tersimpan sebagai" in page and f"/label/{iid}" in page and "GLD-000001" in page
    assert "Tersimpan sebagai" not in kasir_client.get("/katalog/baru").text


def test_form_ubah_menampilkan_qr_dan_barcode(kasir_client, conn):
    iid = make_item(conn)
    page = kasir_client.get(f"/katalog/{iid}/edit").text
    assert "/kode/GLD-000001/qr.svg" in page and "/kode/GLD-000001/barcode.svg" in page
