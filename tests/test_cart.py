from app.services.cart import add_to_cart, list_cart, remove_from_cart
from app.services.transactions import LineIn, create_transaction
from tests.helpers import make_item


def test_tambah_hapus_dan_tidak_ganda(conn, kasir_id):
    a = make_item(conn)
    add_to_cart(conn, kasir_id, a)
    add_to_cart(conn, kasir_id, a)
    assert [r["id"] for r in list_cart(conn, kasir_id)] == [a]
    remove_from_cart(conn, kasir_id, a)
    assert list_cart(conn, kasir_id) == []


def test_hanya_perhiasan_tersedia(conn, kasir_id):
    a = make_item(conn)
    conn.execute("UPDATE items SET status='terjual' WHERE id=?", (a,))
    try:
        add_to_cart(conn, kasir_id, a)
    except ValueError as e:
        assert "terjual" in str(e)
    else:
        raise AssertionError("harus ditolak")
    try:
        add_to_cart(conn, kasir_id, 9999)
    except ValueError as e:
        assert "tidak ditemukan" in str(e)


def test_keranjang_per_pengguna_dan_bersih_setelah_terjual(conn, kasir_id, owner_id, prices):
    a = make_item(conn)
    add_to_cart(conn, kasir_id, a)
    add_to_cart(conn, owner_id, a)
    assert len(list_cart(conn, owner_id)) == 1
    create_transaction(conn, "jual", kasir_id, "x", [LineIn(item_id=a, harga_per_gram=1_200_000)], "2026-11-19 09:00:00")
    assert list_cart(conn, kasir_id) == [] and list_cart(conn, owner_id) == []


def test_api_keranjang(kasir_client, conn, prices):
    a = make_item(conn)
    from app.timeutil import today

    conn.execute("UPDATE daily_prices SET tanggal=?", (today(),))
    assert kasir_client.get("/api/keranjang").json() == {"items": []}
    r = kasir_client.post("/api/keranjang", json={"item_id": a})
    item = r.json()["items"][0]
    assert r.status_code == 200 and item["id"] == a and item["harga_jual"] == 1_200_000 and item["code"].startswith("GLD-")
    assert kasir_client.post("/api/keranjang", json={"item_id": 9999}).status_code == 409
    assert kasir_client.delete(f"/api/keranjang/{a}").json() == {"items": []}


def test_api_keranjang_butuh_login(client, conn):
    assert client.get("/api/keranjang").status_code == 401


def test_api_perhiasan_tersedia_tanpa_yang_di_keranjang(kasir_client, conn):
    a, b = make_item(conn, name="A"), make_item(conn, name="B")
    conn.execute("UPDATE items SET status='terjual' WHERE id=?", (make_item(conn, name="C"),))
    kasir_client.post("/api/keranjang", json={"item_id": a})
    names = [i["name"] for i in kasir_client.get("/api/items/tersedia").json()["items"]]
    assert names == ["B"] and b
