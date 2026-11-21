import re

_KADAR = re.compile(r"^\d{1,2}K$")
KODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,29}$")


def normalize_kadar(value: str) -> str:
    v = (value or "").strip().upper()
    if not _KADAR.match(v):
        raise ValueError("Kadar tidak valid (contoh: 24K, 22K, 18K)")
    return v


def normalize_kode(value: str) -> str:
    v = (value or "").strip().upper()
    if not KODE_RE.match(v):
        raise ValueError("Kode hanya boleh huruf, angka, tanda - _ . (3 sampai 30 karakter, tanpa spasi)")
    return v
