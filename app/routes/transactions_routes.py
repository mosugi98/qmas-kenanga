from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..auth import get_db, require_owner, require_user
from ..config import JENIS, KADAR_UMUM
from ..services.items import ItemNotAvailable
from ..services.transactions import (
    TIPE, LineIn, TransactionError, cancel_transaction, create_transaction, create_tukar_tambah,
    get_transaction, list_transactions,
)
from ..web import render

router = APIRouter()


class LineBody(BaseModel):
    kadar: str = ""
    berat: float = 0
    harga_per_gram: int
    ongkos: int = 0
    item_id: int | None = None
    nama: str | None = None
    jenis: str | None = None


class TransaksiBody(BaseModel):
    tipe: str
    pihak: str = ""
    metode: str = "Tunai"
    lines: list[LineBody]


class TukarTambahBody(BaseModel):
    pihak: str = ""
    metode: str = "Tunai"
    jual_lines: list[LineBody]
    beli_lines: list[LineBody]


def _lines(items: list[LineBody]) -> list[LineIn]:
    return [LineIn(**i.model_dump()) for i in items]


@router.post("/api/transaksi")
def api_buat(body: TransaksiBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        tx_id = create_transaction(db, body.tipe, user["id"], body.pihak, _lines(body.lines), metode=body.metode)
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"id": tx_id}


@router.post("/api/transaksi/tukar-tambah")
def api_tukar_tambah(body: TukarTambahBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        r = create_tukar_tambah(
            db, user["id"], body.pihak, _lines(body.jual_lines), _lines(body.beli_lines), metode=body.metode
        )
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {
        "jual_id": r.jual_id, "beli_id": r.beli_id,
        "total_jual": r.total_jual, "total_beli": r.total_beli, "selisih": r.selisih,
    }


@router.get("/transaksi/baru")
def baru(request: Request, user=Depends(require_user)):
    return render(request, "transaksi_baru.html", user, JENIS=JENIS, KADAR=KADAR_UMUM)


@router.get("/transaksi")
def riwayat(
    request: Request, start: str = "", end: str = "", tipe: str = "",
    user=Depends(require_user), db=Depends(get_db),
):
    try:
        e = date.fromisoformat(end) if end else date.today()
        s = date.fromisoformat(start) if start else e - timedelta(days=29)
    except ValueError:
        e = date.today()
        s = e - timedelta(days=29)
    tipe = tipe if tipe in TIPE else ""
    rows = list_transactions(db, s.isoformat(), e.isoformat(), tipe)
    return render(request, "transaksi_riwayat.html", user, rows=rows, start=s.isoformat(), end=e.isoformat(), tipe=tipe, TIPE=TIPE)


def _detail(request, user, db, tx_id, status_code=200, error=None):
    data = get_transaction(db, tx_id)
    if data is None:
        raise HTTPException(404, "Transaksi tidak ditemukan")
    return render(request, "transaksi_detail.html", user, status_code=status_code, error=error, **data)


@router.get("/transaksi/{tx_id}")
def detail(tx_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    return _detail(request, user, db, tx_id)


@router.post("/transaksi/{tx_id}/batal")
def batal(tx_id: int, request: Request, alasan: str = Form(""), user=Depends(require_owner), db=Depends(get_db)):
    try:
        cancel_transaction(db, tx_id, user["id"], alasan)
    except TransactionError as e:
        return _detail(request, user, db, tx_id, 400, str(e))
    return RedirectResponse(f"/transaksi/{tx_id}", status_code=303)
