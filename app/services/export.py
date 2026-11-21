"""Ekspor data ke CSV dan Excel (.xlsx). Tanpa dependensi tambahan."""
from __future__ import annotations

import csv
import io
import zipfile
from xml.sax.saxutils import escape

_RUMUS = ("=", "+", "-", "@", "\t", "\r")


def stok_rows(conn) -> tuple[list[str], list[list]]:
    header = ["Kode", "Nama", "Jenis", "Kadar", "Berat (gram)", "Ongkos (Rp)", "Status"]
    rows = conn.execute(
        "SELECT code, name, jenis, kadar, berat, ongkos, status FROM items ORDER BY code"
    ).fetchall()
    return header, [list(r) for r in rows]


def transaksi_rows(conn, dari: str, sampai: str) -> tuple[list[str], list[list]]:
    """Satu baris per item transaksi, dalam rentang tanggal (inklusif)."""
    header = ["No. Transaksi", "Tanggal", "Tipe", "Pihak", "Metode", "Status", "Kasir", "Kode", "Nama",
              "Kadar", "Berat (gram)", "Harga/gram (Rp)", "Ongkos (Rp)", "Subtotal (Rp)", "Total Transaksi (Rp)"]
    rows = conn.execute(
        "SELECT t.id, t.tanggal, t.tipe, t.pihak, t.metode, t.status, u.username, "
        "COALESCE(i.code,''), COALESCE(i.name,''), l.kadar, l.berat, l.harga_per_gram, l.ongkos, l.subtotal, t.total "
        "FROM transactions t JOIN transaction_lines l ON l.transaction_id=t.id "
        "JOIN users u ON u.id=t.kasir_id LEFT JOIN items i ON i.id=l.item_id "
        "WHERE date(t.tanggal) BETWEEN ? AND ? ORDER BY t.tanggal, t.id, l.id",
        (dari, sampai),
    ).fetchall()
    return header, [list(r) for r in rows]


def _aman(v):
    """Cegah teks dibaca Excel sebagai rumus (formula injection)."""
    if isinstance(v, str) and v.startswith(_RUMUS):
        return "'" + v
    return v


def to_csv(header: list[str], rows: list[list], pemisah: str = ";") -> bytes:
    """CSV UTF-8 dengan BOM agar Excel membaca benar. Pemisah ';' memakai koma desimal (Excel Indonesia)."""
    if pemisah not in (";", ","):
        pemisah = ";"
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=pemisah, lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        out = []
        for v in r:
            v = _aman(v)
            if isinstance(v, float) and pemisah == ";":
                v = f"{v:g}".replace(".", ",")
            out.append(v)
        w.writerow(out)
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def _kolom(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sel(ref: str, v, gaya: int = 0) -> str:
    if v is None:
        return f'<c r="{ref}"/>'
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, (int, float)):
        return f'<c r="{ref}" s="{gaya}"><v>{v!r}</v></c>'
    teks = escape(str(v))
    return f'<c r="{ref}" t="inlineStr" s="{gaya}"><is><t xml:space="preserve">{teks}</t></is></c>'


def to_xlsx(judul: str, header: list[str], rows: list[list]) -> bytes:
    """Berkas .xlsx minimal (satu sheet, header tebal, lebar kolom otomatis, baris atas dibekukan)."""
    judul = "".join(c for c in judul if c not in '[]:*?/\\')[:31] or "Data"
    lebar = [max(len(str(h)), *(len(str(r[i])) for r in rows[:500]), 0) if rows else len(str(h)) for i, h in enumerate(header)]
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{min(max(w + 2, 8), 45)}" customWidth="1"/>' for i, w in enumerate(lebar)
    )
    data = ['<row r="1">' + "".join(_sel(f"{_kolom(i)}1", h, 1) for i, h in enumerate(header)) + "</row>"]
    for n, r in enumerate(rows, start=2):
        data.append(f'<row r="{n}">' + "".join(_sel(f"{_kolom(i)}{n}", v) for i, v in enumerate(r)) + "</row>")
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{''.join(data)}</sheetData></worksheet>"
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(judul)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        ),
        "xl/worksheets/sheet1.xml": sheet,
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for nama, isi in parts.items():
            z.writestr(nama, isi)
    return out.getvalue()


def opname_rows(conn, take_id: int) -> tuple[list[str], list[list]]:
    """Satu baris per barang stok awal opname, HILANG di urutan pertama."""
    from . import stocktake

    lap = stocktake.laporan(conn, take_id)
    header = ["Hasil", "Kode", "Nama", "Jenis", "Kadar", "Berat (gram)", "Keterangan"]
    label = {"hilang": "HILANG", "terjual": "Terjual", "nonaktif": "Nonaktif", "cocok": "Cocok"}
    rows: list[list] = []
    for kunci in ("hilang", "terjual", "nonaktif", "cocok"):
        for d in lap[kunci]["daftar"]:
            ket = ""
            if kunci == "terjual":
                ket = f"Nota #{d['nota']} {d.get('pihak') or ''}".strip() if d.get("nota") else "Terjual"
            elif kunci == "cocok":
                ket = f"Discan {d['ditemukan']}"
            rows.append([label[kunci], d["code"], d["name"], d["jenis"], d["kadar"], d["berat"], ket])
    for t in lap.get("temuan", []):
        rows.append(["TEMUAN", t["kode"], "", "", "", "", t["hasil"]])
    return header, rows
