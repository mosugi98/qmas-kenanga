from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..auth import current_user, get_db, require_owner
from ..services import audit
from ..services.backup import make_backup
from ..services.users import create_user, list_users, set_password
from ..web import render

router = APIRouter()


def _page(request, user, db, status_code=200, error=None, ok=""):
    return render(request, "pengguna.html", user, status_code=status_code, users=list_users(db), error=error, ok=ok)


@router.get("/pengguna")
def pengguna(request: Request, ok: str = "", user=Depends(require_owner), db=Depends(get_db)):
    return _page(request, user, db, ok=ok)


@router.post("/pengguna")
def pengguna_tambah(
    request: Request, username: str = Form(""), password: str = Form(""), role: str = Form("kasir"),
    user=Depends(require_owner), db=Depends(get_db),
):
    try:
        create_user(db, username, password, role)
    except ValueError as e:
        return _page(request, user, db, 400, error=str(e))
    return RedirectResponse("/pengguna?ok=Pengguna+ditambahkan", status_code=303)


@router.post("/pengguna/{user_id}/sandi")
def pengguna_sandi(
    user_id: int, request: Request, password: str = Form(""), user=Depends(require_owner), db=Depends(get_db)
):
    try:
        set_password(db, user_id, password)
    except ValueError as e:
        return _page(request, user, db, 400, error=str(e))
    audit.log(db, user["id"], "ganti_sandi", {"user_id": user_id})
    return RedirectResponse("/pengguna?ok=Kata+sandi+diganti", status_code=303)


@router.post("/backup")
def backup(request: Request, user=Depends(require_owner)):
    path = make_backup(request.app.state.settings)
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/sertifikat")
def sertifikat(request: Request, user=Depends(current_user)):
    ada = (request.app.state.settings.cert_dir / "server.crt").exists()
    return render(request, "sertifikat.html", user, ada=ada)


@router.get("/sertifikat.crt")
def sertifikat_file(request: Request):
    path = request.app.state.settings.cert_dir / "server.crt"
    if not path.is_file():
        raise HTTPException(404, "Sertifikat belum dibuat")
    return FileResponse(path, media_type="application/x-x509-ca-cert", filename="toko-emas.crt")
