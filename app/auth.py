from fastapi import Depends, Request

from .db import connect


class NotLoggedIn(Exception):
    pass


class Forbidden(Exception):
    pass


def get_db(request: Request):
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def current_user(request: Request, db=Depends(get_db)):
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.execute("SELECT id, username, role FROM users WHERE id=?", (uid,)).fetchone()


def require_user(user=Depends(current_user)):
    if user is None:
        raise NotLoggedIn()
    return user


def require_owner(user=Depends(require_user)):
    if user["role"] != "pemilik":
        raise Forbidden()
    return user
