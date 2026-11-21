"""Lisensi Q-mas: kunci bertanda tangan Ed25519, terikat ke satu komputer, bekerja offline.

Berkas ini sengaja mandiri (hanya pustaka standar + cryptography) agar alat penerbit lisensi
bisa memakai salinan yang sama persis.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# Kunci publik penerbit (aman dibagikan). Pasangan privatnya hanya dipegang penerbit lisensi.
PUBLIC_KEY_B64 = "uoZu5zRDpU0BBiBRDLTk_3I-agfwV43UIN5G7om9F1o"

PREFIX = "QMAS1"
PRODUK = "qmas"
PERINGATAN_HARI = 14   # banner "segera habis"
TENGGANG_HARI = 7      # tetap bisa dipakai sesudah tanggal habis
CACHE_DETIK = 300


class LisensiError(ValueError):
    pass


# ---------- kode perangkat ----------
def machine_id() -> str:
    """ID unik komputer ini yang stabil (tidak berubah saat ganti RAM/disk)."""
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                v = Path(p).read_text().strip()
                if v:
                    return v
            except OSError:
                pass
    except Exception:
        pass
    return f"mac-{uuid.getnode():x}"


def kode_perangkat(mid: str | None = None) -> str:
    h = hashlib.sha256(f"{PRODUK}|{mid or machine_id()}".encode()).hexdigest().upper()[:16]
    return "QM-" + "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _norm_kode(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


# ---------- penerbitan (sisi penerbit) ----------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def buat_pasangan() -> tuple[str, str]:
    """(private_pem, public_b64)"""
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pem, _b64(pub)


def terbitkan(private_pem: str, toko: str, perangkat: str, sampai: str | None, terbit: date | None = None) -> str:
    toko = (toko or "").strip()
    if not toko:
        raise LisensiError("Nama toko wajib diisi")
    if not re.fullmatch(r"QM[0-9A-F]{16}", _norm_kode(perangkat)):
        raise LisensiError("Kode perangkat tidak valid (contoh: QM-1A2B-3C4D-5E6F-7A8B)")
    if sampai:
        try:
            date.fromisoformat(sampai)
        except ValueError:
            raise LisensiError("Tanggal habis harus berformat AAAA-BB-HH") from None
    kode = _norm_kode(perangkat)
    payload = {
        "p": PRODUK, "toko": toko[:80], "dev": "QM-" + "-".join(kode[2 + i:6 + i] for i in range(0, 16, 4)),
        "terbit": (terbit or date.today()).isoformat(), "sampai": sampai or None,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return f"{PREFIX}.{_b64(raw)}.{_b64(key.sign(raw))}"


# ---------- reset kata sandi (hanya penerbit) ----------
# Pelanggan membuka /lupa-sandi dan mendapat kode tantangan. Hanya penerbit (pemegang kunci privat) yang bisa
# menandatangani token untuk tantangan + kode perangkat itu. Token sekali pakai karena tantangan diganti setelah dipakai.
PREFIX_RESET = "QMRST1"
_ALFABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # tanpa huruf/angka yang mudah tertukar (I, O, 0, 1)
RESET_HARI = 2                                  # token berlaku sampai akhir hari ke-2 sejak diterbitkan
TANTANGAN_HARI = 7                              # tantangan lama diganti otomatis


def _norm_tantangan(v: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def terbitkan_reset(private_pem: str, perangkat: str, tantangan: str, hari_ini: date | None = None) -> str:
    kode = _norm_kode(perangkat)
    if not re.fullmatch(r"QM[0-9A-F]{16}", kode):
        raise LisensiError("Kode perangkat tidak valid (contoh: QM-1A2B-3C4D-5E6F-7A8B)")
    t = _norm_tantangan(tantangan)
    if len(t) != 8:
        raise LisensiError("Kode tantangan harus 8 karakter")
    payload = {
        "p": PRODUK, "r": "reset", "dev": "QM-" + "-".join(kode[2 + i:6 + i] for i in range(0, 16, 4)), "t": t,
        "exp": ((hari_ini or date.today()) + timedelta(days=RESET_HARI)).isoformat(),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return f"{PREFIX_RESET}.{_b64(raw)}.{_b64(key.sign(raw))}"


def periksa_reset(token: str, perangkat: str, tantangan: str, hari_ini: date, pubkey_b64: str | None = None) -> None:
    """Melempar LisensiError bila token bukan buatan penerbit, bukan untuk komputer/tantangan ini, atau kedaluwarsa."""
    bagian = "".join((token or "").split()).split(".")
    if len(bagian) != 3 or bagian[0] != PREFIX_RESET:
        raise LisensiError("Token reset tidak dikenal")
    try:
        raw, sig = _unb64(bagian[1]), _unb64(bagian[2])
        Ed25519PublicKey.from_public_bytes(_unb64(pubkey_b64 or PUBLIC_KEY_B64)).verify(sig, raw)
        d = json.loads(raw)
    except InvalidSignature:
        raise LisensiError("Token reset tidak sah") from None
    except Exception:
        raise LisensiError("Token reset rusak atau terpotong, salin ulang seluruhnya") from None
    if d.get("p") != PRODUK or d.get("r") != "reset":
        raise LisensiError("Token reset tidak sah")
    if _norm_kode(d.get("dev", "")) != _norm_kode(perangkat):
        raise LisensiError("Token ini untuk komputer lain")
    if d.get("t") != _norm_tantangan(tantangan):
        raise LisensiError("Token ini untuk kode tantangan yang berbeda atau sudah dipakai")
    try:
        if hari_ini > date.fromisoformat(d.get("exp", "")):
            raise LisensiError("Token reset sudah kedaluwarsa, minta token baru")
    except ValueError:
        raise LisensiError("Token reset rusak") from None


def tantangan_reset(settings, hari_ini: date | None = None) -> str:
    """Kode tantangan aktif; dibuat bila belum ada atau sudah lama. Dimuat ulang tidak mengganti kodenya."""
    import secrets
    hari_ini = hari_ini or date.today()
    f = settings.data_dir / "reset-tantangan.txt"
    try:
        kode, tgl = f.read_text(encoding="utf-8").split()
        if len(kode) == 8 and (hari_ini - date.fromisoformat(tgl)).days <= TANTANGAN_HARI:
            return kode
    except (OSError, ValueError):
        pass
    kode = "".join(secrets.choice(_ALFABET) for _ in range(8))
    f.write_text(f"{kode} {hari_ini.isoformat()}\n", encoding="utf-8")
    return kode


def hapus_tantangan(settings) -> None:
    try:
        (settings.data_dir / "reset-tantangan.txt").unlink()
    except OSError:
        pass


# ---------- pemeriksaan ----------
@dataclass(frozen=True)
class Status:
    kode: str          # aktif | segera_habis | masa_tenggang | kedaluwarsa | jam_mundur | belum_ada | tidak_valid | salah_perangkat
    pesan: str
    boleh_pakai: bool
    toko: str = ""
    sampai: str | None = None
    sisa_hari: int | None = None


def urai(kunci: str, pubkey_b64: str | None = None) -> dict:
    """Verifikasi tanda tangan lalu kembalikan isinya. Melempar LisensiError bila tidak sah."""
    s = "".join((kunci or "").split())
    bagian = s.split(".")
    if len(bagian) != 3 or bagian[0] != PREFIX:
        raise LisensiError("Format kunci lisensi tidak dikenal")
    try:
        raw, sig = _unb64(bagian[1]), _unb64(bagian[2])
        pub = Ed25519PublicKey.from_public_bytes(_unb64(pubkey_b64 or PUBLIC_KEY_B64))
        pub.verify(sig, raw)
        data = json.loads(raw)
    except InvalidSignature:
        raise LisensiError("Kunci lisensi tidak sah (tanda tangan tidak cocok)") from None
    except Exception:
        raise LisensiError("Kunci lisensi rusak atau terpotong, salin ulang seluruhnya") from None
    if data.get("p") != PRODUK:
        raise LisensiError("Kunci ini bukan untuk Q-mas")
    return data


def periksa(
    kunci: str, perangkat: str, hari_ini: date, pubkey_b64: str | None = None, terakhir_terlihat: date | None = None
) -> Status:
    if not (kunci or "").strip():
        return Status("belum_ada", "Aplikasi belum diaktifkan. Kirim Kode Perangkat ke penyedia untuk mendapat kunci lisensi.", False)
    try:
        d = urai(kunci, pubkey_b64)
    except LisensiError as e:
        return Status("tidak_valid", str(e), False)
    toko = d.get("toko", "")
    if _norm_kode(d.get("dev", "")) != _norm_kode(perangkat):
        return Status("salah_perangkat", "Kunci lisensi ini untuk komputer lain. Kirim Kode Perangkat komputer ini untuk mendapat kunci baru.", False, toko)
    if not d.get("sampai"):
        return Status("aktif", "Lisensi aktif (tanpa batas waktu).", True, toko)
    try:
        sampai = date.fromisoformat(d["sampai"])
    except ValueError:
        return Status("tidak_valid", "Tanggal pada lisensi tidak valid", False, toko)
    if terakhir_terlihat and hari_ini < terakhir_terlihat - timedelta(days=1):
        return Status("jam_mundur", "Tanggal komputer tampak diundur. Perbaiki tanggal dan jam Windows, lalu muat ulang halaman.", False, toko, d["sampai"])
    sisa = (sampai - hari_ini).days
    if sisa > PERINGATAN_HARI:
        return Status("aktif", f"Lisensi aktif sampai {sampai:%d-%m-%Y}.", True, toko, d["sampai"], sisa)
    if sisa >= 0:
        return Status("segera_habis", f"Lisensi habis dalam {sisa} hari ({sampai:%d-%m-%Y}). Hubungi penyedia untuk perpanjangan.", True, toko, d["sampai"], sisa)
    if sisa >= -TENGGANG_HARI:
        sisa_t = TENGGANG_HARI + sisa
        return Status("masa_tenggang", f"Lisensi sudah habis. Masa tenggang tinggal {sisa_t} hari, segera perpanjang.", True, toko, d["sampai"], sisa)
    return Status("kedaluwarsa", f"Lisensi habis pada {sampai:%d-%m-%Y}. Perpanjang untuk melanjutkan. Data Anda tetap aman.", False, toko, d["sampai"], sisa)


# ---------- penghubung ke aplikasi ----------
def baca_kunci(settings) -> str:
    try:
        return settings.lisensi_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def simpan_kunci(settings, kunci: str) -> None:
    settings.lisensi_file.write_text("".join(kunci.split()) + "\n", encoding="utf-8")


def _terakhir_terlihat(settings) -> date | None:
    from contextlib import closing

    from .db import connect

    try:
        with closing(connect(settings.db_path)) as c:
            r = c.execute(
                "SELECT MAX(d) FROM (SELECT MAX(tanggal) AS d FROM transactions UNION ALL SELECT MAX(waktu) FROM audit_log)"
            ).fetchone()
        return datetime.strptime(r[0][:10], "%Y-%m-%d").date() if r and r[0] else None
    except Exception:
        return None


def status_sekarang(settings, hari_ini: date | None = None) -> Status:
    if not settings.lisensi_wajib:
        return Status("aktif", "Lisensi tidak diwajibkan.", True)
    return periksa(
        baca_kunci(settings), kode_perangkat(), hari_ini or date.today(), settings.lisensi_pubkey,
        _terakhir_terlihat(settings),
    )


def status_cache(app) -> Status:
    import time

    now = time.monotonic()
    c = getattr(app.state, "lisensi_cache", None)
    if c and now - c[0] < CACHE_DETIK:
        return c[1]
    st = status_sekarang(app.state.settings)
    app.state.lisensi_cache = (now, st)
    return st


def reset_cache(app) -> None:
    app.state.lisensi_cache = None
