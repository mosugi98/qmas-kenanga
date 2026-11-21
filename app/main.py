from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import Forbidden, NotLoggedIn
from .config import Settings, load_settings
from .db import init_db
from . import lisensi
from .netguard import is_local
from .routes import (
    admin_routes, auth_routes, cart_routes, dashboard_routes, export_routes, items_routes, lisensi_routes, opname_routes, prices_routes,
    scan_routes,
    transactions_routes,
)

BASE = Path(__file__).resolve().parent

ROUTERS = [
    auth_routes.router,
    dashboard_routes.router,
    prices_routes.router,
    items_routes.router,
    cart_routes.router,
    scan_routes.router,
    transactions_routes.router,
    admin_routes.router,
    export_routes.router,
    lisensi_routes.router,
    opname_routes.router,
]


def _secret(settings: Settings) -> str:
    if settings.secret_file.exists():
        return settings.secret_file.read_text().strip()
    value = secrets.token_hex(32)
    settings.secret_file.write_text(value)
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)

    app = FastAPI(title="Q-mas")
    app.state.settings = settings
    app.add_middleware(
        SessionMiddleware,
        secret_key=_secret(settings),
        max_age=8 * 3600,
        same_site="lax",
        https_only=settings.https_only,
    )
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.exception_handler(NotLoggedIn)
    async def _not_logged_in(request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Silakan login"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(Forbidden)
    async def _forbidden(request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Tidak diizinkan"}, status_code=403)
        return HTMLResponse("<h1>Tidak diizinkan</h1><a href='/'>Kembali</a>", status_code=403)

    @app.middleware("http")
    async def lan_only(request, call_next):
        host = request.client.host if request.client else None
        if not is_local(host):
            return PlainTextResponse("Hanya untuk jaringan lokal", status_code=403)
        return await call_next(request)

    # Penjaga lisensi: tanpa lisensi sah, semua halaman diarahkan ke /lisensi
    # (kecuali halaman lisensi, berkas statis, login, backup, dan sertifikat).
    _BEBAS = ("/lisensi", "/static/", "/login", "/logout", "/backup", "/sertifikat")

    @app.middleware("http")
    async def penjaga_lisensi(request, call_next):
        if settings.lisensi_wajib and not request.url.path.startswith(_BEBAS):
            st = lisensi.status_cache(app)
            if not st.boleh_pakai:
                if request.url.path.startswith("/api/"):
                    return JSONResponse({"detail": st.pesan}, status_code=402)
                return RedirectResponse("/lisensi", status_code=303)
        return await call_next(request)

    for router in ROUTERS:
        app.include_router(router)
    return app
