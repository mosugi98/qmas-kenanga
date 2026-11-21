@echo off
cd /d "%~dp0"
title Q-mas - jangan ditutup selama toko buka
if not exist ".venv\Scripts\python.exe" (
  echo Aplikasi belum terpasang. Jalankan instalasi.bat terlebih dahulu.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py
echo.
echo Aplikasi berhenti. Jika ini tidak disengaja, lihat pesan di atas.
pause
