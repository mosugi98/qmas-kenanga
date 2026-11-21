from app.db import tx
from app.services.items import NewItem, create_item


def make_item(conn, name="Cincin A", jenis="Cincin", kadar="22K", berat=2.5, ongkos=50_000) -> int:
    with tx(conn):
        return create_item(conn, NewItem(name, jenis, kadar, berat, ongkos))
