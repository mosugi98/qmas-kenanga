import pytest

from app.services.items import NewItem, add_item, get_by_code, next_code, update_item
from app.validation import normalize_kode
from tests.helpers import make_item


def _item(code=None, name="Cincin", **kw):
    return NewItem(name, "Cincin", "22K", 2.0, 0, None, code)


@pytest.mark.parametrize("raw,hasil", [(" cc-0412 ", "CC-0412"), ("abc", "ABC"), ("Emas_01.A", "EMAS_01.A")])
def test_normalize_kode_valid(raw, hasil):
    assert normalize_kode(raw) == hasil


@pytest.mark.parametrize("raw", ["", "ab", "a b c", "-ABC", "AB/CD", "A" * 31, "kode#1", "kódé"])
def test_normalize_kode_tidak_valid(raw):
    with pytest.raises(ValueError):
        normalize_kode(raw)


def test_kode_bebas_disimpan_huruf_besar(conn, owner_id):
    iid = add_item(conn, _item("cc-0412"), owner_id)
    assert get_by_code(conn, "CC-0412")["id"] == iid
    assert get_by_code(conn, "cc-0412")["id"] == iid


def test_kode_tidak_boleh_kembar_case_insensitive(conn, owner_id):
    add_item(conn, _item("CC-0412", name="Pertama"), owner_id)
    with pytest.raises(ValueError, match="sudah dipakai oleh Pertama"):
        add_item(conn, _item("cc-0412", name="Kedua"), owner_id)
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_kode_otomatis_tidak_terganggu_kode_bebas(conn, owner_id):
    add_item(conn, _item("CC-0412"), owner_id)
    assert next_code(conn) == "GLD-000001"
    add_item(conn, _item("GLD-000050"), owner_id)
    assert next_code(conn) == "GLD-000051"
    iid = add_item(conn, _item(None), owner_id)
    assert conn.execute("SELECT code FROM items WHERE id=?", (iid,)).fetchone()[0] == "GLD-000051"


def test_ubah_kode(conn, owner_id):
    a = add_item(conn, _item("AAA-1", name="A"), owner_id)
    add_item(conn, _item("BBB-1", name="B"), owner_id)
    update_item(conn, a, _item("aaa-2", name="A"), owner_id)
    assert get_by_code(conn, "AAA-2")["id"] == a and get_by_code(conn, "AAA-1") is None
    with pytest.raises(ValueError, match="sudah dipakai"):
        update_item(conn, a, _item("bbb-1", name="A"), owner_id)
    update_item(conn, a, _item(None, name="A baru"), owner_id)  # kosong = kode tetap
    assert get_by_code(conn, "AAA-2")["name"] == "A baru"
    update_item(conn, a, _item("AAA-2", name="A"), owner_id)  # kode sendiri boleh


def test_route_buat_dengan_kode_bebas(kasir_client, conn):
    r = kasir_client.post(
        "/katalog/baru",
        data={"name": "Cincin K", "jenis": "Cincin", "kadar": "22K", "berat": "2", "ongkos": "0", "code": "cc-0412"},
        follow_redirects=False,
    )
    row = get_by_code(conn, "CC-0412")
    assert r.status_code == 303 and r.headers["location"] == f"/label/{row['id']}?baru=1"
    r2 = kasir_client.post(
        "/katalog/baru", data={"name": "Lain", "jenis": "Cincin", "kadar": "22K", "berat": "1", "ongkos": "0", "code": "CC-0412"}
    )
    assert r2.status_code == 400 and "sudah dipakai" in r2.text and 'value="CC-0412"' in r2.text
    r3 = kasir_client.post(
        "/katalog/baru", data={"name": "Salah", "jenis": "Cincin", "kadar": "22K", "berat": "1", "ongkos": "0", "code": "a b"}
    )
    assert r3.status_code == 400 and "Kode hanya boleh" in r3.text


def test_route_ubah_kode(kasir_client, conn):
    iid = make_item(conn)
    r = kasir_client.post(
        f"/katalog/{iid}/edit",
        data={"name": "X", "jenis": "Cincin", "kadar": "22K", "berat": "2", "ongkos": "0", "code": "baru-9"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and get_by_code(conn, "BARU-9")["id"] == iid


def test_api_kode_tersedia(kasir_client, conn):
    iid = make_item(conn)
    j = kasir_client.get("/api/items/kode-tersedia", params={"kode": "gld-000001"}).json()
    assert j["ok"] is False and "sudah dipakai" in j["pesan"]
    assert kasir_client.get("/api/items/kode-tersedia", params={"kode": "gld-000001", "abaikan": iid}).json()["ok"] is True
    assert kasir_client.get("/api/items/kode-tersedia", params={"kode": "BARU-1"}).json() == {"ok": True, "kode": "BARU-1", "pesan": "Kode tersedia"}
    assert kasir_client.get("/api/items/kode-tersedia", params={"kode": "a b"}).json()["ok"] is False
    assert kasir_client.get("/api/items/kode-tersedia", params={"kode": ""}).json()["ok"] is True


def test_gambar_untuk_kode_bebas(kasir_client):
    for jenis in ("qr", "barcode"):
        assert kasir_client.get(f"/kode/CC-0412/{jenis}.svg").status_code == 200
    assert kasir_client.get("/kode/a%20b/qr.svg").status_code == 404
