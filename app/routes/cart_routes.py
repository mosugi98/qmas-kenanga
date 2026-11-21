from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_db, require_user
from ..services.cart import add_to_cart, list_cart, remove_from_cart
from ..services.items import item_payload
from ..services.prices import get_prices
from ..timeutil import today

router = APIRouter()


class CartBody(BaseModel):
    item_id: int


def _payload(db, user_id: int) -> dict:
    harga = get_prices(db, today())
    items = []
    for row in list_cart(db, user_id):
        price = harga.get(row["kadar"])
        items.append(item_payload(row, price["jual"] if price else None))
    return {"items": items}


@router.get("/api/keranjang")
def keranjang(user=Depends(require_user), db=Depends(get_db)):
    return _payload(db, user["id"])


@router.post("/api/keranjang")
def keranjang_tambah(body: CartBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        add_to_cart(db, user["id"], body.item_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return _payload(db, user["id"])


@router.delete("/api/keranjang/{item_id}")
def keranjang_hapus(item_id: int, user=Depends(require_user), db=Depends(get_db)):
    remove_from_cart(db, user["id"], item_id)
    return _payload(db, user["id"])
