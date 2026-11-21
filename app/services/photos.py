import uuid

MAX_BYTES = 8 * 1024 * 1024


def _ext(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_photo(settings, data: bytes) -> str:
    ext = _ext(data)
    if ext is None:
        raise ValueError("Foto harus berformat JPEG, PNG, atau WebP")
    if len(data) > MAX_BYTES:
        raise ValueError("Foto terlalu besar (maksimal 8 MB)")
    name = uuid.uuid4().hex + ext
    (settings.photo_dir / name).write_bytes(data)
    return name
