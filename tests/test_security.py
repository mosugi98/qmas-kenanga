from app.security import hash_password, verify_password


def test_hash_dan_verifikasi():
    h = hash_password("rahasia123")
    assert h != "rahasia123"
    assert verify_password("rahasia123", h)
    assert not verify_password("salah", h)


def test_hash_berbeda_tiap_kali():
    assert hash_password("abc123") != hash_password("abc123")


def test_format_rusak_ditolak():
    assert not verify_password("x", "bukan-hash")
