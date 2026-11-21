from cryptography import x509

from app.certs import ensure_cert, local_ips


def test_local_ips_memuat_loopback():
    assert "127.0.0.1" in local_ips()


def test_ensure_cert_membuat_dan_memakai_ulang(tmp_path):
    cert, key = ensure_cert(tmp_path, hosts=["127.0.0.1", "192.168.1.20"])
    assert cert.exists() and key.exists()
    parsed = x509.load_pem_x509_certificate(cert.read_bytes())
    san = parsed.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    ips = [str(i) for i in san.get_values_for_type(x509.IPAddress)]
    assert "192.168.1.20" in ips and "127.0.0.1" in ips
    before = cert.read_bytes()
    ensure_cert(tmp_path, hosts=["127.0.0.1", "192.168.1.20"])
    assert cert.read_bytes() == before
    ensure_cert(tmp_path, hosts=["127.0.0.1", "192.168.1.99"])
    assert cert.read_bytes() != before


def test_halaman_dan_unduhan_sertifikat(client, settings):
    assert client.get("/sertifikat").status_code == 200
    assert client.get("/sertifikat.crt").status_code == 404
    ensure_cert(settings.cert_dir, hosts=["127.0.0.1"])
    r = client.get("/sertifikat.crt")
    assert r.status_code == 200 and r.content.startswith(b"-----BEGIN CERTIFICATE-----")
