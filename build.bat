@echo off
pyinstaller --noconfirm --onedir --name Qmas ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\static;app\static" ^
  --collect-submodules uvicorn ^
  --collect-all barcode ^
  --collect-all qrcode ^
  run.py
echo.
echo Selesai. Hasil: dist\Qmas\Qmas.exe
