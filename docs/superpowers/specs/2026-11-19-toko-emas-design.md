# Aplikasi Toko Emas — Desain

Tanggal: 2026-11-19
Status: menunggu review pengguna

## 1. Tujuan

Aplikasi web untuk satu toko emas, diakses lewat WiFi/LAN lokal. Fitur:

1. Dashboard
2. Total penjualan
3. Total pembelian
4. Gramasi jual
5. Gramasi beli
6. Identifikasi perhiasan dengan foto dan kode unik
7. Scan barcode/QR untuk identifikasi

## 2. Keputusan yang sudah disepakati

- Semua data diinput langsung di aplikasi (tidak ada impor data lama).
- Jenis transaksi: jual, beli dari pelanggan, tukar tambah, beli dari supplier.
- Harga: harga harian per gram per kadar (jual dan beli) + ongkos. Kasir boleh mengubah harga saat transaksi.
- Identifikasi = katalog foto + kode unik. Pencarian berbasis foto/AI **tidak** termasuk.
- Scanner: kamera HP lewat browser dan scanner USB/Bluetooth.
- Server: 1 PC Windows di toko, diakses 2–5 perangkat.
- Stack: Python (FastAPI) + SQLite + halaman web ringan, dibungkus `.exe` Windows.

## 3. Arsitektur

- Satu program Python (FastAPI) berjalan di PC toko dan melayani halaman web lewat HTTPS pada port 8443.
- Perangkat lain membuka `https://<IP-PC-toko>:8443`. PC toko diberi IP tetap.
- HTTPS memakai sertifikat lokal (self-signed). Ini wajib karena browser hanya mengizinkan kamera pada HTTPS. Setiap HP menerima peringatan sertifikat satu kali.
- Data: satu file SQLite. Foto perhiasan: folder `foto/` di samping database.
- Backup: tombol "Backup" membuat satu zip berisi database dan foto. Backup otomatis harian ke folder di PC. Salinan manual ke flashdisk.

## 4. Model data

- **Perhiasan:** kode unik, nama, jenis, kadar, berat (gram), ongkos, foto, status (`tersedia` / `terjual` / `nonaktif`).
- **Transaksi:** tipe (`jual` / `beli_pelanggan` / `beli_supplier`), tanggal, nama pihak terkait (teks bebas), total, kasir, status (`aktif` / `batal`), alasan batal, `grup_tukar_tambah` (opsional, mengikat dua transaksi tukar tambah).
- **Baris transaksi:** perhiasan (opsional), atau emas curah (berat + kadar tanpa perhiasan), berat, kadar, harga per gram yang dipakai, ongkos, subtotal.
- **Harga harian:** tanggal, kadar, harga jual per gram, harga beli per gram.
- **Pengguna:** nama pengguna, hash kata sandi, peran (`pemilik` / `kasir`).
- **Log audit:** siapa, kapan, aksi, nilai lama, nilai baru (untuk pembatalan dan perubahan harga).

### Aturan perhitungan

- Subtotal baris = berat × harga per gram + ongkos.
- Total penjualan = jumlah total transaksi `jual` berstatus `aktif` dalam rentang tanggal.
- Total pembelian = jumlah total transaksi `beli_pelanggan` dan `beli_supplier` berstatus `aktif`.
- Gramasi jual / beli = jumlah berat dari baris transaksi tipe terkait, termasuk emas curah.
- Transaksi `batal` tidak dihitung di dashboard.
- Tukar tambah menghasilkan dua transaksi (satu `jual`, satu `beli_pelanggan`) dengan `grup_tukar_tambah` yang sama. Selisih yang dibayar ditampilkan di layar, tetapi nominal dan gramasi tiap sisi masuk ke totalnya masing-masing.
- Stok emas curah **tidak** dilacak pada versi awal. Hanya perhiasan berkode yang punya status stok.

## 5. Layar

1. **Dashboard:** kartu Total Penjualan, Total Pembelian, Gramasi Jual, Gramasi Beli. Filter hari ini / minggu ini / bulan ini / rentang tanggal. Grafik tren harian dan 10 transaksi terakhir. Nominal penuh hanya untuk pemilik.
2. **Scan:** tombol kamera dan kolom input untuk scanner USB (otomatis fokus). Hasil: foto, kode, kadar, berat, harga, status, tombol "Tambah ke transaksi".
3. **Katalog perhiasan:** daftar berfoto, pencarian, filter (jenis, kadar, status). Tambah/edit item, unggah foto (termasuk dari kamera HP), cetak label barcode/QR.
4. **Transaksi baru:** pilih tipe lalu tambah baris item.
5. **Riwayat transaksi:** daftar, detail, cetak struk, pembatalan dengan alasan. Transaksi tidak pernah dihapus.
6. **Harga harian:** form harga jual dan beli per gram per kadar.
7. **Pengguna dan backup:** hanya pemilik.

## 6. Alur transaksi

- **Jual:** scan perhiasan, harga terisi otomatis (berat × harga harian + ongkos), kasir boleh mengubah. Setelah disimpan, item berstatus `terjual`.
- **Beli dari pelanggan:** isi berat dan kadar, pilih harga beli. Dicatat sebagai item baru (diberi kode dan foto, status `tersedia`) atau sebagai emas curah.
- **Tukar tambah:** satu layar dua sisi (barang lama masuk, barang baru keluar). Selisih dihitung otomatis.
- **Beli dari supplier:** input item baru dan beratnya. Item langsung masuk katalog dengan kode unik dan status `tersedia`.
- **Pembatalan:** transaksi jual dibatalkan → item kembali `tersedia`. Transaksi beli dibatalkan → item yang dibuat oleh transaksi itu menjadi `nonaktif`; jika item sudah terjual, pembatalan ditolak sampai penjualannya dibatalkan lebih dulu.

## 7. Label barcode/QR

- Isi kode hanya kode unik, mis. `GLD-000123`. Tidak ada harga di dalam kode.
- Label dicetak dari browser. Printer label khusus tidak diwajibkan.

## 8. Error handling

- Kode tidak ditemukan: pesan "Kode tidak terdaftar", input siap scan lagi.
- Item terjual dijual lagi: ditolak, tampilkan transaksi sebelumnya.
- Dua kasir memakai item sama bersamaan: pengecekan status dilakukan saat simpan; yang kedua mendapat pemberitahuan item tidak tersedia.
- Harga harian belum diisi: transaksi jual/beli diblokir dengan peringatan.
- Gagal di tengah simpan (listrik mati dll.): seluruh langkah dalam satu transaksi database (semua tersimpan atau tidak sama sekali).
- Kamera tidak aktif: panduan singkat menerima sertifikat; cadangan memakai scanner atau mengetik kode.

## 9. Keamanan

- Wajib login, kata sandi di-hash, sesi habis otomatis.
- Pemilik: semua fitur. Kasir: scan, katalog, transaksi.
- Server hanya untuk jaringan lokal, tidak dibuka ke internet.
- Pembatalan dan perubahan harga dicatat di log audit.

## 10. Pengujian

- Tes otomatis untuk logika harga, ongkos, tukar tambah, pembatalan, dan total dashboard.
- Tes alur utama (jual, beli, tukar tambah, scan) lewat API dengan database sementara.
- Uji manual di perangkat asli: kamera HP lewat HTTPS, scanner USB, cetak label.

## 11. Di luar cakupan awal

Pencarian foto dengan AI, data pelanggan lengkap, laporan pajak, multi-cabang, pelacakan stok emas curah.
