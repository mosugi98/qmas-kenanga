"""Pembuat PAKET SIAP JALAN Q-mas untuk komputer Windows lain (tanpa Python, tanpa internet di sisi tujuan).

Jalankan di PC Windows yang punya internet (butuh Python 3.10+ dan pip):
    python tools\\buat_paket.py
    python tools\\buat_paket.py --toko "Toko Emas Maju"
    python tools\\buat_paket.py --python-zip C:\\unduhan\\python-3.12.10-embed-amd64.zip   (tanpa unduh)

Hasil: dist\\Q-mas-SiapJalan-<tanggal>.zip. Cukup salin zip itu ke komputer tujuan, ekstrak, lalu
klik dua kali jalankan.bat. Paket TIDAK memuat kunci privat lisensi.
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_DEFAULT = "3.12.10"
RUNTIME = ["run.py", "requirements.txt", "PANDUAN.md"]

JALANKAN = r"""@echo off
setlocal
cd /d "%~dp0"
title Q-mas - jangan ditutup selama toko buka
"python\python.exe" run.py
echo.
echo Aplikasi berhenti. Jika ini tidak disengaja, lihat pesan di atas.
pause
"""

JALANKAN_OTOMATIS = r"""@echo off
rem Dipakai oleh Task Scheduler (mode server). Menjalankan ulang otomatis bila aplikasi berhenti.
setlocal
cd /d "%~dp0"
if not exist "data" mkdir "data"
:ulang
echo [%date% %time%] mulai >> "data\q-mas.log"
"python\python.exe" run.py >> "data\q-mas.log" 2>&1
echo [%date% %time%] berhenti, mulai ulang 10 detik lagi >> "data\q-mas.log"
timeout /t 10 /nobreak >nul
goto ulang
"""

KODE_PERANGKAT = r"""@echo off
setlocal
cd /d "%~dp0"
echo Kode Perangkat komputer ini:
echo.
"python\python.exe" run.py --kode-perangkat
echo.
echo Kirim kode di atas ke penyedia Q-mas untuk mendapat kunci lisensi.
pause
"""

PASANG = r"""@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Pasang Q-mas (mode server)
net session >nul 2>&1
if errorlevel 1 (
  echo Skrip ini harus dijalankan sebagai Administrator.
  echo Klik kanan pasang-otomatis.bat lalu pilih "Run as administrator".
  pause
  exit /b 1
)
set "PORT=8443"
echo [1/3] Membuka port %PORT% di firewall...
netsh advfirewall firewall delete rule name="Q-mas" >nul 2>&1
netsh advfirewall firewall add rule name="Q-mas" dir=in action=allow protocol=TCP localport=%PORT% >nul
if errorlevel 1 (echo       GAGAL membuat aturan firewall) else (echo       OK)
echo [2/3] Mendaftarkan Q-mas agar jalan otomatis saat komputer menyala (tanpa perlu login)...
schtasks /Delete /TN "Q-mas" /F >nul 2>&1
schtasks /Create /TN "Q-mas" /TR "\"%~dp0jalankan-otomatis.bat\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F >nul
if errorlevel 1 (echo       GAGAL mendaftarkan tugas) else (echo       OK)
echo [3/3] Membuat pintasan di Desktop...
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('CommonDesktopDirectory');$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\Q-mas.lnk');$s.TargetPath='%~dp0jalankan.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1
echo       OK
echo.
echo Menjalankan Q-mas sekarang...
schtasks /Run /TN "Q-mas" >nul 2>&1
timeout /t 8 /nobreak >nul
echo.
echo Selesai. Buka salah satu alamat ini dari perangkat di WiFi toko:
"python\python.exe" run.py --alamat
echo.
echo Aplikasi kini jalan sendiri tiap komputer dinyalakan. Untuk melihatnya langsung, buka data\q-mas.log.
pause
"""

HAPUS = r"""@echo off
setlocal
net session >nul 2>&1
if errorlevel 1 (
  echo Jalankan sebagai Administrator.
  pause
  exit /b 1
)
schtasks /End /TN "Q-mas" >nul 2>&1
schtasks /Delete /TN "Q-mas" /F
netsh advfirewall firewall delete rule name="Q-mas" >nul 2>&1
echo Jalan-otomatis dan aturan firewall Q-mas dihapus. Data di folder data tidak diubah.
pause
"""

BACA_DULU = """Q-MAS - PAKET SIAP JALAN
========================
Tidak perlu memasang Python dan tidak perlu internet.

PEMASANGAN DI KOMPUTER BARU
1. Ekstrak zip ke folder biasa, misalnya C:\\Qmas (bukan dari dalam zip, bukan di folder Downloads/Desktop).
2. Klik dua kali jalankan.bat untuk mencoba. Jendela menampilkan alamat, misalnya https://192.168.1.20:8443.
3. Aplikasi meminta lisensi pada pemakaian pertama. Salin "Kode Perangkat" yang tampil di halaman Lisensi
   (atau klik dua kali kode-perangkat.bat), kirim ke penyedia, lalu tempel kunci yang Anda terima.
4. Agar jalan sendiri saat komputer menyala (mode server): klik kanan pasang-otomatis.bat > Run as administrator.
   Ini membuka port 8443 di firewall, mendaftarkan jalan-otomatis, dan membuat pintasan Desktop.
   Untuk melepas: hapus-otomatis.bat.
5. Beri komputer ini alamat IP tetap di router (reservasi DHCP) agar alamat aplikasi tidak berubah.

PINDAH KE KOMPUTER LAIN
- Lisensi terikat ke satu komputer. Salin folder data (database, foto) ke komputer baru, minta kunci lisensi baru
  memakai Kode Perangkat komputer baru, lalu tempel di halaman Lisensi.

UPDATE VERSI
- Ekstrak paket baru ke folder yang sama dan timpa file yang sama. Folder data tidak ikut tertimpa.

Panduan lengkap: PANDUAN.md
"""


def _crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def _unduh(url: str) -> bytes:
    print(f"Mengunduh {url} ...")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.read()
    except Exception as e:
        sys.exit(
            f"Gagal mengunduh Python portable: {e}\n"
            "Unduh manual berkas 'Windows embeddable package (64-bit)' dari https://www.python.org/downloads/windows/\n"
            "lalu jalankan lagi dengan: --python-zip <lokasi-berkas.zip>"
        )


def _siapkan_python(stage: Path, versi: str, zip_lokal: str | None) -> Path:
    data = Path(zip_lokal).read_bytes() if zip_lokal else _unduh(
        f"https://www.python.org/ftp/python/{versi}/python-{versi}-embed-amd64.zip"
    )
    py = stage / "python"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(py)
    pth = next(py.glob("python*._pth"), None)
    if pth is None:
        sys.exit("Berkas zip bukan paket 'embeddable' Python (python3xx._pth tidak ditemukan).")
    zipname = next(py.glob("python*.zip"), None)
    isi = [(zipname.name if zipname else pth.stem.split("._pth")[0] + ".zip"), ".", r"Lib\site-packages", "..", "import site"]
    pth.write_text("\n".join(isi) + "\n")
    return py


def _pasang_paket(py: Path, versi: str) -> None:
    site = py / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    mm = "".join(versi.split(".")[:2])
    cmd = [
        sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--target", str(site),
        "--platform", "win_amd64", "--python-version", mm, "--implementation", "cp", "--only-binary=:all:",
        "-r", str(ROOT / "requirements.txt"),
    ]
    print("Memasang dependensi untuk Windows 64-bit ...")
    subprocess.run(cmd, check=True)


def _salin_app(stage: Path) -> None:
    for nama in RUNTIME:
        shutil.copy2(ROOT / nama, stage / nama)
    shutil.copytree(
        ROOT / "app", stage / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _periksa(stage: Path) -> None:
    perlu = ["run.py", "app/main.py", "app/lisensi.py", "app/templates/base.html", "app/static/app.css",
             "app/static/vendor/html5-qrcode.min.js", "python/python.exe", "python/Lib/site-packages/fastapi/__init__.py",
             "python/Lib/site-packages/cryptography/__init__.py"]
    hilang = [p for p in perlu if not (stage / p).exists()]
    if hilang:
        sys.exit("Paket tidak lengkap, hilang: " + ", ".join(hilang))
    if "PASANG_KUNCI_PUBLIK_DI_SINI" in (stage / "app/lisensi.py").read_text():
        sys.exit("Kunci publik lisensi belum dipasang di app/lisensi.py")
    for p in stage.rglob("*"):
        if p.name in ("lisensi-private.pem",) or p.suffix == ".pem":
            sys.exit(f"Ada kunci privat di dalam paket: {p}")
    if sys.platform == "win32":
        r = subprocess.run([str(stage / "python/python.exe"), "-c", "import app.main, app.lisensi; print('ok')"],
                           cwd=stage, capture_output=True, text=True)
        if r.returncode != 0 or "ok" not in r.stdout:
            sys.exit("Uji impor gagal di Python portable:\n" + r.stderr)
        print("Uji impor di Python portable: OK")
    else:
        print("(Uji jalan Python portable dilewati: bukan Windows)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python-versi", default=PY_DEFAULT, help=f"versi Python portable (bawaan {PY_DEFAULT})")
    ap.add_argument("--python-zip", help="pakai berkas python-x.y.z-embed-amd64.zip yang sudah diunduh")
    ap.add_argument("--toko", default="Toko Emas Kenanga", help="nama toko awal (ditulis ke data/nama_toko.txt), bawaan Toko Emas Kenanga")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", a.python_versi):
        sys.exit("--python-versi harus seperti 3.12.10")

    out = Path(a.out)
    stage = out / "Qmas"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    py = _siapkan_python(stage, a.python_versi, a.python_zip)
    _pasang_paket(py, a.python_versi)
    _salin_app(stage)
    for nama, isi in {
        "jalankan.bat": JALANKAN, "jalankan-otomatis.bat": JALANKAN_OTOMATIS, "kode-perangkat.bat": KODE_PERANGKAT,
        "pasang-otomatis.bat": PASANG, "hapus-otomatis.bat": HAPUS, "BACA-DULU.txt": BACA_DULU,
    }.items():
        (stage / nama).write_bytes(_crlf(isi))
    if a.toko:
        (stage / "data").mkdir()
        (stage / "data" / "nama_toko.txt").write_text(a.toko.strip()[:60] + "\n", encoding="utf-8")
    _periksa(stage)

    zip_path = out / f"Q-mas-SiapJalan-{date.today().isoformat()}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out).as_posix())
    mb = zip_path.stat().st_size / 1_048_576
    print(f"\nSelesai: {zip_path} ({mb:.0f} MB)")
    print("Salin zip ini ke komputer tujuan, ekstrak, lalu klik dua kali jalankan.bat (atau ikuti BACA-DULU.txt).")


if __name__ == "__main__":
    main()
