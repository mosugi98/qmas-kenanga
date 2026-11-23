@echo off
cd /d "%~dp0"
title Q-mas - jangan ditutup selama toko buka
if not exist ".venv\Scripts\python.exe" (
  echo Aplikasi belum terpasang. Jalankan instalasi.bat terlebih dahulu.
  pause
  exit /b 1
)
rem Agar HP bisa masuk: buat aturan firewall sekali saja (Windows meminta izin Administrator).
netsh advfirewall firewall show rule name=Q-mas >nul 2>&1
if errorlevel 1 (
  echo Membuka port 8443 di firewall agar HP bisa masuk. Pilih Yes pada jendela izin yang muncul.
  powershell -NoProfile -Command "Start-Process netsh -Verb RunAs -Wait -ArgumentList 'advfirewall firewall add rule name=Q-mas dir=in action=allow protocol=TCP localport=8443 profile=any'" >nul 2>&1
  netsh advfirewall firewall show rule name=Q-mas >nul 2>&1
  if errorlevel 1 echo [PERHATIAN] Firewall belum dibuka, HP mungkin belum bisa masuk. Lihat PANDUAN.md bagian firewall.
)
".venv\Scripts\python.exe" run.py
echo.
echo Aplikasi berhenti. Jika ini tidak disengaja, lihat pesan di atas.
pause
