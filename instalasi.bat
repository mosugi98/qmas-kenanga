@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Instalasi Q-mas
set "LOG=%~dp0instalasi.log"
set "PORT=8443"
set "PY="
set "CEKSAJA="
set "N_GAGAL=0"
set "N_PERHATIAN=0"
if /i "%~1"=="/cek" set "CEKSAJA=1"

echo ============================================================
echo   INSTALASI Q-MAS
if defined CEKSAJA (echo   Mode: cek prasyarat saja, tidak ada yang dipasang) else (echo   Mode: cek prasyarat + instalasi)
echo ============================================================
echo.
echo [%date% %time%] mulai > "%LOG%"

echo --- 1. Cek prasyarat ---

rem ---- Windows 64-bit
set "ARS_OK=1"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 set "ARS_OK="
if defined ARS_OK (
  echo [OK]    Windows 64-bit
) else (
  echo [GAGAL] Windows 32-bit tidak didukung. Pakai Windows 64-bit.
  set /a N_GAGAL+=1
)

rem ---- Berkas aplikasi lengkap
set "HILANG="
call :cek_berkas run.py
call :cek_berkas requirements.txt
call :cek_berkas app\main.py
call :cek_berkas app\lisensi.py
call :cek_berkas app\templates\base.html
call :cek_berkas app\static\app.css
call :cek_berkas app\static\vendor\html5-qrcode.min.js
if defined HILANG (
  echo [GAGAL] Berkas aplikasi tidak lengkap, hilang:%HILANG%
  echo         Ekstrak ulang seluruh isi zip ke folder baru, lalu jalankan lagi.
  set /a N_GAGAL+=1
) else (
  echo [OK]    Berkas aplikasi lengkap
)

rem ---- Python 3.10+ 64-bit
call :cari_python
if not defined PY goto :python_tidak_ada
for /f "delims=" %%V in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%V"
echo [OK]    Python %PYVER% (64-bit)
goto :python_selesai

:python_tidak_ada
echo [GAGAL] Python 3.10 atau lebih baru (64-bit) tidak ditemukan.
set /a N_GAGAL+=1
if defined CEKSAJA goto :python_selesai
where winget >nul 2>&1
if errorlevel 1 (
  echo         winget tidak tersedia. Pasang Python manual dari https://www.python.org/downloads/
  echo         PENTING: centang "Add python.exe to PATH" saat pemasangan, lalu jalankan instalasi.bat lagi.
  goto :selesai_gagal
)
echo.
choice /c YT /n /m "Pasang Python 3.12 otomatis lewat winget sekarang? [Y=ya, T=tidak] "
if errorlevel 2 (
  echo         Pasang Python manual dari https://www.python.org/downloads/ lalu jalankan instalasi.bat lagi.
  goto :selesai_gagal
)
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo [GAGAL] Pemasangan Python lewat winget gagal. Pasang manual dari https://www.python.org/downloads/
  goto :selesai_gagal
)
echo.
echo Python terpasang. TUTUP jendela ini, lalu klik dua kali instalasi.bat lagi untuk melanjutkan.
pause
exit /b 0

:python_selesai

rem ---- Port 8443 bebas
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [PERHATIAN] Port %PORT% sedang dipakai. Jika itu Q-mas yang sedang jalan, tutup dulu jendelanya.
  set /a N_PERHATIAN+=1
) else (
  echo [OK]    Port %PORT% bebas
)

rem ---- Folder data bisa ditulis
if not exist "data" mkdir "data" >nul 2>&1
echo test> "data\.tulis" 2>nul
if exist "data\.tulis" (
  del "data\.tulis" >nul 2>&1
  echo [OK]    Folder data bisa ditulis
) else (
  echo [GAGAL] Folder data tidak bisa ditulis. Pindahkan aplikasi ke folder biasa, mis. C:\Qmas
  set /a N_GAGAL+=1
)

rem ---- Internet (untuk mengunduh paket Python) atau folder wheels
if exist "wheels\" (
  echo [OK]    Folder wheels ditemukan, paket dipasang tanpa internet
) else if exist ".venv\Scripts\python.exe" (
  echo [OK]    Lingkungan Python sudah ada, internet tidak wajib
) else (
  powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol='Tls12';(Invoke-WebRequest -Uri 'https://pypi.org/simple/pip/' -UseBasicParsing -TimeoutSec 10).StatusCode | Out-Null}catch{exit 1}" >nul 2>&1
  if errorlevel 1 (
    echo [GAGAL] Tidak bisa terhubung ke internet ^(pypi.org^). Sambungkan PC ke internet lalu ulangi.
    set /a N_GAGAL+=1
  ) else (
    echo [OK]    Internet tersedia
  )
)

rem ---- Hak administrator (untuk firewall)
net session >nul 2>&1
if errorlevel 1 (
  set "ADMIN="
  echo [PERHATIAN] Tidak berjalan sebagai Administrator: aturan firewall tidak bisa dibuat otomatis.
  set /a N_PERHATIAN+=1
) else (
  set "ADMIN=1"
  echo [OK]    Berjalan sebagai Administrator
)

if %N_GAGAL% GTR 0 goto :selesai_gagal
if defined CEKSAJA goto :selesai_ok

echo.
echo --- 2. Instalasi ---

if exist ".venv\Scripts\python.exe" (
  echo [OK]    Lingkungan Python sudah ada
) else (
  echo Membuat lingkungan Python ...
  %PY% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [GAGAL] Gagal membuat lingkungan Python. Lihat instalasi.log
    goto :selesai_gagal
  )
  echo [OK]    Lingkungan Python dibuat
)

echo Memasang paket ^(bisa beberapa menit^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
if exist "wheels\" (
  ".venv\Scripts\python.exe" -m pip install --no-index --find-links wheels -r requirements.txt >> "%LOG%" 2>&1
) else (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%LOG%" 2>&1
)
if errorlevel 1 (
  echo [GAGAL] Pemasangan paket gagal. Periksa internet lalu ulangi; detail ada di instalasi.log
  goto :selesai_gagal
)
echo [OK]    Paket terpasang

".venv\Scripts\python.exe" -c "import app.main" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [GAGAL] Aplikasi tidak bisa dimuat setelah instalasi. Lihat instalasi.log
  goto :selesai_gagal
)
echo [OK]    Aplikasi lolos uji muat

if defined ADMIN (
  netsh advfirewall firewall delete rule name="Toko Emas" >nul 2>&1
  netsh advfirewall firewall delete rule name="Q-mas" >nul 2>&1
  netsh advfirewall firewall add rule name="Q-mas" dir=in action=allow protocol=TCP localport=%PORT% >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [PERHATIAN] Aturan firewall gagal dibuat. Buat manual, lihat PANDUAN.md
    set /a N_PERHATIAN+=1
  ) else (
    echo [OK]    Firewall: port %PORT% dibuka untuk jaringan toko
  )
) else (
  echo [PERHATIAN] Firewall belum diatur. HP belum bisa membuka aplikasi sampai port %PORT% dibuka.
  echo             Klik kanan instalasi.bat lalu "Run as administrator", atau jalankan di CMD Administrator:
  echo             netsh advfirewall firewall add rule name="Q-mas" dir=in action=allow protocol=TCP localport=%PORT%
)

powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop');Remove-Item ($d+'\Toko Emas.lnk') -ErrorAction SilentlyContinue;$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\Q-mas.lnk');$s.TargetPath='%~dp0jalankan.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [PERHATIAN] Pintasan desktop gagal dibuat. Jalankan aplikasi lewat jalankan.bat
  set /a N_PERHATIAN+=1
) else (
  echo [OK]    Pintasan "Q-mas" dibuat di Desktop
)

:selesai_ok
echo.
echo ============================================================
if defined CEKSAJA (
  echo   HASIL CEK: semua prasyarat terpenuhi. Perhatian: %N_PERHATIAN%
  echo   Jalankan instalasi.bat tanpa "/cek" untuk memasang.
) else (
  echo   INSTALASI SELESAI. Perhatian: %N_PERHATIAN%
  echo   Jalankan aplikasi: klik dua kali "Q-mas" di Desktop atau jalankan.bat
  echo   Alamat untuk HP akan tampil di jendela aplikasi, lalu buat akun pemilik
  echo   di halaman pengaturan awal.
)
echo ============================================================
pause
exit /b 0

:selesai_gagal
echo.
echo ============================================================
echo   BELUM BERHASIL. Gagal: %N_GAGAL%. Perbaiki butir [GAGAL] di atas lalu jalankan lagi.
echo   Detail teknis: instalasi.log
echo ============================================================
pause
exit /b 1

:cari_python
set "PY="
for %%C in ("py -3" "python" "python3") do (
  if not defined PY (
    %%~C -c "import sys,struct;sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize('P')==8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=%%~C"
  )
)
exit /b 0

:cek_berkas
if not exist "%~1" set "HILANG=%HILANG% %~1"
exit /b 0
