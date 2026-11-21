"""Alat PENERBIT lisensi Q-mas (hanya untuk penyedia aplikasi, JANGAN diberikan ke pelanggan).

Contoh:
  python penerbit.py keygen                       # sekali saja: buat pasangan kunci
  python penerbit.py terbit --toko "Toko Emas Maju" --perangkat QM-XXXX-XXXX-XXXX-XXXX --sampai 2027-12-31
  python penerbit.py terbit --toko "Toko Emas Maju" --perangkat QM-... --selamanya
  python penerbit.py periksa QMAS1....            # cek isi sebuah kunci
"""
import argparse
import csv
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:                                   # di repo: pakai modul aplikasi
    sys.path.insert(0, str(HERE.parent))
    from app import lisensi
except ImportError:                    # di paket penerbit: salinan modul ada di samping berkas ini
    sys.path.insert(0, str(HERE))
    import qmas_lisensi as lisensi


def _kunci_privat(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Berkas kunci privat tidak ditemukan: {p}\nJalankan dulu: python penerbit.py keygen")
    return p.read_text()


def _tanya(label: str, default: str = "") -> str:
    try:
        v = input(label).strip()
    except EOFError:
        sys.exit("\nInput dihentikan.")
    return v or default


def _masa_berlaku() -> str | None:
    print("\nMasa berlaku lisensi:")
    print("  1. 30 hari (uji coba)")
    print("  2. 90 hari")
    print("  3. 1 tahun (365 hari)")
    print("  4. Selamanya (tanpa batas waktu)")
    print("  5. Tanggal sendiri")
    while True:
        p = _tanya("Pilih 1-5 [3]: ", "3")
        if p in ("1", "2", "3"):
            return (date.today() + timedelta(days={"1": 30, "2": 90, "3": 365}[p])).isoformat()
        if p == "4":
            return None
        if p == "5":
            t = _tanya("Berlaku sampai (AAAA-BB-HH): ")
            try:
                if date.fromisoformat(t) <= date.today():
                    print("  Tanggal harus setelah hari ini.")
                    continue
                return t
            except ValueError:
                print("  Format tanggal harus AAAA-BB-HH, contoh 2027-12-31.")
                continue
        print("  Pilihan tidak dikenal.")


def _catat(toko: str, perangkat: str, sampai: str | None) -> None:
    """Riwayat penerbitan: riwayat-lisensi.csv di samping alat ini."""
    f = Path.cwd() / "riwayat-lisensi.csv"
    baru = not f.exists()
    aman = lambda v: ("'" + v) if v[:1] in ("=", "+", "-", "@") else v  # noqa: E731
    with open(f, "a", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        if baru:
            w.writerow(["Tanggal terbit", "Toko", "Kode Perangkat", "Berlaku sampai"])
        w.writerow([date.today().isoformat(), aman(toko), perangkat, sampai or "selamanya"])


def _salin(teks: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        subprocess.run(["clip"], input=teks.encode("ascii"), check=True)
        return True
    except Exception:
        return False


def interaktif(kunci_path: str) -> None:
    pem = _kunci_privat(kunci_path)
    print("=" * 60)
    print("  GENERATOR LISENSI Q-MAS")
    print("=" * 60)
    while True:
        toko = _tanya("\nNama toko: ")
        if not toko:
            print("  Nama toko wajib diisi.")
            continue
        while True:
            kode = _tanya("Kode Perangkat pelanggan (QM-XXXX-XXXX-XXXX-XXXX): ").upper()
            if re.fullmatch(r"QM[0-9A-F]{16}", re.sub(r"[^A-Z0-9]", "", kode)):
                break
            print("  Kode tidak valid. Salin persis dari halaman Lisensi atau kode-perangkat.bat milik pelanggan.")
        sampai = _masa_berlaku()
        try:
            key = lisensi.terbitkan(pem, toko, kode, sampai)
        except lisensi.LisensiError as e:
            print(f"  Gagal: {e}")
            continue
        nama = re.sub(r"[^a-z0-9]+", "-", toko.lower()).strip("-") or "toko"
        out = Path.cwd() / f"lisensi-{nama}.key"
        out.write_text(key + "\n")
        _catat(toko, kode, sampai)
        print("\n" + "-" * 60)
        print(f"Toko     : {toko}\nKomputer : {kode}\nBerlaku  : {'selamanya' if not sampai else 'sampai ' + sampai}")
        print("\nKUNCI LISENSI (kirim seluruhnya ke pelanggan):\n")
        print(key)
        print("\n" + "-" * 60)
        print(f"Tersimpan di {out.name} dan dicatat di riwayat-lisensi.csv")
        if _salin(key):
            print("Kunci sudah disalin ke clipboard: tinggal Paste (Ctrl+V) di WhatsApp.")
        if _tanya("\nBuat lisensi lain? (y/t) [t]: ", "t").lower() not in ("y", "ya"):
            return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen"); k.add_argument("--out", default=str(HERE / "lisensi-private.pem"))
    t = sub.add_parser("terbit")
    t.add_argument("--kunci", default=str(HERE / "lisensi-private.pem"))
    t.add_argument("--toko", required=True); t.add_argument("--perangkat", required=True)
    g = t.add_mutually_exclusive_group(required=True)
    g.add_argument("--sampai", help="tanggal habis AAAA-BB-HH"); g.add_argument("--selamanya", action="store_true")
    i = sub.add_parser("interaktif"); i.add_argument("--kunci", default=str(HERE / "lisensi-private.pem"))
    c = sub.add_parser("periksa"); c.add_argument("kunci"); c.add_argument("--perangkat")
    c.add_argument("--pub", help="kunci publik base64 (bawaan: yang tertanam di aplikasi)")
    a = ap.parse_args()

    if a.cmd == "interaktif":
        interaktif(a.kunci)
    elif a.cmd == "keygen":
        out = Path(a.out)
        if out.exists():
            sys.exit(f"{out} sudah ada. Tidak ditimpa (menimpa kunci membuat semua lisensi lama tidak sah).")
        pem, pub = lisensi.buat_pasangan()
        out.write_text(pem)
        print(f"Kunci privat disimpan di: {out}  (RAHASIA, simpan cadangan di tempat aman)")
        print(f"Kunci publik (tempel ke PUBLIC_KEY_B64 di app/lisensi.py lalu rilis ulang aplikasi):\n{pub}")
    elif a.cmd == "terbit":
        try:
            key = lisensi.terbitkan(_kunci_privat(a.kunci), a.toko, a.perangkat, None if a.selamanya else a.sampai)
        except lisensi.LisensiError as e:
            sys.exit(f"Gagal: {e}")
        nama = re.sub(r"[^a-z0-9]+", "-", a.toko.lower()).strip("-") or "toko"
        out = Path.cwd() / f"lisensi-{nama}.key"
        out.write_text(key + "\n")
        print(f"Lisensi untuk {a.toko} ({'tanpa batas waktu' if a.selamanya else 'sampai ' + a.sampai}) disimpan di: {out}\n")
        print(key)
        print("\nKirim kunci di atas ke pelanggan (WhatsApp boleh). Mereka tempel di halaman Lisensi.")
    else:
        try:
            d = lisensi.urai(a.kunci, a.pub)
        except lisensi.LisensiError as e:
            sys.exit(f"TIDAK SAH: {e}")
        print("SAH:", d)
        if a.perangkat:
            st = lisensi.periksa(a.kunci, a.perangkat, date.today(), a.pub)
            print(f"Untuk {a.perangkat}: {st.kode} - {st.pesan}")


if __name__ == "__main__":
    main()
