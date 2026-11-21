import re

from tests.helpers import make_item


def _n(text, pat):
    return len(re.findall(pat, text))


def test_label_default_qr_dan_barcode(kasir_client, conn):
    iid = make_item(conn)
    t = kasir_client.get(f"/label/{iid}").text
    assert _n(t, r'class="qr"') == 1 and _n(t, r'class="bc"') == 1 and "GLD-000001" in t


def test_label_hanya_qr_atau_hanya_barcode(kasir_client, conn):
    iid = make_item(conn)
    q = kasir_client.get(f"/label/{iid}?isi=qr").text
    assert _n(q, r'class="qr"') == 1 and _n(q, r'class="bc"') == 0
    b = kasir_client.get(f"/label/{iid}?isi=barcode").text
    assert _n(b, r'class="qr"') == 0 and _n(b, r'class="bc"') == 1


def test_label_salinan_dan_ukuran(kasir_client, conn):
    iid = make_item(conn)
    t = kasir_client.get(f"/label/{iid}?salinan=3&ukuran=besar").text
    assert _n(t, r'class="labelcard lbl-besar') == 3
    # nilai ngawur jatuh ke bawaan, salinan dibatasi 1..100
    t2 = kasir_client.get(f"/label/{iid}?salinan=9999&ukuran=x&isi=y").text
    assert _n(t2, r'class="labelcard lbl-sedang') == 100 and _n(t2, r'class="qr"') == 100 and _n(t2, r'class="bc"') == 100
    assert _n(kasir_client.get(f"/label/{iid}?salinan=abc").text, r'class="labelcard') == 1


def test_label_garis_potong(kasir_client, conn):
    iid = make_item(conn)
    assert "potong" in kasir_client.get(f"/label/{iid}?garis=1").text.split('class="labelsheet')[1].split(">")[0]
    assert "potong" not in kasir_client.get(f"/label/{iid}").text.split('class="labelsheet')[1].split(">")[0]


def test_cetak_banyak_perhiasan(kasir_client, conn):
    a = make_item(conn, name="A")
    b = make_item(conn, name="B")
    t = kasir_client.get(f"/label/cetak?ids={a},{b},99999,x&salinan=2&isi=qr").text
    assert _n(t, r'class="labelcard') == 4  # 2 item ada x 2 salinan; id ngawur diabaikan
    assert "GLD-000001" in t and "GLD-000002" in t
    assert kasir_client.get("/label/cetak?ids=").status_code == 400


def test_katalog_punya_pilihan_cetak(kasir_client, conn):
    make_item(conn)
    t = kasir_client.get("/katalog").text
    assert 'class="pk"' in t and "/label/cetak" in t


def test_label_butuh_login(client, conn):
    assert client.get("/label/cetak?ids=1", follow_redirects=False).status_code == 303
