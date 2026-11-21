# Q-mas

Aplikasi toko emas berbasis web untuk jaringan lokal (WiFi/LAN toko). Setiap perhiasan punya kode unik dan label QR/barcode, sehingga stok, kasir, dan laporan tertib tanpa catatan kertas. Data tersimpan di komputer toko sendiri, tidak keluar ke internet.

## Fitur

| Area | Isi |
|---|---|
| **Beranda** | Penjualan, pembelian, gramasi jual/beli, stok tersedia, harga hari ini, tren harian |
| **Kasir** | Jual, beli dari pelanggan, tukar tambah, beli dari supplier; metode Tunai/Transfer/QRIS; batalkan transaksi (pemilik) |
| **Stok & Katalog** | Foto, kadar, berat, ongkos, status; kode unik bebas (tidak boleh kembar) atau otomatis `GLD-000123` |
| **Label** | Cetak QR, barcode, atau keduanya; ukuran 40/55/80 mm; banyak salinan; cetak banyak perhiasan sekaligus |
| **Buat massal** | Pilih jenis, kadar, gramasi, dan jumlah pcs: kode unik dibuat otomatis (contoh `KNG-CIN-3G5-001`) lalu label dicetak sekaligus (sampai 500 label) |
| **Opname & deteksi kehilangan** | Scan seluruh barang dengan scanner USB; stok awal dicocokkan dengan barang terjual dan barang tersisa, yang tidak ditemukan dilaporkan HILANG (bisa diekspor) |
| **Lacak barang** | Scan satu kode untuk melihat status, riwayat nota, dan hasil opname |
| **Scan** | Kamera HP lewat browser, atau scanner USB/Bluetooth; hasil scan langsung masuk Kasir |
| **Harga Emas** | Harga harian bersifat opsional; bila tidak diisi, kasir mengisi harga per gram sendiri |
| **Ekspor** | Stok dan transaksi ke Excel (.xlsx) atau CSV (pemilik) |
| **Pengguna & Backup** | Peran pemilik/kasir, backup manual dan otomatis harian |
| **Lisensi** | Kunci terikat ke satu komputer, dicek offline, bisa berbatas waktu |

## Teknologi

FastAPI, Jinja2, SQLite (WAL), HTTPS dengan sertifikat swasta, tanpa build frontend. Uang disimpan sebagai rupiah bulat (integer). Python 3.10 atau lebih baru.

## Menjalankan untuk pengembangan

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt      # Windows: .venv\Scripts\pip
.venv/bin/python -m pytest -q                       # semua tes
TOKOEMAS_DATA=/tmp/demo .venv/bin/python run.py     # jalan di https://<IP>:8443
```

- Data (database, foto, sertifikat, backup) disimpan di folder `data/` di samping aplikasi, atau lokasi lain lewat variabel `TOKOEMAS_DATA`.
- Aplikasi hanya menerima koneksi dari jaringan lokal.
- Aplikasi asli selalu mewajibkan lisensi. Untuk mencoba, terbitkan kunci dengan `tools/penerbit.py` (butuh kunci privat penerbit), lalu tempel di halaman **/lisensi**.
- Opsi `python run.py --kode-perangkat` menampilkan kode komputer, `--alamat` menampilkan alamat akses.

## Memasang di komputer toko

Panduan lengkap untuk pengguna ada di [PANDUAN.md](PANDUAN.md). Ringkasnya ada dua jalur.

**1. Dengan Python terpasang.** Ekstrak ke `C:\Qmas`, klik kanan `instalasi.bat` lalu Run as administrator. Skrip mengecek prasyarat, memasang paket, membuka firewall port 8443, dan membuat pintasan Desktop. `instalasi.bat /cek` hanya mengecek tanpa memasang.

**2. Paket siap jalan (tanpa Python dan tanpa internet di komputer tujuan).** Di satu PC Windows ber-internet:

```bat
buat-paket.bat --toko "Nama Toko"
```

Hasilnya `dist\Q-mas-SiapJalan-<tanggal>.zip` berisi Python portable, semua paket, dan aplikasi. Di komputer tujuan: ekstrak, klik `jalankan.bat`, dan untuk mode server klik kanan `pasang-otomatis.bat` lalu Run as administrator (firewall dan jalan otomatis saat komputer menyala).

## Lisensi

- Pelanggan membuka halaman **Lisensi** dan mengirim **Kode Perangkat** (`QM-XXXX-XXXX-XXXX-XXXX`).
- Penerbit membuat kunci dengan `tools/generator_lisensi.bat` (atau `python tools/penerbit.py terbit ...`), lalu pelanggan menempelnya dan menekan **Aktifkan**.
- Kunci ditandatangani Ed25519. Kunci publik tertanam di `app/lisensi.py`; **kunci privat tidak pernah masuk repo atau paket pelanggan** (`*.pem` diabaikan git).
- Peringatan 14 hari sebelum habis, masa tenggang 7 hari, lalu aplikasi terkunci. Data tetap aman dan pemilik masih bisa mengunduh backup. Pengunduran jam komputer terdeteksi.
- Pindah komputer atau instal ulang Windows membutuhkan kunci baru.

> Karena kode berupa Python, lisensi ini mencegah penyalinan biasa, bukan pembobolan oleh ahli. Untuk perlindungan lebih kuat, build `.exe` dengan `build.bat` (PyInstaller).

## Struktur

```
app/
  main.py            pembuatan aplikasi, middleware (jaringan lokal, lisensi)
  lisensi.py         kode perangkat, penerbitan dan verifikasi kunci
  routes/            halaman dan API (kasir, katalog, label, ekspor, lisensi, ...)
  services/          logika bisnis (items, transactions, bulk, stocktake, export, backup, ...)
  templates/         Jinja2
  static/            CSS, font, pustaka pemindai
tests/               pytest (221 tes)
tools/               penerbit.py, generator_lisensi.bat, buat_paket.py (tidak ikut paket pelanggan)
docs/                QA-manual.md (daftar uji manual sebelum rilis), spesifikasi dan rencana
run.py               titik masuk
```

## Pengujian

- `python -m pytest -q` menjalankan tes otomatis (database sementara, tanpa jaringan).
- [docs/QA-manual.md](docs/QA-manual.md) berisi daftar uji manual di perangkat sebenarnya (kamera HP, scanner, cetak label, lisensi, paket siap jalan).

## Keamanan singkat

- Hanya jaringan lokal yang boleh mengakses; sesi berbasis cookie bertanda tangan, HTTPS saja.
- Kata sandi disimpan sebagai hash; log aktivitas mencatat transaksi, perubahan kode, ekspor, dan aktivasi lisensi.
- Ekspor dan pengelolaan pengguna hanya untuk peran pemilik. Sel yang diawali `=`, `+`, `-`, `@` dinetralkan di CSV agar tidak dibaca Excel sebagai rumus.
- Jangan membuka aplikasi ke internet publik; ia dirancang untuk jaringan toko.

## Hak cipta

Hak cipta © Moh Suprayogi.
