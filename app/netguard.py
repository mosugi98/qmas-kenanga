import ipaddress


def is_local(host: str | None) -> bool:
    """True untuk jaringan lokal. Nilai non-IP (mis. klien uji) dianggap lokal."""
    if not host:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local
