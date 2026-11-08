#!/usr/bin/env python3
"""
Genera el arte del modpack Manhunt con estilo de "menú de evento": cielo espacial con nebulosa,
una explosión gigante hecha de vóxeles, plataforma oscura con borde encendido, logo de bloques
sobre un emblema de brújula y botones de solo texto en colores.

    python3 tools/make-art.py Modpack

Crea en Modpack/: icon.png, logo.png, background.png
y en Modpack/config/fancymenu/assets/: background.apng, intro.apng, txt-*.png (botones del menú),
btn*.png (resto de botones del juego), barra de carga y sonidos.
Después corre el make-menu del launcher: al ver txt-play.png arma el menú a la izquierda
y el personaje a la derecha. Requiere Pillow.
"""
import math
import random
import struct
import sys
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

INK = (22, 10, 18)
SPACE_TOP = (10, 10, 34)
SPACE_MID = (34, 16, 58)
NEBULA = [(120, 40, 140), (190, 60, 120), (90, 40, 160), (230, 110, 120)]
AURORA = (70, 220, 120)
FIRE = [(255, 236, 160), (255, 170, 60), (250, 110, 40), (210, 60, 30)]
GOLD_TOP = (255, 236, 120)
GOLD_BOT = (255, 140, 40)
EXTRUDE = (150, 40, 30)
BUTTONS = {  # texto y color de cada botón del menú (como los de un menú de evento)
    'play': ('JUGAR', (255, 80, 96)),
    'options': ('OPCIONES', (255, 220, 80)),
    'quit': ('SALIR', (96, 255, 128)),
}


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def glow_of(img, radius, strength=1.0):
    """Halo: copia desenfocada para sumar encima (modo 'screen')."""
    g = img.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        g = g.point(lambda v: min(255, int(v * strength)))
    return g


# ------------------------------------------------------------------ escena
def sky(W, H, seed=2):
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=mix(SPACE_TOP, SPACE_MID, y / H * 1.3))
    # nebulosa: manchas grandes y muy desenfocadas
    neb = Image.new('RGB', (W, H))
    dn = ImageDraw.Draw(neb)
    rnd = random.Random(seed)
    for _ in range(14):
        cx, cy = rnd.uniform(0.15, 0.8) * W, rnd.uniform(0.0, 0.9) * H
        r = rnd.uniform(0.12, 0.3) * W
        c = mix((0, 0, 0), rnd.choice(NEBULA), rnd.uniform(0.2, 0.45))
        dn.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=c)
    img = ImageChops.screen(img, neb.filter(ImageFilter.GaussianBlur(W / 14)))
    # aurora verde abajo a la izquierda
    au = Image.new('RGB', (W, H))
    da = ImageDraw.Draw(au)
    for i in range(60):
        x = W * (i / 60) * 0.55
        y = H * (0.62 + 0.08 * math.sin(i / 7)) - x * 0.15
        da.ellipse((x - W * 0.03, y - H * 0.12, x + W * 0.03, y + H * 0.02), fill=mix((0, 0, 0), AURORA, 0.35))
    return ImageChops.screen(img, au.filter(ImageFilter.GaussianBlur(W / 40)))


def stars(img, t, seed=4):
    """Cielo bien estrellado: polvo fino, estrellas de colores y algunas grandes con destello en cruz."""
    W, H = img.size
    u = max(1, W // 960)  # 1 px a 960 de ancho, 2 px a 1920
    lay = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(lay)
    rnd = random.Random(seed)
    tints = [(255, 245, 230), (200, 220, 255), (255, 220, 200), (230, 200, 255)]
    for i in range(int(W * H / 700)):
        x, y = int(rnd.random() * W), int(rnd.random() * H * 0.88)
        b = 0.35 + 0.65 * abs(math.sin(rnd.random() * 9 + t * math.tau * (1 + i % 3)))  # titilan
        s = u * (2 if rnd.random() < 0.1 else 1)
        d.rectangle((x, y, x + s - 1, y + s - 1), fill=mix((30, 20, 50), rnd.choice(tints), b * rnd.uniform(0.5, 1)))
    big = Image.new('RGB', (W, H))
    db = ImageDraw.Draw(big)
    for i in range(int(W * H / 40000)):
        x, y = int(rnd.uniform(0.02, 0.98) * W), int(rnd.uniform(0.02, 0.8) * H)
        b = 0.6 + 0.4 * abs(math.sin(rnd.random() * 9 + t * math.tau * (1 + i % 2)))
        c = mix((0, 0, 0), rnd.choice(tints), b)
        arm = u * rnd.randint(3, 6)
        db.rectangle((x - u, y - u, x + u, y + u), fill=c)
        db.rectangle((x - arm, y, x + arm, y + u - 1), fill=mix((0, 0, 0), c, 0.7))  # destello en cruz
        db.rectangle((x, y - arm, x + u - 1, y + arm), fill=mix((0, 0, 0), c, 0.7))
    lay = ImageChops.screen(lay, ImageChops.screen(big, glow_of(big, u * 3, 1.8)))
    img.paste(ImageChops.screen(img, lay))


def explosion(W, H, t):
    """Explosión de vóxeles: un resplandor naranja y miles de cubitos brillantes en rayos."""
    lay = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(lay)
    cx, cy, R = W * 0.82, H * 0.42, H * 0.42
    pulse = 1 + 0.03 * math.sin(t * math.tau)
    for k in range(6, 0, -1):  # resplandor de fondo
        r = R * k / 6 * 1.05 * pulse
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix((0, 0, 0), (240, 80, 30), 0.35 + 0.11 * (6 - k)))
    lay = lay.filter(ImageFilter.GaussianBlur(W / 30))
    cubes = Image.new('RGB', (W, H))
    dc = ImageDraw.Draw(cubes)
    rnd = random.Random(9)
    s0 = max(2, W // 240)
    rot = t * 0.08
    for ray in range(110):
        a = ray / 110 * math.tau + rnd.uniform(-0.03, 0.03) + rot
        length = rnd.uniform(0.55, 1.0) * R * pulse
        for _ in range(int(length / (s0 * 1.6))):
            r = rnd.uniform(0.12, 1) ** 0.7 * length
            if rnd.random() < 0.25:  # huecos oscuros entre fragmentos
                continue
            x, y = cx + math.cos(a) * r + rnd.uniform(-1, 1) * s0 * 3, cy + math.sin(a) * r + rnd.uniform(-1, 1) * s0 * 3
            s = s0 * rnd.choice((1, 1, 1, 2))
            heat = 1 - r / R  # más blanco cerca del centro
            c = FIRE[min(3, int((1 - heat) * 4 + rnd.uniform(-0.6, 0.6)))] if heat < 1 else FIRE[0]
            dc.rectangle((x, y, x + s, y + s), fill=c)
    lay = ImageChops.screen(lay, cubes)
    return ImageChops.screen(lay, glow_of(cubes, W / 160, 1.2))


def platform(img):
    """Plataforma oscura de bloques en primer plano, con el borde iluminado por la explosión."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    top = int(H * 0.885)
    d.rectangle((0, top, W, H), fill=(26, 18, 26))
    blk = H // 22
    rnd = random.Random(3)
    for x in range(0, W, blk):  # bloques del frente
        for y in range(top + 2, H, blk // 2):
            d.rectangle((x, y, x + blk - 2, y + blk // 2 - 2), fill=mix((24, 16, 24), (60, 36, 40), rnd.random() * 0.6 * (x / W)))
    # escalones a la derecha
    for i in range(5):
        x0 = int(W * (0.66 + i * 0.07))
        y0 = top - int(H * 0.02 * (i % 3))
        d.rectangle((x0, y0, x0 + int(W * 0.07), top), fill=(30, 20, 28))
        d.line((x0, y0, x0 + int(W * 0.07), y0), fill=(255, 150, 80), width=max(1, H // 360))
    edge = Image.new('RGB', (W, H))
    de = ImageDraw.Draw(edge)
    for x in range(0, W, 2):
        de.line((x, top, x + 1, top), fill=mix((90, 40, 40), (255, 190, 110), x / W))
    de.rectangle((0, top + 1, W, top + max(1, H // 270)), fill=(150, 70, 50))
    return ImageChops.screen(img, ImageChops.screen(edge, glow_of(edge, H / 60, 2.5)))


_STATIC = {}


def scene(W, H, t=0.0):
    if (W, H) not in _STATIC:
        _STATIC[(W, H)] = sky(W, H)
    img = _STATIC[(W, H)].copy()
    stars(img, t)
    img = ImageChops.screen(img, explosion(W, H, t))
    return platform(img)


# ------------------------------------------------------------------ fuente de bloques
FONT = {
    'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
    'C': ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
    'D': ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
    'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
    'G': ['01111', '10000', '10000', '10011', '10001', '10001', '01111'],
    'H': ['10001', '10001', '10001', '11111', '10001', '10001', '10001'],
    'I': ['111', '010', '010', '010', '010', '010', '111'],
    'J': ['00111', '00001', '00001', '00001', '00001', '10001', '01110'],
    'L': ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
    'M': ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
    'N': ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
    'O': ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
    'P': ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
    'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
    'S': ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
    'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
    'U': ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
    'V': ['10001', '10001', '10001', '10001', '01010', '01010', '00100'],
    ' ': ['000', '000', '000', '000', '000', '000', '000'],
}


def cells(text):
    out, x = [], 0
    for ch in text:
        rows = FONT[ch]
        out += [(x + cx, cy) for cy, r in enumerate(rows) for cx, v in enumerate(r) if v == '1']
        x += len(rows[0]) + 1
    return out, x - 1


def bold(c, cell):
    """Rectángulos de cada celda, media celda más anchos: trazos gruesos como en los logos de eventos."""
    return [(x * cell, y * cell, x * cell + cell + cell // 2 - 1, y * cell + cell - 1) for x, y in c]


def block_text(text, cell, depth, top=GOLD_TOP, bottom=GOLD_BOT, side=EXTRUDE):
    """Letras de bloques en 3D: cara con degradé, relieve hacia abajo a la derecha y borde oscuro."""
    c, cols = cells(text)
    rects = bold(c, cell)
    o = max(2, cell // 5)  # grosor del borde
    w, h = cols * cell + cell // 2 + depth + o * 2, 7 * cell + depth + o * 2
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in rects:  # borde de todo (cara + relieve)
        d.rectangle((x0, y0, x1 + depth + o * 2, y1 + depth + o * 2), fill=INK)
    for i in range(depth, 0, -1):
        for x0, y0, x1, y1 in rects:
            d.rectangle((o + x0 + i, o + y0 + i, o + x1 + i, o + y1 + i), fill=mix(side, INK, 0.5 * i / depth))
    for x0, y0, x1, y1 in rects:
        for py in range(y0, y1 + 1):
            d.line((o + x0, o + py, o + x1, o + py), fill=mix(top, bottom, py / (7 * cell)))
    for (x, y), (x0, y0, x1, _) in zip(c, rects):  # brillo arriba de cada fila de bloques
        if (x, y - 1) not in c:
            d.rectangle((o + x0, o + y0, o + x1, o + y0 + max(1, cell // 6)), fill=mix(top, (255, 255, 255), 0.6))
    return img


def emblem(r, needle=True):
    """Emblema redondo: aro de bronce, vidrio de colores adentro y una aguja de brújula."""
    s = r * 2 + 8
    img = Image.new('RGBA', (s, s))
    c = s / 2
    glass = Image.new('RGB', (s, s), (40, 20, 60))
    dg = ImageDraw.Draw(glass)
    cols = [(255, 70, 80), (90, 140, 255), (200, 80, 255), (60, 220, 240), (255, 200, 70), (255, 110, 200)]
    rnd = random.Random(12)
    for i in range(14):  # cristales de colores
        a0 = i / 14 * 360 + rnd.uniform(-8, 8)
        dg.pieslice((c - r, c - r, c + r, c + r), a0, a0 + rnd.uniform(14, 30), fill=cols[i % len(cols)])
    glass = glass.filter(ImageFilter.GaussianBlur(r / 9))
    mask = Image.new('L', (s, s))
    ImageDraw.Draw(mask).ellipse((c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82), fill=255)
    d = ImageDraw.Draw(img)
    d.ellipse((c - r - 3, c - r - 3, c + r + 3, c + r + 3), fill=INK)
    d.ellipse((c - r, c - r, c + r, c + r), fill=(200, 110, 50))
    d.ellipse((c - r * 0.92, c - r * 0.92, c + r * 0.92, c + r * 0.92), fill=(150, 60, 30))
    img.paste(glass, (0, 0), mask)
    d.ellipse((c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82), outline=INK, width=max(2, r // 40))
    for i in range(16):  # marcas del aro
        a = i / 16 * math.tau
        k = 0.86 if i % 4 else 0.82
        d.line((c + math.cos(a) * r * k, c + math.sin(a) * r * k, c + math.cos(a) * r * 0.97, c + math.sin(a) * r * 0.97), fill=(255, 210, 120), width=max(2, r // 30))
    if needle:
        a = -math.pi / 4
        tip, wd = r * 0.78, r * 0.12
        px, py = math.cos(a + math.pi / 2) * wd, math.sin(a + math.pi / 2) * wd
        d.polygon([(c + math.cos(a) * tip, c + math.sin(a) * tip), (c + px, c + py), (c - px, c - py)], fill=(240, 50, 50), outline=INK)
        d.polygon([(c - math.cos(a) * tip, c - math.sin(a) * tip), (c + px, c + py), (c - px, c - py)], fill=(235, 230, 220), outline=INK)
        d.ellipse((c - wd * 0.6, c - wd * 0.6, c + wd * 0.6, c + wd * 0.6), fill=INK)
    return img


def logo_img(cell=16):
    title = block_text('MANHUNT', cell, depth=cell // 2)
    sub = block_text('SURVIVAL', cell // 2, depth=cell // 4, top=(255, 255, 255), bottom=(255, 200, 120))
    r = int(title.height * 1.55)
    em = emblem(r)
    W = max(title.width, em.width) + 20
    H = em.height + sub.height // 2
    img = Image.new('RGBA', (W, H))
    ex, ey = (W - em.width) // 2, 0
    img.alpha_composite(em, (ex, ey))
    img.alpha_composite(title, ((W - title.width) // 2, ey + em.height // 2 - title.height // 2 - cell))
    img.alpha_composite(sub, ((W - sub.width) // 2, ey + em.height - sub.height // 2 - cell))
    return img


def text_button(text, color, hover=False, cell=4):
    """Botón de solo texto: letras de bloques gruesas del color del botón con un halo suave."""
    c, cols = cells(text)
    pad = cell * 4
    w, h = cols * cell + cell // 2 + pad * 2, 7 * cell + pad * 2
    face = mix(color, (255, 255, 255), 0.45) if hover else color
    letters = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(letters)
    for x0, y0, x1, y1 in bold(c, cell):
        d.rectangle((pad + x0 + 1, pad + y0 + 2, pad + x1 + 1, pad + y1 + 2), fill=(*mix(color, INK, 0.7), 255))  # sombra
    for x0, y0, x1, y1 in bold(c, cell):
        d.rectangle((pad + x0, pad + y0, pad + x1, pad + y1), fill=(*face, 255))
    halo = Image.new('RGBA', (w, h), (*color, 0))
    halo.putalpha(letters.getchannel('A').filter(ImageFilter.GaussianBlur(cell * (2.2 if hover else 1.4))).point(lambda v: min(255, int(v * (1.4 if hover else 0.8)))))
    halo.alpha_composite(letters)
    return halo


# ------------------------------------------------------------------ resto de la interfaz
def ui_button(w, h, hover=False, inactive=False):
    """Botones del resto del juego (Opciones, Volver…): vidrio oscuro con borde naranja."""
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    edge = (110, 100, 110) if inactive else (255, 200, 110) if hover else (230, 120, 60)
    fill = (30, 26, 34, 200) if inactive else (90, 40, 60, 225) if hover else (36, 18, 40, 215)
    d.rectangle((0, 0, w - 1, h - 1), fill=(*INK, 255))
    d.rectangle((1, 1, w - 2, h - 2), fill=fill, outline=(*edge, 255))
    d.line((2, 2, w - 3, 2), fill=(*mix(edge, (255, 255, 255), 0.3), 160))
    return img


def loading_bar(w=200, h=10, filled=True):
    img = Image.new('RGBA', (w, h), (*INK, 255))
    d = ImageDraw.Draw(img)
    for y in range(1, h - 1):
        c = mix((255, 220, 120), (230, 90, 40), y / h) if filled else mix((50, 30, 60), (30, 18, 40), y / h)
        d.line((1, y, w - 2, y), fill=c)
    return img


def save_apng(path, frames, ms):
    pal = frames[0].quantize(256)  # misma paleta en todos los cuadros: sin parpadeo de colores
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True)


def intro(path, frames=36, ms=60):
    W, H = 960, 540
    lg = logo_img(cell=12)
    out = []
    for i in range(frames):
        f = scene(W, H, i / frames).convert('RGBA')
        p = min(1, i / 18)
        k = 0.7 + 0.3 * (1 - (1 - p) ** 3)  # se acerca y se frena
        l = lg.resize((round(lg.width * k), round(lg.height * k)), Image.LANCZOS)
        l.putalpha(l.getchannel('A').point(lambda v: int(v * p)))
        f.alpha_composite(l, ((W - l.width) // 2, (H - l.height) // 2 - 20))
        out.append(f.convert('RGB'))
    save_apng(path, out, ms)


def blip(path, freqs, ms, vol):
    rate = 22050
    n = int(rate * ms / 1000)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        data = b''
        for i in range(n):
            k = i / n
            f = freqs[0] + (freqs[1] - freqs[0]) * k
            v = math.sin(math.tau * f * i / rate) * vol * (1 - k) ** 2
            data += struct.pack('<h', int(v * 32767))
        w.writeframes(data)


def main():
    pack = Path(sys.argv[1] if len(sys.argv) > 1 else 'Modpack')
    assets = pack / 'config' / 'fancymenu' / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    # texturas de estilos anteriores que este menú ya no usa
    for old in ('island.png', 'glow.png', 'btn-play.png', 'btn-play-hover.png', 'txt-singleplayer.png', 'txt-singleplayer-hover.png'):
        (assets / old).unlink(missing_ok=True)
    emblem(124).resize((256, 256), Image.LANCZOS).save(pack / 'icon.png')
    logo_img().save(pack / 'logo.png')
    scene(1920, 1080).save(pack / 'background.png', optimize=True)
    save_apng(assets / 'background.apng', [scene(960, 540, i / 24) for i in range(24)], 110)
    intro(assets / 'intro.apng')
    for name, (text, color) in BUTTONS.items():
        text_button(text, color).save(assets / f'txt-{name}.png')
        text_button(text, color, hover=True).save(assets / f'txt-{name}-hover.png')
    ui_button(98, 20).save(assets / 'btn.png')
    ui_button(98, 20, hover=True).save(assets / 'btn-hover.png')
    ui_button(98, 20, inactive=True).save(assets / 'btn-inactive.png')
    ui_button(8, 20, hover=True).save(assets / 'slider-handle.png')
    ui_button(8, 20, hover=True).save(assets / 'slider-handle-hover.png')
    loading_bar().save(assets / 'loading-bar.png')
    loading_bar(filled=False).save(assets / 'loading-bar-bg.png')
    blip(assets / 'hover.wav', (700, 1000), 40, 0.1)
    blip(assets / 'click.wav', (220, 520), 90, 0.22)
    for f in sorted([*pack.glob('*.png'), *assets.glob('*.png'), *assets.glob('*.apng')]):
        with Image.open(f) as im:
            print(f'{f.name}: {im.width}x{im.height}, {f.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
