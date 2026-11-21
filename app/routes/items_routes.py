import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

from ..auth import get_db, require_user
from ..config import JENIS, KADAR_UMUM
from ..pricing import line_subtotal
from ..services import labels
from ..services.bulk import MAKS_PER_BARIS, MAKS_TOTAL, BatchRow, buat_massal, rencana_kode
from ..services.cart import list_cart
from ..services.prices import get_prices
from ..services.reports import stock_summary
from ..services.items import NewItem, add_item, get_by_code, get_item, item_payload, next_code, pastikan_kode_unik, search, update_item
from ..services.photos import save_photo
from ..timeutil import today
from ..validation import KODE_RE, normalize_kode
from ..web import render

router = APIRouter()
CODE_RE = KODE_RE


async def _upload_name(request: Request, foto: UploadFile | None):
    if foto is None or not foto.filename:
        return None
    return save_photo(request.app.state.settings, await foto.read())


def _form_page(request, user, item, f, error=None, status_code=200, db=None):
    kode_berikut = next_code(db) if (db is not None and item is None) else None
    return render(request, "item_form.html", user, status_code=status_code, item=item, f=f, JENIS=JENIS, error=error,
                  kode_berikut=kode_berikut)


@router.get("/katalog")
def katalog(
    request: Request, q: str = "", jenis: str = "", kadar: str = "", status: str = "tersedia",
    user=Depends(require_user), db=Depends(get_db),
):
    harga = get_prices(db, today())
    in_cart = {r["id"] for r in list_cart(db, user["id"])}
    items = []
    for it in search(db, q, jenis, kadar, "" if status == "semua" else status):
        p = harga.get(it["kadar"])
        est = line_subtotal(it["berat"], p["jual"], it["ongkos"]) if p else None
        items.append({**dict(it), "est": est, "in_cart": it["id"] in in_cart})
    return render(
        request, "katalog.html", user,
        items=items, q=q, jenis=jenis, kadar=kadar, status=status, JENIS=JENIS, KADAR=KADAR_UMUM,
        stok=stock_summary(db),
    )


@router.get("/katalog/baru")
def baru_form(request: Request, ok: int = 0, user=Depends(require_user), db=Depends(get_db)):
    page = _form_page(request, user, None, {"name": "", "jenis": "Cincin", "kadar": "22K", "berat": "", "ongkos": 0, "code": ""}, db=db)
    saved = get_item(db, ok) if ok else None
    if saved is None:
        return page
    return render(request, "item_form.html", user, item=None, f={"name": "", "jenis": "Cincin", "kadar": "22K", "berat": "", "ongkos": 0, "code": ""},
                  JENIS=JENIS, error=None, saved=saved, kode_berikut=next_code(db))


@router.post("/katalog/baru")
async def baru(
    request: Request, name: str = Form(...), jenis: str = Form(...), kadar: str = Form(...),
    berat: float = Form(...), ongkos: int = Form(0), aksi: str = Form("label"), code: str = Form(""),
    foto: UploadFile | None = File(None), user=Depends(require_user), db=Depends(get_db),
):
    f = {"name": name, "jenis": jenis, "kadar": kadar, "berat": berat, "ongkos": ongkos, "code": code.strip().upper()}
    try:
        item_id = add_item(db, NewItem(name, jenis, kadar, berat, ongkos, await _upload_name(request, foto), code), user["id"])
    except ValueError as e:
        return _form_page(request, user, None, f, str(e), 400, db=db)
    # kode, QR, dan barcode dibuat otomatis saat disimpan; tampilkan labelnya langsung
    if aksi == "lagi":
        return RedirectResponse(f"/katalog/baru?ok={item_id}", status_code=303)
    return RedirectResponse(f"/label/{item_id}?baru=1", status_code=303)


def _baris_dari_form(jenis, kadar, berat, pcs):
    rows = []
    for j, k, b, p in zip(jenis, kadar, berat, pcs):
        if not (str(b).strip() or str(p).strip()):
            continue                      # baris kosong diabaikan
        rows.append(BatchRow(j, k, b, p))
    return rows


@router.get("/katalog/massal")
def massal_form(request: Request, user=Depends(require_user)):
    return render(request, "item_massal.html", user, JENIS=JENIS, awalan=request.app.state.settings.awalan_kode,
                  rows=[{"jenis": "Cincin", "kadar": "22K", "berat": "", "pcs": ""}], error=None,
                  MAKS_TOTAL=MAKS_TOTAL, MAKS_PER_BARIS=MAKS_PER_BARIS)


@router.post("/katalog/massal")
def massal_buat(
    request: Request, awalan: str = Form(""), jenis: list[str] = Form([]), kadar: list[str] = Form([]),
    berat: list[str] = Form([]), pcs: list[str] = Form([]), user=Depends(require_user), db=Depends(get_db),
):
    try:
        ids = buat_massal(db, _baris_dari_form(jenis, kadar, berat, pcs), user["id"], awalan)
    except ValueError as e:
        echo = [{"jenis": j, "kadar": k, "berat": b, "pcs": p} for j, k, b, p in zip(jenis, kadar, berat, pcs)] or [
            {"jenis": "Cincin", "kadar": "22K", "berat": "", "pcs": ""}]
        return render(request, "item_massal.html", user, status_code=400, JENIS=JENIS, awalan=awalan.upper(), rows=echo,
                      error=str(e), MAKS_TOTAL=MAKS_TOTAL, MAKS_PER_BARIS=MAKS_PER_BARIS)
    return RedirectResponse("/label/cetak?baru=1&ids=" + ",".join(map(str, ids)), status_code=303)


class PratinjauBaris(BaseModel):
    jenis: str
    kadar: str
    berat: float
    pcs: int


class PratinjauBody(BaseModel):
    awalan: str = ""
    baris: list[PratinjauBaris]


@router.post("/api/items/massal-pratinjau")
def massal_pratinjau(body: PratinjauBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        rencana = rencana_kode(db, [BatchRow(b.jenis, b.kadar, b.berat, b.pcs) for b in body.baris], body.awalan)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    per_baris: list[dict] = []
    i = 0
    for b in body.baris:
        kode = [p["kode"] for p in rencana[i:i + b.pcs]]
        i += b.pcs
        per_baris.append({"awal": kode[0], "akhir": kode[-1], "pcs": b.pcs})
    return {"total": len(rencana), "baris": per_baris}


@router.get("/katalog/{item_id}/edit")
def edit_form(item_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    return _form_page(request, user, item, dict(item))


@router.post("/katalog/{item_id}/edit")
async def edit(
    item_id: int, request: Request, name: str = Form(...), jenis: str = Form(...), kadar: str = Form(...),
    berat: float = Form(...), ongkos: int = Form(0), code: str = Form(""), foto: UploadFile | None = File(None),
    user=Depends(require_user), db=Depends(get_db),
):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    f = {"name": name, "jenis": jenis, "kadar": kadar, "berat": berat, "ongkos": ongkos, "code": code.strip().upper() or item["code"]}
    try:
        update_item(db, item_id, NewItem(name, jenis, kadar, berat, ongkos, await _upload_name(request, foto), code), user["id"])
    except ValueError as e:
        return _form_page(request, user, item, f, str(e), 400)
    return RedirectResponse("/katalog", status_code=303)


@router.get("/foto/{name}")
def foto_file(name: str, request: Request, user=Depends(require_user)):
    path = request.app.state.settings.photo_dir / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "Foto tidak ditemukan")
    return FileResponse(path)


@router.get("/api/items/kode-tersedia")
def kode_tersedia(kode: str = "", abaikan: int | None = None, user=Depends(require_user), db=Depends(get_db)):
    """Cek apakah kode bebas boleh dipakai (untuk pesan langsung di form)."""
    if not kode.strip():
        return {"ok": True, "kode": None, "pesan": "Kosong: kode dibuat otomatis"}
    try:
        k = normalize_kode(kode)
        pastikan_kode_unik(db, k, abaikan)
    except ValueError as e:
        return {"ok": False, "kode": None, "pesan": str(e)}
    return {"ok": True, "kode": k, "pesan": "Kode tersedia"}


@router.get("/api/items/by-code/{code}")
def by_code(code: str, user=Depends(require_user), db=Depends(get_db)):
    item = get_by_code(db, code)
    if item is None:
        raise HTTPException(404, "Kode tidak terdaftar")
    price = db.execute(
        "SELECT harga_jual FROM daily_prices WHERE tanggal=? AND kadar=?", (today(), item["kadar"])
    ).fetchone()
    return {
        "id": item["id"], "code": item["code"], "name": item["name"], "jenis": item["jenis"],
        "kadar": item["kadar"], "berat": item["berat"], "ongkos": item["ongkos"], "status": item["status"],
        "foto_url": f"/foto/{item['foto']}" if item["foto"] else None,
        "harga_jual": price["harga_jual"] if price else None,
        "est": line_subtotal(item["berat"], price["harga_jual"], item["ongkos"]) if price else None,
    }


@router.get("/api/items/tersedia")
def api_tersedia(limit: int = 12, user=Depends(require_user), db=Depends(get_db)):
    """Perhiasan tersedia terbaru yang belum ada di keranjang pengguna (untuk chip di Kasir)."""
    harga = get_prices(db, today())
    in_cart = {r["id"] for r in list_cart(db, user["id"])}
    out = []
    for it in search(db, "", "", "", "tersedia"):
        if it["id"] in in_cart:
            continue
        p = harga.get(it["kadar"])
        out.append(item_payload(it, p["jual"] if p else None))
        if len(out) >= min(max(limit, 1), 50):
            break
    return {"items": out}


LABEL_ISI = ("keduanya", "qr", "barcode")
LABEL_UKURAN = ("kecil", "sedang", "besar")


def _opsi_label(request: Request) -> dict:
    q = request.query_params
    isi = q.get("isi") if q.get("isi") in LABEL_ISI else "keduanya"
    ukuran = q.get("ukuran") if q.get("ukuran") in LABEL_UKURAN else "sedang"
    try:
        salinan = max(1, min(100, int(q.get("salinan", "1"))))
    except ValueError:
        salinan = 1
    return {"isi": isi, "ukuran": ukuran, "salinan": salinan, "garis": q.get("garis") == "1"}


def _render_label(request, user, items, **extra):
    opsi = _opsi_label(request)
    daftar = [it for it in items for _ in range(opsi["salinan"])]
    return render(request, "label.html", user, items=items, daftar=daftar, opsi=opsi,
                  baru=request.query_params.get("baru") == "1", **extra)


@router.get("/label/cetak")
def label_cetak(request: Request, ids: str = "", user=Depends(require_user), db=Depends(get_db)):
    """Cetak label banyak perhiasan sekaligus: /label/cetak?ids=1,2,3"""
    wanted = []
    for x in ids.split(","):
        if x.strip().isdigit() and int(x) not in wanted:
            wanted.append(int(x))
    items = [it for it in (get_item(db, i) for i in wanted[:500]) if it is not None]
    if not items:
        raise HTTPException(400, "Pilih minimal satu perhiasan")
    return _render_label(request, user, items, ids=",".join(str(i["id"]) for i in items))


@router.get("/label/{item_id}")
def label(item_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    item = get_item(db, item_id)
    if item is None:
        raise HTTPException(404, "Perhiasan tidak ditemukan")
    return _render_label(request, user, [item], ids="")


def _check_code(code: str) -> str:
    if not CODE_RE.match(code):
        raise HTTPException(404, "Kode tidak valid")
    return code


@router.get("/kode/{code}/qr.svg")
def qr(code: str, user=Depends(require_user)):
    return Response(labels.qr_svg(_check_code(code)), media_type="image/svg+xml")


@router.get("/kode/{code}/barcode.svg")
def barcode_svg(code: str, user=Depends(require_user)):
    return Response(labels.code128_svg(_check_code(code)), media_type="image/svg+xml")
