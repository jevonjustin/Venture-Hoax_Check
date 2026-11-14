"""Pembatas beban /analisis (Sesi 8.1).

Paling banyak `maks_bersamaan` analisis berjalan bersamaan. Permintaan lain menunggu giliran paling lama
`antre_maks_detik`; lewat dari itu dijawab 503 dengan kode `server_sibuk`. Batasnya untuk seluruh server, tidak per
alamat IP, karena pengunjung showcase berbagi satu IP Wi-Fi kampus. /health tidak melewati pembatas ini.
"""

import asyncio
from contextlib import asynccontextmanager

from .galat import GalatApi
from .konfigurasi import Pengaturan, pengaturan as pengaturan_global


class PembatasBeban:
    def __init__(self, maks_bersamaan: int, antre_maks_detik: float):
        self.maks_bersamaan = maks_bersamaan
        self.antre_maks_detik = antre_maks_detik
        self.berjalan = 0
        self.menunggu = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._semafor: asyncio.Semaphore | None = None

    @classmethod
    def dari(cls, cfg: Pengaturan) -> "PembatasBeban":
        return cls(cfg.maks_bersamaan, cfg.antre_maks_detik)

    def _semafor_loop(self) -> asyncio.Semaphore:
        # Semaphore asyncio terikat ke satu event loop. Server hanya punya satu loop; uji (TestClient) bisa membuat
        # loop baru per permintaan, jadi semafor dibuat ulang bila loop berganti.
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._semafor = loop, asyncio.Semaphore(self.maks_bersamaan)
            self.berjalan = self.menunggu = 0
        return self._semafor

    @asynccontextmanager
    async def giliran(self):
        """Menunggu giliran analisis. Melempar GalatApi(503, server_sibuk) bila antrean melewati batas waktu."""
        semafor = self._semafor_loop()
        if semafor.locked():
            self.menunggu += 1
            try:
                await asyncio.wait_for(semafor.acquire(), timeout=self.antre_maks_detik)
            except TimeoutError:
                raise GalatApi(
                    503, "server_sibuk",
                    f"{self.maks_bersamaan} analisis sedang berjalan; antrean lebih dari {self.antre_maks_detik:g} detik",
                ) from None
            finally:
                self.menunggu -= 1
        else:
            await semafor.acquire()
        self.berjalan += 1
        try:
            yield
        finally:
            self.berjalan -= 1
            semafor.release()


# Diganti oleh uji (monkeypatch) bila butuh batas lain.
pembatas = PembatasBeban.dari(pengaturan_global)
