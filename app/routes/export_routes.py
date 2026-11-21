from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from ..auth import get_db, require_owner
from ..services import audit, export
from ..web import render

router = APIRouter()

_MIME = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _tanggal(v: str, default: date) -> str:
    if not v:
        return default.isoformat()
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise HTTPException(400, "Tanggal tidak valid (format AAAA-BB-HH)")


def _kirim(jenis: str, fmt: str, judul: str, header, rows, pemisah: str, user, db, detail: dict) -> Response:
    if fmt == "csv":
        body = export.to_csv(header, rows, pemisah)
    else:
        body = export.to_xlsx(judul, header, rows)
    audit.log(db, user["id"], "ekspor", {"jenis": jenis, "format": fmt, "baris": len(rows), **detail})
    nama = f"q-mas-{jenis}-{date.today().isoformat()}.{fmt}"
    return Response(body, media_type=_MIME[fmt], headers={"Content-Disposition": f'attachment; filename="{nama}"'})


@router.get("/ekspor")
def ekspor_page(request: Request, user=Depends(require_owner), db=Depends(get_db)):
    hari = date.today()
    jumlah = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    return render(request, "ekspor.html", user, cur="ekspor", jumlah=jumlah,
                  awal=hari.replace(day=1).isoformat(), akhir=hari.isoformat())


@router.get("/ekspor/stok.{fmt}")
def ekspor_stok(fmt: str, pemisah: str = ";", user=Depends(require_owner), db=Depends(get_db)):
    if fmt not in _MIME:
        raise HTTPException(404)
    header, rows = export.stok_rows(db)
    return _kirim("stok", fmt, "Stok", header, rows, pemisah, user, db, {})


@router.get("/ekspor/transaksi.{fmt}")
def ekspor_transaksi(
    fmt: str, dari: str = "", sampai: str = "", pemisah: str = ";",
    user=Depends(require_owner), db=Depends(get_db),
):
    if fmt not in _MIME:
        raise HTTPException(404)
    hari = date.today()
    dari = _tanggal(dari, hari.replace(day=1))
    sampai = _tanggal(sampai, hari)
    if dari > sampai:
        raise HTTPException(400, "Tanggal awal tidak boleh setelah tanggal akhir")
    header, rows = export.transaksi_rows(db, dari, sampai)
    return _kirim("transaksi", fmt, "Transaksi", header, rows, pemisah, user, db, {"dari": dari, "sampai": sampai})
