import io

import barcode
import qrcode
import qrcode.image.svg
from barcode.writer import SVGWriter


def qr_svg(code: str) -> bytes:
    img = qrcode.make(code, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def code128_svg(code: str) -> bytes:
    buf = io.BytesIO()
    barcode.get("code128", code, writer=SVGWriter()).write(
        buf, options={"write_text": False, "module_height": 8.0, "quiet_zone": 2.0}
    )
    return buf.getvalue()
