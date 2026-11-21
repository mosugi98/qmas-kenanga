from fastapi import APIRouter, Depends, Request

from ..auth import require_user
from ..web import render

router = APIRouter()


@router.get("/scan")
def scan(request: Request, user=Depends(require_user)):
    return render(request, "scan.html", user)
