from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from datetime import date

from .. import lisensi
from ..auth import get_db
from ..services import audit
from ..services.users import authenticate, count_users, create_user, set_password
from ..web import render

router = APIRouter()


@router.get("/setup")
def setup_form(request: Request, db=Depends(get_db)):
    if count_users(db) > 0:
        return RedirectResponse("/login", status_code=303)
    return render(request, "setup.html", None)


@router.post("/setup")
def setup(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    if count_users(db) > 0:
        return RedirectResponse("/login", status_code=303)
    try:
        uid = create_user(db, username, password, "pemilik")
    except ValueError as e:
        return render(request, "setup.html", None, status_code=400, error=str(e))
    request.session["uid"] = uid
    return RedirectResponse("/", status_code=303)


@router.get("/login")
def login_form(request: Request, db=Depends(get_db)):
    if count_users(db) == 0:
        return RedirectResponse("/setup", status_code=303)
    return render(request, "login.html", None, info="Kata sandi berhasil diganti. Silakan masuk." if request.query_params.get("reset") else None)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    user = authenticate(db, username, password)
    if user is None:
        return render(request, "login.html", None, status_code=401, error="Nama pengguna atau kata sandi salah")
    request.session["uid"] = user["id"]
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def _lupa_page(request, status_code=200, error=None, username=""):
    st = request.app.state.settings
    return render(
        request, "lupa_sandi.html", None, status_code=status_code, error=error, username=username,
        perangkat=lisensi.kode_perangkat(), tantangan=lisensi.tantangan_reset(st),
    )


@router.get("/lupa-sandi")
def lupa_form(request: Request):
    return _lupa_page(request)


@router.post("/lupa-sandi")
def lupa_proses(
    request: Request, username: str = Form(""), token: str = Form(""), sandi: str = Form(""), db=Depends(get_db),
):
    """Reset kata sandi: hanya token bertanda tangan penerbit untuk komputer dan tantangan ini yang diterima."""
    st = request.app.state.settings
    username = username.strip()
    try:
        lisensi.periksa_reset(token, lisensi.kode_perangkat(), lisensi.tantangan_reset(st), date.today(), st.lisensi_pubkey)
    except lisensi.LisensiError as e:
        return _lupa_page(request, 400, str(e), username)
    u = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if u is None:
        return _lupa_page(request, 400, "Nama pengguna tidak ditemukan", username)
    try:
        set_password(db, u["id"], sandi)
    except ValueError as e:
        return _lupa_page(request, 400, str(e), username)
    lisensi.hapus_tantangan(st)
    audit.log(db, None, "reset_sandi", {"username": username})
    return RedirectResponse("/login?reset=1", status_code=303)
