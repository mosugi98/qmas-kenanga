# Q-mas

Aplikasi toko emas berbasis web. Setiap perhiasan punya kode unik dan label QR/barcode, sehingga stok, kasir, dan laporan tertib tanpa catatan kertas. Bisa dipasang di komputer toko (WiFi/LAN, data tidak keluar ke internet) atau dihosting online agar bisa diakses dari mana saja.

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

## Hosting online (akses dari mana saja)

Set `TOKOEMAS_ONLINE=1` dan aplikasi berjalan sebagai layanan web di belakang proxy HTTPS. GitHub Pages tidak bisa menjalankan aplikasi ini (hanya situs statis); yang dipakai adalah image Docker yang dibangun GitHub dan dijalankan di server/hosting.

Perbedaan mode online: tidak dibatasi jaringan lokal; lisensi per-komputer tidak berlaku; akun pemilik pertama hanya bisa dibuat dengan **token pengaturan** (`TOKOEMAS_SETUP_TOKEN`) agar orang asing tidak bisa mengambil alih; login dibatasi (5 gagal per akun / 30 per alamat dalam 15 menit); header keamanan dan HSTS aktif.

**Opsi A, server sendiri (VPS, paling hemat dan datanya di tangan Anda)**
1. Server Linux dengan Docker; arahkan DNS domain ke IP server.
2. `git clone https://github.com/mosugi98/qmas-kenanga && cd qmas-kenanga && cp .env.example .env`, isi `DOMAIN` dan `TOKOEMAS_SETUP_TOKEN` (buat acak: `openssl rand -hex 24`).
3. `docker compose up -d`. Caddy mengurus sertifikat HTTPS otomatis. Buka `https://DOMAIN/setup`.
4. Update: `docker compose pull && docker compose up -d`. Workflow **Docker** membangun image ke `ghcr.io/mosugi98/qmas-kenanga` di tiap push ke `main`.

**Opsi B, Render.com**: Dashboard > New > Blueprint > pilih repo ini (`render.yaml`). Disk persisten (tempat database) butuh paket berbayar; tanpa disk, data hilang tiap deploy ulang. Token setup dibuat otomatis, lihat di Environment.

Data (database SQLite, foto, backup harian) ada di volume `/data`. Backup juga bisa diunduh pemilik dari aplikasi; simpan salinannya di luar server. Jangan membuka port 8000 langsung ke internet; hanya proxy yang boleh menjangkaunya.

## Rilis dan pemasangan dari GitHub

Aplikasi ini untuk jaringan toko (bukan layanan cloud), jadi "deploy" berarti membuat paket yang bisa dipasang di komputer toko.
GitHub Actions melakukannya otomatis:

1. Sekali saja: di GitHub buka **Settings > Actions > General > Workflow permissions**, pilih **Read and write permissions**.
2. Rilis baru: `git tag v2.1 && git push origin v2.1`.
3. Workflow **Rilis** menjalankan tes, membangun paket siap-jalan Windows (Python portable + dependensi) dan ZIP update, lalu menaruhnya di halaman **Releases**.
4. Komputer toko baru: unduh `Q-mas-SiapJalan-*.zip`, ekstrak, klik dua kali `jalankan.bat`. Toko yang sudah memakai: unduh `Q-mas-update-*.zip` dan timpa ke folder Q-mas (folder `data` aman).

Workflow **Tes** berjalan di setiap push. Kunci privat lisensi tidak pernah masuk repo maupun workflow; kunci lisensi pelanggan tetap diterbitkan manual lewat `tools/generator_lisensi.bat`, dan reset kata sandi lewat `tools/reset-password.bat`.

## Lisensi

- Pelanggan membuka halaman **Lisensi** dan mengirim **Kode Perangkat** (`QM-XXXX-XXXX-XXXX-XXXX`).
- Penerbit membuat kunci dengan `tools/generator_lisensi.bat` (atau `python tools/penerbit.py terbit ...`), lalu pelanggan menempelnya dan menekan **Aktifkan**.
- Kunci ditandatangani Ed25519. Kunci publik tertanam di `app/lisensi.py`; **kunci privat tidak pernah masuk repo atau paket pelanggan** (`*.pem` diabaikan git).
- Peringatan 14 hari sebelum habis, masa tenggang 7 hari, lalu aplikasi terkunci. Data tetap aman dan pemilik masih bisa mengunduh backup. Pengunduran jam komputer terdeteksi.
- **Langganan**: masa berlaku lisensi berfungsi sebagai langganan (30 hari, 90 hari, 1 tahun). Saat pelanggan membayar, penerbit menjalankan `generator_lisensi.bat` dan mengisi tanggal habis lisensi lama; perpanjangan menyambung dari tanggal itu sehingga sisa hari tidak hangus. Pelanggan menempel kunci baru di halaman Lisensi tanpa restart.
- **Reset kata sandi (hanya penerbit)**: pelanggan membuka **Masuk > Lupa kata sandi** dan mengirim Kode Perangkat + Kode Tantangan. Penerbit menjalankan `tools/reset-password.bat` dan mengirim balik token. Token hanya sah untuk komputer dan tantangan itu, sekali pakai, berlaku 2 hari.
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
tests/               pytest
tools/               penerbit.py, generator_lisensi.bat, reset-password.bat, buat_paket.py, buat_update.py (tidak ikut paket pelanggan)
.github/workflows/   tes.yml (CI), rilis.yml (bangun paket Windows saat tag v*)
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
