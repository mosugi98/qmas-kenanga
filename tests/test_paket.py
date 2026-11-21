import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import buat_paket  # noqa: E402


def _embed_zip(tmp_path, nama="python312"):
    p = tmp_path / "embed.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("python.exe", "MZ")
        z.writestr(f"{nama}.zip", "PK")
        z.writestr(f"{nama}._pth", f"{nama}.zip\n.\n#import site\n")
    return p


def test_pth_diatur_agar_app_dan_site_packages_terbaca(tmp_path):
    stage = tmp_path / "Qmas"
    stage.mkdir()
    py = buat_paket._siapkan_python(stage, "3.12.10", str(_embed_zip(tmp_path)))
    isi = (py / "python312._pth").read_text().split()
    assert isi == ["python312.zip", ".", r"Lib\site-packages", "..", "import", "site"]


def test_bukan_paket_embeddable_ditolak(tmp_path):
    p = tmp_path / "salah.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("x.txt", "x")
    stage = tmp_path / "Qmas"
    stage.mkdir()
    with pytest.raises(SystemExit):
        buat_paket._siapkan_python(stage, "3.12.10", str(p))


def test_skrip_bat_crlf_dan_tanpa_kunci_privat():
    for isi in (buat_paket.PASANG, buat_paket.JALANKAN_OTOMATIS):
        assert b"\r\n" in buat_paket._crlf(isi) and b"\n" not in buat_paket._crlf(isi).replace(b"\r\n", b"")
    assert "private" not in buat_paket.PASANG.lower()


def test_penerbit_cli_roundtrip(tmp_path):
    pen = ROOT / "tools" / "penerbit.py"
    pem = tmp_path / "k.pem"
    subprocess.run([sys.executable, str(pen), "keygen", "--out", str(pem)], check=True, capture_output=True)
    assert pem.exists()
    again = subprocess.run([sys.executable, str(pen), "keygen", "--out", str(pem)], capture_output=True, text=True)
    assert again.returncode != 0 and "tidak ditimpa" in (again.stderr + again.stdout).lower()   # tidak menimpa
    out = subprocess.run(
        [sys.executable, str(pen), "terbit", "--kunci", str(pem), "--toko", "Toko A", "--perangkat",
         "QM-1A2B-3C4D-5E6F-7A8B", "--selamanya"], capture_output=True, text=True, cwd=tmp_path)
    assert out.returncode == 0 and "QMAS1." in out.stdout and (tmp_path / "lisensi-toko-a.key").exists()


def test_generator_interaktif(tmp_path):
    pen = ROOT / "tools" / "penerbit.py"
    pem = tmp_path / "lisensi-private.pem"
    subprocess.run([sys.executable, str(pen), "keygen", "--out", str(pem)], check=True, capture_output=True)
    # kode salah dulu, lalu benar; masa berlaku "1 tahun" (pilih 3); tidak membuat lagi
    masukan = "Toko =Maju\nsalah\nQM-1A2B-3C4D-5E6F-7A8B\n3\nt\n"
    r = subprocess.run([sys.executable, str(pen), "interaktif", "--kunci", str(pem)],
                       input=masukan, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Kode tidak valid" in r.stdout and "QMAS1." in r.stdout
    assert (tmp_path / "lisensi-toko-maju.key").exists()
    # riwayat tercatat dan nama berawalan '=' dinetralkan
    from_csv = (tmp_path / "riwayat-lisensi.csv").read_text(encoding="utf-8-sig")
    assert "QM-1A2B-3C4D-5E6F-7A8B" in from_csv and "'=Maju" not in from_csv and "Toko =Maju" in from_csv


def test_generator_tanpa_kunci_privat(tmp_path):
    pen = ROOT / "tools" / "penerbit.py"
    r = subprocess.run([sys.executable, str(pen), "interaktif", "--kunci", str(tmp_path / "tidak-ada.pem")],
                       input="", capture_output=True, text=True)
    assert r.returncode != 0 and "tidak ditemukan" in r.stderr + r.stdout
