"""Gera um vídeo vertical (720x1280) no estilo "receita na bancada" com
legendas palavra-a-palavra, cenas ilustradas originais e trilha sintetizada.

Tudo é desenhado do zero (sem reaproveitar imagens de terceiros), então o
resultado não carrega footage, marca ou texto do vídeo de referência.

Uso:  python3 gerar_video.py [saida.mp4]
Dependências: pillow, numpy, ffmpeg no PATH.
"""
import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 720, 1280, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# (texto, duração em segundos, destaque?) — ver COPY.md
COPY = [
    ("JÁ TENTOU", 0.75, False), ("DE TUDO", 0.65, True),
    ("E SÓ SE", 0.6, False), ("FRUSTROU?", 0.9, True),
    ("ANTES DE", 0.55, False), ("GASTAR MAIS", 0.8, True),
    ("COM O QUE", 0.55, False), ("NÃO FUNCIONA", 0.95, True),
    ("OLHA ESSA", 0.6, False), ("RECEITA", 0.8, True),
    ("DE COZINHA", 0.8, False), ("COM 4", 0.55, False),
    ("INGREDIENTES", 0.95, True), ("QUE VOCÊ", 0.55, False),
    ("JÁ TEM", 0.6, False), ("EM CASA", 0.8, True),
    ("SIMPLES", 0.7, True), ("RÁPIDA", 0.7, True),
    ("SEM SEGREDO", 0.95, False), ("O PASSO", 0.6, False),
    ("A PASSO", 0.7, True), ("ESTÁ NO", 0.55, False),
    ("LINK", 0.7, True), ("ABAIXO ↓", 1.4, True),
]
DUR = sum(d for _, d, _ in COPY)
N = int(DUR * FPS)

BOWL_C = (W // 2, 900)
BOWL_RX, BOWL_RY = 270, 85
rng = random.Random(7)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


# ---------- fundo fixo: bancada de madeira clara ----------
def make_background():
    img = Image.new("RGB", (W, H))
    px = np.zeros((H, W, 3), np.float32)
    y = np.arange(H)[:, None]
    x = np.arange(W)[None, :]
    grain = (np.sin(x * 0.045 + np.sin(y * 0.004) * 6) * 0.5
             + np.sin(x * 0.17 + y * 0.002) * 0.25
             + np.sin(x * 0.011) * 0.25)
    base = np.array([196, 150, 104], np.float32)
    dark = np.array([160, 112, 72], np.float32)
    t = (grain + 1) / 2
    px[:] = base * (1 - t[..., None] * 0.55) + dark * (t[..., None] * 0.55)
    # vinheta suave
    vy = (y - H / 2) / (H / 2)
    vx = (x - W / 2) / (W / 2)
    v = 1 - 0.25 * (vx ** 2 + vy ** 2)
    px *= v[..., None]
    img = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # pote de vidro com rótulo genérico (sem marca)
    jx, jy = 360, 330
    d.rounded_rectangle((jx - 150, jy - 230, jx + 150, jy + 200), 40,
                        fill=(236, 240, 242), outline=(200, 208, 212), width=4)
    d.rounded_rectangle((jx - 130, jy - 280, jx + 130, jy - 220), 18,
                        fill=(46, 125, 96))
    d.rounded_rectangle((jx - 135, jy - 90, jx + 135, jy + 90), 14,
                        fill=(250, 250, 246), outline=(46, 125, 96), width=5)
    f1 = ImageFont.truetype(FONT, 30)
    f2 = ImageFont.truetype(FONT, 20)
    d.text((jx, jy - 30), "BICARBONATO", font=f1, fill=(46, 125, 96), anchor="mm")
    d.text((jx, jy + 20), "de sódio • 500 g", font=f2, fill=(90, 90, 90), anchor="mm")
    return img


def draw_small_bowl(d, level):
    cx, cy = 630, 1040
    d.ellipse((cx - 72, cy - 28, cx + 72, cy + 40), fill=(150, 110, 75))
    d.ellipse((cx - 70, cy - 30, cx + 70, cy + 30), fill=(232, 240, 244),
              outline=(190, 205, 212), width=3)
    if level > 0:
        r = 58 * level
        d.ellipse((cx - r, cy - r * 0.38, cx + r, cy + r * 0.38),
                  fill=(206, 52, 30))
        for i in range(25):
            a = rng.random() * math.tau
            rr = rng.random() * r * 0.9
            d.point((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.38),
                    fill=(150, 30, 20))


def bowl_back(d):
    cx, cy = BOWL_C
    d.ellipse((cx - BOWL_RX - 10, cy + 60, cx + BOWL_RX + 10, cy + 150),
              fill=(150, 108, 72))  # sombra
    d.ellipse((cx - BOWL_RX, cy - BOWL_RY, cx + BOWL_RX, cy + BOWL_RY),
              fill=(222, 232, 236), outline=(170, 200, 215), width=6)


def bowl_front(d):
    cx, cy = BOWL_C
    d.arc((cx - BOWL_RX, cy - BOWL_RY, cx + BOWL_RX, cy + BOWL_RY), 10, 170,
          fill=(120, 170, 205), width=9)
    d.arc((cx - BOWL_RX + 30, cy - BOWL_RY + 15, cx - 40, cy + BOWL_RY - 10),
          200, 250, fill=(255, 255, 255), width=5)


def draw_contents(d, t, f):
    cx, cy = BOWL_C
    powder = ease((t - 1.2) / 1.5)          # bicarbonato caindo
    liquid = ease((t - 4.2) / 2.0)          # limão
    red = ease((t - 10.0) / 1.6)            # páprica
    stir = ease((t - 12.5) / 3.0)           # mexer → rosado
    if powder > 0:
        r = 140 * powder
        if liquid < 0.6:
            d.ellipse((cx - r, cy - r * 0.32 - 20 * powder, cx + r, cy + r * 0.3),
                      fill=(250, 250, 250), outline=(225, 225, 228), width=3)
    if liquid > 0:
        rx = lerp(150, BOWL_RX - 25, liquid)
        col = mix((250, 250, 250), (238, 72, 72), stir * 0.85)
        d.ellipse((cx - rx, cy - rx * 0.29, cx + rx, cy + rx * 0.29), fill=col)
        # espuma / bolhas da efervescência
        n = int(140 * liquid * (1 - 0.6 * stir))
        loc = random.Random(f // 2)
        for _ in range(n):
            a = loc.random() * math.tau
            rr = math.sqrt(loc.random()) * rx * 0.95
            bx, by = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.29
            s = loc.randint(3, 11)
            bc = mix((255, 255, 255), (255, 170, 170), stir)
            d.ellipse((bx - s, by - s * 0.8, bx + s, by + s * 0.8),
                      outline=bc, width=2)
    if red > 0 and stir < 1:
        loc = random.Random(99)
        for _ in range(int(320 * red * (1 - stir))):
            a = loc.random() * math.tau
            rr = math.sqrt(loc.random()) * 120
            sw = stir * 6 * (rr / 120)
            bx = cx + math.cos(a + sw) * (rr + stir * 80)
            by = cy + math.sin(a + sw) * (rr + stir * 80) * 0.29
            s = loc.randint(2, 5)
            d.ellipse((bx - s, by - s, bx + s, by + s), fill=(200, 40, 25))
    if stir > 0:  # redemoinho
        for k in range(4):
            r0 = 40 + k * 45
            ang = t * 4 + k
            d.arc((cx - r0, cy - r0 * 0.29, cx + r0, cy + r0 * 0.29),
                  math.degrees(ang) % 360, (math.degrees(ang) + 120) % 360,
                  fill=(255, 205, 205), width=4)


def draw_spoon(d, x, y, angle, fill=None):
    ca, sa = math.cos(angle), math.sin(angle)
    hx, hy = x + ca * 260, y + sa * 260
    d.line((x, y, hx, hy), fill=(175, 180, 186), width=14)
    d.line((x, y, hx, hy), fill=(215, 220, 226), width=6)
    d.ellipse((x - 42, y - 28, x + 42, y + 28), fill=(190, 196, 202),
              outline=(150, 156, 162), width=3)
    if fill:
        d.ellipse((x - 32, y - 19, x + 32, y + 19), fill=fill)


def draw_hand(d, x, y):
    skin, shade = (232, 186, 150), (205, 155, 120)
    d.rounded_rectangle((x - 10, y - 60, x + 260, y + 60), 55, fill=skin)
    for i in range(4):
        d.rounded_rectangle((x - 70, y - 52 + i * 27, x + 40, y - 30 + i * 27),
                            12, fill=skin, outline=shade, width=2)
    d.rounded_rectangle((x + 230, y - 70, x + 420, y + 70), 30, fill=(70, 80, 95))


def draw_lemon(d, x, y, squeeze):
    s = 1 - 0.15 * squeeze
    d.ellipse((x - 85 * s, y - 70, x + 85 * s, y + 70), fill=(250, 200, 30))
    d.ellipse((x - 72 * s, y - 58, x + 72 * s, y + 58), fill=(255, 238, 140))
    for k in range(8):
        a = k * math.tau / 8
        d.line((x, y, x + math.cos(a) * 62 * s, y + math.sin(a) * 50),
               fill=(245, 215, 90), width=4)


def draw_actions(d, t, f):
    cx, cy = BOWL_C
    # 0.0–3.0: colher leva bicarbonato
    if t < 3.2:
        p = ease(t / 1.4)
        sx = lerp(360, cx - 20, p)
        sy = lerp(470, cy - 160, p) + (math.sin(t * 9) * 4 if t > 1.4 else 0)
        draw_spoon(d, sx, sy, -0.5, fill=(252, 252, 252) if t < 1.4 else None)
        if 1.2 < t < 2.7:
            loc = random.Random(f)
            for _ in range(40):
                px, py = sx + loc.uniform(-30, 30), sy + loc.uniform(10, 150)
                d.ellipse((px, py, px + 4, py + 4), fill=(255, 255, 255))
    # 3.0–7.0: limão espremido
    if 3.0 < t < 7.3:
        p = ease((t - 3.0) / 0.8) * (1 - ease((t - 6.6) / 0.7))
        lx, ly = lerp(820, cx + 40, p), cy - 250
        draw_lemon(d, lx, ly, clamp((t - 4) / 0.4))
        draw_hand(d, lx + 40, ly - 110)
        if 4.0 < t < 6.4:
            for k in range(6):
                yy = ly + 60 + ((t * 600 + k * 40) % 200)
                d.ellipse((lx - 6, yy, lx + 6, yy + 16), fill=(255, 245, 190))
    # 7.0–10.0: mel
    if 7.0 < t < 10.3:
        p = ease((t - 7.0) / 0.8) * (1 - ease((t - 9.6) / 0.7))
        sx, sy = lerp(-200, cx - 10, p), cy - 230
        draw_spoon(d, sx, sy, -2.6, fill=(205, 130, 30))
        if 7.8 < t < 9.6:
            d.line((sx, sy + 20, sx + 4 * math.sin(t * 5), cy - 10),
                   fill=(215, 140, 35), width=9)
    # 10.0–12.6: páprica
    if 9.9 < t < 12.8:
        p = ease((t - 9.9) / 0.7) * (1 - ease((t - 12.1) / 0.7))
        sx, sy = lerp(800, cx + 30, p), cy - 200
        draw_spoon(d, sx, sy, -0.45, fill=(200, 45, 25) if t < 11.4 else None)
        if 10.4 < t < 11.6:
            loc = random.Random(f)
            for _ in range(60):
                yy = sy + loc.uniform(10, 180)
                xx = sx + loc.uniform(-28, 28)
                d.rectangle((xx, yy, xx + 3, yy + 3), fill=(190, 35, 20))
    # 12.5–fim: mexendo
    if t > 12.5:
        a = (t - 12.5) * 5.5
        sx = cx + math.cos(a) * 120
        sy = cy + math.sin(a) * 30 - 10
        p = ease((t - 12.5) / 0.6)
        draw_spoon(d, sx + (1 - p) * 500, sy, -0.55,
                   fill=(240, 110, 110) if t > 14 else None)


def caption_at(t):
    acc = 0.0
    for i, (txt, dur, hl) in enumerate(COPY):
        if t < acc + dur:
            return txt, hl, t - acc, i
        acc += dur
    txt, _, hl = COPY[-1]
    return txt, hl, 1.0, len(COPY) - 1


_font_cache = {}


def font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT, size)
    return _font_cache[size]


def draw_caption(img, t):
    txt, hl, local, _ = caption_at(t)
    pop = 1 + 0.25 * max(0, 1 - local / 0.12)  # "pop" de entrada
    size = int(78 * pop)
    f = font(size)
    while f.getlength(txt) > W - 70 and size > 30:
        size -= 4
        f = font(size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = 1150
    if hl:
        bw = f.getlength(txt) + 50
        d.rounded_rectangle((W / 2 - bw / 2, y - size * 0.72, W / 2 + bw / 2,
                             y + size * 0.72), 22, fill=(255, 214, 0, 255))
        d.text((W / 2, y), txt, font=f, fill=(20, 20, 20), anchor="mm",
               embedded_color=True)
    else:
        d.text((W / 2, y), txt, font=f, fill=(255, 255, 255), anchor="mm",
               stroke_width=8, stroke_fill=(0, 0, 0), embedded_color=True)
    shadow = layer.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(Image.eval(shadow, lambda v: v // 2), (0, 6))
    img.alpha_composite(layer)


def draw_overlay(img, t):
    d = ImageDraw.Draw(img)
    # barra de progresso (retenção)
    d.rectangle((0, 0, W * t / DUR, 10), fill=(255, 214, 0))
    # aviso de conteúdo informativo
    d.text((W / 2, H - 36), "Conteúdo informativo. Não substitui orientação médica.",
           font=font(19), fill=(255, 255, 255), anchor="mm",
           stroke_width=3, stroke_fill=(0, 0, 0))


def render_frame(bg, f):
    t = f / FPS
    img = bg.copy()
    d = ImageDraw.Draw(img)
    draw_small_bowl(d, 1 - ease((t - 10.4) / 1.2) * 0.7)
    bowl_back(d)
    draw_contents(d, t, f)
    bowl_front(d)
    draw_actions(d, t, f)
    # leve zoom lento ("ken burns") para dar movimento
    z = 1 + 0.06 * (t / DUR)
    if z > 1.001:
        nw, nh = int(W * z), int(H * z)
        img = img.resize((nw, nh), Image.BILINEAR)
        ox, oy = (nw - W) // 2, int((nh - H) * 0.6)
        img = img.crop((ox, oy, ox + W, oy + H))
    img = img.convert("RGBA")
    draw_caption(img, t)
    draw_overlay(img, t)
    return img.convert("RGB")


# ---------- trilha original sintetizada ----------
def make_music(path, sr=44100):
    n = int(DUR * sr)
    tt = np.arange(n) / sr
    out = np.zeros(n)
    bpm = 104
    beat = 60 / bpm
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63],
              [196.0, 246.94, 293.66], [164.81, 207.65, 246.94]]
    for i in range(int(DUR / beat) + 1):
        s = int(i * beat * sr)
        # kick
        L = int(0.25 * sr)
        k = np.arange(min(L, n - s)) / sr
        if len(k):
            out[s:s + len(k)] += 0.55 * np.sin(2 * np.pi * (50 + 90 * np.exp(-k * 30)) * k) * np.exp(-k * 12)
        # hi-hat no contratempo
        hs = int((i + 0.5) * beat * sr)
        L = min(int(0.05 * sr), n - hs)
        if L > 0:
            out[hs:hs + L] += 0.08 * np.random.default_rng(i).standard_normal(L) * np.exp(-np.arange(L) / sr * 80)
    for bar in range(int(DUR / (beat * 4)) + 1):
        s, e = int(bar * 4 * beat * sr), min(n, int((bar + 1) * 4 * beat * sr))
        seg = tt[s:e] - tt[s]
        env = np.minimum(1, seg * 4) * np.exp(-seg * 0.4)
        for fr in chords[bar % 4]:
            out[s:e] += 0.07 * np.sin(2 * np.pi * fr * tt[s:e]) * env
    # "pop" sutil a cada legenda
    acc = 0.0
    for _, dur, hl in COPY:
        s = int(acc * sr)
        L = min(int(0.06 * sr), n - s)
        k = np.arange(L) / sr
        out[s:s + L] += (0.18 if hl else 0.1) * np.sin(2 * np.pi * 900 * k) * np.exp(-k * 70)
        acc += dur
    fade = int(0.8 * sr)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / np.max(np.abs(out)) * 0.85
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "video_receita.mp4"
    music = out.rsplit(".", 1)[0] + "_trilha.wav"
    make_music(music)
    bg = make_background()
    proc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", music,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out,
    ], stdin=subprocess.PIPE)
    for f in range(N):
        proc.stdin.write(render_frame(bg, f).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"ok: {out} ({DUR:.1f}s, {N} frames)")


if __name__ == "__main__":
    main()
