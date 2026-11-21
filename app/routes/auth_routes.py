from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..auth import get_db
from ..services.users import authenticate, count_users, create_user
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
    return render(request, "login.html", None)


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
