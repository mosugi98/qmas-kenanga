from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _rupiah(v) -> str:
    if v is None:
        return "—"
    return "Rp " + f"{int(v):,}".replace(",", ".")


def _gram(v) -> str:
    if v is None:
        return "—"
    return f"{float(v):.3f}".rstrip("0").rstrip(".").replace(".", ",") + " g"


templates.env.filters["rupiah"] = _rupiah
templates.env.filters["gram"] = _gram


def _lisensi_info(request: Request, user):
    """Peringatan lisensi (segera habis / masa tenggang) hanya untuk pemilik."""
    if not user or user["role"] != "pemilik" or not request.app.state.settings.lisensi_wajib:
        return None
    from .lisensi import status_cache

    st = status_cache(request.app)
    return st if st.kode in ("segera_habis", "masa_tenggang") else None


def render(request: Request, name: str, user, status_code: int = 200, **ctx):
    ctx = {"user": user, "nama_toko": request.app.state.settings.nama_toko, "lisensi_info": _lisensi_info(request, user), **ctx}
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


_TIPE = {"jual": "Jual", "beli_pelanggan": "Beli pelanggan", "beli_supplier": "Beli supplier"}


def _jt(v) -> str:
    if not v:
        return "0"
    return f"{v / 1_000_000:g}".replace(".", ",") + " jt"


templates.env.filters["jt"] = _jt
templates.env.filters["tipe_label"] = lambda v: _TIPE.get(v, v)


# Ikon perhiasan (kotak 28x28) per jenis; dipakai di Kasir, Stok, dan Scan.
JENIS_PATHS = {
    "Cincin": "M7 17a7 7 0 1 0 14 0a7 7 0 1 0-14 0M11 8l3-4 3 4-3 3z",
    "Kalung": "M5 5c0 9 4 14 9 14s9-5 9-14M14 19v3.2M12.2 24a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0",
    "Gelang": "M5 14a9 6 0 1 0 18 0a9 6 0 1 0-18 0M9 14a5 2.6 0 1 0 10 0a5 2.6 0 1 0-10 0",
    "Anting": "M14 3v4M8 15a6 6 0 1 0 12 0a6 6 0 1 0-12 0",
    "Liontin": "M14 3v4M14 8c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z",
    "Lainnya": "M7 10l3-5h8l3 5-7 13zM7 10h14M12 10l2 13M16 10l-2 13",
}


def jenis_path(jenis) -> str:
    return JENIS_PATHS.get(jenis, JENIS_PATHS["Lainnya"])


templates.env.globals["jenis_path"] = jenis_path
templates.env.globals["JENIS_PATHS"] = JENIS_PATHS


_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November",
    "Desember",
]


def tanggal_panjang(d) -> str:
    return f"{_HARI[d.weekday()]}, {d.day} {_BULAN[d.month - 1]} {d.year}"


templates.env.globals["tanggal_panjang"] = tanggal_panjang
