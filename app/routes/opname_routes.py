from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from ..auth import get_db, require_owner, require_user
from ..services import audit, export, stocktake
from ..services.items import search
from ..web import render

router = APIRouter()


class ScanIn(BaseModel):
    kode: str


@router.get("/opname")
def opname_list(request: Request, user=Depends(require_user), db=Depends(get_db)):
    return render(request, "opname.html", user, cur="opname", daftar=stocktake.daftar_opname(db),
                  jalan=stocktake.aktif(db), error=request.query_params.get("error"))


@router.post("/opname/mulai")
def opname_mulai(nama: str = Form(""), user=Depends(require_user), db=Depends(get_db)):
    try:
        take = stocktake.mulai(db, user["id"], nama)
    except ValueError:
        jalan = stocktake.aktif(db)
        return RedirectResponse(f"/opname/{jalan['id']}", status_code=303)
    return RedirectResponse(f"/opname/{take}", status_code=303)


def _ada(db, take_id):
    try:
        return stocktake.laporan(db, take_id)
    except LookupError:
        raise HTTPException(404, "Opname tidak ditemukan")


@router.get("/opname/{take_id}")
def opname_scan(take_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    lap = _ada(db, take_id)
    if lap["status"] == "selesai":
        return RedirectResponse(f"/opname/{take_id}/laporan", status_code=303)
    return render(request, "opname_scan.html", user, cur="opname", lap=lap, take_id=take_id)


@router.post("/opname/{take_id}/scan")
def opname_scan_post(take_id: int, body: ScanIn, user=Depends(require_user), db=Depends(get_db)):
    try:
        return stocktake.scan(db, take_id, user["id"], body.kode)
    except LookupError:
        raise HTTPException(404, "Opname tidak ditemukan")
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


@router.get("/opname/{take_id}/laporan")
def opname_laporan(take_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    lap = _ada(db, take_id)
    return render(request, "opname_laporan.html", user, cur="opname", lap=lap, take_id=take_id)


@router.post("/opname/{take_id}/selesai")
def opname_selesai(take_id: int, catatan: str = Form(""), user=Depends(require_user), db=Depends(get_db)):
    _ada(db, take_id)
    try:
        stocktake.selesai(db, take_id, user["id"], catatan)
    except ValueError:
        pass
    return RedirectResponse(f"/opname/{take_id}/laporan", status_code=303)


_MIME = {"csv": "text/csv; charset=utf-8", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@router.get("/opname/{take_id}/ekspor.{fmt}")
def opname_ekspor(take_id: int, fmt: str, pemisah: str = ";", user=Depends(require_owner), db=Depends(get_db)):
    if fmt not in _MIME:
        raise HTTPException(404)
    _ada(db, take_id)
    header, rows = export.opname_rows(db, take_id)
    body = export.to_csv(header, rows, pemisah) if fmt == "csv" else export.to_xlsx("Opname", header, rows)
    audit.log(db, user["id"], "ekspor", {"jenis": "opname", "format": fmt, "baris": len(rows), "id": take_id})
    nama = f"q-mas-opname-{take_id}-{date.today().isoformat()}.{fmt}"
    return Response(body, media_type=_MIME[fmt], headers={"Content-Disposition": f'attachment; filename="{nama}"'})


@router.get("/lacak")
def lacak_page(request: Request, user=Depends(require_user)):
    return render(request, "lacak.html", user, cur="lacak")


@router.get("/api/lacak")
def api_lacak(kode: str = "", q: str = "", user=Depends(require_user), db=Depends(get_db)):
    if kode:
        j = stocktake.jejak(db, kode)
        if j is None:
            raise HTTPException(404, "Kode tidak terdaftar")
        return j
    daftar = [
        {k: r[k] for k in ("code", "name", "jenis", "kadar", "berat", "status")}
        for r in search(db, q.strip(), "", "", "")
    ]
    return {"daftar": daftar}
