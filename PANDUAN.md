# Panduan Pemasangan Q-mas

## Di PC toko (sekali saja)
1. Ekstrak `Q-mas.zip` ke folder biasa, mis. `C:\Qmas` (jangan dijalankan dari dalam zip).
2. Beri PC **alamat IP tetap** di router (reservasi DHCP) agar alamat aplikasi tidak berubah.
3. Klik kanan **instalasi.bat** lalu pilih **Run as administrator**. Skrip akan:
   - mengecek prasyarat: Windows 64-bit, berkas lengkap, Python 3.10+ (64-bit), port 8443 bebas, folder data bisa ditulis, internet, dan hak administrator;
   - menawarkan pemasangan Python otomatis (winget) bila belum ada;
   - membuat lingkungan Python, memasang paket, menguji aplikasi, membuka port 8443 di firewall, dan membuat pintasan "Q-mas" di Desktop.
   Hanya ingin mengecek? Jalankan `instalasi.bat /cek` lewat CMD. Jika ada masalah, lihat `instalasi.log`.
   PC tanpa internet: salin folder `wheels` berisi paket dari `requirements.txt` ke samping `instalasi.bat`; paket dipasang dari sana.
4. Jalankan aplikasi dengan klik dua kali pintasan **Q-mas** (atau `jalankan.bat`). Jendela akan menampilkan alamat, mis. `https://192.168.1.20:8443`. Biarkan jendela terbuka selama toko buka.
5. Buka alamat itu di browser PC, buat akun pemilik di halaman pengaturan awal, lalu isi **Harga Emas** setiap pagi sebelum transaksi. Nama di pojok kiri atas bawaannya **Q-mas**; ganti dengan nama toko Anda lewat file `data\nama_toko.txt` (satu baris, lalu jalankan ulang aplikasi).

## Lisensi
- Pada pemakaian pertama aplikasi meminta **kunci lisensi**. Buka halaman **Lisensi** (otomatis terbuka), salin **Kode Perangkat** (atau jalankan `python run.py --kode-perangkat`), kirim ke penyedia aplikasi, lalu tempel kunci yang diterima dan klik **Aktifkan**. Tidak perlu internet.
- Lisensi terikat ke **satu komputer** dan bisa berbatas waktu. Pemilik melihat peringatan 14 hari sebelum habis; sesudah habis ada masa tenggang 7 hari. Setelah itu aplikasi terkunci sampai kunci baru dimasukkan, tetapi **data tetap aman** dan pemilik masih bisa mengunduh backup.
- Pindah komputer atau Windows diinstal ulang: kirim Kode Perangkat yang baru untuk mendapat kunci baru, lalu salin folder `data` ke komputer baru.
- Jam komputer jangan diundur: aplikasi mendeteksinya dan mengunci sampai tanggal dibetulkan.

## Paket siap jalan (pasang di komputer lain tanpa Python dan tanpa internet)
1. Di satu PC Windows yang punya internet dan Python, klik dua kali **buat-paket.bat** (opsi: `--toko "Nama Toko"`). Hasilnya `dist\Q-mas-SiapJalan-<tanggal>.zip`, berisi Python portable, semua paket, dan aplikasi.
2. Salin zip itu ke komputer tujuan (flashdisk), ekstrak ke `C:\Qmas`, lalu klik dua kali **jalankan.bat**.
3. Mode server: klik kanan **pasang-otomatis.bat** > Run as administrator. Port 8443 dibuka di firewall dan Q-mas jalan sendiri tiap komputer menyala (log di `data\q-mas.log`). Lepas dengan **hapus-otomatis.bat**.
4. Masukkan kunci lisensi seperti di atas. Paket tidak memuat kunci privat penerbit.

## Di HP / perangkat lain
- Buka alamat yang sama. Saat muncul peringatan sertifikat, pilih lanjutkan. Jika kamera scan tidak aktif, ikuti halaman **/sertifikat**.

## Scanner USB / Bluetooth
- Colok scanner (mode keyboard / HID, bawaan hampir semua scanner USB). Di halaman **Kasir**, **Opname**, dan **Lacak barang** scanner langsung bekerja tanpa klik kolom apa pun; bunyi bip pendek = berhasil, dua bip = sudah discan, bip rendah = kode tidak dikenal.
- Pastikan scanner mengirim Enter di akhir (bawaan). Bila tidak, scan barcode konfigurasi "Enter suffix" dari buku manual scanner.

## Alur harian
- **Perhiasan baru**: di **Stok & Katalog** klik tambah, isi data, lalu **Simpan & buat label**. Kode (GLD-000123), QR, dan barcode dibuat otomatis dan langsung tampil siap cetak. Untuk input banyak perhiasan berurutan, pakai **Simpan & tambah lagi**; label tiap perhiasan bisa dicetak kapan saja lewat tombol Label di katalog.
- **Kode sendiri**: di form perhiasan, isi kolom **Kode unik** bila ingin kode buatan sendiri (contoh `CC-0412`; huruf, angka, `-` `_` `.`, 3 sampai 30 karakter). Tiap kode hanya boleh dipakai satu perhiasan dan langsung dicek saat diketik. Kosongkan untuk kode otomatis (GLD-000123). Kode bisa diubah lewat Ubah, tetapi label lama yang sudah ditempel jadi tidak berlaku, jadi cetak ulang.
- **Cetak label**: di halaman label pilih isi (QR, barcode, atau keduanya), ukuran (40/55/80 mm), jumlah salinan, dan garis potong, lalu **Cetak**. Untuk banyak perhiasan sekaligus, centang **Pilih** di Stok & Katalog lalu klik **Cetak label terpilih**.
- **Ekspor ke Excel/CSV** (pemilik): menu **Ekspor** untuk stok dan transaksi per rentang tanggal. Pilih pemisah titik koma untuk Excel Indonesia, atau koma untuk Google Sheets. Setiap unduhan tercatat di log aktivitas.
- **Buat banyak sekaligus**: **Stok & Katalog > Buat banyak sekaligus**. Isi tiap baris: jenis, kadar, gramasi, jumlah pcs (bisa beberapa baris). Pratinjau menampilkan rentang kode, misalnya `KNG-CIN-3G5-001` sampai `KNG-CIN-3G5-020`. Klik buat, label langsung siap dicetak. Maksimal 200 pcs per baris dan 500 pcs sekali buat. Awalan kode (bawaan KNG) bisa diubah di kolom awalan.
- **Opname / cek kehilangan**: menu **Opname > Mulai opname**. Semua perhiasan berstatus tersedia saat itu dicatat sebagai **stok awal**. Scan setiap barang yang ada di etalase dan brankas. Saat **Selesai**, laporan mengelompokkan stok awal menjadi: *cocok* (ditemukan), *terjual* (tercatat nota), dan *HILANG* (tidak ditemukan dan tidak terjual). Kode asing, barang tercatat terjual tetapi masih ada, dan barang baru dicatat sebagai temuan. Hanya satu opname boleh berjalan; laporan yang sudah selesai dikunci. Pemilik bisa mengunduh Excel/CSV.
- **Lacak barang**: menu **Lacak barang**, scan atau ketik kode untuk melihat status, nota penjualan, dan hasil opname barang itu.
- **Harga emas harian tidak wajib**: kasir tetap bisa jual/beli; bila harga hari itu belum diisi, isi harga per gram langsung di keranjang. Foto perhiasan juga tidak wajib.
- **Kasir**: pilih Jual, Beli dari pelanggan, Tukar tambah, atau Beli dari supplier. Scan kode atau pilih perhiasan dari katalog, atur berat/ongkos bila perlu, pilih pembayaran (Tunai/Transfer/QRIS), lalu **Selesaikan transaksi**.
- **Scan di HP**: buka menu **Scan**, ketuk kotak kamera, arahkan ke label, lalu **Tambah ke kasir**. Perhiasan muncul sendiri di Kasir PC dalam beberapa detik.
- **Beranda**: ringkasan penjualan, pembelian, gramasi, stok, dan harga hari ini (nominal hanya untuk pemilik).

## HP tidak bisa membuka alamat
1. Pastikan HP dan komputer di WiFi yang sama (bukan data seluler atau WiFi tamu) dan alamatnya `https://IP:8443` (pakai `https`).
2. Klik dua kali **buka-firewall.bat** (atau `jalankan.bat` pada versi terbaru); saat Windows meminta izin Administrator untuk firewall, pilih **Yes** (sekali saja). Manual: Command Prompt sebagai Administrator, lalu `netsh advfirewall firewall add rule name=Q-mas dir=in action=allow protocol=TCP localport=8443 profile=any`.
3. Bila IP yang tampil tidak cocok, ketik `ipconfig` dan pakai IPv4 adapter WiFi/LAN.
4. Peringatan sertifikat di browser HP normal: pilih Lanjutkan / Advanced > Proceed.

## Lupa kata sandi
- Di halaman Masuk klik **Lupa kata sandi?**. Kirim **Kode Perangkat** dan **Kode Tantangan** yang tampil ke penyedia aplikasi. Tempel token balasannya, isi nama pengguna dan kata sandi baru. Reset hanya bisa dilakukan penyedia aplikasi.

## Backup
- Otomatis setiap hari ke `data\backup\` (14 hari terakhir disimpan). Salin zip terbaru ke flashdisk secara berkala.
- Manual: menu **Pengguna → Unduh backup sekarang**.
- Pemulihan: tutup aplikasi, ekstrak zip, salin `tokoemas.db` ke `data\` dan isi `foto\` ke `data\foto\`, lalu jalankan lagi.

## Sertifikat kedaluwarsa (±2 tahun)
- Hapus folder `data\cert` lalu jalankan ulang aplikasi; sertifikat baru dibuat. HP perlu menerima sertifikat lagi.
