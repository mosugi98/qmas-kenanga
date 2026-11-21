from datetime import date

from fastapi import APIRouter, Depends, Request

from ..auth import get_db, require_user
from ..config import KADAR_UMUM
from ..services.prices import get_prices
from ..services.reports import day_rows, nice_scale, preset_range, stock_summary, summary
from ..timeutil import today
from ..web import render

router = APIRouter()
PRESETS = [("hari_ini", "Hari ini"), ("minggu_ini", "Minggu ini"), ("bulan_ini", "Bulan ini")]
PERIODE = {"hari_ini": "hari ini", "minggu_ini": "minggu ini", "bulan_ini": "bulan ini"}


@router.get("/")
def dashboard(
    request: Request, preset: str = "hari_ini", start: str = "", end: str = "",
    user=Depends(require_user), db=Depends(get_db),
):
    error = None
    if start or end:
        try:
            s, e = date.fromisoformat(start), date.fromisoformat(end)
            if s > e:
                raise ValueError
            start, end, preset = s.isoformat(), e.isoformat(), "custom"
        except ValueError:
            error = "Rentang tanggal tidak valid"
            start = end = ""
    if not (start and end):
        preset = preset if preset in [k for k, _ in PRESETS] else "hari_ini"
        start, end = preset_range(preset, date.today())
    data = summary(db, start, end)
    peak = max([p[k] for p in data["series"] for k in ("penjualan", "pembelian")], default=0)
    top, ticks = nice_scale(peak)
    harga = get_prices(db, today())
    return render(
        request, "dashboard.html", user,
        d=data, owner=user["role"] == "pemilik", start=start, end=end, preset=preset,
        presets=PRESETS, top=top, ticks=ticks, error=error,
        periode=PERIODE.get(preset, "periode ini"),
        rates=[(k, harga[k]) for k in KADAR_UMUM if k in harga],
        stok=stock_summary(db), rows=day_rows(db, start, end, 10), today_date=date.today(),
    )
