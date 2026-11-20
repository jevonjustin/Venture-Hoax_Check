"""Membuat logo Veritas (SVG, PNG 1024 px, dan pratinjau) dari satu sumber geometri.

Bentuk V digambar ulang dari referensi_logo.jpeg: titik sudutnya diukur dari gambar acuan
(kontur warna krem), lalu dirapikan supaya simetris terhadap sumbu tengah V.

Jalankan dari root repo dengan Python sistem (butuh Pillow dan fontTools):
    python docs/showcase/logo/buat_logo.py            # SVG, PNG, pratinjau.png
    python docs/showcase/logo/buat_logo.py --android  # tambah drawable ikon aplikasi

PNG dibuat dengan merender SVG lewat Microsoft Edge headless, jadi PNG selalu sama dengan SVG.
Tulisan VERITAS dan DEBUG diubah menjadi path (glyph Arial) supaya tidak bergantung font.
"""
import math
import subprocess
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
RES = ROOT / "app" / "src"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_TEBAL = Path(r"C:\Windows\Fonts\arialbd.ttf")

MERAH = "#A22020"  # median piksel merah acuan: (162, 32, 32)
KREM = "#FCF9F2"  # median piksel krem acuan: (252, 249, 242)
NAVY = "#1B3A6B"  # warna utama UI, dipakai untuk pita DEBUG

# Titik sudut V dalam satuan piksel acuan; x = 0 di sumbu tengah V, y = 0 di tepi atas.
# Urutan: ujung kiri bendera, sepanjang tepi atas ke dalam lengan kiri, turun ke lekuk tengah,
# naik ke lengan kanan, tepi luar kanan turun ke dasar datar, tepi luar kiri naik ke bawah bendera.
V = [
    (-182.5, 0), (-78, 0), (0, 202), (78, 0), (156, 0),
    (27.5, 306), (-27.5, 306), (-128.5, 66), (-182.5, 66),
]
# Tulisan di acuan: tinggi huruf kapital 11 px, lebar 62 px, tepi atas 20 px di bawah dasar V.
TEKS_TINGGI_KAPITAL = 11.0
TEKS_LEBAR = 62.0
TEKS_JARAK = 20.0


def bbox(titik):
    xs = [p[0] for p in titik]
    ys = [p[1] for p in titik]
    return min(xs), min(ys), max(xs), max(ys)


def pusat_bbox(titik):
    """Pusat kotak batas V dan jarak titik sudut terjauh dari pusat itu."""
    x0, y0, x1, y1 = bbox(titik)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx, cy, max(math.hypot(x - cx, y - cy) for x, y in titik)


def ubah(titik, s, tx, ty):
    return [(x * s + tx, y * s + ty) for x, y in titik]


def path_poligon(titik):
    a = " L".join(f"{x:.2f},{y:.2f}" for x, y in titik)
    return f"M{a} Z"


def path_teks(teks, berkas_font, tinggi_kapital, lebar_target, pusat_x, atas_y, presisi=2):
    """Path SVG per huruf, diskalakan ke tinggi huruf kapital dan direntang ke lebar target."""
    font = TTFont(berkas_font)
    glyph = font.getGlyphSet()
    cmap = font.getBestCmap()
    kapital = font["OS/2"].sCapHeight
    s = tinggi_kapital / kapital
    nama = [cmap[ord(c)] for c in teks]
    # Lebar alami dari tepi tinta huruf pertama sampai tepi tinta huruf terakhir.
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    maju = [hmtx[n][0] for n in nama]
    kiri0 = glyf[nama[0]].xMin
    kanan_akhir = glyf[nama[-1]].xMax
    alami = (sum(maju[:-1]) + kanan_akhir - kiri0) * s
    renggang = (lebar_target - alami) / (len(teks) - 1)  # jarak tambahan antarhuruf
    angka = lambda v: f"{v:.{presisi}f}".rstrip("0").rstrip(".")
    per_huruf = []
    x = pusat_x - lebar_target / 2 - kiri0 * s
    for n, m in zip(nama, maju):
        pen = SVGPathPen(glyph, ntos=angka)
        # Koordinat font: y ke atas; dibalik supaya tepi atas kapital ada di atas_y.
        glyph[n].draw(TransformPen(pen, (s, 0, 0, -s, x, atas_y + tinggi_kapital)))
        per_huruf.append(pen.getCommands())
        x += m * s + renggang
    return per_huruf


def svg(isi, ukuran=1024):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ukuran}" height="{ukuran}" '
        f'viewBox="0 0 {ukuran} {ukuran}">\n'
        f'  <rect width="{ukuran}" height="{ukuran}" fill="{MERAH}"/>\n{isi}</svg>\n'
    )


def logo_ikon():
    """V saja, dipusatkan pada kotak batasnya."""
    cx, cy, r = pusat_bbox(V)
    s = 1.75
    titik = ubah(V, s, 512 - cx * s, 512 - cy * s)
    return svg(f'  <path fill="{KREM}" d="{path_poligon(titik)}"/>\n'), s


def logo_teks():
    """V dan tulisan VERITAS, tata letak mengikuti acuan."""
    x0, _, x1, _ = bbox(V)
    bawah = 306 + TEKS_JARAK + TEKS_TINGGI_KAPITAL
    s = 1.9
    tx = 512 - (x0 + x1) / 2 * s
    ty = 512 - bawah / 2 * s
    titik = ubah(V, s, tx, ty)
    d = "".join(path_teks(
        "VERITAS", FONT, TEKS_TINGGI_KAPITAL * s, TEKS_LEBAR * s, tx, ty + (306 + TEKS_JARAK) * s
    ))
    return svg(
        f'  <path fill="{KREM}" d="{path_poligon(titik)}"/>\n'
        f'  <path fill="{KREM}" d="{d}"/>\n'
    )


def render_svg(berkas_svg, berkas_png):
    subprocess.run(
        [
            str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", "--window-size=1024,1024",
            f"--screenshot={berkas_png}", berkas_svg.resolve().as_uri(),
        ],
        check=True, capture_output=True, timeout=60,
    )
    im = Image.open(berkas_png).convert("RGB")
    if im.size != (1024, 1024):
        raise SystemExit(f"Ukuran render {berkas_png.name} tidak 1024x1024: {im.size}")
    im.save(berkas_png, optimize=True)


# ---------------------------------------------------------------- ikon adaptif (108 dp)

ADAPTIF = 108
SAFE_R = 33  # safe zone ikon adaptif: lingkaran diameter 66 dp di tengah
V_R = 31  # titik sudut V terjauh berjarak 31 dp dari tengah, jadi tetap di dalam safe zone


def v_adaptif():
    cx, cy, r = pusat_bbox(V)
    s = V_R / r
    return ubah(V, s, 54 - cx * s, 54 - cy * s)


def pita_debug():
    """Pita navy selebar ikon dengan tulisan DEBUG; tulisannya tetap di dalam safe zone."""
    atas, tinggi, kapital = 77.0, 9.0, 5.0
    # Presisi 0,1 dp dan satu path per huruf supaya tiap path pendek (peringatan lint VectorPath).
    huruf = path_teks("DEBUG", FONT_TEBAL, kapital, 24.0, 54, atas + (tinggi - kapital) / 2, presisi=1)
    return atas, tinggi, huruf


def render_adaptif(px, debug=False):
    """Render ikon adaptif utuh (108 dp penuh, belum dimasker), supersampling 4x."""
    k = 4
    n = px * k
    s = n / ADAPTIF
    im = Image.new("RGB", (n, n), MERAH)
    dr = ImageDraw.Draw(im)
    dr.polygon([(x * s, y * s) for x, y in v_adaptif()], fill=KREM)
    if debug:
        atas, tinggi, _ = pita_debug()
        dr.rectangle([0, atas * s, n, (atas + tinggi) * s], fill=NAVY)
        # Pratinjau saja: tulisan DEBUG digambar dengan font yang sama seperti path di drawable.
        f = ImageFont.truetype(str(FONT_TEBAL), round(5.0 / 0.716 * s))
        dr.text((54 * s, (atas + tinggi / 2) * s), "DEBUG", font=f, fill=KREM, anchor="mm")
    return im.resize((px, px), Image.LANCZOS)


def masker(px, bentuk):
    k = 4
    n = px * k
    m = Image.new("L", (n, n), 0)
    dr = ImageDraw.Draw(m)
    if bentuk == "bulat":
        dr.ellipse([0, 0, n - 1, n - 1], fill=255)
    elif bentuk == "persegi_bulat":
        dr.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.22, fill=255)
    else:  # squircle (superelips n = 4)
        r = n / 2
        titik = []
        for i in range(720):
            t = 2 * math.pi * i / 720
            c, si = math.cos(t), math.sin(t)
            titik.append((r + r * math.copysign(abs(c) ** 0.5, c), r + r * math.copysign(abs(si) ** 0.5, si)))
        dr.polygon(titik, fill=255)
    return m.resize((px, px), Image.LANCZOS)


def ikon_termasker(px, bentuk, latar, debug=False):
    # Masker launcher memotong 72 dp di tengah dari lapisan 108 dp.
    besar = round(px * ADAPTIF / 72)
    full = render_adaptif(besar, debug)
    o = (besar - px) // 2
    isi = full.crop((o, o, o + px, o + px))
    bg = Image.new("RGB", (px, px), latar)
    bg.paste(isi, (0, 0), masker(px, bentuk))
    return bg


def pratinjau(png_ikon, png_teks):
    acuan = Image.open(FOLDER / "referensi_logo.jpeg").convert("RGB")
    W = 1500
    kanvas = Image.new("RGB", (W, 1240), "#EEF1F5")
    dr = ImageDraw.Draw(kanvas)
    dr.text((40, 20), "Acuan (WhatsApp)", fill="#1B1B1B")
    dr.text((520, 20), "logo_veritas_teks.svg", fill="#1B1B1B")
    dr.text((1000, 20), "logo_veritas.svg", fill="#1B1B1B")
    a = acuan.copy()
    a.thumbnail((440, 440))
    kanvas.paste(a, (40 + (440 - a.width) // 2, 40))
    kanvas.paste(Image.open(png_teks).resize((440, 440), Image.LANCZOS), (520, 40))
    kanvas.paste(Image.open(png_ikon).resize((440, 440), Image.LANCZOS), (1000, 40))

    y = 520
    dr.text((40, y), "Ikon adaptif: bulat, squircle, persegi bulat (192 px)  |  debug", fill="#1B1B1B")
    x = 40
    for bentuk in ("bulat", "squircle", "persegi_bulat"):
        kanvas.paste(ikon_termasker(192, bentuk, "#EEF1F5"), (x, y + 24))
        x += 232
    for bentuk in ("bulat", "squircle"):
        kanvas.paste(ikon_termasker(192, bentuk, "#EEF1F5", debug=True), (x, y + 24))
        x += 232
    # Garis safe zone pada lapisan utuh (merah = 108 dp penuh, garis = lingkaran 66 dp).
    utuh = render_adaptif(192)
    d2 = ImageDraw.Draw(utuh)
    r = SAFE_R * 192 / ADAPTIF
    d2.ellipse([96 - r, 96 - r, 96 + r, 96 + r], outline="#00C2FF", width=2)
    rv = V_R * 192 / ADAPTIF
    d2.ellipse([96 - rv, 96 - rv, 96 + rv, 96 + rv], outline="#FFD400", width=1)
    kanvas.paste(utuh, (x, y + 24))
    dr.text((x, y + 222), "lapisan 108 dp + safe zone", fill="#1B1B1B")

    y = 800
    dr.text((40, y), "48 px di latar terang dan gelap", fill="#1B1B1B")
    for i, (latar, warna_teks) in enumerate((("#FFFFFF", "#1B1B1B"), ("#121212", "#E6E6E6"))):
        x0 = 40 + i * 720
        dr.rectangle([x0, y + 24, x0 + 680, y + 24 + 160], fill=latar)
        x = x0 + 30
        for bentuk in ("bulat", "squircle", "persegi_bulat"):
            kanvas.paste(ikon_termasker(48, bentuk, latar), (x, y + 24 + 40))
            dr.text((x, y + 24 + 100), "Veritas", fill=warna_teks)
            x += 100
        # Themed icon Android 13+: hanya bentuk monochrome yang dipakai, warnanya dari sistem.
        for tema_bg, tema_fg in (("#D9E2FF", "#1B3A6B"), ("#2D3A55", "#C9D6FF")):
            m = Image.new("L", (192, 192), 0)
            ImageDraw.Draw(m).polygon([(px * 192 / 72 - 18 * 192 / 72, py * 192 / 72 - 18 * 192 / 72)
                                        for px, py in v_adaptif()], fill=255)
            ikon = Image.new("RGB", (192, 192), tema_bg)
            ikon.paste(Image.new("RGB", (192, 192), tema_fg), (0, 0), m)
            ikon = ikon.resize((48, 48), Image.LANCZOS)
            bg = Image.new("RGB", (48, 48), latar)
            bg.paste(ikon, (0, 0), masker(48, "bulat"))
            kanvas.paste(bg, (x, y + 24 + 40))
            dr.text((x - 6, y + 24 + 100), "themed", fill=warna_teks)
            x += 100
    dr.text((40, 1010), f"Merah {MERAH}  Krem {KREM}  (pita debug {NAVY})", fill="#1B1B1B")
    kanvas.save(FOLDER / "pratinjau.png", optimize=True)


# ---------------------------------------------------------------- drawable Android

def vector_xml(isi, komentar):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<!-- {komentar}\n     Dibuat oleh docs/showcase/logo/buat_logo.py; ubah lewat skrip itu. -->\n"
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="108dp"\n    android:height="108dp"\n'
        '    android:viewportWidth="108"\n    android:viewportHeight="108">\n'
        f"{isi}</vector>\n"
    )


def tulis_android():
    d_v = path_poligon(v_adaptif())
    main = RES / "main" / "res"
    (main / "drawable" / "ic_launcher_foreground.xml").write_text(vector_xml(
        f'    <path\n        android:fillColor="{KREM}"\n        android:pathData="{d_v}" />\n',
        "Lapisan depan ikon adaptif: huruf V Veritas di dalam safe zone (lingkaran 66 dp).",
    ), encoding="utf-8")
    (main / "drawable" / "ic_launcher_monochrome.xml").write_text(vector_xml(
        f'    <path\n        android:fillColor="#FFFFFFFF"\n        android:pathData="{d_v}" />\n',
        "Ikon monochrome untuk themed icons Android 13+: hanya bentuknya yang dipakai sistem.",
    ), encoding="utf-8")
    (main / "drawable" / "ic_launcher_background.xml").write_text(vector_xml(
        f'    <path\n        android:fillColor="{MERAH}"\n        android:pathData="M0,0h108v108h-108z" />\n',
        "Lapisan belakang ikon adaptif: merah Veritas.",
    ), encoding="utf-8")
    atas, tinggi, huruf = pita_debug()
    path_huruf = "".join(
        f'    <path\n        android:fillColor="{KREM}"\n        android:pathData="{d}" />\n' for d in huruf
    )
    dbg = RES / "debug" / "res" / "drawable"
    dbg.mkdir(parents=True, exist_ok=True)
    (dbg / "ic_launcher_foreground.xml").write_text(vector_xml(
        f'    <path\n        android:fillColor="{KREM}"\n        android:pathData="{d_v}" />\n'
        f'    <path\n        android:fillColor="{NAVY}"\n'
        f'        android:pathData="M0,{atas:g}h108v{tinggi:g}h-108z" />\n'
        + path_huruf,
        "Lapisan depan ikon versi debug: V Veritas dengan pita DEBUG supaya mudah dibedakan.",
    ), encoding="utf-8")
    # Ikon bitmap lama (mipmap-*dpi) tidak pernah dipakai: minSdk 26 selalu memakai
    # mipmap-anydpi (ikon adaptif). Isinya tetap diperbarui supaya tidak ada logo lama tersisa.
    for folder, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        for nama, bentuk in (("ic_launcher", "persegi_bulat"), ("ic_launcher_round", "bulat")):
            im = ikon_termasker(px, bentuk, (0, 0, 0)).convert("RGBA")
            im.putalpha(masker(px, bentuk))
            im.save(main / f"mipmap-{folder}" / f"{nama}.webp", lossless=True)


def main():
    teks_ikon, _ = logo_ikon()
    berkas_ikon = FOLDER / "logo_veritas.svg"
    berkas_teks = FOLDER / "logo_veritas_teks.svg"
    berkas_ikon.write_text(teks_ikon, encoding="utf-8")
    berkas_teks.write_text(logo_teks(), encoding="utf-8")
    png_ikon = FOLDER / "logo_veritas.png"
    png_teks = FOLDER / "logo_veritas_teks.png"
    render_svg(berkas_ikon, png_ikon)
    render_svg(berkas_teks, png_teks)
    pratinjau(png_ikon, png_teks)
    va = v_adaptif()
    print("V adaptif (dp): x %.1f..%.1f, y %.1f..%.1f" % (*[f(p[0] for p in va) for f in (min, max)],
                                                           *[f(p[1] for p in va) for f in (min, max)]))
    print("Selesai:", ", ".join(p.name for p in (berkas_ikon, berkas_teks, png_ikon, png_teks)), "pratinjau.png")
    if "--android" in sys.argv:
        tulis_android()
        print("Drawable ikon Android diperbarui.")


if __name__ == "__main__":
    main()
