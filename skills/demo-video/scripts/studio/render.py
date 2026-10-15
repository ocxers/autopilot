#!/usr/bin/env python3
"""camera=studio / frame=wallpaper: push-ins on what is clicked or typed, in a browser window on a wallpaper.

    python3 render.py <session dir> <out.mp4> [--timeline timeline.json] [--camera studio|static]
                      [--frame wallpaper|none] [--background <name|image|#hex>] [--window browser|plain]
                      [--size WxH] [--url URL] [--max-zoom 1.8] [--fps 30] [--preview]

The session is to_session.py's: frames/ plus timeline.json with frames [{t, file}], viewport and
focuses [{t, readyAt, interactionEnd, end, x, y, width, height, result?}] (CSS px, output seconds).
The camera eases in on each focus (its target, plus the result the click opened when both stay readable),
holds while the interaction lasts, then eases back out, or pans straight on when the next focus is near.
--camera static keeps the full page (a plain recording on the wallpaper).
--frame none: the page fills the video, no wallpaper or window (default size: the recording's own pixels).
--timeline (post.sh's timeline-<name>.json) adds captions, chapter pills, tips and fast-forward badges.
--background: a render_demo.py preset (Recordly wallpaper such as ventura, or an original gradient such as aurora),
an image path, or a #hex colour; default ventura when downloaded, else aurora. The cursor is in the recording.
"""
import bisect
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'post'), str(HERE.parent)]
import build  # noqa: E402  (fonts and the caption / badge / chapter overlay)

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
session, out = Path(args[0]), args[1]
FPS = int(opt('--fps', 30))
PREVIEW = '--preview' in sys.argv
TL = json.loads((session / 'timeline.json').read_text())
VW, VH = TL['viewport']['width'], TL['viewport']['height']
SCALE = TL.get('capture', {}).get('scale', 2)
FRAME = opt('--frame', 'wallpaper')
MAX_ZOOM = 1.0 if opt('--camera', 'studio') == 'static' else float(opt('--max-zoom', 1.8))
W, H = (int(v) for v in opt('--size', f'{VW * SCALE}x{VH * SCALE}' if FRAME == 'none' else '1920x1080').split('x'))
URL = opt('--url', TL.get('url', ''))
WINDOW = opt('--window', 'browser')
CAPS = json.loads(Path(opt('--timeline')).read_text()) if opt('--timeline') else None
DURATION = max(TL['duration'], CAPS['duration'] if CAPS else 0)

# ---------- camera ----------
ease = lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
FULL = (VW / 2, VH / 2, 1.0)


def view_for(boxes):
    """Camera (cx, cy, zoom) framing the boxes with room around them, 16:9, inside the viewport."""
    x0 = min(b['x'] for b in boxes); y0 = min(b['y'] for b in boxes)
    x1 = max(b['x'] + b['width'] for b in boxes); y1 = max(b['y'] + b['height'] for b in boxes)
    w = (x1 - x0) * 1.6 + 120
    h = (y1 - y0) * 1.6 + 90
    w = max(w, h * VW / VH, VW / MAX_ZOOM)
    zoom = max(1.0, min(MAX_ZOOM, VW / w))
    vw, vh = VW / zoom, VH / zoom
    cx = min(max((x0 + x1) / 2, vw / 2), VW - vw / 2)
    cy = min(max((y0 + y1) / 2, vh / 2), VH - vh / 2)
    return (cx, cy, zoom)


def keyframes():
    ks = [(0.0, FULL)]
    focuses = sorted((f for f in TL.get('focuses', []) if f.get('width') and f.get('height')), key=lambda f: f['t'])
    for i, f in enumerate(focuses):
        r = f.get('result') if (f.get('result') or {}).get('width') else None
        # The result joins the frame when both still read at about 1.25x or more; otherwise the camera
        # frames the control for the click, then pans to the result it opened.
        both = r is not None and view_for([f, r])[2] >= 1.25
        target = view_for([f, r] if both else [f])
        start = max(ks[-1][0], min(f.get('readyAt', f['t']), f['t']) - 0.45)
        arrive = start + 0.6
        ks.append((start, camera_at(start, ks)))
        ks.append((arrive, target))
        if r is not None and not both:
            leave = max(arrive + 0.3, f.get('interactionEnd', f['t']) + 0.15)
            ks.append((leave, target))
            target = view_for([r])
            arrive = leave + 0.7
            ks.append((arrive, target))
        hold = max(arrive + 0.4, f.get('end', f['t']) + 0.35)
        ks.append((hold, target))
        nxt = focuses[i + 1]['t'] if i + 1 < len(focuses) else None
        if nxt is None or nxt - hold > 1.6:
            ks.append((hold + 0.8, FULL))
    return ks


def camera_at(t, ks):
    times = [k[0] for k in ks]
    i = bisect.bisect_right(times, t) - 1
    if i < 0:
        return ks[0][1]
    if i >= len(ks) - 1:
        return ks[-1][1]
    (t0, a), (t1, b) = ks[i], ks[i + 1]
    if t1 - t0 < 1e-6:
        return b
    u = ease(min(1.0, max(0.0, (t - t0) / (t1 - t0))))
    return tuple(a[j] + (b[j] - a[j]) * u for j in range(3))


KS = keyframes()
# For the review: where the camera is at each keyframe (centre in CSS px, zoom).
(session / 'camera.json').write_text(json.dumps([{'t': round(t, 3), 'cx': round(c[0]), 'cy': round(c[1]), 'zoom': round(c[2], 3)} for t, c in KS]))

# ---------- stage: background, window, toolbar ----------
s = W / 1920
win_w = int(W * 0.86) if FRAME != 'none' else W
bar_h = int(46 * s) if WINDOW == 'browser' and FRAME != 'none' else 0
content_w, content_h = win_w, int(win_w * VH / VW)
if content_h + bar_h > H * (0.9 if FRAME != 'none' else 1.0):
    content_h = int(H * (0.9 if FRAME != 'none' else 1.0)) - bar_h
    content_w = int(content_h * VW / VH)
    win_w = content_w
win_h = content_h + bar_h
wx, wy = (W - win_w) // 2, (H - win_h) // 2
radius = int(14 * s) if FRAME != 'none' else 0


def background():
    """--background: a preset of render_demo.py (Recordly wallpaper or original gradient), an image, or #hex."""
    import render_demo as rd
    name = opt('--background')
    if name and name.startswith('#'):
        return Image.new('RGB', (W, H), name)
    if name and Path(name).exists():
        return rd.cover(Image.open(name).convert('RGB'), (W, H))
    if not name:
        name = 'ventura' if (rd.RECORDLY_CACHE / 'ventura.jpg').exists() else 'aurora'
    return rd.make_background(name, (W, H), Path.cwd())


def stage():
    if FRAME == 'none':
        return Image.new('RGB', (W, H)), Image.new('L', (W, H), 255)
    bg = background()
    shadow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([wx, wy + int(18 * s), wx + win_w, wy + win_h + int(18 * s)], radius, fill=150)
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(28 * s)))
    bg.paste((0, 0, 0), (0, 0), shadow)
    if bar_h:
        bar = Image.new('RGB', (win_w, bar_h), (236, 238, 241))
        d = ImageDraw.Draw(bar)
        for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
            cx, cy, r = int((22 + i * 20) * s), bar_h // 2, int(6 * s)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
        ux0, ux1 = int(110 * s), win_w - int(110 * s)
        d.rounded_rectangle([ux0, int(9 * s), ux1, bar_h - int(9 * s)], int(8 * s), fill=(255, 255, 255))
        f = build.font(max(12, int(16 * s)), 'regular')
        text = URL
        while text and d.textlength(text, font=f) > ux1 - ux0 - int(24 * s):
            text = text[:-2] + '…' if not text.endswith('…') else text[:-2] + '…'
        d.text((ux0 + int(12 * s), bar_h // 2), text, font=f, fill=(90, 96, 105), anchor='lm')
        bg.paste(bar, (wx, wy))
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([wx, wy, wx + win_w, wy + win_h], radius, fill=255)
    return bg, mask


STAGE, WIN_MASK = stage()
CONTENT_MASK = WIN_MASK.crop((wx, wy + bar_h, wx + content_w, wy + bar_h + content_h))

# ---------- captions / chapters / fast-forward (post.sh's timeline) ----------
_ov = {}


def overlay_at(t):
    if not CAPS:
        return None
    cap = next(((c['text'], c.get('pos', 'bottom')) for c in CAPS['captions'] if c['from'] <= t < c['to']), (None, 'bottom'))
    chapter = next((c['name'] for c in CAPS['chapters'] if c['at'] <= t < c['at'] + build.CHAPTER_S), None)
    ff = next((f for f in CAPS['fast_forward'] if f['from'] <= t < f['to'] and f['speed'] > 1), None)
    badge = os.environ.get('BADGE', 'Fast-forward ×{n}').format(n=int(ff['speed'])) if ff else None
    tip = next(({k: v for k, v in c.items() if k not in ('from', 'to')} for c in CAPS.get('tips', []) if c['from'] <= t < c['to']), None)
    state = [cap[0], cap[1], badge, chapter, json.dumps(tip, ensure_ascii=False) if tip else None]
    if not any(state[i] for i in (0, 2, 3, 4)):
        return None
    key = json.dumps(state, ensure_ascii=False)
    if key not in _ov:
        build.TMP.mkdir(parents=True, exist_ok=True)
        png = build.overlay_png(state, build.TMP)
        _ov[key] = Image.open(png).convert('RGBA').resize((W, H), Image.LANCZOS)
    return _ov[key]


# ---------- render ----------
frames = TL['frames']
ftimes = [f['t'] for f in frames]
cache = {'i': None, 'img': None}


def source_at(t):
    i = max(0, bisect.bisect_right(ftimes, t) - 1)
    if cache['i'] != i:
        cache['img'] = Image.open(session / frames[i]['file']).convert('RGB')
        cache['i'] = i
    return cache['img']


ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'veryfast' if PREVIEW else 'medium', '-crf', '23' if PREVIEW else '18',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
n = int(DURATION * FPS) + 1
for k in range(n):
    t = k / FPS
    img = source_at(t)
    sx, sy = img.width / VW, img.height / VH
    cx, cy, z = camera_at(t, KS)
    vw, vh = VW / z, VH / z
    box = (int((cx - vw / 2) * sx), int((cy - vh / 2) * sy), int((cx + vw / 2) * sx), int((cy + vh / 2) * sy))
    content = img.resize((content_w, content_h), Image.BILINEAR, box=box)
    frame = STAGE.copy()
    frame.paste(content, (wx, wy + bar_h), CONTENT_MASK)
    ov = overlay_at(t)
    if ov is not None:
        frame = frame.convert('RGBA')
        frame.alpha_composite(ov)
        frame = frame.convert('RGB')
    ff.stdin.write(frame.tobytes())
    if k % (FPS * 30) == 0:
        print(f'{t:.0f}s / {DURATION:.0f}s', flush=True)
ff.stdin.close()
if ff.wait() != 0:
    raise SystemExit('ffmpeg failed')
print('wrote', out, f'{DURATION:.1f}s, {len([k for k in KS if k[1] != FULL])} camera holds')
