from __future__ import annotations

from ..timeutil import now_str

_COLS = "i.id, i.code, i.name, i.jenis, i.kadar, i.berat, i.ongkos, i.foto"


def list_cart(conn, user_id: int):
    """Isi keranjang kasir milik pengguna; perhiasan yang sudah tidak tersedia ikut dibersihkan."""
    conn.execute(
        "DELETE FROM cart_items WHERE item_id IN (SELECT id FROM items WHERE status!='tersedia')"
    )
    return conn.execute(
        f"SELECT {_COLS} FROM cart_items c JOIN items i ON i.id=c.item_id "
        "WHERE c.user_id=? ORDER BY c.added, i.id",
        (user_id,),
    ).fetchall()


def add_to_cart(conn, user_id: int, item_id: int) -> None:
    item = conn.execute("SELECT code, status FROM items WHERE id=?", (item_id,)).fetchone()
    if item is None:
        raise ValueError("Perhiasan tidak ditemukan")
    if item["status"] != "tersedia":
        raise ValueError(f"{item['code']} berstatus {item['status']}, tidak bisa dijual")
    conn.execute(
        "INSERT OR IGNORE INTO cart_items(user_id, item_id, added) VALUES (?,?,?)",
        (user_id, item_id, now_str()),
    )


def remove_from_cart(conn, user_id: int, item_id: int) -> None:
    conn.execute("DELETE FROM cart_items WHERE user_id=? AND item_id=?", (user_id, item_id))
