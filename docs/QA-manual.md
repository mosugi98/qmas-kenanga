# Uji Manual (perangkat asli)

Centang setiap butir di PC toko dan minimal satu HP Android dan satu iPhone bila tersedia.

- [ ] `TokoEmas.exe` jalan dari folder bersih; folder `data` terbentuk di sebelahnya.
- [ ] Alamat `https://<IP-PC>:8443` terbuka dari HP lewat WiFi toko; dari jaringan luar (data seluler) tidak bisa dibuka.
- [ ] Halaman setup membuat pemilik; login kasir (dibuat dari menu Pengguna) tidak melihat menu Harga/Pengguna dan tidak melihat nominal di Beranda.
- [ ] Kamera di halaman Scan menyala di HP (setelah menerima sertifikat) dan membaca QR serta barcode dari label hasil cetak.
- [ ] Scan di HP → "Tambah ke kasir": perhiasan muncul di Kasir PC dalam ±4 detik; setelah transaksi selesai, keranjang kosong.
- [ ] Metode bayar (Tunai/Transfer/QRIS) tersimpan dan tampil di Riwayat dan detail transaksi.
- [ ] Scanner USB/Bluetooth: scan label → data perhiasan muncul tanpa mengetik.
- [ ] Label tercetak jelas (QR dan barcode terbaca) dari browser; ukuran cukup untuk label perhiasan.
- [ ] Alur: harga harian → tambah perhiasan berfoto dari kamera HP → jual (harga diubah kasir) → struk tercetak.
- [ ] Beli dari pelanggan (perhiasan baru dan emas curah), beli dari supplier, tukar tambah: total, selisih, dan gramasi di dashboard sesuai hitungan manual.
- [ ] Dua HP menjual perhiasan yang sama bersamaan: salah satu mendapat pesan tidak tersedia.
- [ ] Batalkan penjualan (pemilik): perhiasan kembali tersedia dan angka dashboard berkurang.
- [ ] Matikan PC mendadak saat idle, nyalakan lagi: data utuh.
- [ ] Backup manual terunduh; pemulihan di folder baru membuka data yang sama.
- [ ] Kode sendiri: isi `CC-0412` di perhiasan baru lalu simpan; coba kode yang sama di perhiasan lain, muncul pesan "sudah dipakai" dan tidak tersimpan.
- [ ] Cetak label: ukuran kecil/sedang/besar, QR saja, barcode saja, dan salinan 3 tercetak benar; hasil cetak tetap terbaca scanner.
- [ ] Centang beberapa perhiasan di katalog lalu "Cetak label terpilih": semua label tampil dan tercetak.
- [ ] Ekspor stok dan transaksi (xlsx dan csv) terbuka di Excel tanpa karakter rusak; kolom angka bisa dijumlahkan; nama yang diawali `=` tampil sebagai teks.
- [ ] Kasir tidak melihat menu Ekspor dan tidak bisa membuka /ekspor.
- [ ] Tanpa lisensi semua halaman mengarah ke Lisensi; Kode Perangkat tampil dan bisa disalin.
- [ ] Kunci yang salah/terpotong/untuk komputer lain ditolak dengan pesan jelas; kunci yang benar mengaktifkan tanpa restart.
- [ ] Lisensi 5 hari lagi: banner kuning tampil untuk pemilik (tidak untuk kasir). Lisensi habis +8 hari: aplikasi terkunci, pemilik masih bisa login dan unduh backup.
- [ ] Paket siap jalan: ekstrak di PC bersih tanpa Python dan tanpa internet, jalankan.bat membuka aplikasi; pasang-otomatis.bat membuka firewall dan aplikasi hidup sendiri setelah restart PC (tanpa login Windows).
- [ ] HP di WiFi toko membuka alamat server yang baru dan kamera scan berfungsi setelah sertifikat diterima.

## Versi 2 (Kenanga): massal, opname, scanner
- [ ] Buat massal: 2 baris (Cincin 22K 3,5 g x 20; Kalung 24K 12 g x 5): pratinjau benar, 25 perhiasan terbuat, 25 label tampil dan tercetak; ulangi dengan baris yang sama: nomor lanjut (021 dst), tidak ada kode kembar.
- [ ] Scanner USB asli: scan label di Kasir tanpa klik kolom kode, perhiasan masuk keranjang; di Opname terdengar bip dan hitungan Cocok bertambah.
- [ ] Scan label yang sama dua kali di Opname: muncul "Sudah discan", hitungan tidak bertambah.
- [ ] Sembunyikan satu perhiasan, selesaikan opname: laporan menyebut tepat perhiasan itu HILANG; Excel hasil ekspor memuatnya di baris pertama.
- [ ] Jual satu perhiasan saat opname berjalan (tanpa discan): masuk kelompok Terjual dengan nomor nota, bukan Hilang.
- [ ] Kasir tidak bisa mengunduh ekspor opname (ditolak), tetapi bisa menjalankan opname dan melihat laporan.
- [ ] Tanpa harga harian: kasir bisa jual dan beli dengan mengisi harga per gram; beranda tidak menampilkan peringatan merah.

