"""Pembatas percobaan gagal (login, token pengaturan awal) agar kata sandi tidak bisa ditebak lewat internet."""
from __future__ import annotations

import time
from collections import defaultdict


class Throttle:
    def __init__(self, maks: int = 5, jendela: int = 15 * 60):
        self.maks, self.jendela = maks, jendela
        self._gagal: dict[str, list[float]] = defaultdict(list)
        self._geser = 0.0

    def _now(self) -> float:
        return time.monotonic() + self._geser

    def geser_waktu(self, detik: float) -> None:
        """Hanya untuk uji: majukan jam internal."""
        self._geser += detik

    def _bersih(self, kunci: str) -> list[float]:
        batas = self._now() - self.jendela
        daftar = [t for t in self._gagal[kunci] if t > batas]
        if daftar:
            self._gagal[kunci] = daftar
        else:
            self._gagal.pop(kunci, None)
        return daftar

    def sisa_menit(self, kunci: str, maks: int | None = None) -> int:
        """0 bila boleh mencoba; selain itu menit tersisa sampai dibuka lagi."""
        maks = maks or self.maks
        daftar = self._bersih(kunci)
        if len(daftar) < maks:
            return 0
        buka = daftar[-maks] + self.jendela
        return max(1, int((buka - self._now()) // 60) + 1)

    def gagal(self, kunci: str) -> None:
        self._bersih(kunci)
        self._gagal[kunci].append(self._now())

    def berhasil(self, kunci: str) -> None:
        self._gagal.pop(kunci, None)
