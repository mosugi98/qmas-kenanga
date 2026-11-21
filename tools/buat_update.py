"""Pembuat ZIP UPDATE Q-mas (tanpa Python portable, kecil): timpa ke folder Q-mas yang sudah terpasang.

    python tools/buat_update.py --versi v2.0 --out dist
Folder data (database, foto, lisensi) tidak ada di zip, jadi tidak tertimpa.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["run.py", "requirements.txt", "README.md", "PANDUAN.md"]


def buat(out: Path, versi: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    tujuan = out / f"Q-mas-update-{versi}.zip"
    with zipfile.ZipFile(tujuan, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((ROOT / "app").rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                z.write(p, p.relative_to(ROOT).as_posix())
        for f in FILES:
            z.write(ROOT / f, f)
        z.writestr("BACA-DULU.txt", (
            f"Update Q-mas {versi}\n1. Tutup Q-mas (jendela jalankan.bat).\n"
            "2. Ekstrak zip ini ke folder Q-mas, timpa file lama. Folder data TIDAK tersentuh.\n"
            "3. Jalankan lagi. Perubahan tabel database dibuat otomatis saat pertama jalan.\n"
        ).replace("\n", "\r\n"))
    return tujuan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versi", default="baru")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    print(buat(Path(a.out), a.versi))


if __name__ == "__main__":
    main()
