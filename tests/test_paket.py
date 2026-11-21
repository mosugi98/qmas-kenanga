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
    masukan = "Toko =Maju\nsalah\nQM-1A2B-3C4D-5E6F-7A8B\n\n3\nt\n"   # baris kosong = bukan perpanjangan
    r = subprocess.run([sys.executable, str(pen), "interaktif", "--kunci", str(pem)],
                       input=masukan, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Kode tidak valid" in r.stdout and "QMAS1." in r.stdout
    assert (tmp_path / "lisensi-toko-maju.key").exists()
    # riwayat tercatat dan nama berawalan '=' dinetralkan
    from_csv = (tmp_path / "riwayat-lisensi.csv").read_text(encoding="utf-8-sig")
    assert "QM-1A2B-3C4D-5E6F-7A8B" in from_csv and "'=Maju" not in from_csv and "Toko =Maju" in from_csv


def test_generator_perpanjangan_menyambung_dari_tanggal_habis(tmp_path):
    from datetime import date, timedelta
    from app import lisensi
    pen = ROOT / "tools" / "penerbit.py"
    pem = tmp_path / "lisensi-private.pem"
    subprocess.run([sys.executable, str(pen), "keygen", "--out", str(pem)], check=True, capture_output=True)
    lama = date.today() + timedelta(days=10)
    masukan = f"Toko Maju\nQM-1A2B-3C4D-5E6F-7A8B\n{lama.isoformat()}\n1\nt\n"   # 30 hari disambung dari tanggal lama
    r = subprocess.run([sys.executable, str(pen), "interaktif", "--kunci", str(pem)],
                       input=masukan, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    kunci = (tmp_path / "lisensi-toko-maju.key").read_text().strip()
    d = lisensi.urai(kunci, pub_dari(pem))
    assert d["sampai"] == (lama + timedelta(days=30)).isoformat()


def pub_dari(pem):
    from cryptography.hazmat.primitives import serialization
    from app.lisensi import _b64
    k = serialization.load_pem_private_key(pem.read_bytes(), password=None)
    return _b64(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def test_reset_password_alat_penerbit(tmp_path):
    from datetime import date
    from app import lisensi
    pen = ROOT / "tools" / "penerbit.py"
    pem = tmp_path / "lisensi-private.pem"
    subprocess.run([sys.executable, str(pen), "keygen", "--out", str(pem)], check=True, capture_output=True)
    masukan = "salah\nabcd2345\nQM-1A2B-3C4D-5E6F-7A8B\nabcd2345\nt\n"
    r = subprocess.run([sys.executable, str(pen), "reset-interaktif", "--kunci", str(pem)],
                       input=masukan, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Kode perangkat tidak valid" in r.stdout
    token = next(x for x in r.stdout.split() if x.startswith("QMRST1."))
    lisensi.periksa_reset(token, "QM-1A2B-3C4D-5E6F-7A8B", "ABCD2345", date.today(), pub_dari(pem))
    assert "QM-1A2B-3C4D-5E6F-7A8B" in (tmp_path / "riwayat-reset.csv").read_text(encoding="utf-8-sig")


def test_reset_password_bat_hanya_di_tools():
    assert (ROOT / "tools" / "reset-password.bat").exists()
    assert "reset-interaktif" in (ROOT / "tools" / "reset-password.bat").read_text()


def test_zip_update_tanpa_data_dan_kunci(tmp_path):
    import zipfile
    sys.path.insert(0, str(ROOT / "tools"))
    import buat_update
    z = zipfile.ZipFile(buat_update.buat(tmp_path, "v9"))
    nama = z.namelist()
    assert "app/main.py" in nama and "run.py" in nama and "BACA-DULU.txt" in nama
    assert not any(n.startswith("data/") or n.endswith(".pem") or "__pycache__" in n or n.startswith("tests/") for n in nama)


def test_workflow_rilis_ada():
    isi = (ROOT / ".github" / "workflows" / "rilis.yml").read_text(encoding="utf-8")
    assert "buat_paket.py" in isi and "windows-latest" in isi and "tags:" in isi
    assert "pem" not in isi.lower().replace("pembuat", "")   # tidak ada urusan dengan kunci privat


def test_generator_tanpa_kunci_privat(tmp_path):
    pen = ROOT / "tools" / "penerbit.py"
    r = subprocess.run([sys.executable, str(pen), "interaktif", "--kunci", str(tmp_path / "tidak-ada.pem")],
                       input="", capture_output=True, text=True)
    assert r.returncode != 0 and "tidak ditemukan" in r.stderr + r.stdout
