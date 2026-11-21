import sqlite3
import zipfile

from app.services.backup import backup_if_needed, make_backup, prune
from app.services.users import create_user


def test_backup_berisi_db_dan_foto(settings, conn):
    create_user(conn, "bos", "rahasia123", "pemilik")
    (settings.photo_dir / "a.png").write_bytes(b"fotoku")
    path = make_backup(settings)
    assert path.parent == settings.backup_dir and path.suffix == ".zip"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert "tokoemas.db" in names and "foto/a.png" in names
        z.extract("tokoemas.db", settings.data_dir / "restore")
    c = sqlite3.connect(settings.data_dir / "restore" / "tokoemas.db")
    assert c.execute("SELECT username FROM users").fetchone()[0] == "bos"
    c.close()
    assert not list(settings.data_dir.glob("_snap-*"))


def test_backup_harian_sekali_per_hari(settings, conn):
    first = backup_if_needed(settings, "20261119")
    assert first is not None
    assert backup_if_needed(settings, "20261119") is None


def test_prune_menyisakan_terbaru(settings, conn):
    for i in range(5):
        (settings.backup_dir / f"tokoemas-2026110{i + 1}-000000.zip").write_bytes(b"x")
    prune(settings, keep=2)
    assert sorted(p.name for p in settings.backup_dir.glob("*.zip")) == [
        "tokoemas-20261104-000000.zip", "tokoemas-20261105-000000.zip",
    ]
