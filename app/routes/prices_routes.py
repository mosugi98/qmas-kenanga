from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from ..auth import get_db, require_owner, require_user
from ..config import KADAR_UMUM
from ..services.prices import get_prices, latest_prices, set_price
from ..timeutil import today
from ..web import render

router = APIRouter()


def _page(request, user, db, status_code=200, **extra):
    return render(
        request,
        "harga.html",
        user,
        status_code=status_code,
        tanggal=today(),
        prices=get_prices(db, today()),
        latest=latest_prices(db, today()),
        kadar_list=KADAR_UMUM,
        **extra,
    )


@router.get("/harga")
def harga(request: Request, saved: int = 0, user=Depends(require_owner), db=Depends(get_db)):
    return _page(request, user, db, saved=bool(saved))


@router.post("/harga")
async def harga_simpan(request: Request, user=Depends(require_owner), db=Depends(get_db)):
    form = await request.form()
    try:
        for k in KADAR_UMUM:
            jual = str(form.get(f"jual_{k}", "")).strip()
            beli = str(form.get(f"beli_{k}", "")).strip()
            if not jual and not beli:
                continue
            if not jual or not beli:
                raise ValueError(f"Isi harga jual dan harga beli untuk {k}")
            set_price(db, user["id"], today(), k, int(jual), int(beli))
    except ValueError as e:
        return _page(request, user, db, status_code=400, saved=False, error=str(e))
    return RedirectResponse("/harga?saved=1", status_code=303)


@router.get("/api/harga")
def api_harga(user=Depends(require_user), db=Depends(get_db)):
    return {"tanggal": today(), "harga": get_prices(db, today())}
