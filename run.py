import os
import sys
import threading

import uvicorn

from app import lisensi
from app.certs import ensure_cert, local_ips
from app.config import PORT, load_settings
from app.main import create_app
from app.services.backup import daily_backup_loop


def jalankan_online(settings) -> None:
    """Mode hosting: HTTP polos di belakang proxy HTTPS (Caddy, Render, dst). Proxy yang mengurus sertifikat."""
    # ID instans dipatok ke berkas di volume data agar kode perangkat (dipakai reset sandi) stabil antar-restart.
    if not os.environ.get("QMAS_MACHINE_ID"):
        f = settings.data_dir / "instance-id.txt"
        if not f.exists():
            import uuid
            f.write_text(uuid.uuid4().hex + "\n", encoding="utf-8")
        os.environ["QMAS_MACHINE_ID"] = f.read_text(encoding="utf-8").strip()
    app = create_app(settings)
    threading.Thread(target=daily_backup_loop, args=(settings,), daemon=True).start()
    if not settings.setup_token:
        print("PERINGATAN: TOKOEMAS_SETUP_TOKEN belum diatur; akun pemilik pertama tidak bisa dibuat.")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Q-mas mode online di port {port} (data: {settings.data_dir})")
    # proxy_headers: alamat klien asli dari X-Forwarded-For; hanya aman bila port ini tidak dibuka langsung ke internet.
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*", log_level="warning")


def main() -> None:
    if "--kode-perangkat" in sys.argv:
        print(lisensi.kode_perangkat())
        return
    if "--alamat" in sys.argv:
        for ip in local_ips():
            print(f"   https://{ip}:{PORT}")
        return
    settings = load_settings()
    settings.ensure_dirs()
    if settings.online:
        return jalankan_online(settings)
    cert, key = ensure_cert(settings.cert_dir)
    app = create_app(settings)
    threading.Thread(target=daily_backup_loop, args=(settings,), daemon=True).start()
    st = lisensi.status_sekarang(settings)
    print(f"Lisensi: {st.pesan}")
    if not st.boleh_pakai:
        print(f"Kode Perangkat komputer ini: {lisensi.kode_perangkat()}")
    print("Q-mas berjalan. Buka salah satu alamat ini dari perangkat di WiFi toko:")
    for ip in local_ips():
        print(f"  https://{ip}:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, ssl_certfile=str(cert), ssl_keyfile=str(key), log_level="warning")


if __name__ == "__main__":
    main()
