"""Embedding multilingual-e5 lewat onnxruntime (tanpa PyTorch) dan indeks vektor NumPy.

Cara pakai e5: teks artikel berawalan 'passage: ', kueri berawalan 'query: '. Keluaran dirata-ratakan
(mean pooling, memperhatikan attention mask) lalu dinormalisasi L2, sehingga skor cosine = perkalian titik.
"""

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from skema import FOLDER_DB, baca_jsonl, teks_passage
from unduh_model import jalur_model, jalur_tokenizer

MAKS_TOKEN = 256


class Embedder:
    def __init__(self, ukuran: str = "small", varian: str = "fp32", maks_token: int = MAKS_TOKEN):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.ukuran, self.varian, self.maks_token = ukuran, varian, maks_token
        self.tok = Tokenizer.from_file(str(jalur_tokenizer(ukuran)))
        self.tok.enable_truncation(max_length=maks_token)
        self.tok.enable_padding(pad_id=self.tok.token_to_id("<pad>") or 1, pad_token="<pad>")
        opsi = ort.SessionOptions()
        opsi.log_severity_level = 3
        self.sesi = ort.InferenceSession(str(jalur_model(ukuran, varian)), opsi, providers=["CPUExecutionProvider"])
        self.nama_masukan = {i.name for i in self.sesi.get_inputs()}

    def encode(self, teks: list[str], ukuran_batch: int = 32, kemajuan: bool = False) -> np.ndarray:
        """Mengembalikan matriks float32 (n, dimensi), baris ternormalisasi L2, urutan sama dengan masukan."""
        urutan = sorted(range(len(teks)), key=lambda i: len(teks[i]))  # panjang mirip -> sedikit padding
        hasil = None
        mulai = time.perf_counter()
        for b in range(0, len(urutan), ukuran_batch):
            idx = urutan[b:b + ukuran_batch]
            enc = self.tok.encode_batch([teks[i] for i in idx])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            masukan = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.nama_masukan:
                masukan["token_type_ids"] = np.zeros_like(ids)
            keluar = self.sesi.run(None, masukan)[0]
            m = mask[:, :, None].astype(np.float32)
            vek = (keluar * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            vek /= np.clip(np.linalg.norm(vek, axis=1, keepdims=True), 1e-12, None)
            if hasil is None:
                hasil = np.zeros((len(teks), vek.shape[1]), dtype=np.float32)
            hasil[idx] = vek
            if kemajuan and (b // ukuran_batch) % 20 == 0:
                done = b + len(idx)
                dt = time.perf_counter() - mulai
                print(f"\r  {done}/{len(teks)}  {dt:5.0f} dtk  sisa ~{dt / done * (len(teks) - done):5.0f} dtk", end="", flush=True)
        if kemajuan:
            print()
        return hasil if hasil is not None else np.zeros((0, 0), dtype=np.float32)

    def encode_kueri(self, teks: list[str]) -> np.ndarray:
        return self.encode(["query: " + t for t in teks])


def sidik_jari(jalur: Path) -> str:
    return hashlib.sha1(jalur.read_bytes()).hexdigest()[:16]


def sidik_teks(artikel: list[dict]) -> str:
    """Sidik jari id dan teks yang di-embed, sesuai urutan. Label, URL, dan field lain sengaja tidak ikut,
    sehingga mengubahnya tidak membatalkan vektor."""
    h = hashlib.sha1()
    for a in artikel:
        h.update(f"{a['id']}\n{teks_passage(a)}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def periksa_cocok(meta: dict, artikel: list[dict], ukuran: str, varian: str):
    if meta.get("teks_sha1") != sidik_teks(artikel) or meta["jumlah"] != len(artikel):
        raise SystemExit("Vektor tidak cocok dengan artikel.jsonl (id atau teks artikel berubah, atau urutannya). "
                         "Jalankan: python evaluasi.py vektor --ukuran %s --varian %s" % (ukuran, varian))


def jalur_vektor(folder: Path, ukuran: str, varian: str) -> Path:
    return folder / f"vektor_{ukuran}_{varian}.npy"


def bangun_vektor(folder: Path = FOLDER_DB, ukuran: str = "small", varian: str = "fp32") -> dict:
    """Meng-embed seluruh artikel.jsonl dan menyimpannya. Mengembalikan statistik (detik, ukuran berkas)."""
    artikel = baca_jsonl(folder / "artikel.jsonl")
    emb = Embedder(ukuran, varian)
    teks = [teks_passage(a) for a in artikel]
    mulai = time.perf_counter()
    vek = emb.encode(teks, kemajuan=True)
    detik = time.perf_counter() - mulai
    jalur = jalur_vektor(folder, ukuran, varian)
    np.save(jalur, vek)
    meta = {"jumlah": len(artikel), "dimensi": int(vek.shape[1]), "detik_bangun": round(detik, 1), "ukuran": ukuran,
            "varian": varian, "maks_token": emb.maks_token, "teks_sha1": sidik_teks(artikel)}
    jalur.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta | {"byte_berkas": jalur.stat().st_size}


class Indeks:
    """Artikel beserta vektornya di memori; pencarian cosine brute-force."""

    def __init__(self, folder: Path = FOLDER_DB, ukuran: str = "small", varian: str = "fp32"):
        self.artikel = baca_jsonl(folder / "artikel.jsonl")
        jalur = jalur_vektor(folder, ukuran, varian)
        self.vektor = np.load(jalur)
        meta = json.loads(jalur.with_suffix(".json").read_text(encoding="utf-8"))
        periksa_cocok(meta, self.artikel, ukuran, varian)
        self.embedder = Embedder(ukuran, varian, meta["maks_token"])

    def cari_vektor(self, kueri: np.ndarray, k: int = 5) -> list[list[tuple[int, float]]]:
        """kueri: (n, dimensi) ternormalisasi. Mengembalikan, per kueri, daftar (indeks_artikel, skor) k teratas."""
        skor = kueri @ self.vektor.T
        k = min(k, skor.shape[1])
        teratas = np.argpartition(-skor, k - 1, axis=1)[:, :k]
        hasil = []
        for b in range(skor.shape[0]):
            urut = teratas[b][np.argsort(-skor[b, teratas[b]])]
            hasil.append([(int(i), float(skor[b, i])) for i in urut])
        return hasil

    def cari(self, teks: list[str], k: int = 5) -> list[list[tuple[dict, float]]]:
        return [[(self.artikel[i], s) for i, s in baris] for baris in self.cari_vektor(self.embedder.encode_kueri(teks), k)]
