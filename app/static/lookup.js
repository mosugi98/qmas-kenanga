async function lookupCode(code) {
  const r = await fetch('/api/items/by-code/' + encodeURIComponent(code.trim()));
  if (r.status === 404) throw new Error('Kode tidak terdaftar');
  if (!r.ok) throw new Error('Gagal mengambil data perhiasan');
  return r.json();
}
function rupiah(n) { return 'Rp ' + Math.round(n).toLocaleString('id-ID'); }
function fmtGram(n) { return (+n).toFixed(3).replace(/\.?0+$/, '').replace('.', ',') + ' g'; }
