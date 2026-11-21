from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from .. import lisensi
from ..auth import current_user, get_db
from ..web import render

router = APIRouter()


def _page(request: Request, user, status_code=200, error=None, ok=False):
    return render(
        request, "lisensi.html", user, status_code=status_code, st=lisensi.status_cache(request.app),
        perangkat=lisensi.kode_perangkat(), error=error, ok=ok, wajib=request.app.state.settings.lisensi_wajib,
    )


@router.get("/lisensi")
def lisensi_page(request: Request, ok: int = 0, user=Depends(current_user)):
    return _page(request, user, ok=bool(ok))


@router.post("/lisensi")
def lisensi_aktifkan(request: Request, kunci: str = Form(""), user=Depends(current_user), db=Depends(get_db)):
    """Terbuka tanpa login: hanya kunci bertanda tangan sah untuk komputer ini yang diterima."""
    s = request.app.state.settings
    st = lisensi.periksa(kunci, lisensi.kode_perangkat(), date.today(), s.lisensi_pubkey)
    if not st.boleh_pakai:
        return _page(request, user, 400, error=st.pesan)
    lisensi.simpan_kunci(s, kunci)
    lisensi.reset_cache(request.app)
    from ..services import audit
    audit.log(db, user["id"] if user else None, "lisensi_aktif", {"toko": st.toko, "sampai": st.sampai})
    return RedirectResponse("/lisensi?ok=1", status_code=303)
