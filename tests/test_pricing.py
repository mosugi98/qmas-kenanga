from app.pricing import line_subtotal


def test_subtotal_dasar():
    assert line_subtotal(2.5, 1_200_000, 50_000) == 3_050_000


def test_subtotal_tanpa_ongkos():
    assert line_subtotal(10, 1_200_000) == 12_000_000


def test_pembulatan_setengah_ke_atas():
    assert line_subtotal(0.0005, 1000) == 1
    assert line_subtotal(0.0004, 1000) == 0
