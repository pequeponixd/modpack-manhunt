#!/usr/bin/env python3
"""
Genera el arte estilo Minecraft del modpack Manhunt (pixel art con bloques).

    python3 tools/make-art.py Modpack

Crea en Modpack/: icon.png (brújula), logo.png, background.png
y en Modpack/config/fancymenu/assets/: background.apng, intro.apng, island.png, glow.png,
botones, barra de carga y sonidos. Después corre el make-menu del launcher. Requiere Pillow.

Todo se dibuja en una cuadrícula chica (480x270, bloques de 8 px) y se agranda sin suavizar.
"""
import math
import random
import struct
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H = 480, 270
B = 8  # tamaño de un bloque en la cuadrícula
INK = (20, 16, 22)
GRASS = (98, 160, 58)
DIRT = (128, 88, 56)
STONE = (122, 122, 126)
OBSIDIAN = (30, 20, 44)
LOG = (88, 62, 38)
LEAVES = (46, 92, 52)
PORTAL = (150, 60, 230)
WHITE = (250, 248, 240)
GOLD = (236, 190, 60)
RED = (210, 44, 44)
SKY = [(30, 34, 82), (62, 52, 120), (128, 70, 140), (214, 98, 110), (246, 150, 92), (252, 200, 120)]


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def jitter(c, rnd, amount=12):
    d = rnd.randint(-amount, amount)
    return tuple(max(0, min(255, v + d)) for v in c)


def up(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


# --------------------------------------------------------- texturas de 1 bloque
def texture(kind, seed=0, tint=None):
    rnd = random.Random(f'{kind}:{seed}')  # semilla de texto: mismo resultado en cada ejecución
    t = Image.new('RGBA', (B, B))
    px = t.load()
    for y in range(B):
        for x in range(B):
            if kind == 'grass':
                edge = 2 + (rnd.random() < 0.3)
                c = jitter(GRASS, rnd) if y < edge else jitter(DIRT, rnd, 14)
            elif kind == 'dirt':
                c = jitter(DIRT, rnd, 14)
            elif kind == 'stone':
                c = jitter(STONE, rnd, 10) if rnd.random() > 0.1 else jitter(mix(STONE, INK, 0.3), rnd, 6)
            elif kind == 'obsidian':
                c = jitter(OBSIDIAN, rnd, 6) if rnd.random() > 0.12 else (80, 50, 120)
            elif kind == 'log':
                c = jitter(mix(LOG, INK, 0.35) if x % 4 == 0 else LOG, rnd, 8)
            elif kind == 'leaves':
                c = jitter(LEAVES, rnd, 16) if rnd.random() > 0.15 else mix(LEAVES, INK, 0.45)
            if tint:
                c = mix(c, tint[0], tint[1])
            px[x, y] = (*c, 255)
    return t


def portal_tex(t, w, h):
    """Remolino violeta animado: ondas que bajan. t en [0,1)."""
    img = Image.new('RGBA', (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            v = math.sin((x * 0.5 + y * 0.9) - t * math.tau) + math.sin((x * 0.9 - y * 0.4) + t * math.tau * 2)
            px[x, y] = (*mix(PORTAL, (220, 160, 255) if v > 0.9 else (90, 30, 160), min(1, abs(v) / 2)), 255)
    return img


# ------------------------------------------------------------------ paisaje
def heights(n, base, amp, seed, step=2):
    rnd = random.Random(seed)
    h, out = base, []
    for i in range(n):
        if i % step == 0:
            h = max(base - amp, min(base + amp, h + rnd.choice((-1, 0, 0, 1))))
        out.append(h)
    return out


def spruce(layer, x, ground, rnd, tint=None):
    """Pino de bloques: tronco y capas de hojas cada vez más angostas."""
    trunk = rnd.randint(2, 3)
    for k in range(trunk):
        layer.alpha_composite(texture('log', x + k, tint), (x * B, (ground - 1 - k) * B))
    # copa de abajo hacia arriba: ancha, angosta, ancha, angosta… y punta
    widths = rnd.choice(([2, 1, 2, 1, 1, 0], [3, 2, 1, 2, 1, 0], [2, 1, 1, 0]))
    for k, wd in enumerate(widths):
        y = ground - trunk - k
        for dx in range(-wd, wd + 1):
            layer.alpha_composite(texture('leaves', x * 7 + dx + k * 3, tint), ((x + dx) * B, (y - 1) * B))


PORTAL_COL, PORTAL_W, PORTAL_H = 45, 4, 5  # columna (en bloques), ancho y alto del marco


def terrain():
    """Capas de bloques encima del cielo. Devuelve (capa RGBA, rect del hueco del portal en px)."""
    cols, rows = W // B, H // B + 1
    layer = Image.new('RGBA', (W, H))
    # montañas lejanas, desteñidas hacia el color del cielo
    far = heights(cols, rows - 13, 3, 3, step=2)
    haze = (SKY[1], 0.6)
    for x, h in enumerate(far):
        for y in range(h, rows):
            layer.alpha_composite(texture('stone' if y > h else 'grass', x * 31 + y, haze), (x * B, y * B))
    # colinas del medio con pinos y el portal
    mid = heights(cols, rows - 8, 2, 8, step=3)
    mid[PORTAL_COL - 1:PORTAL_COL + PORTAL_W + 1] = [mid[PORTAL_COL]] * (PORTAL_W + 2)  # piso plano bajo el portal
    rnd = random.Random(5)
    for x, h in enumerate(mid):
        for y in range(h, rows):
            layer.alpha_composite(texture('grass' if y == h else 'dirt' if y < h + 3 else 'stone', x * 13 + y), (x * B, y * B))
    for x in (3, 7, 12, 17, 41, 53, 57):  # el centro queda libre para el personaje y los botones
        spruce(layer, x, mid[x], rnd)
    g = mid[PORTAL_COL]
    for i in range(PORTAL_W):
        for j in range(PORTAL_H):
            if i in (0, PORTAL_W - 1) or j in (0, PORTAL_H - 1):
                layer.alpha_composite(texture('obsidian', i * 5 + j), ((PORTAL_COL + i) * B, (g - 1 - j) * B))
    hole = ((PORTAL_COL + 1) * B, (g - PORTAL_H + 1) * B, (PORTAL_COL + PORTAL_W - 1) * B, (g - 1) * B)
    layer.paste((0, 0, 0, 0), hole)  # hueco transparente: ahí se dibuja el portal animado
    # primer plano: una fila de bloques más cerca, centro despejado para el personaje
    near = heights(cols, rows - 4, 1, 21, step=4)
    for x, h in enumerate(near):
        for y in range(h, rows):
            layer.alpha_composite(texture('grass' if y == h else 'dirt', x * 17 + y + 99, (INK, 0.15)), (x * B, y * B))
    return layer, hole


def sky():
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    band = H * 0.75 / len(SKY)
    for y in range(H):
        k = min(len(SKY) - 1, int(y / band))
        frac = y / band - k
        # entre franjas, tramado de 2 colores como en los juegos viejos
        c = SKY[min(len(SKY) - 1, k + 1)] if frac > 0.75 and k + 1 < len(SKY) else SKY[k]
        d.line((0, y, W, y), fill=c)
        if 0.75 < frac < 0.88 and k + 1 < len(SKY):
            for x in range(y % 2, W, 2):
                img.putpixel((x, y), SKY[k])
    rnd = random.Random(1)
    for _ in range(60):
        x, y = rnd.randrange(W), rnd.randrange(int(H * 0.3))
        img.putpixel((x, y), WHITE if rnd.random() < 0.3 else (170, 170, 210))
    # sol cuadrado bajando en el horizonte
    sx, sy, s = int(W * 0.88), int(H * 0.5), 22
    d.rectangle((sx - s // 2 - 4, sy - s // 2 - 4, sx + s // 2 + 4, sy + s // 2 + 4), fill=mix(SKY[4], (255, 230, 140), 0.5))
    d.rectangle((sx - s // 2, sy - s // 2, sx + s // 2, sy + s // 2), fill=(255, 236, 150))
    return img


CLOUDS = [(10, 26, 48, 8), (120, 14, 64, 10), (220, 40, 40, 6), (330, 22, 56, 8), (420, 48, 32, 6)]


def clouds(img, t):
    """Nubes planas de bloques que se mueven a la izquierda y dan la vuelta."""
    over = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(over)
    for x0, y, w, h in CLOUDS:
        x = round((x0 - t * W) % (W + 80)) - 80
        d.rectangle((x, y, x + w, y + h), fill=(255, 255, 255, 215))
        d.rectangle((x + 8, y - 4, x + w - 12, y), fill=(255, 255, 255, 215))
        d.rectangle((x, y + h - 2, x + w, y + h), fill=(220, 210, 230, 215))
    img.paste(over, (0, 0), over)


_TERRAIN = None


def scene(t=0.0):
    global _TERRAIN
    if _TERRAIN is None:
        _TERRAIN = (sky(), *terrain())
    base, layer, hole = _TERRAIN
    img = base.copy()
    clouds(img, t)
    img.paste(portal_tex(t, hole[2] - hole[0], hole[3] - hole[1]), hole[:2])
    img = img.convert('RGBA')
    img.alpha_composite(layer)
    return img.convert('RGB')


# ------------------------------------------------------------------ logo
FONT = {
    'M': ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
    'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
    'N': ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
    'H': ['10001', '10001', '10001', '11111', '10001', '10001', '10001'],
    'U': ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
    'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
    'S': ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
    'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
    'V': ['10001', '10001', '10001', '10001', '01010', '01010', '00100'],
    'I': ['111', '010', '010', '010', '010', '010', '111'],
    'L': ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
}


def cells(text):
    out, x = [], 0
    for ch in text:
        rows = FONT[ch]
        out += [(x + cx, cy) for cy, r in enumerate(rows) for cx, v in enumerate(r) if v == '1']
        x += len(rows[0]) + 1
    return out, x - 1


def logo_img(k=4):
    """Letras de piedra con relieve hacia abajo y el subtítulo amarillo, como un título de juego de bloques."""
    c, cols = cells('MANHUNT')
    cs, depth = 6, 3  # cada celda del texto mide 6 px; 3 px de profundidad
    sub, scols = cells('SURVIVAL')
    sc = 2
    w = cols * cs + depth + 2
    h = 7 * cs + depth + 2 + 7 * sc + 6
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    for i in range(depth + 1, 0, -1):  # relieve y borde
        for x, y in c:
            col = INK if i == depth + 1 else mix(STONE, INK, 0.55 + 0.1 * i / depth)
            d.rectangle((1 + x * cs + i - 1, 1 + y * cs + i - 1, x * cs + cs + i, y * cs + cs + i), fill=col)
    for x, y in c:
        d.rectangle((x * cs, y * cs, x * cs + cs + 1, y * cs + cs + 1), fill=INK)
    for x, y in c:
        for py in range(cs):
            for px_ in range(cs):
                g = mix((200, 200, 204), STONE, (y * cs + py) / (7 * cs))  # más claro arriba
                img.putpixel((1 + x * cs + px_, 1 + y * cs + py), (*jitter(g, rnd, 10), 255))
    ox, oy = (w - scols * sc) // 2, 7 * cs + depth + 5
    for x, y in sub:
        d.rectangle((ox + x * sc - 1, oy + y * sc - 1, ox + x * sc + sc, oy + y * sc + sc), fill=INK)
    for x, y in sub:
        d.rectangle((ox + x * sc, oy + y * sc, ox + x * sc + sc - 1, oy + y * sc + sc - 1), fill=(255, 220, 60))
    return up(img, k)


# --------------------------------------------------------------- iconos y UI
COMPASS = [
    '.....XXXXXX.....',
    '...XXGGGGGGXX...',
    '..XGGYYYYYYGGX..',
    '.XGYWWWWWWWWYGX.',
    '.XGYWWWWWWRRYGX.',
    'XGYWWWWWWRRRWYGX',
    'XGYWWWWWRRRWWYGX',
    'XGYWWWWXXRWWWYGX',
    'XGYWWWBXXWWWWYGX',
    'XGYWWBBBWWWWWYGX',
    'XGYWBBBWWWWWWYGX',
    '.XGYBBWWWWWWYGX.',
    '.XGYWWWWWWWWYGX.',
    '..XGGYYYYYYGGX..',
    '...XXGGGGGGXX...',
    '.....XXXXXX.....',
]


def compass_icon():
    pal = {'X': INK, 'G': (170, 120, 30), 'Y': GOLD, 'W': (232, 228, 214), 'R': RED, 'B': (70, 100, 200)}
    img = Image.new('RGBA', (16, 16))
    for y, row in enumerate(COMPASS):
        for x, ch in enumerate(row):
            if ch in pal:
                img.putpixel((x, y), (*pal[ch], 255))
    return up(img, 16)


def button(w, h, base, hover=False, seed=3):
    """Botón de piedra: borde negro, luz arriba a la izquierda y sombra abajo a la derecha."""
    rnd = random.Random(seed)
    if hover:
        base = mix(base, (150, 170, 255), 0.35)
    img = Image.new('RGBA', (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if x in (0, w - 1) or y in (0, h - 1):
                c = WHITE if hover else INK
            elif y == 1 or x == 1:
                c = mix(base, WHITE, 0.4)
            elif y >= h - 3 or x == w - 2:
                c = mix(base, INK, 0.45)
            else:
                c = jitter(base, rnd, 6)
            px[x, y] = (*c, 255)
    return img


def island():
    """Isla flotante de bloques donde se para el personaje (grilla de 8 px, agrandada x4)."""
    img = Image.new('RGBA', (64, 40))
    rows = [(0, 8, 'grass'), (1, 8, 'dirt'), (2, 6, 'dirt'), (3, 4, 'stone'), (4, 2, 'stone')]
    for r, n, kind in rows:
        x0 = (8 - n) * 4
        for i in range(n):
            t = texture(kind, r * 9 + i).resize((8, 8), Image.NEAREST)
            img.alpha_composite(t, (x0 + i * 8, r * 8))
    return up(img, 4)


def glow(w=180, h=220):
    img = Image.new('RGBA', (w, h))
    ImageDraw.Draw(img).ellipse((w * 0.15, h * 0.1, w * 0.85, h * 0.9), fill=(255, 220, 140, 110))
    return img.filter(ImageFilter.GaussianBlur(w / 8))


def loading_bar(w=200, h=10, filled=True):
    img = Image.new('RGBA', (w, h), (*INK, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((1, 1, w - 2, h - 2), fill=(90, 160, 60) if filled else (60, 60, 64))
    if filled:
        d.line((1, 1, w - 2, 1), fill=(150, 210, 100))
        for x in range(2, w - 2, 8):  # marcas de bloques
            d.line((x, 2, x, h - 3), fill=(70, 130, 46))
    d.line((1, h - 2, w - 2, h - 2), fill=mix((90, 160, 60) if filled else (60, 60, 64), INK, 0.5))
    return img


def save_apng(path, frames, ms):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, optimize=True)


def intro(path, frames=40, ms=60):
    lg = logo_img(k=2)
    out = []
    for i in range(frames):
        f = scene(0.0)
        p = min(1, i / 16)
        y = int(H * 0.3 - (1 - p) ** 2 * 200 + abs(math.sin(p * math.pi * 2)) * (1 - p) * 24)  # cae y rebota
        f2 = up(f, 2)
        f2.paste(lg, ((W * 2 - lg.width) // 2, y * 2 - lg.height // 2), lg)
        out.append(f2.convert('P', palette=Image.ADAPTIVE, colors=128))
    save_apng(path, out, ms)


def blip(path, freqs, ms, vol):
    """Click corto y seco, como el de los botones de un juego de bloques."""
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
            sq = 1 if math.sin(math.tau * f * i / rate) > 0 else -1  # onda cuadrada: suena "retro"
            data += struct.pack('<h', int(sq * vol * (1 - k) ** 3 * 32767))
        w.writeframes(data)


def main():
    pack = Path(sys.argv[1] if len(sys.argv) > 1 else 'Modpack')
    assets = pack / 'config' / 'fancymenu' / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    compass_icon().save(pack / 'icon.png')
    logo_img().save(pack / 'logo.png')
    up(scene(), 4).save(pack / 'background.png', optimize=True)
    save_apng(assets / 'background.apng', [up(scene(i / 40), 2).convert('P', palette=Image.ADAPTIVE, colors=128) for i in range(40)], 120)
    intro(assets / 'intro.apng')
    island().save(assets / 'island.png')
    glow().save(assets / 'glow.png')
    button(200, 24, (96, 150, 64)).save(assets / 'btn-play.png')
    button(200, 24, (96, 150, 64), hover=True).save(assets / 'btn-play-hover.png')
    button(98, 20, (112, 112, 116)).save(assets / 'btn.png')
    button(98, 20, (112, 112, 116), hover=True).save(assets / 'btn-hover.png')
    button(98, 20, (60, 60, 64), seed=4).save(assets / 'btn-inactive.png')
    button(8, 20, (150, 150, 154), seed=5).save(assets / 'slider-handle.png')
    button(8, 20, (150, 150, 154), hover=True, seed=5).save(assets / 'slider-handle-hover.png')
    loading_bar().save(assets / 'loading-bar.png')
    loading_bar(filled=False).save(assets / 'loading-bar-bg.png')
    blip(assets / 'hover.wav', (900, 1100), 25, 0.06)
    blip(assets / 'click.wav', (420, 260), 60, 0.12)
    for f in sorted([*pack.glob('*.png'), *assets.glob('*.png'), *assets.glob('*.apng')]):
        with Image.open(f) as im:
            print(f'{f.name}: {im.width}x{im.height}, {f.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
