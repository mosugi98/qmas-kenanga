@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Generator Lisensi Q-mas

set "PY="
for %%C in (python py) do (
  if not defined PY (
    %%C -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=%%C"
  )
)
if not defined PY (
  echo Python 3.10 atau lebih baru belum terpasang di komputer ini.
  echo Pasang dari https://www.python.org/downloads/ ^(centang "Add python.exe to PATH"^), lalu jalankan lagi.
  pause
  exit /b 1
)

%PY% -c "import cryptography" >nul 2>&1
if errorlevel 1 (
  echo Memasang paket cryptography ^(sekali saja, butuh internet^)...
  %PY% -m pip install --quiet cryptography
  if errorlevel 1 (
    echo Gagal memasang cryptography. Periksa koneksi internet lalu coba lagi.
    pause
    exit /b 1
  )
)

if not exist "lisensi-private.pem" (
  echo Berkas lisensi-private.pem tidak ada di folder ini.
  echo Letakkan kunci privat penerbit di folder yang sama dengan generator_lisensi.bat.
  pause
  exit /b 1
)

%PY% penerbit.py interaktif
echo.
pause
