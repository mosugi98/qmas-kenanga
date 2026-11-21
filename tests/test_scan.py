from pathlib import Path


def test_halaman_scan(kasir_client):
    r = kasir_client.get("/scan")
    assert r.status_code == 200
    for teks in ('id="kode"', 'id="cam"', "lookup.js", "html5-qrcode.min.js"):
        assert teks in r.text


def test_scan_butuh_login(client, conn):
    assert client.get("/scan", follow_redirects=False).status_code == 303


def test_aset_statis_tersedia(client):
    assert client.get("/static/lookup.js").status_code == 200
    r = client.get("/static/vendor/html5-qrcode.min.js")
    assert r.status_code == 200 and len(r.content) > 10_000
    assert Path("app/static/vendor/html5-qrcode.LICENSE").exists()
