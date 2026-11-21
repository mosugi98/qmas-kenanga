from decimal import ROUND_HALF_UP, Decimal


def line_subtotal(berat: float, harga_per_gram: int, ongkos: int = 0) -> int:
    emas = (Decimal(str(berat)) * Decimal(int(harga_per_gram))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(emas) + int(ongkos)
