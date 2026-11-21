from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

JENIS = ["Cincin", "Kalung", "Gelang", "Anting", "Liontin", "Lainnya"]
KADAR_UMUM = ["24K", "22K", "18K", "16K", "9K"]
PORT = 8443


def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    https_only: bool = True
    lisensi_wajib: bool = False       # aplikasi asli (load_settings) selalu True
    lisensi_pubkey: str | None = None  # None = kunci publik bawaan; hanya diganti oleh tes

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tokoemas.db"

    @property
    def nama_toko(self) -> str:
        """Nama toko dari baris pertama data/nama_toko.txt (jika ada)."""
        try:
            text = (self.data_dir / "nama_toko.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return "Q-mas"
        return text.splitlines()[0].strip()[:60] if text else "Q-mas"

    @property
    def awalan_kode(self) -> str:
        """Awalan kode massal (data/awalan_kode.txt). Bawaan KNG (Kenanga)."""
        try:
            t = (self.data_dir / "awalan_kode.txt").read_text(encoding="utf-8").strip().upper()
        except OSError:
            return "KNG"
        return t.splitlines()[0][:6] if t else ""

    @property
    def photo_dir(self) -> Path:
        return self.data_dir / "foto"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backup"

    @property
    def cert_dir(self) -> Path:
        return self.data_dir / "cert"

    @property
    def lisensi_file(self) -> Path:
        return self.data_dir / "lisensi.key"

    @property
    def secret_file(self) -> Path:
        return self.data_dir / "secret.key"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.photo_dir, self.backup_dir, self.cert_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    return Settings(data_dir=Path(os.environ.get("TOKOEMAS_DATA") or _default_data_dir()), lisensi_wajib=True)
