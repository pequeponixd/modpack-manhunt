#!/usr/bin/env python3
"""
Genera el arte estilo dibujo animado del modpack Manhunt (contornos gruesos, colores planos).

    python3 tools/make-art.py Modpack

Crea en Modpack/: icon.png (brújula), logo.png, background.png
y en Modpack/config/fancymenu/assets/: background.apng, intro.apng, island.png, glow.png,
botones, barra de carga y sonidos. Después corre el make-menu del launcher. Requiere Pillow.
"""
import math
import random
import struct
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).with_name('LuckiestGuy-Regular.ttf')
INK = (34, 22, 46)
SKY_TOP = (58, 64, 150)
SKY_MID = (238, 112, 140)
SKY_LOW = (255, 196, 110)
SUN = (255, 222, 92)
HILL_FAR = (150, 96, 170)
HILL_MID = (64, 140, 96)
HILL_NEAR = (110, 196, 92)
PINE = (36, 102, 78)
PORTAL = (70, 34, 110)
PORTAL_IN = (186, 92, 255)
ORANGE = (255, 136, 40)
RED = (226, 52, 52)
WHITE = (255, 250, 240)
SS = 2  # todo se dibuja al doble y se reduce: bordes suaves de dibujo animado


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shrink(img, size):
    return img.resize(size, Image.LANCZOS)


def blob(d, pts, fill, w):
    """Polígono con contorno grueso."""
    d.polygon(pts, fill=fill, outline=INK, width=w)


def circles(d, cs, fill, w):
    """Varias esferas unidas con un solo contorno (nubes, arbustos)."""
    for x, y, r in cs:
        d.ellipse((x - r - w, y - r - w, x + r + w, y + r + w), fill=INK)
    for x, y, r in cs:
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def hill(W, H, base, amp, freq, phase):
    pts = [(0, H)]
    for i in range(0, 101):
        x = W * i / 100
        pts.append((x, base + amp * math.sin(freq * i / 100 * math.tau + phase)))
    return pts + [(W, H)]


def pine(d, x, y, h, w):
    d.rectangle((x - h * 0.06, y - h * 0.15, x + h * 0.06, y), fill=(110, 70, 50), outline=INK, width=w)
    for k in range(3):
        top = y - h * (0.45 + 0.27 * k)
        half = h * (0.32 - 0.07 * k)
        blob(d, [(x, top - h * 0.28), (x - half, top + h * 0.12), (x + half, top + h * 0.12)], PINE, w)


def scene(W, H, t=0.0):
    """Atardecer con colinas, pinos y un portal al Nether. t en [0,1) anima nubes, sol y portal."""
    w, h = W * SS, H * SS
    lw = max(2, round(h / 180))  # grosor del contorno
    img = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        c = mix(SKY_TOP, SKY_MID, k / 0.55) if k < 0.55 else mix(SKY_MID, SKY_LOW, (k - 0.55) / 0.45)
        d.line((0, y, w, y), fill=c)
    # sol con rayos que giran
    sx, sy, sr = w * 0.73, h * 0.5, h * 0.13
    for i in range(12):
        a = i / 12 * math.tau + t * math.tau / 12
        a2 = a + 0.12
        r1, r2 = sr * 1.25, sr * 1.75
        d.polygon([(sx + r1 * math.cos(a), sy + r1 * math.sin(a)), (sx + r2 * math.cos(a + 0.06), sy + r2 * math.sin(a + 0.06)),
                   (sx + r1 * math.cos(a2), sy + r1 * math.sin(a2))], fill=mix(SUN, SKY_LOW, 0.4))
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=SUN, outline=INK, width=lw)
    # nubes que avanzan y dan la vuelta
    for i, (cx, cy, s) in enumerate([(0.12, 0.18, 1.0), (0.45, 0.1, 0.7), (0.8, 0.22, 0.85), (1.1, 0.33, 0.6)]):
        x = ((cx + t * (0.25 if i % 2 else 0.5)) % 1.3 - 0.15) * w
        y, r = cy * h, s * h * 0.05
        circles(d, [(x, y, r), (x + r * 1.2, y - r * 0.5, r * 1.3), (x + r * 2.5, y, r * 1.05), (x + r * 1.2, y + r * 0.3, r * 1.1)], WHITE, lw)
    blob(d, hill(w, h, h * 0.62, h * 0.05, 1.5, 0.4), HILL_FAR, lw)
    # portal al Nether en la colina lejana (la meta del corredor)
    px, py, pw, ph = w * 0.16, h * 0.66, h * 0.16, h * 0.24
    d.rectangle((px, py - ph, px + pw, py), fill=PORTAL, outline=INK, width=lw)
    f = pw * 0.18
    inner = Image.new('RGB', (round(pw - 2 * f), round(ph - 2 * f)), PORTAL_IN)
    di = ImageDraw.Draw(inner)
    for k in range(-6, 12):
        y0 = (k / 6 + t) % 2 * inner.height - inner.height * 0.5
        di.line((0, y0, inner.width, y0 + inner.width * 0.6), fill=mix(PORTAL_IN, WHITE, 0.35), width=max(2, inner.width // 12))
    img.paste(inner, (round(px + f), round(py - ph + f)))
    d.rectangle((px + f, py - ph + f, px + pw - f, py - f), outline=INK, width=lw)
    blob(d, hill(w, h, h * 0.72, h * 0.04, 2.2, 2.0), HILL_MID, lw)
    rnd = random.Random(4)
    for i in range(16):
        x = w * (i + rnd.random() * 0.6) / 16
        if 0.35 < x / w < 0.65:  # centro libre para el personaje y los botones
            continue
        base = h * 0.72 + h * 0.04 * math.sin(2.2 * x / w * math.tau + 2.0) + h * 0.02
        pine(d, x, base, h * (0.13 + rnd.random() * 0.06), lw)
    blob(d, hill(w, h, h * 0.86, h * 0.03, 1.2, 4.0), HILL_NEAR, lw)
    for x in (0.04, 0.3, 0.7, 0.95):
        bx, by, r = x * w, h * 0.88, h * 0.035
        circles(d, [(bx, by, r), (bx + r, by - r * 0.5, r * 1.1), (bx + r * 2, by, r)], mix(HILL_NEAR, PINE, 0.35), lw)
    return shrink(img, (W, H))


def save_apng(path, frames, ms):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, optimize=True)


def logo_img(text='MANHUNT', sub='SURVIVAL', size=200):
    font = ImageFont.truetype(str(FONT), size * SS)
    small = ImageFont.truetype(str(FONT), size * SS // 3)
    stroke = size * SS // 12
    l, t, r, b = font.getbbox(text, stroke_width=stroke)
    sl, st, sr, sb = small.getbbox(sub, stroke_width=stroke // 2)
    W, H = r - l + stroke * 2, b - t + sb - st + stroke * 2
    img = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(img)
    ox, oy = stroke - l, stroke - t
    d.text((ox + stroke * 0.6, oy + stroke * 0.9), text, font=font, fill=INK, stroke_width=stroke, stroke_fill=INK)  # sombra
    d.text((ox, oy), text, font=font, fill=INK, stroke_width=stroke, stroke_fill=INK)
    mask = Image.new('L', img.size)
    ImageDraw.Draw(mask).text((ox, oy), text, font=font, fill=255)
    grad = Image.new('RGBA', img.size)
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        gd.line((0, y, W, y), fill=(*mix((255, 214, 70), RED, min(1, y / (b - t))), 255))
    img.paste(grad, (0, 0), mask)
    # brillo blanco arriba de las letras
    shine = Image.new('L', img.size)
    ImageDraw.Draw(shine).text((ox, oy - stroke * 0.5), text, font=font, fill=255)
    shine = Image.composite(shine, Image.new('L', img.size), mask)
    shine = shine.point(lambda v: 90 if v else 0)
    cut = Image.new('L', img.size)
    ImageDraw.Draw(cut).rectangle((0, 0, W, oy + (b - t) * 0.35), fill=255)
    img.paste((255, 255, 255, 255), (0, 0), Image.composite(shine, Image.new('L', img.size), cut))
    sx = (W - (sr - sl)) // 2 - sl
    sy = oy + b - t - st + stroke // 2
    d.text((sx, sy), sub, font=small, fill=WHITE, stroke_width=stroke // 2, stroke_fill=INK)
    return shrink(img, (W // SS, H // SS))


def compass_icon(n=256):
    s = n * SS
    img = Image.new('RGBA', (s, s))
    d = ImageDraw.Draw(img)
    lw = s // 28
    c, r = s / 2, s * 0.44
    d.ellipse((c - r, c - r, c + r, c + r), fill=(240, 180, 50), outline=INK, width=lw)
    r2 = r * 0.78
    d.ellipse((c - r2, c - r2, c + r2, c + r2), fill=WHITE, outline=INK, width=lw)
    for i in range(8):
        a = i / 8 * math.tau
        k = 0.85 if i % 2 else 0.75
        d.line((c + r2 * k * math.cos(a), c + r2 * k * math.sin(a), c + r2 * 0.95 * math.cos(a), c + r2 * 0.95 * math.sin(a)), fill=INK, width=lw // 2)
    a = -math.pi / 4  # aguja apuntando al corredor
    tip, tail, wd = r2 * 0.85, r2 * 0.85, r2 * 0.2
    px, py = math.cos(a + math.pi / 2) * wd, math.sin(a + math.pi / 2) * wd
    blob(d, [(c + tip * math.cos(a), c + tip * math.sin(a)), (c + px, c + py), (c - px, c - py)], RED, lw)
    blob(d, [(c - tail * math.cos(a), c - tail * math.sin(a)), (c + px, c + py), (c - px, c - py)], (90, 130, 230), lw)
    d.ellipse((c - lw * 1.6, c - lw * 1.6, c + lw * 1.6, c + lw * 1.6), fill=INK)
    return shrink(img, (n, n))


def button(w, h, color, hover=False, k=4):
    """Botón redondeado con borde negro, brillo arriba y sombra abajo. Se dibuja a k veces y se reduce."""
    if hover:
        color = mix(color, WHITE, 0.25)
    W, H = w * k, h * k
    img = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(img)
    rad = min(H // 3, 3 * k)
    d.rounded_rectangle((0, 0, W - 1, H - 1), rad, fill=INK)
    d.rounded_rectangle((k, k, W - 1 - k, H - 1 - k), rad - k, fill=mix(color, INK, 0.35))
    d.rounded_rectangle((k, k, W - 1 - k, H - 1 - 2 * k), rad - k, fill=color)
    d.rounded_rectangle((2 * k, 2 * k, W - 1 - 2 * k, 2 * k + H // 6), k, fill=mix(color, WHITE, 0.45))
    return shrink(img, (w, h))


def island(w=256, h=160):
    s = 2
    img = Image.new('RGBA', (w * s, h * s))
    d = ImageDraw.Draw(img)
    W, H = w * s, h * s
    lw = W // 40
    blob(d, [(W * 0.06, H * 0.3), (W * 0.94, H * 0.3), (W * 0.7, H * 0.7), (W * 0.55, H * 0.95), (W * 0.42, H * 0.8), (W * 0.28, H * 0.66)], (150, 104, 70), lw)
    d.line((W * 0.3, H * 0.45, W * 0.5, H * 0.6), fill=INK, width=lw // 2)
    d.rounded_rectangle((W * 0.02, H * 0.14, W * 0.98, H * 0.36), H * 0.1, fill=HILL_NEAR, outline=INK, width=lw)
    for x in range(6):
        gx = W * (0.12 + x * 0.15)
        d.polygon([(gx, H * 0.36), (gx + W * 0.04, H * 0.36), (gx + W * 0.02, H * 0.46)], fill=HILL_NEAR, outline=INK)
    return shrink(img, (w, h))


def glow(w=180, h=220):
    img = Image.new('RGBA', (w, h))
    ImageDraw.Draw(img).ellipse((w * 0.15, h * 0.1, w * 0.85, h * 0.9), fill=(255, 220, 140, 120))
    return img.filter(ImageFilter.GaussianBlur(w / 8))


def loading_bar(w=200, h=10, filled=True):
    k = 4
    img = Image.new('RGBA', (w * k, h * k))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), h * k // 2, fill=INK)
    inner = (k * 2, k * 2, w * k - 1 - k * 2, h * k - 1 - k * 2)
    d.rounded_rectangle(inner, h * k // 2 - k * 2, fill=ORANGE if filled else (70, 50, 90))
    if filled:
        for x in range(-h * k, w * k, h * k):
            d.polygon([(x, inner[3]), (x + h * k // 2, inner[1]), (x + h * k, inner[1]), (x + h * k // 2, inner[3])], fill=(255, 176, 70))
        d.rounded_rectangle(inner, h * k // 2 - k * 2, outline=INK, width=k)
    return shrink(img, (w, h))


def intro(path, frames=44, ms=60):
    bg = scene(960, 540, 0.0)
    lg = logo_img(size=120)
    out = []
    for i in range(frames):
        f = bg.copy()
        p = min(1, i / 18)
        # cae desde arriba y rebota (como en las caricaturas)
        y = 540 * 0.28 + (1 - p) ** 2 * -400 + math.sin(p * math.pi * 3) * (1 - p) * 40
        sq = 1 + math.sin(min(1, i / 22) * math.pi * 4) * 0.08 * max(0, 1 - i / 26)
        l = lg.resize((round(lg.width * sq), round(lg.height / sq)), Image.LANCZOS)
        f.paste(l, (round((960 - l.width) / 2), round(y - l.height / 2)), l)
        out.append(f.convert('P', palette=Image.ADAPTIVE, colors=200))
    save_apng(path, out, ms)


def blip(path, freqs, ms, vol):
    """Sonido corto tipo caricatura: varias notas que suben (boing)."""
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
    compass_icon().save(pack / 'icon.png')
    logo_img().save(pack / 'logo.png')
    scene(1920, 1080).save(pack / 'background.png', optimize=True)
    save_apng(assets / 'background.apng', [scene(960, 540, i / 30).convert('P', palette=Image.ADAPTIVE, colors=200) for i in range(30)], 100)
    intro(assets / 'intro.apng')
    island().save(assets / 'island.png')
    glow().save(assets / 'glow.png')
    button(200, 24, ORANGE).save(assets / 'btn-play.png')
    button(200, 24, ORANGE, hover=True).save(assets / 'btn-play-hover.png')
    button(98, 20, (110, 70, 160)).save(assets / 'btn.png')
    button(98, 20, (110, 70, 160), hover=True).save(assets / 'btn-hover.png')
    button(98, 20, (120, 112, 130)).save(assets / 'btn-inactive.png')
    button(8, 20, ORANGE).save(assets / 'slider-handle.png')
    button(8, 20, ORANGE, hover=True).save(assets / 'slider-handle-hover.png')
    loading_bar().save(assets / 'loading-bar.png')
    loading_bar(filled=False).save(assets / 'loading-bar-bg.png')
    blip(assets / 'hover.wav', (500, 900), 60, 0.12)
    blip(assets / 'click.wav', (300, 700), 110, 0.2)
    for f in sorted([*pack.glob('*.png'), *assets.glob('*.png'), *assets.glob('*.apng')]):
        with Image.open(f) as im:
            print(f'{f.name}: {im.width}x{im.height}, {f.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
