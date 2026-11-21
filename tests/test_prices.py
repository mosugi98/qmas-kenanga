import json

import pytest

from app.services.prices import PriceMissing, get_prices, require_price, set_price
from app.timeutil import today

TGL = "2026-11-19"


def test_set_price_baru_dan_ubah_tercatat_audit(conn, owner_id):
    set_price(conn, owner_id, TGL, "22k", 1_200_000, 1_100_000)
    assert get_prices(conn, TGL) == {"22K": {"jual": 1_200_000, "beli": 1_100_000}}
    set_price(conn, owner_id, TGL, "22K", 1_250_000, 1_150_000)
    assert get_prices(conn, TGL)["22K"]["jual"] == 1_250_000
    rows = conn.execute("SELECT detail FROM audit_log WHERE aksi='harga' ORDER BY id").fetchall()
    assert json.loads(rows[0]["detail"])["lama"] is None
    assert json.loads(rows[1]["detail"])["lama"] == [1_200_000, 1_100_000]


def test_harga_harus_positif(conn, owner_id):
    with pytest.raises(ValueError):
        set_price(conn, owner_id, TGL, "22K", 0, 1_100_000)


def test_require_price(conn, owner_id):
    with pytest.raises(PriceMissing) as e:
        require_price(conn, TGL, "22K")
    assert "22K" in str(e.value)
    set_price(conn, owner_id, TGL, "22K", 1, 1)
    assert require_price(conn, TGL, "22K")["harga_jual"] == 1


def test_kasir_tidak_boleh_buka_halaman_harga(kasir_client):
    assert kasir_client.get("/harga").status_code == 403


def test_pemilik_simpan_harga_dan_api(owner_client, kasir_client):
    r = owner_client.post(
        "/harga",
        data={"jual_24K": "1300000", "beli_24K": "1200000", "jual_22K": "", "beli_22K": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    api = kasir_client.get("/api/harga").json()
    assert api["tanggal"] == today()
    assert api["harga"]["24K"] == {"jual": 1_300_000, "beli": 1_200_000}
    assert "22K" not in api["harga"]


def test_harga_setengah_terisi_ditolak(owner_client):
    r = owner_client.post("/harga", data={"jual_24K": "1300000", "beli_24K": ""})
    assert r.status_code == 400 and "24K" in r.text
