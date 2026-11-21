from __future__ import annotations

import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path


def make_backup(settings, dest: Path | None = None, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest or settings.backup_dir / f"tokoemas-{stamp}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    snap = settings.data_dir / f"_snap-{stamp}.db"
    src, dst = sqlite3.connect(settings.db_path), sqlite3.connect(snap)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    try:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "tokoemas.db")
            for p in sorted(settings.photo_dir.glob("*")):
                if p.is_file():
                    z.write(p, f"foto/{p.name}")
    finally:
        snap.unlink(missing_ok=True)
    return dest


def prune(settings, keep: int = 14) -> None:
    files = sorted(settings.backup_dir.glob("tokoemas-*.zip"))
    for old in files[:-keep] if keep > 0 else files:
        old.unlink(missing_ok=True)


def backup_if_needed(settings, today_str: str | None = None) -> Path | None:
    today_str = today_str or datetime.now().strftime("%Y%m%d")
    if any(p.name.startswith(f"tokoemas-{today_str}-") for p in settings.backup_dir.glob("tokoemas-*.zip")):
        return None
    path = make_backup(settings, stamp=f"{today_str}-{datetime.now().strftime('%H%M%S')}")
    prune(settings)
    return path


def daily_backup_loop(settings, interval: int = 3600) -> None:
    while True:
        try:
            backup_if_needed(settings)
        except Exception as e:  # backup tidak boleh mematikan server
            print(f"Backup otomatis gagal: {e}")
        time.sleep(interval)
