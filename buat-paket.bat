@echo off
setlocal
cd /d "%~dp0"
title Buat paket siap jalan Q-mas
where python >nul 2>&1
if errorlevel 1 (
  echo Python belum terpasang di PC ini. Pasang dari https://www.python.org/downloads/ lalu ulangi.
  pause
  exit /b 1
)
python tools\buat_paket.py %*
echo.
pause
