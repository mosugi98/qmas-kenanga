import sys
import threading

import uvicorn

from app import lisensi
from app.certs import ensure_cert, local_ips
from app.config import PORT, load_settings
from app.main import create_app
from app.services.backup import daily_backup_loop


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
