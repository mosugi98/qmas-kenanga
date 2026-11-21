# Toko Emas — Rencana 2: Layar, Scan, dan Rilis

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Melengkapi aplikasi toko emas dengan dashboard, halaman scan (kamera HP dan scanner USB), layar transaksi dan riwayat, manajemen pengguna, backup, pembatasan jaringan lokal, HTTPS, dan paket `.exe` Windows.

**Architecture:** Melanjutkan struktur Rencana 1 (FastAPI + SQLite + Jinja2). Dashboard dan chart dirender server-side (HTML/CSS, tanpa pustaka chart); layar transaksi memakai satu blok JavaScript kecil yang memanggil API JSON dari Rencana 1. Pustaka scan kamera (`html5-qrcode`) disimpan lokal di `app/static/vendor/` karena jaringan toko tanpa internet.

**Tech Stack:** Sama dengan Rencana 1, ditambah `html5-qrcode` 2.3.8 (vendored), `cryptography` (sertifikat HTTPS), PyInstaller (pengemasan).

**Prasyarat:** Rencana 1 (`2026-11-19-toko-emas-1-fondasi.md`) selesai dan `pytest -q` hijau.

## Global Constraints

Disalin dari spesifikasi `docs/superpowers/specs/2026-11-19-toko-emas-design.md`:

- Server di 1 PC Windows toko, diakses 2–5 perangkat lewat WiFi; HTTPS pada port 8443 dengan sertifikat lokal (self-signed). Kamera browser hanya jalan di HTTPS; scanner USB tidak terpengaruh.
- Peran `pemilik` (semua fitur) dan `kasir` (scan, katalog, transaksi). Nominal penuh di dashboard hanya untuk pemilik.
- Dashboard: kartu Total Penjualan, Total Pembelian, Gramasi Jual, Gramasi Beli; filter hari ini / minggu ini / bulan ini / rentang tanggal; grafik tren harian; 10 transaksi terakhir.
- Dashboard hanya menghitung transaksi `aktif`.
- Isi barcode/QR hanya kode unik (`GLD-000123`), tanpa harga.
- Server hanya untuk jaringan lokal, tidak dibuka ke internet.
- Backup: tombol "Backup" menghasilkan satu zip berisi database dan foto; backup otomatis harian ke folder di PC.
- Pembatalan transaksi hanya oleh pemilik; transaksi tidak pernah dihapus.
- Kamera tidak aktif: tampilkan panduan menerima sertifikat; cadangan memakai scanner atau mengetik kode.

Aturan grafik (panduan visualisasi data): palet kategori slot 1 biru (`#2a78d6` terang / `#3987e5` gelap) untuk Penjualan dan slot 2 oranye (`#eb6834` / `#d95926`) untuk Pembelian; batang maksimum 24px dengan ujung data membulat 4px; jarak 2px antar batang; legenda selalu ada untuk dua seri; teks memakai warna teks, bukan warna seri; gridline hairline 1px; tooltip saat hover/fokus; tersedia tampilan tabel; tanpa sumbu ganda.

## Struktur File (tambahan)

```
app/
  netguard.py                         # is_local(host)
  certs.py                            # local_ips(), ensure_cert()
  services/
    reports.py                        # preset_range(), nice_scale(), summary()
    backup.py                         # make_backup(), prune(), backup_if_needed(), daily_backup_loop()
    transactions.py                   # (ubah) + list_transactions(), get_transaction()
  routes/
    dashboard_routes.py               # (ganti) dashboard
    scan_routes.py                    # /scan
    transactions_routes.py            # (ganti) + halaman baru/riwayat/detail/batal
    admin_routes.py                   # /pengguna, /backup, /sertifikat
  templates/ dashboard.html scan.html transaksi_baru.html transaksi_riwayat.html
             transaksi_detail.html pengguna.html sertifikat.html
  static/    lookup.js  vendor/html5-qrcode.min.js
run.py  build.bat  PANDUAN.md  docs/QA-manual.md
tests/ test_reports.py test_dashboard.py test_scan.py test_transactions_pages.py
       test_netguard.py test_backup.py test_admin.py test_certs.py
```

---

### Task 6: Dashboard

**Files:**
- Create: `app/services/reports.py`, `app/templates/dashboard.html`
- Modify: `app/routes/dashboard_routes.py` (ganti seluruh isi), `app/web.py` (tambah filter), `app/static/app.css` (tambah gaya)
- Delete: `app/templates/home.html`
- Test: `tests/test_reports.py`, `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `create_transaction`, `LineIn`, `cancel_transaction`, `create_tukar_tambah` (Rencana 1, Task 5); `require_user`, `get_db`, `render`.
- Produces:
  - `app.services.reports.preset_range(preset: str, today: date) -> tuple[str, str]` (`"hari_ini"`, `"minggu_ini"` (Senin–hari ini), `"bulan_ini"`; selain itu = hari ini).
  - `app.services.reports.nice_scale(vmax: int) -> tuple[int, list[int]]` → `(nilai_atas, tick)`; minimum skala 1.000.000.
  - `app.services.reports.summary(conn, start: str, end: str) -> dict` dengan kunci `penjualan: int`, `pembelian: int`, `gram_jual: float`, `gram_beli: float`, `series: list[{"tgl", "penjualan", "pembelian"}]` (setiap hari terisi, maksimum 92 hari terakhir dari rentang), `recent: list[Row]` (10 transaksi terakhir semua status, kolom `id, tipe, tanggal, pihak, total, status, kasir`).
  - Filter Jinja `jt` (angka rupiah → "2,5 jt") dan `tipe_label` ("jual" → "Jual", dst.).
  - `GET /` dengan query `preset`, `start`, `end`.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/test_reports.py`:
```python
from datetime import date

from app.services.reports import nice_scale, preset_range, summary
from app.services.transactions import LineIn, cancel_transaction, create_transaction, create_tukar_tambah
from tests.helpers import make_item


def _harga(conn, tanggal):
    for kadar, jual, beli in (("22K", 1_200_000, 1_100_000), ("24K", 1_300_000, 1_200_000)):
        conn.execute(
            "INSERT OR REPLACE INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)",
            (tanggal, kadar, jual, beli),
        )


def _data(conn, kasir_id, owner_id):
    for d in ("2026-11-18", "2026-11-19"):
        _harga(conn, d)
    a, b = make_item(conn), make_item(conn, name="B")
    create_transaction(conn, "jual", kasir_id, "x", [LineIn(item_id=a, harga_per_gram=1_200_000, ongkos=50_000)], "2026-11-18 09:00:00")
    batal = create_transaction(conn, "jual", kasir_id, "x", [LineIn(item_id=b, harga_per_gram=1_200_000, ongkos=50_000)], "2026-11-19 09:00:00")
    create_transaction(conn, "beli_pelanggan", kasir_id, "y", [LineIn(kadar="22K", berat=4, harga_per_gram=1_100_000)], "2026-11-19 10:00:00")
    create_transaction(
        conn, "beli_supplier", kasir_id, "z",
        [LineIn(kadar="24K", berat=1.5, harga_per_gram=1_200_000, nama="K", jenis="Kalung")], "2026-11-19 11:00:00",
    )
    cancel_transaction(conn, batal, owner_id, "salah")


def test_summary_hanya_transaksi_aktif(conn, kasir_id, owner_id):
    _data(conn, kasir_id, owner_id)
    s = summary(conn, "2026-11-18", "2026-11-19")
    assert s["penjualan"] == 3_050_000
    assert s["pembelian"] == 6_200_000
    assert s["gram_jual"] == 2.5 and s["gram_beli"] == 5.5
    assert s["series"][0] == {"tgl": "2026-11-18", "penjualan": 3_050_000, "pembelian": 0}
    assert s["series"][1] == {"tgl": "2026-11-19", "penjualan": 0, "pembelian": 6_200_000}
    assert len(s["recent"]) == 4 and s["recent"][0]["kasir"] == "kasir0"


def test_summary_satu_hari_dan_hari_kosong(conn, kasir_id, owner_id):
    _data(conn, kasir_id, owner_id)
    s = summary(conn, "2026-11-19", "2026-11-19")
    assert s["penjualan"] == 0 and s["pembelian"] == 6_200_000 and len(s["series"]) == 1
    s = summary(conn, "2026-11-17", "2026-11-19")
    assert [p["tgl"] for p in s["series"]] == ["2026-11-17", "2026-11-18", "2026-11-19"]
    assert s["series"][0] == {"tgl": "2026-11-17", "penjualan": 0, "pembelian": 0}


def test_summary_tukar_tambah_masuk_dua_sisi(conn, kasir_id):
    _harga(conn, "2026-11-19")
    item = make_item(conn)
    create_tukar_tambah(
        conn, kasir_id, "Budi",
        [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)],
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000)],
        "2026-11-19 10:00:00",
    )
    s = summary(conn, "2026-11-19", "2026-11-19")
    assert (s["penjualan"], s["pembelian"], s["gram_jual"], s["gram_beli"]) == (3_050_000, 2_750_000, 2.5, 2.5)


def test_series_dibatasi_92_hari(conn):
    s = summary(conn, "2026-01-01", "2026-11-19")
    assert len(s["series"]) == 92 and s["series"][-1]["tgl"] == "2026-11-19"


def test_preset_range():
    kamis = date(2026, 11, 19)
    assert preset_range("hari_ini", kamis) == ("2026-11-19", "2026-11-19")
    assert preset_range("minggu_ini", kamis) == ("2026-11-16", "2026-11-19")
    assert preset_range("bulan_ini", kamis) == ("2026-11-01", "2026-11-19")
    assert preset_range("ngawur", kamis) == ("2026-11-19", "2026-11-19")


def test_nice_scale():
    assert nice_scale(0) == (1_000_000, [0, 500_000, 1_000_000])
    assert nice_scale(3_050_000) == (4_000_000, [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000])
    assert nice_scale(7_300_000) == (8_000_000, [0, 2_000_000, 4_000_000, 6_000_000, 8_000_000])
```

`tests/test_dashboard.py`:
```python
from app.services.transactions import LineIn, create_transaction
from app.timeutil import today
from tests.helpers import make_item


def _jual_hari_ini(conn, kasir_id):
    conn.execute(
        "INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)", (today(), "22K", 1_200_000, 1_100_000)
    )
    item = make_item(conn)
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)])


def test_pemilik_melihat_nominal_dan_grafik(owner_client, conn, kasir_id):
    _jual_hari_ini(conn, kasir_id)
    html = owner_client.get("/").text
    for teks in ("Total penjualan", "Total pembelian", "Gramasi jual", "Gramasi beli", "Rp 3.050.000", "Tren harian", "Lihat sebagai tabel"):
        assert teks in html


def test_kasir_tanpa_nominal(kasir_client, conn, kasir_id):
    _jual_hari_ini(conn, kasir_id)
    html = kasir_client.get("/").text
    assert "Total penjualan" in html and "Gramasi jual" in html
    assert "3.050.000" not in html and "Tren harian" not in html


def test_preset_dan_rentang(owner_client):
    assert owner_client.get("/?preset=bulan_ini").status_code == 200
    r = owner_client.get("/?start=2026-11-01&end=2026-11-19")
    assert r.status_code == 200 and "2026-11-01" in r.text


def test_rentang_tidak_valid_tidak_error(owner_client):
    r = owner_client.get("/?start=ngawur&end=2026-11-19")
    assert r.status_code == 200 and "Rentang tanggal tidak valid" in r.text
    r = owner_client.get("/?start=2026-11-19&end=2026-11-01")
    assert r.status_code == 200 and "Rentang tanggal tidak valid" in r.text


def test_dashboard_butuh_login(client, conn):
    assert client.get("/", follow_redirects=False).status_code == 303
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_reports.py tests/test_dashboard.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.services.reports'`.

- [ ] **Step 3: Tulis implementasi**

`app/services/reports.py`:
```python
from __future__ import annotations

import math
from datetime import date, timedelta

MAX_CHART_DAYS = 92
_RANGE = "t.status='aktif' AND date(t.tanggal) BETWEEN ? AND ?"


def preset_range(preset: str, today: date) -> tuple[str, str]:
    if preset == "minggu_ini":
        start = today - timedelta(days=today.weekday())
    elif preset == "bulan_ini":
        start = today.replace(day=1)
    else:
        start = today
    return start.isoformat(), today.isoformat()


def nice_scale(vmax: int) -> tuple[int, list[int]]:
    vmax = max(int(vmax), 1_000_000)
    raw = vmax / 4
    exp = 10 ** math.floor(math.log10(raw))
    step = next(m * exp for m in (1, 2, 5, 10) if m * exp >= raw)
    top = step * math.ceil(vmax / step)
    return int(top), [int(i * step) for i in range(int(top // step) + 1)]


def _scalar(conn, sql: str, *args):
    return conn.execute(sql, args).fetchone()[0]


def summary(conn, start: str, end: str) -> dict:
    def total(cond: str) -> int:
        return _scalar(conn, f"SELECT COALESCE(SUM(t.total),0) FROM transactions t WHERE {cond} AND {_RANGE}", start, end)

    def gram(cond: str) -> float:
        value = _scalar(
            conn,
            "SELECT COALESCE(SUM(l.berat),0) FROM transaction_lines l "
            f"JOIN transactions t ON t.id=l.transaction_id WHERE {cond} AND {_RANGE}",
            start, end,
        )
        return round(value, 3)

    last = date.fromisoformat(end)
    first = max(date.fromisoformat(start), last - timedelta(days=MAX_CHART_DAYS - 1))
    rows = conn.execute(
        "SELECT date(t.tanggal) AS tgl, "
        "SUM(CASE WHEN t.tipe='jual' THEN t.total ELSE 0 END) AS penjualan, "
        "SUM(CASE WHEN t.tipe!='jual' THEN t.total ELSE 0 END) AS pembelian "
        f"FROM transactions t WHERE {_RANGE} GROUP BY date(t.tanggal)",
        (first.isoformat(), end),
    ).fetchall()
    per_day = {r["tgl"]: r for r in rows}
    series = []
    day = first
    while day <= last:
        r = per_day.get(day.isoformat())
        series.append(
            {"tgl": day.isoformat(), "penjualan": r["penjualan"] if r else 0, "pembelian": r["pembelian"] if r else 0}
        )
        day += timedelta(days=1)

    recent = conn.execute(
        "SELECT t.id, t.tipe, t.tanggal, t.pihak, t.total, t.status, u.username AS kasir "
        "FROM transactions t JOIN users u ON u.id=t.kasir_id ORDER BY t.id DESC LIMIT 10"
    ).fetchall()
    return {
        "penjualan": total("t.tipe='jual'"),
        "pembelian": total("t.tipe!='jual'"),
        "gram_jual": gram("t.tipe='jual'"),
        "gram_beli": gram("t.tipe!='jual'"),
        "series": series,
        "recent": recent,
    }
```

Tambahkan di `app/web.py`, tepat setelah baris `templates.env.filters["gram"] = _gram`:
```python
_TIPE = {"jual": "Jual", "beli_pelanggan": "Beli dari pelanggan", "beli_supplier": "Beli dari supplier"}


def _jt(v) -> str:
    if not v:
        return "0"
    return f"{v / 1_000_000:g}".replace(".", ",") + " jt"


templates.env.filters["jt"] = _jt
templates.env.filters["tipe_label"] = lambda v: _TIPE.get(v, v)
```

Ganti seluruh isi `app/routes/dashboard_routes.py`:
```python
from datetime import date

from fastapi import APIRouter, Depends, Request

from ..auth import get_db, require_user
from ..services.reports import nice_scale, preset_range, summary
from ..web import render

router = APIRouter()
PRESETS = [("hari_ini", "Hari ini"), ("minggu_ini", "Minggu ini"), ("bulan_ini", "Bulan ini")]


@router.get("/")
def dashboard(
    request: Request, preset: str = "hari_ini", start: str = "", end: str = "",
    user=Depends(require_user), db=Depends(get_db),
):
    error = None
    if start or end:
        try:
            s, e = date.fromisoformat(start), date.fromisoformat(end)
            if s > e:
                raise ValueError
            start, end, preset = s.isoformat(), e.isoformat(), "custom"
        except ValueError:
            error = "Rentang tanggal tidak valid"
            start = end = ""
    if not (start and end):
        preset = preset if preset in [k for k, _ in PRESETS] else "hari_ini"
        start, end = preset_range(preset, date.today())
    data = summary(db, start, end)
    peak = max([p[k] for p in data["series"] for k in ("penjualan", "pembelian")], default=0)
    top, ticks = nice_scale(peak)
    return render(
        request, "dashboard.html", user,
        d=data, owner=user["role"] == "pemilik", start=start, end=end, preset=preset,
        presets=PRESETS, top=top, ticks=ticks, error=error,
    )
```

Hapus `app/templates/home.html` (`git rm app/templates/home.html`).

`app/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<h1>Dashboard</h1>
<form class="row" method="get">
  {% for key, label in presets %}<a class="chip {{ 'on' if preset == key }}" href="/?preset={{ key }}">{{ label }}</a>{% endfor %}
  <label>Dari <input type="date" name="start" value="{{ start }}"></label>
  <label>Sampai <input type="date" name="end" value="{{ end }}"></label>
  <button>Terapkan</button>
</form>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<p class="muted">{{ start }} s/d {{ end }}</p>

<div class="tiles">
  <div class="tile"><div class="tl">Total penjualan</div><div class="tv">{{ (d.penjualan if owner else None)|rupiah }}</div></div>
  <div class="tile"><div class="tl">Total pembelian</div><div class="tv">{{ (d.pembelian if owner else None)|rupiah }}</div></div>
  <div class="tile"><div class="tl">Gramasi jual</div><div class="tv">{{ d.gram_jual|gram }}</div></div>
  <div class="tile"><div class="tl">Gramasi beli</div><div class="tv">{{ d.gram_beli|gram }}</div></div>
</div>

{% if owner %}
<section class="card">
  <h2>Tren harian</h2>
  <div class="legend">
    <span><i class="sw s1"></i>Penjualan</span>
    <span><i class="sw s2"></i>Pembelian</span>
  </div>
  <div class="chart" role="img" aria-label="Grafik batang penjualan dan pembelian per hari">
    <div class="yaxis">{% for t in ticks|reverse %}<span>{{ t|jt }}</span>{% endfor %}</div>
    <div class="plot">
      {% for t in ticks %}<div class="gridline" style="bottom:{{ (t / top * 100)|round(2) }}%"></div>{% endfor %}
      <div class="cols">
        {% for p in d.series %}
        <div class="grp" tabindex="0" data-tip="{{ p.tgl }}|Penjualan {{ p.penjualan|rupiah }}|Pembelian {{ p.pembelian|rupiah }}">
          <div class="bar s1" style="height:{{ (p.penjualan / top * 100)|round(2) }}%"></div>
          <div class="bar s2" style="height:{{ (p.pembelian / top * 100)|round(2) }}%"></div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>
  <div class="xaxis"><span>{{ d.series[0].tgl }}</span>{% if d.series|length > 1 %}<span>{{ d.series[-1].tgl }}</span>{% endif %}</div>
  <details>
    <summary>Lihat sebagai tabel</summary>
    <table>
      <tr><th>Tanggal</th><th class="num">Penjualan</th><th class="num">Pembelian</th></tr>
      {% for p in d.series %}<tr><td>{{ p.tgl }}</td><td class="num">{{ p.penjualan|rupiah }}</td><td class="num">{{ p.pembelian|rupiah }}</td></tr>{% endfor %}
    </table>
  </details>
</section>
<div id="tip" class="tip" hidden></div>
{% endif %}

<section class="card">
  <h2>10 transaksi terakhir</h2>
  <table>
    <tr><th>#</th><th>Waktu</th><th>Tipe</th><th>Pihak</th>{% if owner %}<th class="num">Total</th>{% endif %}<th>Status</th></tr>
    {% for r in d.recent %}
    <tr>
      <td><a href="/transaksi/{{ r.id }}">{{ r.id }}</a></td><td>{{ r.tanggal }}</td><td>{{ r.tipe|tipe_label }}</td><td>{{ r.pihak }}</td>
      {% if owner %}<td class="num">{{ r.total|rupiah }}</td>{% endif %}<td>{{ r.status }}</td>
    </tr>
    {% else %}
    <tr><td colspan="6" class="muted">Belum ada transaksi.</td></tr>
    {% endfor %}
  </table>
</section>
{% endblock %}
{% block scripts %}
{% if owner %}
<script>
(function () {
  const tip = document.getElementById('tip');
  function show(g) {
    const parts = g.dataset.tip.split('|');
    tip.replaceChildren(...parts.map((t, i) => Object.assign(document.createElement(i ? 'div' : 'b'), { textContent: t })));
    tip.hidden = false;
    const r = g.getBoundingClientRect();
    const left = r.left + r.width / 2 - tip.offsetWidth / 2;
    tip.style.left = Math.min(window.innerWidth - tip.offsetWidth - 8, Math.max(8, left)) + 'px';
    tip.style.top = Math.max(8, r.top - tip.offsetHeight - 6) + 'px';
  }
  document.querySelectorAll('.grp').forEach(g => {
    g.addEventListener('mouseenter', () => show(g));
    g.addEventListener('focus', () => show(g));
    g.addEventListener('mouseleave', () => { tip.hidden = true; });
    g.addEventListener('blur', () => { tip.hidden = true; });
  });
})();
</script>
{% endif %}
{% endblock %}
```

Tambahkan di akhir `app/static/app.css`:
```css
.chip{padding:6px 12px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{border:1px solid var(--line);border-radius:10px;padding:12px}
.tl{color:var(--ink2);font-size:14px}
.tv{font-size:24px;font-weight:600}
.legend{display:flex;gap:16px;margin:4px 0 10px;color:var(--ink)}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.s1{background:var(--s1)}
.s2{background:var(--s2)}
.chart{display:flex;gap:8px;height:220px}
.yaxis{display:flex;flex-direction:column;justify-content:space-between;color:var(--ink2);font-size:12px;text-align:right;min-width:54px}
.plot{position:relative;flex:1;border-bottom:1px solid var(--line);overflow:hidden}
.gridline{position:absolute;left:0;right:0;border-top:1px solid var(--line)}
.cols{position:absolute;inset:0;display:flex;align-items:flex-end;gap:6px;overflow-x:auto}
.grp{height:100%;flex:1;min-width:14px;max-width:56px;display:flex;align-items:flex-end;justify-content:center;gap:2px;outline-offset:-2px}
.bar{flex:1;max-width:24px;border-radius:4px 4px 0 0}
.xaxis{display:flex;justify-content:space-between;color:var(--ink2);font-size:12px;margin:4px 0 0 62px}
.tip{position:fixed;z-index:10;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13px;pointer-events:none}
details{margin-top:10px}
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus. Lalu cek tampilan: jalankan `TOKOEMAS_DATA=/tmp/tokodev python -c "import uvicorn; from app.main import create_app; from app.config import Settings; from pathlib import Path; uvicorn.run(create_app(Settings(Path('/tmp/tokodev'), https_only=False)), port=8000)"`, buka `http://localhost:8000/setup`, buat pemilik, isi harga, buat satu transaksi lewat API, lalu lihat `/`. Pastikan label sumbu tidak bertabrakan, batang tidak melewati 24px, dan tooltip muncul saat hover.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: dashboard dengan kartu total, gramasi, grafik tren, dan tabel"
```

---

### Task 7: Halaman scan (kamera HP dan scanner USB)

**Files:**
- Create: `app/routes/scan_routes.py`, `app/templates/scan.html`, `app/static/lookup.js`, `app/static/vendor/html5-qrcode.min.js`, `app/static/vendor/html5-qrcode.LICENSE`
- Modify: `app/main.py` (daftarkan router)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `GET /api/items/by-code/{code}` (Rencana 1, Task 4), `require_user`, `render`.
- Produces: `GET /scan`; `lookup.js` mendefinisikan fungsi global `lookupCode(code) -> Promise<object>` (melempar `Error("Kode tidak terdaftar")` jika 404), `rupiah(n)`, `fmtGram(n)`. Halaman scan menyimpan pilihan di `sessionStorage['keranjang']` (array objek hasil `lookupCode`) lalu membuka `/transaksi/baru?tipe=jual`.

- [ ] **Step 1: Ambil pustaka scan dan tulis tes yang gagal**

```bash
mkdir -p /tmp/h5q && cd /tmp/h5q && npm pack html5-qrcode@2.3.8 && tar xzf html5-qrcode-2.3.8.tgz
mkdir -p /home/claude/toko-emas/app/static/vendor
cp /tmp/h5q/package/html5-qrcode.min.js /home/claude/toko-emas/app/static/vendor/
cp /tmp/h5q/package/LICENSE /home/claude/toko-emas/app/static/vendor/html5-qrcode.LICENSE
ls -la /home/claude/toko-emas/app/static/vendor
```
Expected: `html5-qrcode.min.js` berukuran puluhan–ratusan KB.

`tests/test_scan.py`:
```python
from pathlib import Path


def test_halaman_scan(kasir_client):
    r = kasir_client.get("/scan")
    assert r.status_code == 200
    for teks in ('id="kode"', 'id="cam"', "lookup.js", "html5-qrcode.min.js"):
        assert teks in r.text


def test_scan_butuh_login(client, conn):
    assert client.get("/scan", follow_redirects=False).status_code == 303


def test_aset_statis_tersedia(client):
    assert client.get("/static/lookup.js").status_code == 200
    r = client.get("/static/vendor/html5-qrcode.min.js")
    assert r.status_code == 200 and len(r.content) > 10_000
    assert Path("app/static/vendor/html5-qrcode.LICENSE").exists()
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_scan.py -q`
Expected: `test_halaman_scan` gagal 404 (route belum ada).

- [ ] **Step 3: Tulis implementasi**

`app/routes/scan_routes.py`:
```python
from fastapi import APIRouter, Depends, Request

from ..auth import require_user
from ..web import render

router = APIRouter()


@router.get("/scan")
def scan(request: Request, user=Depends(require_user)):
    return render(request, "scan.html", user)
```

`app/static/lookup.js`:
```js
async function lookupCode(code) {
  const r = await fetch('/api/items/by-code/' + encodeURIComponent(code.trim()));
  if (r.status === 404) throw new Error('Kode tidak terdaftar');
  if (!r.ok) throw new Error('Gagal mengambil data perhiasan');
  return r.json();
}
function rupiah(n) { return 'Rp ' + Math.round(n).toLocaleString('id-ID'); }
function fmtGram(n) { return (+n).toFixed(3).replace(/\.?0+$/, '') + ' g'; }
```

`app/templates/scan.html`:
```html
{% extends "base.html" %}
{% block title %}Scan{% endblock %}
{% block content %}
<h1>Scan perhiasan</h1>
<form id="f" class="row">
  <input id="kode" autofocus autocomplete="off" placeholder="Scan atau ketik kode, lalu Enter">
  <button>Cari</button>
  <button type="button" id="cam">Kamera</button>
</form>
<div id="reader" hidden></div>
<p id="err" class="error" hidden></p>
<div id="hasil" class="card" hidden>
  <img id="r-foto" class="thumb" style="max-width:240px" alt="" hidden>
  <h2 id="r-code"></h2>
  <p id="r-name"></p>
  <p id="r-detail"></p>
  <p id="r-status"></p>
  <button type="button" id="tambah">Tambah ke transaksi</button>
  <a id="r-edit" href="#">Lihat di katalog</a>
</div>
<p class="muted">Kamera memerlukan HTTPS. Jika kamera tidak aktif, buka <a href="/sertifikat">panduan sertifikat</a> atau pakai scanner USB.</p>
{% endblock %}
{% block scripts %}
<script src="/static/vendor/html5-qrcode.min.js"></script>
<script src="/static/lookup.js"></script>
<script>
const $ = id => document.getElementById(id);
let scanner = null, current = null;

function showError(msg) { $('err').textContent = msg; $('err').hidden = false; }

async function show(code) {
  $('err').hidden = true; $('hasil').hidden = true;
  try {
    const it = await lookupCode(code);
    current = it;
    $('r-code').textContent = it.code;
    $('r-name').textContent = it.name + ' · ' + it.jenis;
    $('r-detail').textContent = it.kadar + ' · ' + fmtGram(it.berat) + ' · ongkos ' + rupiah(it.ongkos) +
      (it.harga_jual ? ' · harga/g ' + rupiah(it.harga_jual) : ' · harga hari ini belum diisi');
    $('r-status').textContent = 'Status: ' + it.status;
    const f = $('r-foto');
    if (it.foto_url) { f.src = it.foto_url; f.hidden = false; } else { f.hidden = true; }
    $('tambah').disabled = it.status !== 'tersedia';
    $('r-edit').href = '/katalog/' + it.id + '/edit';
    $('hasil').hidden = false;
  } catch (e) { showError(e.message); }
  $('kode').value = ''; $('kode').focus();
}

$('f').onsubmit = ev => { ev.preventDefault(); if ($('kode').value.trim()) show($('kode').value); };

$('tambah').onclick = () => {
  const cart = JSON.parse(sessionStorage.getItem('keranjang') || '[]');
  if (!cart.some(c => c.id === current.id)) cart.push(current);
  sessionStorage.setItem('keranjang', JSON.stringify(cart));
  location.href = '/transaksi/baru?tipe=jual';
};

async function stopCam() {
  if (!scanner) return;
  try { await scanner.stop(); scanner.clear(); } catch (e) { /* sudah berhenti */ }
  scanner = null; $('reader').hidden = true;
}

$('cam').onclick = async () => {
  if (scanner) { await stopCam(); return; }
  if (!window.isSecureContext) { showError('Kamera butuh HTTPS. Pakai scanner USB atau ketik kode.'); return; }
  scanner = new Html5Qrcode('reader');
  $('reader').hidden = false;
  try {
    await scanner.start(
      { facingMode: 'environment' },
      { fps: 10, formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE, Html5QrcodeSupportedFormats.CODE_128] },
      async text => { await stopCam(); show(text); },
      () => {}
    );
  } catch (e) { showError('Kamera tidak bisa dibuka: ' + e); await stopCam(); }
};
</script>
{% endblock %}
```

Modifikasi `app/main.py`: ganti
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes, transactions_routes
```
menjadi
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes, scan_routes, transactions_routes
```
dan ganti
```python
    items_routes.router,
    transactions_routes.router,
```
menjadi
```python
    items_routes.router,
    scan_routes.router,
    transactions_routes.router,
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: halaman scan dengan kamera HP dan input scanner USB"
```

---

### Task 8: Layar transaksi, riwayat, detail, pembatalan

**Files:**
- Modify: `app/services/transactions.py` (tambah `list_transactions`, `get_transaction`)
- Modify: `app/routes/transactions_routes.py` (ganti seluruh isi)
- Create: `app/templates/transaksi_baru.html`, `transaksi_riwayat.html`, `transaksi_detail.html`
- Test: `tests/test_transactions_pages.py`

**Interfaces:**
- Consumes: `create_transaction`, `create_tukar_tambah`, `cancel_transaction`, `LineIn`, `TIPE`, `TransactionError`, `ItemNotAvailable` (Rencana 1); `lookupCode`, `rupiah`, `fmtGram` (`lookup.js`); `GET /api/harga`; `render`, filter `tipe_label`.
- Produces:
  - `list_transactions(conn, start: str, end: str, tipe: str = "") -> list[Row]` (kolom transaksi + `kasir`, terbaru dulu, maksimum 500).
  - `get_transaction(conn, tx_id) -> dict | None` dengan kunci `t` (Row + `kasir`), `lines` (kolom baris + `code`, `nama`, `created_by_tx`, `iid`), `pair` (Row `id, tipe` atau `None`).
  - Route: `GET /transaksi/baru`, `GET /transaksi` (query `start`, `end`, `tipe`; default 30 hari terakhir), `GET /transaksi/{tx_id}`, `POST /transaksi/{tx_id}/batal` (pemilik, form `alasan`), serta API dari Rencana 1.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/test_transactions_pages.py`:
```python
from app.services.items import get_item
from app.services.transactions import LineIn, create_transaction
from app.timeutil import today
from tests.helpers import make_item


def _harga(conn):
    conn.execute(
        "INSERT INTO daily_prices(tanggal,kadar,harga_jual,harga_beli) VALUES (?,?,?,?)", (today(), "22K", 1_200_000, 1_100_000)
    )


def test_halaman_transaksi_baru(kasir_client):
    r = kasir_client.get("/transaksi/baru")
    assert r.status_code == 200
    for teks in ('id="simpan"', 'id="tipe"', "tukar_tambah", "lookup.js"):
        assert teks in r.text


def test_riwayat_dan_filter_tipe(kasir_client, conn, kasir_id):
    _harga(conn)
    item = make_item(conn)
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000, ongkos=50_000)])
    create_transaction(conn, "beli_pelanggan", kasir_id, "Ani", [LineIn(kadar="22K", berat=2, harga_per_gram=1_100_000)])
    html = kasir_client.get("/transaksi").text
    assert "Budi" in html and "Ani" in html
    html = kasir_client.get("/transaksi?tipe=jual").text
    assert "Budi" in html and "Ani" not in html
    assert kasir_client.get("/transaksi?start=ngawur").status_code == 200


def test_detail_dan_tautan_perhiasan_baru(kasir_client, conn, kasir_id):
    _harga(conn)
    tid = create_transaction(
        conn, "beli_supplier", kasir_id, "PT Emas",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin Baru", jenis="Cincin")],
    )
    html = kasir_client.get(f"/transaksi/{tid}").text
    for teks in ("GLD-000001", "Cincin Baru", "Rp 2.750.000", "/katalog/1/edit", "PT Emas"):
        assert teks in html


def test_detail_tidak_ada(kasir_client):
    assert kasir_client.get("/transaksi/999").status_code == 404


def test_batal_hanya_pemilik(kasir_client, owner_client, conn, kasir_id):
    _harga(conn)
    item = make_item(conn)
    tid = create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=item, harga_per_gram=1_200_000)])
    r = kasir_client.post(f"/transaksi/{tid}/batal", data={"alasan": "salah"}, follow_redirects=False)
    assert r.status_code == 403
    r = owner_client.post(f"/transaksi/{tid}/batal", data={"alasan": ""})
    assert r.status_code == 400 and "wajib" in r.text
    r = owner_client.post(f"/transaksi/{tid}/batal", data={"alasan": "salah input"}, follow_redirects=False)
    assert r.status_code == 303
    html = owner_client.get(f"/transaksi/{tid}").text
    assert "DIBATALKAN" in html and "salah input" in html
    assert get_item(conn, item)["status"] == "tersedia"


def test_batal_beli_yang_perhiasannya_terjual_ditolak(owner_client, conn, kasir_id):
    _harga(conn)
    beli = create_transaction(
        conn, "beli_supplier", kasir_id, "PT",
        [LineIn(kadar="22K", berat=2.5, harga_per_gram=1_100_000, nama="Cincin", jenis="Cincin")],
    )
    create_transaction(conn, "jual", kasir_id, "Budi", [LineIn(item_id=1, harga_per_gram=1_200_000)])
    r = owner_client.post(f"/transaksi/{beli}/batal", data={"alasan": "salah"})
    assert r.status_code == 400 and "GLD-000001" in r.text
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_transactions_pages.py -q`
Expected: gagal 404/405 karena halaman belum ada.

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke akhir `app/services/transactions.py`:
```python
def list_transactions(conn, start: str, end: str, tipe: str = ""):
    sql = (
        "SELECT t.*, u.username AS kasir FROM transactions t JOIN users u ON u.id=t.kasir_id "
        "WHERE date(t.tanggal) BETWEEN ? AND ?"
    )
    args = [start, end]
    if tipe:
        sql += " AND t.tipe=?"
        args.append(tipe)
    return conn.execute(sql + " ORDER BY t.id DESC LIMIT 500", args).fetchall()


def get_transaction(conn, tx_id: int):
    t = conn.execute(
        "SELECT t.*, u.username AS kasir FROM transactions t JOIN users u ON u.id=t.kasir_id WHERE t.id=?",
        (tx_id,),
    ).fetchone()
    if t is None:
        return None
    lines = conn.execute(
        "SELECT l.*, i.code AS code, i.name AS nama, i.created_by_tx AS created_by_tx, i.id AS iid "
        "FROM transaction_lines l LEFT JOIN items i ON i.id=l.item_id WHERE l.transaction_id=? ORDER BY l.id",
        (tx_id,),
    ).fetchall()
    pair = None
    if t["grup_tukar_tambah"]:
        pair = conn.execute(
            "SELECT id, tipe FROM transactions WHERE grup_tukar_tambah=? AND id!=?", (t["grup_tukar_tambah"], tx_id)
        ).fetchone()
    return {"t": t, "lines": lines, "pair": pair}
```

Ganti seluruh isi `app/routes/transactions_routes.py`:
```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..auth import get_db, require_owner, require_user
from ..config import JENIS
from ..services.items import ItemNotAvailable
from ..services.transactions import (
    TIPE, LineIn, TransactionError, cancel_transaction, create_transaction, create_tukar_tambah,
    get_transaction, list_transactions,
)
from ..web import render

router = APIRouter()


class LineBody(BaseModel):
    kadar: str = ""
    berat: float = 0
    harga_per_gram: int
    ongkos: int = 0
    item_id: int | None = None
    nama: str | None = None
    jenis: str | None = None


class TransaksiBody(BaseModel):
    tipe: str
    pihak: str = ""
    lines: list[LineBody]


class TukarTambahBody(BaseModel):
    pihak: str = ""
    jual_lines: list[LineBody]
    beli_lines: list[LineBody]


def _lines(items: list[LineBody]) -> list[LineIn]:
    return [LineIn(**i.model_dump()) for i in items]


@router.post("/api/transaksi")
def api_buat(body: TransaksiBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        tx_id = create_transaction(db, body.tipe, user["id"], body.pihak, _lines(body.lines))
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"id": tx_id}


@router.post("/api/transaksi/tukar-tambah")
def api_tukar_tambah(body: TukarTambahBody, user=Depends(require_user), db=Depends(get_db)):
    try:
        r = create_tukar_tambah(db, user["id"], body.pihak, _lines(body.jual_lines), _lines(body.beli_lines))
    except ItemNotAvailable as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {
        "jual_id": r.jual_id, "beli_id": r.beli_id,
        "total_jual": r.total_jual, "total_beli": r.total_beli, "selisih": r.selisih,
    }


@router.get("/transaksi/baru")
def baru(request: Request, user=Depends(require_user)):
    return render(request, "transaksi_baru.html", user, JENIS=JENIS)


@router.get("/transaksi")
def riwayat(
    request: Request, start: str = "", end: str = "", tipe: str = "",
    user=Depends(require_user), db=Depends(get_db),
):
    try:
        e = date.fromisoformat(end) if end else date.today()
        s = date.fromisoformat(start) if start else e - timedelta(days=29)
    except ValueError:
        e = date.today()
        s = e - timedelta(days=29)
    tipe = tipe if tipe in TIPE else ""
    rows = list_transactions(db, s.isoformat(), e.isoformat(), tipe)
    return render(request, "transaksi_riwayat.html", user, rows=rows, start=s.isoformat(), end=e.isoformat(), tipe=tipe, TIPE=TIPE)


def _detail(request, user, db, tx_id, status_code=200, error=None):
    data = get_transaction(db, tx_id)
    if data is None:
        raise HTTPException(404, "Transaksi tidak ditemukan")
    return render(request, "transaksi_detail.html", user, status_code=status_code, error=error, **data)


@router.get("/transaksi/{tx_id}")
def detail(tx_id: int, request: Request, user=Depends(require_user), db=Depends(get_db)):
    return _detail(request, user, db, tx_id)


@router.post("/transaksi/{tx_id}/batal")
def batal(tx_id: int, request: Request, alasan: str = Form(""), user=Depends(require_owner), db=Depends(get_db)):
    try:
        cancel_transaction(db, tx_id, user["id"], alasan)
    except TransactionError as e:
        return _detail(request, user, db, tx_id, 400, str(e))
    return RedirectResponse(f"/transaksi/{tx_id}", status_code=303)
```

`app/templates/transaksi_riwayat.html`:
```html
{% extends "base.html" %}
{% block title %}Riwayat transaksi{% endblock %}
{% block content %}
<h1>Riwayat transaksi</h1>
<form class="row" method="get">
  <label>Dari <input type="date" name="start" value="{{ start }}"></label>
  <label>Sampai <input type="date" name="end" value="{{ end }}"></label>
  <select name="tipe"><option value="">Semua tipe</option>{% for t in TIPE %}<option value="{{ t }}" {{ 'selected' if t == tipe }}>{{ t|tipe_label }}</option>{% endfor %}</select>
  <button>Terapkan</button>
</form>
<table>
  <tr><th>#</th><th>Waktu</th><th>Tipe</th><th>Pihak</th><th>Kasir</th><th class="num">Total</th><th>Status</th></tr>
  {% for r in rows %}
  <tr>
    <td><a href="/transaksi/{{ r.id }}">{{ r.id }}</a></td><td>{{ r.tanggal }}</td><td>{{ r.tipe|tipe_label }}</td>
    <td>{{ r.pihak }}</td><td>{{ r.kasir }}</td><td class="num">{{ r.total|rupiah }}</td>
    <td>{{ r.status }}{% if r.grup_tukar_tambah %} · tukar tambah{% endif %}</td>
  </tr>
  {% else %}
  <tr><td colspan="7" class="muted">Tidak ada transaksi pada rentang ini.</td></tr>
  {% endfor %}
</table>
{% endblock %}
```

`app/templates/transaksi_detail.html`:
```html
{% extends "base.html" %}
{% block title %}Transaksi #{{ t.id }}{% endblock %}
{% block content %}
<h1>Transaksi #{{ t.id }} — {{ t.tipe|tipe_label }}</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<p>{{ t.tanggal }} · Kasir: {{ t.kasir }}{% if t.pihak %} · {{ t.pihak }}{% endif %}</p>
{% if t.status == 'batal' %}<p class="error">DIBATALKAN — {{ t.alasan_batal }}</p>{% endif %}
{% if pair %}<p>Tukar tambah: pasangannya <a href="/transaksi/{{ pair.id }}">#{{ pair.id }} ({{ pair.tipe|tipe_label }})</a></p>{% endif %}
<table>
  <tr><th>Barang</th><th>Kadar</th><th class="num">Berat</th><th class="num">Harga/g</th><th class="num">Ongkos</th><th class="num">Subtotal</th></tr>
  {% for ln in lines %}
  <tr>
    <td>{% if ln.code %}{{ ln.code }} · {{ ln.nama }}{% else %}Emas curah{% endif %}
      {% if ln.created_by_tx == t.id %}<br><span class="noprint"><a href="/katalog/{{ ln.iid }}/edit">Tambah foto</a> · <a href="/label/{{ ln.iid }}">Cetak label</a></span>{% endif %}</td>
    <td>{{ ln.kadar }}</td><td class="num">{{ ln.berat|gram }}</td><td class="num">{{ ln.harga_per_gram|rupiah }}</td>
    <td class="num">{{ ln.ongkos|rupiah }}</td><td class="num">{{ ln.subtotal|rupiah }}</td>
  </tr>
  {% endfor %}
  <tr><th colspan="5">Total</th><th class="num">{{ t.total|rupiah }}</th></tr>
</table>
{% if t.status == 'aktif' and user.role == 'pemilik' %}
<form method="post" action="/transaksi/{{ t.id }}/batal" class="card noprint">
  <label>Alasan pembatalan<br><input name="alasan" required size="40"></label>
  <button>Batalkan transaksi</button>
</form>
{% endif %}
<p class="noprint"><button onclick="window.print()">Cetak struk</button> <a href="/transaksi">Kembali ke riwayat</a></p>
{% endblock %}
```

`app/templates/transaksi_baru.html`:
```html
{% extends "base.html" %}
{% block title %}Transaksi baru{% endblock %}
{% block content %}
<h1>Transaksi baru</h1>
<div class="row">
  <label>Tipe<br>
    <select id="tipe">
      <option value="jual">Jual</option>
      <option value="beli_pelanggan">Beli dari pelanggan</option>
      <option value="tukar_tambah">Tukar tambah</option>
      <option value="beli_supplier">Beli dari supplier</option>
    </select>
  </label>
  <label>Nama pelanggan / supplier<br><input id="pihak"></label>
</div>
<p id="harga-info" class="error" hidden>Harga harian hari ini belum diisi. Minta pemilik mengisinya di menu Harga.</p>
<p id="warn" class="error" hidden></p>

<section id="sec-jual" class="card">
  <h2 id="h-jual">Barang dijual</h2>
  <div class="row">
    <input id="kode" placeholder="Scan / ketik kode perhiasan" autocomplete="off">
    <button type="button" id="btn-kode">Tambah</button>
    <a href="/scan">Scan dengan kamera</a>
    <button type="button" id="btn-curah-jual">+ Emas curah</button>
  </div>
  <table id="t-jual">
    <thead><tr><th>Barang</th><th>Kadar</th><th>Berat (g)</th><th>Harga/g</th><th>Ongkos</th><th class="num">Subtotal</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
</section>

<section id="sec-beli" class="card">
  <h2 id="h-beli">Barang dibeli</h2>
  <div class="row">
    <button type="button" id="btn-baru-beli">+ Perhiasan baru</button>
    <button type="button" id="btn-curah-beli">+ Emas curah</button>
  </div>
  <table id="t-beli">
    <thead><tr><th>Barang</th><th>Kadar</th><th>Berat (g)</th><th>Harga/g</th><th>Ongkos</th><th class="num">Subtotal</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <p class="muted">Foto perhiasan baru bisa ditambahkan setelah transaksi disimpan.</p>
</section>

<p>Total: <b id="total">Rp 0</b> <span id="selisih" class="muted"></span></p>
<p><button type="button" id="simpan">Simpan transaksi</button></p>
{% endblock %}
{% block scripts %}
<script src="/static/lookup.js"></script>
<script>
const $ = id => document.getElementById(id);
const JENIS = {{ JENIS|tojson }};
const KADAR = ['24K', '22K', '18K', '16K', '9K'];
const L = { jual: [], beli: [] };
let PRICES = {};

function price(side, kadar) {
  const p = PRICES[kadar];
  return p ? (side === 'jual' ? p.jual : p.beli) : 0;
}
function sub(l) { return Math.round((+l.berat || 0) * (+l.harga_per_gram || 0)) + (+l.ongkos || 0); }
function el(tag, props, ...kids) {
  const e = Object.assign(document.createElement(tag), props || {});
  kids.forEach(k => e.append(k));
  return e;
}
function showWarn(msg) { $('warn').textContent = msg; $('warn').hidden = !msg; }

function numInput(l, key, readOnly, step) {
  const i = el('input', { type: 'number', value: l[key], readOnly: !!readOnly, min: 0, step });
  i.style.width = '7em';
  i.oninput = () => { l[key] = i.value === '' ? 0 : +i.value; totals(); };
  return i;
}
function kadarSelect(side, l, disabled) {
  const opts = KADAR.includes(l.kadar) ? KADAR : [...KADAR, l.kadar];
  const s = el('select', { disabled });
  opts.forEach(k => s.add(new Option(k, k)));
  s.value = l.kadar;
  s.onchange = () => { l.kadar = s.value; l.harga_per_gram = price(side, l.kadar); render(); };
  return s;
}
function labelCell(l) {
  if (l.nama !== undefined) {
    const n = el('input', { placeholder: 'Nama perhiasan', value: l.nama });
    n.oninput = () => { l.nama = n.value; };
    const j = el('select');
    JENIS.forEach(x => j.add(new Option(x, x)));
    j.value = l.jenis;
    j.onchange = () => { l.jenis = j.value; };
    return el('div', {}, n, j);
  }
  return document.createTextNode(l.label || 'Emas curah');
}

function render() {
  for (const side of ['jual', 'beli']) {
    const tb = $('t-' + side).tBodies[0];
    tb.innerHTML = '';
    L[side].forEach((l, idx) => {
      const tr = tb.insertRow();
      const fixed = l.item_id != null;
      tr.insertCell().append(labelCell(l));
      tr.insertCell().append(kadarSelect(side, l, fixed));
      tr.insertCell().append(numInput(l, 'berat', fixed, '0.001'));
      tr.insertCell().append(numInput(l, 'harga_per_gram', false, '1'));
      tr.insertCell().append(numInput(l, 'ongkos', false, '1'));
      const c = tr.insertCell(); c.className = 'num'; l._cell = c;
      const del = el('button', { type: 'button', textContent: '✕' });
      del.onclick = () => { L[side].splice(idx, 1); render(); };
      tr.insertCell().append(del);
    });
  }
  totals();
}

function totals() {
  const sums = { jual: 0, beli: 0 };
  for (const side of ['jual', 'beli']) {
    for (const l of L[side]) {
      const s = sub(l);
      sums[side] += s;
      if (l._cell) l._cell.textContent = rupiah(s);
    }
  }
  const t = $('tipe').value;
  if (t === 'tukar_tambah') {
    const d = sums.jual - sums.beli;
    $('total').textContent = rupiah(Math.abs(d));
    $('selisih').textContent = d >= 0 ? '(pelanggan membayar selisih)' : '(toko membayar selisih)';
  } else {
    $('total').textContent = rupiah(t === 'jual' ? sums.jual : sums.beli);
    $('selisih').textContent = '';
  }
}

function applyTipe() {
  const t = $('tipe').value;
  $('sec-jual').hidden = !(t === 'jual' || t === 'tukar_tambah');
  $('sec-beli').hidden = t === 'jual';
  $('h-jual').textContent = t === 'tukar_tambah' ? 'Barang baru (dijual ke pelanggan)' : 'Barang dijual';
  $('h-beli').textContent = t === 'tukar_tambah' ? 'Barang lama (dibeli dari pelanggan)' : 'Barang dibeli';
  totals();
}

function addItem(it) {
  if (L.jual.some(l => l.item_id === it.id)) return;
  L.jual.push({
    item_id: it.id, label: it.code + ' · ' + it.name, kadar: it.kadar, berat: it.berat,
    harga_per_gram: it.harga_jual || price('jual', it.kadar), ongkos: it.ongkos,
  });
  render();
}
async function addByCode() {
  const code = $('kode').value.trim();
  if (!code) return;
  showWarn('');
  try {
    const it = await lookupCode(code);
    if (it.status !== 'tersedia') throw new Error(it.code + ' berstatus ' + it.status + ', tidak bisa dijual');
    addItem(it);
  } catch (e) { showWarn(e.message); }
  $('kode').value = ''; $('kode').focus();
}

$('kode').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); addByCode(); } };
$('btn-kode').onclick = addByCode;
$('btn-curah-jual').onclick = () => { L.jual.push({ kadar: '22K', berat: 0, harga_per_gram: price('jual', '22K'), ongkos: 0 }); render(); };
$('btn-curah-beli').onclick = () => { L.beli.push({ kadar: '22K', berat: 0, harga_per_gram: price('beli', '22K'), ongkos: 0 }); render(); };
$('btn-baru-beli').onclick = () => {
  L.beli.push({ nama: '', jenis: 'Cincin', kadar: '22K', berat: 0, harga_per_gram: price('beli', '22K'), ongkos: 0 });
  render();
};
$('tipe').onchange = applyTipe;

const pack = arr => arr.map(l => ({
  item_id: l.item_id ?? null, kadar: l.kadar, berat: +l.berat, harga_per_gram: Math.round(+l.harga_per_gram),
  ongkos: Math.round(+l.ongkos || 0), nama: l.nama ? l.nama : null, jenis: l.nama ? l.jenis : null,
}));

$('simpan').onclick = async () => {
  showWarn('');
  const tipe = $('tipe').value, pihak = $('pihak').value;
  const active = tipe === 'jual' ? L.jual : tipe === 'tukar_tambah' ? [...L.jual, ...L.beli] : L.beli;
  if (active.some(l => l.nama !== undefined && !l.nama.trim())) { showWarn('Isi nama untuk perhiasan baru.'); return; }
  let url, body;
  if (tipe === 'tukar_tambah') {
    url = '/api/transaksi/tukar-tambah';
    body = { pihak, jual_lines: pack(L.jual), beli_lines: pack(L.beli) };
  } else {
    url = '/api/transaksi';
    body = { tipe, pihak, lines: pack(tipe === 'jual' ? L.jual : L.beli) };
  }
  $('simpan').disabled = true;
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { showWarn(typeof data.detail === 'string' ? data.detail : 'Data transaksi tidak valid'); return; }
    sessionStorage.removeItem('keranjang');
    location.href = '/transaksi/' + (data.id ?? data.jual_id);
  } finally { $('simpan').disabled = false; }
};

(async function init() {
  try {
    PRICES = (await (await fetch('/api/harga')).json()).harga;
  } catch (e) { PRICES = {}; }
  $('harga-info').hidden = Object.keys(PRICES).length > 0;
  const t = new URLSearchParams(location.search).get('tipe');
  if (t && [...$('tipe').options].some(o => o.value === t)) $('tipe').value = t;
  JSON.parse(sessionStorage.getItem('keranjang') || '[]').forEach(addItem);
  applyTipe();
  render();
})();
</script>
{% endblock %}
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Uji manual alur di browser**

Jalankan server dev seperti di Task 6 Step 4. Lakukan: isi harga 22K → tambah perhiasan di katalog → `/transaksi/baru`, ketik kodenya, Enter → baris muncul dengan harga terisi → ubah harga → simpan → halaman detail tampil. Ulangi untuk tukar tambah dan beli dari supplier (cek tautan "Tambah foto" dan "Cetak label"). Cetak struk lewat tombol cetak (menu navigasi tidak ikut tercetak).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: layar transaksi baru, riwayat, detail struk, dan pembatalan oleh pemilik"
```

---

### Task 9: Pengguna, backup, dan pembatasan jaringan lokal

**Files:**
- Create: `app/netguard.py`, `app/services/backup.py`, `app/routes/admin_routes.py`, `app/templates/pengguna.html`
- Modify: `app/main.py` (router + middleware)
- Test: `tests/test_netguard.py`, `tests/test_backup.py`, `tests/test_admin.py`

**Interfaces:**
- Consumes: `create_user`, `list_users`, `set_password`, `audit.log`, `require_owner`, `Settings`.
- Produces:
  - `app.netguard.is_local(host: str | None) -> bool` (IP privat/loopback/link-local atau nilai non-IP seperti `"testclient"` → `True`; IP publik → `False`; IPv4-mapped IPv6 diperlakukan sebagai IPv4-nya).
  - `app.services.backup`: `make_backup(settings, dest: Path | None = None) -> Path`; `prune(settings, keep: int = 14) -> None`; `backup_if_needed(settings, today_str: str | None = None) -> Path | None` (`today_str` format `YYYYMMDD`); `daily_backup_loop(settings, interval: int = 3600) -> None`.
  - Route (pemilik): `GET /pengguna`, `POST /pengguna` (form `username`, `password`, `role`), `POST /pengguna/{user_id}/sandi` (form `password`), `POST /backup` (unduh zip berisi `tokoemas.db` dan `foto/*`).
  - Middleware `lan_only` di `create_app`: klien non-lokal → 403 `"Hanya untuk jaringan lokal"`.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/test_netguard.py`:
```python
import pytest

from app.netguard import is_local


@pytest.mark.parametrize(
    "host,expected",
    [
        ("192.168.1.5", True), ("10.0.0.2", True), ("172.16.5.5", True), ("127.0.0.1", True), ("::1", True),
        ("169.254.1.1", True), ("8.8.8.8", False), ("172.32.0.1", False), ("::ffff:192.168.1.5", True),
        ("::ffff:8.8.8.8", False), ("testclient", True), (None, True),
    ],
)
def test_is_local(host, expected):
    assert is_local(host) is expected
```

`tests/test_backup.py`:
```python
import sqlite3
import zipfile

from app.services.backup import backup_if_needed, make_backup, prune
from app.services.users import create_user


def test_backup_berisi_db_dan_foto(settings, conn):
    create_user(conn, "bos", "rahasia123", "pemilik")
    (settings.photo_dir / "a.png").write_bytes(b"fotoku")
    path = make_backup(settings)
    assert path.parent == settings.backup_dir and path.suffix == ".zip"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert "tokoemas.db" in names and "foto/a.png" in names
        z.extract("tokoemas.db", settings.data_dir / "restore")
    c = sqlite3.connect(settings.data_dir / "restore" / "tokoemas.db")
    assert c.execute("SELECT username FROM users").fetchone()[0] == "bos"
    c.close()
    assert not list(settings.data_dir.glob("_snap-*"))


def test_backup_harian_sekali_per_hari(settings, conn):
    first = backup_if_needed(settings, "20261119")
    assert first is not None
    assert backup_if_needed(settings, "20261119") is None


def test_prune_menyisakan_terbaru(settings, conn):
    for i in range(5):
        (settings.backup_dir / f"tokoemas-2026110{i + 1}-000000.zip").write_bytes(b"x")
    prune(settings, keep=2)
    assert sorted(p.name for p in settings.backup_dir.glob("*.zip")) == [
        "tokoemas-20261104-000000.zip", "tokoemas-20261105-000000.zip",
    ]
```

`tests/test_admin.py`:
```python
import io
import zipfile

from fastapi.testclient import TestClient


def test_pengguna_hanya_pemilik(kasir_client):
    assert kasir_client.get("/pengguna").status_code == 403
    assert kasir_client.post("/pengguna", data={"username": "x", "password": "rahasia123", "role": "kasir"}).status_code == 403
    assert kasir_client.post("/backup").status_code == 403


def test_tambah_pengguna_lalu_login(owner_client, app):
    r = owner_client.post("/pengguna", data={"username": "siti", "password": "rahasia123", "role": "kasir"}, follow_redirects=False)
    assert r.status_code == 303
    assert "siti" in owner_client.get("/pengguna").text
    baru = TestClient(app, base_url="https://testserver")
    r = baru.post("/login", data={"username": "siti", "password": "rahasia123"}, follow_redirects=False)
    assert r.status_code == 303


def test_tambah_pengguna_duplikat_dan_sandi_pendek(owner_client):
    r = owner_client.post("/pengguna", data={"username": "pemilik1", "password": "rahasia123", "role": "kasir"})
    assert r.status_code == 400 and "sudah dipakai" in r.text
    r = owner_client.post("/pengguna", data={"username": "baru", "password": "123", "role": "kasir"})
    assert r.status_code == 400 and "minimal" in r.text


def test_ganti_sandi(owner_client, app, conn):
    uid = conn.execute("SELECT id FROM users WHERE username='pemilik1'").fetchone()[0]
    r = owner_client.post(f"/pengguna/{uid}/sandi", data={"password": "sandibaru1"}, follow_redirects=False)
    assert r.status_code == 303
    c = TestClient(app, base_url="https://testserver")
    assert c.post("/login", data={"username": "pemilik1", "password": "rahasia123"}).status_code == 401
    assert c.post("/login", data={"username": "pemilik1", "password": "sandibaru1"}, follow_redirects=False).status_code == 303
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE aksi='ganti_sandi'").fetchone()[0] == 1


def test_unduh_backup(owner_client):
    r = owner_client.post("/backup")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert "tokoemas.db" in z.namelist()
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_netguard.py tests/test_backup.py tests/test_admin.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.netguard'`.

- [ ] **Step 3: Tulis implementasi**

`app/netguard.py`:
```python
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
```

`app/services/backup.py`:
```python
from __future__ import annotations

import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path


def make_backup(settings, dest: Path | None = None, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest or settings.backup_dir / f"tokoemas-{stamp}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    snap = settings.data_dir / f"_snap-{stamp}.db"
    src, dst = sqlite3.connect(settings.db_path), sqlite3.connect(snap)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    try:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "tokoemas.db")
            for p in sorted(settings.photo_dir.glob("*")):
                if p.is_file():
                    z.write(p, f"foto/{p.name}")
    finally:
        snap.unlink(missing_ok=True)
    return dest


def prune(settings, keep: int = 14) -> None:
    files = sorted(settings.backup_dir.glob("tokoemas-*.zip"))
    for old in files[:-keep] if keep > 0 else files:
        old.unlink(missing_ok=True)


def backup_if_needed(settings, today_str: str | None = None) -> Path | None:
    today_str = today_str or datetime.now().strftime("%Y%m%d")
    if any(p.name.startswith(f"tokoemas-{today_str}-") for p in settings.backup_dir.glob("tokoemas-*.zip")):
        return None
    path = make_backup(settings, stamp=f"{today_str}-{datetime.now().strftime('%H%M%S')}")
    prune(settings)
    return path


def daily_backup_loop(settings, interval: int = 3600) -> None:
    while True:
        try:
            backup_if_needed(settings)
        except Exception as e:  # backup tidak boleh mematikan server
            print(f"Backup otomatis gagal: {e}")
        time.sleep(interval)
```
`app/routes/admin_routes.py`:
```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..auth import get_db, require_owner
from ..services import audit
from ..services.backup import make_backup
from ..services.users import create_user, list_users, set_password
from ..web import render

router = APIRouter()


def _page(request, user, db, status_code=200, error=None, ok=""):
    return render(request, "pengguna.html", user, status_code=status_code, users=list_users(db), error=error, ok=ok)


@router.get("/pengguna")
def pengguna(request: Request, ok: str = "", user=Depends(require_owner), db=Depends(get_db)):
    return _page(request, user, db, ok=ok)


@router.post("/pengguna")
def pengguna_tambah(
    request: Request, username: str = Form(""), password: str = Form(""), role: str = Form("kasir"),
    user=Depends(require_owner), db=Depends(get_db),
):
    try:
        create_user(db, username, password, role)
    except ValueError as e:
        return _page(request, user, db, 400, error=str(e))
    return RedirectResponse("/pengguna?ok=Pengguna+ditambahkan", status_code=303)


@router.post("/pengguna/{user_id}/sandi")
def pengguna_sandi(
    user_id: int, request: Request, password: str = Form(""), user=Depends(require_owner), db=Depends(get_db)
):
    try:
        set_password(db, user_id, password)
    except ValueError as e:
        return _page(request, user, db, 400, error=str(e))
    audit.log(db, user["id"], "ganti_sandi", {"user_id": user_id})
    return RedirectResponse("/pengguna?ok=Kata+sandi+diganti", status_code=303)


@router.post("/backup")
def backup(request: Request, user=Depends(require_owner)):
    path = make_backup(request.app.state.settings)
    return FileResponse(path, media_type="application/zip", filename=path.name)
```

`app/templates/pengguna.html`:
```html
{% extends "base.html" %}
{% block title %}Pengguna dan backup{% endblock %}
{% block content %}
<h1>Pengguna</h1>
{% if ok %}<p>{{ ok }}</p>{% endif %}
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<table>
  <tr><th>Nama</th><th>Peran</th><th>Ganti kata sandi</th></tr>
  {% for u in users %}
  <tr>
    <td>{{ u.username }}</td><td>{{ u.role }}</td>
    <td><form method="post" action="/pengguna/{{ u.id }}/sandi" class="row">
      <input name="password" type="password" placeholder="Kata sandi baru" required><button>Simpan</button></form></td>
  </tr>
  {% endfor %}
</table>
<form method="post" action="/pengguna" class="card">
  <h2>Tambah pengguna</h2>
  <p><label>Nama pengguna<br><input name="username" required></label></p>
  <p><label>Kata sandi (minimal 6 karakter)<br><input name="password" type="password" required></label></p>
  <p><label>Peran<br><select name="role"><option value="kasir">kasir</option><option value="pemilik">pemilik</option></select></label></p>
  <p><button>Tambah</button></p>
</form>
<section class="card">
  <h2>Backup</h2>
  <p class="muted">Berisi database dan semua foto. Backup otomatis harian tersimpan di folder <code>data/backup</code>. Salin zip ke flashdisk secara berkala.</p>
  <form method="post" action="/backup"><button>Unduh backup sekarang</button></form>
</section>
{% endblock %}
```

Modifikasi `app/main.py`:

1. Ganti
```python
from .routes import auth_routes, dashboard_routes, items_routes, prices_routes, scan_routes, transactions_routes
```
menjadi
```python
from .netguard import is_local
from .routes import (
    admin_routes, auth_routes, dashboard_routes, items_routes, prices_routes, scan_routes, transactions_routes,
)
```
2. Ganti
```python
    scan_routes.router,
    transactions_routes.router,
```
menjadi
```python
    scan_routes.router,
    transactions_routes.router,
    admin_routes.router,
```
3. Ubah `from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse` menjadi `from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse`.
4. Sisipkan sebelum baris `for router in ROUTERS:`:
```python
    @app.middleware("http")
    async def lan_only(request, call_next):
        host = request.client.host if request.client else None
        if not is_local(host):
            return PlainTextResponse("Hanya untuk jaringan lokal", status_code=403)
        return await call_next(request)

```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: manajemen pengguna, backup zip dan harian, pembatasan jaringan lokal"
```

---

### Task 10: HTTPS lokal, halaman sertifikat, dan peluncur

**Files:**
- Create: `app/certs.py`, `app/templates/sertifikat.html`, `run.py`
- Modify: `app/routes/admin_routes.py` (tambah route sertifikat), `app/templates/login.html` (tautan panduan)
- Test: `tests/test_certs.py`

**Interfaces:**
- Consumes: `Settings.cert_dir`, `load_settings`, `create_app`, `daily_backup_loop`, `PORT`, `current_user`.
- Produces:
  - `app.certs.local_ips() -> list[str]` (selalu memuat `127.0.0.1`); `ensure_cert(cert_dir: Path, hosts: list[str] | None = None) -> tuple[Path, Path]` → `(server.crt, server.key)`; sertifikat dibuat ulang bila daftar host berubah, dipakai ulang bila sama.
  - `GET /sertifikat` (halaman panduan, tanpa login), `GET /sertifikat.crt` (unduh; 404 jika belum ada).
  - `run.py`: jalankan `python run.py` → server HTTPS di `0.0.0.0:8443`, mencetak alamat yang bisa dibuka, dan menjalankan backup harian di thread latar.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/test_certs.py`:
```python
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
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `pytest tests/test_certs.py -q`
Expected: gagal `ModuleNotFoundError: No module named 'app.certs'`.

- [ ] **Step 3: Tulis implementasi**

`app/certs.py`:
```python
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips)


def ensure_cert(cert_dir: Path, hosts: list[str] | None = None) -> tuple[Path, Path]:
    hosts = sorted(set(hosts or local_ips()) | {"127.0.0.1"})
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path, key_path, marker = cert_dir / "server.crt", cert_dir / "server.key", cert_dir / "hosts.txt"
    if cert_path.exists() and key_path.exists() and marker.exists() and marker.read_text().split() == hosts:
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Toko Emas Lokal")])
    now = datetime.now(timezone.utc)
    san = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(h)) for h in hosts]
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    marker.write_text("\n".join(hosts))
    return cert_path, key_path
```

Tambahkan ke `app/routes/admin_routes.py` (impor di bagian atas file: `from fastapi import HTTPException` digabung ke impor `fastapi` yang ada, dan `from ..auth import current_user` digabung ke impor `..auth`), lalu route di akhir file:
```python
@router.get("/sertifikat")
def sertifikat(request: Request, user=Depends(current_user)):
    ada = (request.app.state.settings.cert_dir / "server.crt").exists()
    return render(request, "sertifikat.html", user, ada=ada)


@router.get("/sertifikat.crt")
def sertifikat_file(request: Request):
    path = request.app.state.settings.cert_dir / "server.crt"
    if not path.is_file():
        raise HTTPException(404, "Sertifikat belum dibuat")
    return FileResponse(path, media_type="application/x-x509-ca-cert", filename="toko-emas.crt")
```

`app/templates/sertifikat.html`:
```html
{% extends "base.html" %}
{% block title %}Sertifikat HTTPS{% endblock %}
{% block content %}
<h1>Kamera tidak aktif?</h1>
<p>Kamera di browser hanya jalan pada alamat HTTPS. Aplikasi ini memakai sertifikat buatan sendiri, jadi setiap HP perlu mempercayainya satu kali.</p>
<ol>
  <li>Saat browser menampilkan peringatan sertifikat, pilih <b>Lanjutkan / Advanced → Proceed</b>. Coba lagi tombol Kamera di halaman Scan.</li>
  <li>Jika kamera masih diblokir: unduh sertifikat di bawah, lalu pasang di HP (Android: Pengaturan → Keamanan → Sertifikat CA; iPhone: buka berkas, pasang profil, lalu aktifkan di Pengaturan → Umum → Info → Pengaturan Kepercayaan Sertifikat).</li>
  <li>Tanpa kamera pun tetap bisa: pakai scanner USB/Bluetooth atau ketik kodenya.</li>
</ol>
{% if ada %}<p><a href="/sertifikat.crt"><button>Unduh sertifikat</button></a></p>{% else %}<p class="error">Sertifikat belum dibuat. Jalankan aplikasi lewat <code>run.py</code> / TokoEmas.exe.</p>{% endif %}
{% endblock %}
```

Tambahkan ke `app/templates/login.html`, sebelum `{% endblock %}`:
```html
<p class="muted"><a href="/sertifikat">Kamera HP tidak aktif?</a></p>
```

`run.py`:
```python
import threading

import uvicorn

from app.certs import ensure_cert, local_ips
from app.config import PORT, load_settings
from app.main import create_app
from app.services.backup import daily_backup_loop


def main() -> None:
    settings = load_settings()
    settings.ensure_dirs()
    cert, key = ensure_cert(settings.cert_dir)
    app = create_app(settings)
    threading.Thread(target=daily_backup_loop, args=(settings,), daemon=True).start()
    print("Toko Emas berjalan. Buka salah satu alamat ini dari perangkat di WiFi toko:")
    for ip in local_ips():
        print(f"  https://{ip}:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, ssl_certfile=str(cert), ssl_keyfile=str(key), log_level="warning")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 5: Uji server HTTPS sungguhan**

```bash
cd /home/claude/toko-emas
TOKOEMAS_DATA=/tmp/tokosmoke python run.py > /tmp/tokosmoke.log 2>&1 &
sleep 4
curl -sk -o /dev/null -w "%{http_code} %{redirect_url}\n" https://127.0.0.1:8443/login
curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:8443/sertifikat.crt
kill %1; cat /tmp/tokosmoke.log; ls /tmp/tokosmoke /tmp/tokosmoke/backup
```
Expected: baris pertama `303 https://127.0.0.1:8443/setup` (belum ada pengguna), baris kedua `200`, log menampilkan alamat `https://127.0.0.1:8443`, dan folder `backup` berisi satu zip.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: HTTPS lokal dengan sertifikat buatan sendiri, halaman sertifikat, peluncur run.py"
```

---

### Task 11: Pengemasan `.exe`, panduan, dan uji manual

**Files:**
- Create: `build.bat`, `PANDUAN.md`, `docs/QA-manual.md`

**Interfaces:**
- Consumes: seluruh aplikasi; `run.py`.
- Produces: folder `dist/TokoEmas/` berisi `TokoEmas.exe` (data dibuat di `data/` di samping `.exe`).

- [ ] **Step 1: Tulis berkas pengemasan dan panduan**

`build.bat` (dijalankan di Windows, dari folder proyek, setelah `pip install -r requirements.txt pyinstaller`):
```bat
@echo off
pyinstaller --noconfirm --onedir --name TokoEmas ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\static;app\static" ^
  --collect-submodules uvicorn ^
  --collect-all barcode ^
  --collect-all qrcode ^
  run.py
echo.
echo Selesai. Hasil: dist\TokoEmas\TokoEmas.exe
```

`PANDUAN.md`:
```markdown
# Panduan Pemasangan Toko Emas

## Di PC toko (sekali saja)
1. Salin folder `TokoEmas` (hasil build) ke PC toko, mis. `C:\TokoEmas`.
2. Beri PC **alamat IP tetap** di router (reservasi DHCP) agar alamat aplikasi tidak berubah.
3. Izinkan port di firewall (Command Prompt sebagai Administrator):
   `netsh advfirewall firewall add rule name="Toko Emas" dir=in action=allow protocol=TCP localport=8443`
4. Jalankan `TokoEmas.exe`. Jendela akan menampilkan alamat, mis. `https://192.168.1.20:8443`. Biarkan jendela terbuka selama toko buka.
5. Buka alamat itu di browser PC, buat akun pemilik di halaman pengaturan awal, lalu isi **Harga** setiap pagi sebelum transaksi.

## Di HP / perangkat lain
- Buka alamat yang sama. Saat muncul peringatan sertifikat, pilih lanjutkan. Jika kamera scan tidak aktif, ikuti halaman **/sertifikat**.

## Scanner USB / Bluetooth
- Colok scanner, buka halaman **Scan** atau **Transaksi**, klik kolom kode, lalu scan. Scanner bekerja seperti keyboard dan menekan Enter otomatis.

## Backup
- Otomatis setiap hari ke `data\backup\` (14 hari terakhir disimpan). Salin zip terbaru ke flashdisk secara berkala.
- Manual: menu **Pengguna → Unduh backup sekarang**.
- Pemulihan: tutup aplikasi, ekstrak zip, salin `tokoemas.db` ke `data\` dan isi `foto\` ke `data\foto\`, lalu jalankan lagi.

## Sertifikat kedaluwarsa (±2 tahun)
- Hapus folder `data\cert` lalu jalankan ulang aplikasi; sertifikat baru dibuat. HP perlu menerima sertifikat lagi.
```

`docs/QA-manual.md`:
```markdown
# Uji Manual (perangkat asli)

Centang setiap butir di PC toko dan minimal satu HP Android dan satu iPhone bila tersedia.

- [ ] `TokoEmas.exe` jalan dari folder bersih; folder `data` terbentuk di sebelahnya.
- [ ] Alamat `https://<IP-PC>:8443` terbuka dari HP lewat WiFi toko; dari jaringan luar (data seluler) tidak bisa dibuka.
- [ ] Halaman setup membuat pemilik; login kasir (dibuat dari menu Pengguna) tidak melihat menu Harga/Pengguna dan tidak melihat nominal di dashboard.
- [ ] Kamera di halaman Scan menyala di HP (setelah menerima sertifikat) dan membaca QR serta barcode dari label hasil cetak.
- [ ] Scanner USB/Bluetooth: scan label → data perhiasan muncul tanpa mengetik.
- [ ] Label tercetak jelas (QR dan barcode terbaca) dari browser; ukuran cukup untuk label perhiasan.
- [ ] Alur: harga harian → tambah perhiasan berfoto dari kamera HP → jual (harga diubah kasir) → struk tercetak.
- [ ] Beli dari pelanggan (perhiasan baru dan emas curah), beli dari supplier, tukar tambah: total, selisih, dan gramasi di dashboard sesuai hitungan manual.
- [ ] Dua HP menjual perhiasan yang sama bersamaan: salah satu mendapat pesan tidak tersedia.
- [ ] Batalkan penjualan (pemilik): perhiasan kembali tersedia dan angka dashboard berkurang.
- [ ] Matikan PC mendadak saat idle, nyalakan lagi: data utuh.
- [ ] Backup manual terunduh; pemulihan di folder baru membuka data yang sama.
```

- [ ] **Step 2: Uji bundling (di Linux, validasi struktur paket)**

```bash
cd /home/claude/toko-emas
. .venv/bin/activate
pip install pyinstaller
pyinstaller --noconfirm --onedir --name TokoEmas \
  --add-data "app/templates:app/templates" --add-data "app/static:app/static" \
  --collect-submodules uvicorn --collect-all barcode --collect-all qrcode run.py
TOKOEMAS_DATA=/tmp/tokopkg ./dist/TokoEmas/TokoEmas > /tmp/tokopkg.log 2>&1 &
sleep 6
curl -sk -o /dev/null -w "%{http_code} %{redirect_url}\n" https://127.0.0.1:8443/login
curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:8443/static/app.css
kill %1
```
Expected: `303 https://127.0.0.1:8443/setup` dan `200`. Jika `ModuleNotFoundError` muncul di `/tmp/tokopkg.log`, tambahkan `--hidden-import <modul>` pada `build.bat` dan perintah di atas, lalu ulangi. Build `.exe` Windows yang sebenarnya dijalankan dengan `build.bat` di PC Windows (PyInstaller tidak membuat `.exe` dari Linux).

Tambahkan `build/`, `dist/`, `*.spec` ke `.gitignore` bila belum ada (`build/` dan `dist/` sudah ada dari Rencana 1; tambahkan `TokoEmas.spec`).

- [ ] **Step 3: Jalankan seluruh tes terakhir kali**

Run: `pytest -q`
Expected: semua lulus.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: skrip build exe, panduan pemasangan, dan daftar uji manual"
```

---

## Self-Review (Rencana 2)

**Cakupan spesifikasi:**
- §1 fitur 1–5 (dashboard, total penjualan/pembelian, gramasi jual/beli) → Task 6.
- Fitur 6 (identifikasi foto + kode unik) → Rencana 1 Task 4 + tampilan hasil scan di Task 7.
- Fitur 7 (scan barcode/QR; kamera dan USB) → Task 7.
- §5 layar: Dashboard (6), Scan (7), Katalog (Rencana 1), Transaksi baru dan Riwayat (8), Harga (Rencana 1), Pengguna dan backup (9).
- §6 alur transaksi dan pembatalan → Rencana 1 Task 5 (logika) + Task 8 (layar).
- §3 HTTPS, IP tetap, backup harian dan manual → Task 9, 10, 11 (IP tetap dan firewall di `PANDUAN.md`).
- §8 error handling: kamera tidak aktif (Task 7, 10), harga belum diisi (pesan di Task 8), item tidak tersedia (409 → pesan di layar).
- §9 keamanan: server hanya lokal (Task 9 middleware), peran (Task 6, 8, 9).
- §10 pengujian: tes otomatis tiap tugas; uji manual di perangkat asli → Task 11 `QA-manual.md`.

**Konsistensi:** `render(request, name, user, status_code, **ctx)`, `require_owner`, `LineIn`, `get_transaction → {t, lines, pair}`, `lookupCode`, dan daftar `ROUTERS` konsisten dengan Rencana 1. Kunci JSON API (`id`, `jual_id`, `beli_id`, `selisih`) cocok dengan pemakaian di `transaksi_baru.html`.

**Risiko yang perlu dicek saat eksekusi:** (1) keluaran `python-barcode` SVG (Rencana 1 Task 4), (2) kamera di browser HP dengan sertifikat buatan sendiri (uji manual; cadangannya halaman `/sertifikat`, scanner, dan ketik kode), (3) kebutuhan `--hidden-import` pada PyInstaller (Task 11 Step 2).
