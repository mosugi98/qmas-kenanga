@echo off
rem Membuka port 8443 di firewall Windows agar HP/komputer lain di WiFi toko bisa membuka Q-mas.
net session >nul 2>&1
if errorlevel 1 (
  echo Meminta izin Administrator... pilih Yes.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall delete rule name=Q-mas >nul 2>&1
netsh advfirewall firewall add rule name=Q-mas dir=in action=allow protocol=TCP localport=8443 profile=any
if errorlevel 1 (echo GAGAL membuat aturan firewall.) else (echo Selesai. Port 8443 terbuka. Coba buka alamat Q-mas dari HP lagi.)
echo.
pause
