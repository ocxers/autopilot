#!/usr/bin/env python3
"""Render a polished demo video from real screenshots and a storyboard.

Adds what a screen recorder like Recordly adds in post: a spring-smoothed camera that zooms onto each
action, a cursor that glides on a slight arc and dips on click, click ripples, keystroke badges,
captions, crossfades between captured states, and a framed window on a wallpaper. The screenshots
themselves are never altered.

    python3 render_demo.py storyboard.json             # writes storyboard["output"]
    python3 render_demo.py storyboard.json --preview   # also writes <output>.preview.png contact sheet
    python3 render_demo.py --backgrounds out.png       # swatch sheet of the background presets

Storyboard (paths are relative to the storyboard file):
{
  "output": "../ABC-123-fix.mp4",
  "coord_frame": [1456, 839],     # coordinate system of every "at"/"focus" (the screenshot tool's frame);
                                   # defaults to the images' own pixel size
  "size": [1920, 1080], "fps": 60, # optional
  "background": "tahoe-light",     # a preset name (see --backgrounds; Recordly's set, originals, "macos-*" = this Mac's own
                                   # wallpapers), or {"image": "wall.jpg"},
                                   # {"gradient": ["#1e1b4b", "#6d28d9"]}, {"solid": "#f4f4f5"}
  "zoom": 1.6,                     # optional default zoom while an action happens
  "steps": [
    {"frame": "01.jpg", "hold": 1.5, "caption": "Renew tab, customer selected"},
    {"frame": "02.jpg", "hold": 1.5, "actions": [{"type": "click", "at": [400, 312]}]},
    {"frame": "03.jpg", "hold": 2.5, "actions": [{"type": "type", "at": [450, 313], "text": "2025"}]},
    {"frame": "04.jpg", "hold": 4, "actions": [{"type": "click", "at": [728, 367]}],
     "focus": [700, 560], "focus_zoom": 1.15, "caption": "Typed date is kept",
     "tip": {"title": "Tip", "lines": ["Request blocked locally for this recording, so the app shows an error."],
             "code": ["renewFrom: 2025-10-01"]}}
  ]
}

A step's actions play on the PREVIOUS step's frame (cursor travels, clicks/types), then the step's own
frame - the result of those actions - crossfades in and is held for "hold" seconds. "focus"/"focus_zoom"
re-aim the camera during the hold, e.g. onto a toast. An action may carry its own "zoom". "tip" draws an
annotation card (title, text lines, monospace code lines) in the top-right corner during that step's hold -
the place for anything the app itself does not show, such as a captured request payload.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

MOVE_S = 0.8
CLICK_S = 0.4
TYPE_S = 0.9
REFOCUS_S = 0.8
OUTRO_S = 1.2
END_HOLD_S = 0.6
CROSSFADE_S = 0.22
TEXT_FADE_S = 0.25
CAMERA_OMEGA = 5.5  # spring stiffness (rad/s); critically damped, settles in ~0.8 s

# Original wallpapers in the spirit of Recordly / macOS defaults: base colour + soft colour blobs.
# Each blob: (x, y, radius) as fractions of the canvas, colour.
BACKGROUNDS = {
    'aurora': ('#0b1026', [((0.15, 0.2, 0.55), '#4c1d95'), ((0.85, 0.3, 0.5), '#0e7490'),
                           ((0.55, 0.95, 0.6), '#7c3aed'), ((0.95, 0.9, 0.35), '#1d4ed8')]),
    'violet': ('#1e1b4b', [((0.1, 0.1, 0.6), '#312e81'), ((0.9, 0.9, 0.7), '#7c3aed'),
                           ((0.7, 0.2, 0.4), '#6d28d9')]),
    'sunset': ('#3b0764', [((0.1, 0.9, 0.6), '#f97316'), ((0.5, 0.75, 0.55), '#db2777'),
                           ((0.9, 0.2, 0.55), '#7c3aed'), ((0.2, 0.15, 0.4), '#be123c')]),
    'ocean': ('#082f49', [((0.2, 0.8, 0.6), '#0369a1'), ((0.85, 0.2, 0.55), '#06b6d4'),
                          ((0.6, 0.6, 0.4), '#1e40af')]),
    'mint': ('#ecfdf5', [((0.15, 0.2, 0.55), '#a7f3d0'), ((0.9, 0.8, 0.6), '#99f6e4'),
                         ((0.6, 0.1, 0.4), '#bae6fd')]),
    'lavender': ('#f5f3ff', [((0.2, 0.85, 0.6), '#ddd6fe'), ((0.85, 0.15, 0.55), '#fbcfe8'),
                             ((0.6, 0.6, 0.4), '#c7d2fe')]),
    'peach': ('#fff7ed', [((0.1, 0.2, 0.55), '#fed7aa'), ((0.9, 0.85, 0.6), '#fecdd3'),
                          ((0.7, 0.2, 0.4), '#fde68a')]),
    'graphite': ('#18181b', [((0.2, 0.2, 0.6), '#3f3f46'), ((0.85, 0.85, 0.6), '#27272a'),
                             ((0.8, 0.2, 0.35), '#52525b')]),
}
DEFAULT_BACKGROUND = 'tahoe-light'

# Recordly's built-in wallpapers, in Recordly's own order (its default is tahoe-light). Mostly Apple
# wallpapers that Recordly re-shares; fetched only by an explicit `--fetch-recordly` into a local cache,
# never bundled with the skill or committed to a repo.
RECORDLY_WALLPAPERS = [
    'tahoe-light', 'tahoe-dark', 'midnight-8', 'ipad-17-dark', 'ipad-17-light', 'sequoia-blue',
    'sequoia-blue-orange', 'ventura', 'sonoma-clouds', 'sonoma-light', 'sonoma-dark', 'glassmorphism-3',
    'glassmorphism-4', 'energy-19', 'wallpaper3', 'wallpaper4', 'cityscape', 'levels', 'wallpaper10',
    'ventura-dark', 'sonoma-evening', 'sonoma-horizon', 'iridescent-9', 'energy-17',
]
RECORDLY_CACHE = Path.home() / '.cache' / 'demo-video' / 'recordly'
RECORDLY_URL = 'https://raw.githubusercontent.com/webadderall/Recordly/main/public/wallpapers/{}.jpg'


def fetch_recordly():
    import urllib.request
    RECORDLY_CACHE.mkdir(parents=True, exist_ok=True)
    for name in RECORDLY_WALLPAPERS:
        target = RECORDLY_CACHE / f'{name}.jpg'
        if not target.exists():
            urllib.request.urlretrieve(RECORDLY_URL.format(name), target)
            Image.open(target).verify()
        print(target)

# Apple's own macOS wallpapers, read from THIS Mac's system install at render time and cached as JPEG in
# ~/.cache/demo-video - never copied into the skill or a repo (they are Apple's copyrighted images).
# Value: (label, candidate files or mobile-asset name, seconds into a .mov to grab).
_DP = '/System/Library/Desktop Pictures'
MACOS_BACKGROUNDS = {
    'macos-tahoe': ('Tahoe (26)', [f'{_DP}/.wallpapers/Tahoe Day/Tahoe Day.mov'], 3),
    'macos-sonoma': ('Sonoma Horizon (14)', [f'{_DP}/.wallpapers/Sonoma Horizon/Sonoma Horizon.heic'], 0),
    'macos-sonoma-dark': ('Sonoma Graphic Dark (14)',
                          [f'{_DP}/.wallpapers/Sonoma/Sonoma Graphic Dark Landscape.mov'], 2),
    'macos-sonoma-light': ('Sonoma Graphic Light (14)',
                           [f'{_DP}/.wallpapers/Sonoma/Sonoma Graphic Light Landscape.mov'], 2),
    'macos-ventura': ('Ventura Graphic (13)', ['asset:Ventura Graphic'], 0),
    'macos-monterey': ('Monterey Graphic (12)', ['asset:Monterey Graphic'], 0),
    'macos-big-sur': ('Big Sur (11)', ['asset:Big Sur'], 0),
    'macos-catalina': ('Catalina (10.15)', ['asset:Catalina'], 0),
    'macos-mojave-day': ('Mojave Day (10.14)', ['/Library/Desktop Pictures/Mojave Day.jpg'], 0),
    'macos-mojave-night': ('Mojave Night (10.14)', ['/Library/Desktop Pictures/Mojave Night.jpg'], 0),
    'macos-mac-blue': ('Mac Blue', [f'{_DP}/Mac Blue.heic'], 0),
    'macos-mac-purple': ('Mac Purple', [f'{_DP}/Mac Purple.heic'], 0),
    'macos-mac-pink': ('Mac Pink', [f'{_DP}/Mac Pink.heic'], 0),
    'macos-mac-yellow': ('Mac Yellow', [f'{_DP}/Mac Yellow.heic'], 0),
    'macos-radial-sky-blue': ('Radial Sky Blue', [f'{_DP}/Radial Sky Blue.heic'], 0),
}
WALLPAPER_CACHE = Path.home() / '.cache' / 'demo-video' / 'wallpapers'


def find_macos_source(candidates):
    for c in candidates:
        if c.startswith('asset:'):
            # On-demand wallpapers land here once picked in System Settings > Wallpaper.
            name = c[len('asset:'):].lower()
            root = Path('/System/Library/AssetsV2/com_apple_MobileAsset_DesktopPicture')
            for f in sorted(root.rglob('*')) if root.exists() else []:
                if f.suffix.lower() in ('.heic', '.jpg', '.png', '.mov') and name in f.stem.lower():
                    return f
        elif Path(c).exists():
            return Path(c)
    return None


def macos_wallpaper(key):
    label, candidates, seek = MACOS_BACKGROUNDS[key]
    cached = WALLPAPER_CACHE / f'{key}.jpg'
    if cached.exists():
        return cached
    src = find_macos_source(candidates)
    if src is None:
        sys.exit(f'{label} is not on this Mac yet: open System Settings > Wallpaper and select it once '
                 f'(macOS downloads it), then render again.')
    WALLPAPER_CACHE.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == '.mov':
        cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(seek), '-i', str(src), '-frames:v', '1', '-q:v', '2',
               str(cached)]
    elif src.suffix.lower() == '.heic':
        cmd = ['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '92', str(src), '--out', str(cached)]
    else:
        cmd = ['cp', str(src), str(cached)]
    if subprocess.run(cmd, capture_output=True).returncode != 0 or not cached.exists():
        sys.exit(f'Could not read {src}')
    return cached


def cover(img, size):
    scale = max(size[0] / img.width, size[1] / img.height)
    img = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - size[0]) // 2, (img.height - size[1]) // 2
    return img.crop((left, top, left + size[0], top + size[1]))


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def hex_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_font(size):
    for candidate in (
        '/System/Library/Fonts/SFNS.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def add_grain(img, amount=5):
    """Fine noise so H.264 does not band smooth gradients."""
    noise = Image.effect_noise(img.size, 64).point(lambda v: 128 + (v - 128) * amount // 64)
    return Image.blend(img, Image.merge('RGB', (noise, noise, noise)), 0.04)


def mesh_background(size, base, blobs):
    w, h = size
    sw, sh = max(64, w // 8), max(36, h // 8)
    img = Image.new('RGB', (sw, sh), hex_rgb(base))
    for (x, y, r), color in blobs:
        layer = Image.new('RGB', (sw, sh), hex_rgb(color))
        mask = Image.new('L', (sw, sh), 0)
        rr = r * max(sw, sh) * 0.55
        ImageDraw.Draw(mask).ellipse((x * sw - rr, y * sh - rr * 0.8, x * sw + rr, y * sh + rr * 0.8), fill=230)
        img.paste(layer, (0, 0), mask.filter(ImageFilter.GaussianBlur(rr * 0.45)))
    img = img.filter(ImageFilter.GaussianBlur(max(sw, sh) * 0.015)).resize(size, Image.BICUBIC)
    return add_grain(img)


def make_background(spec, size, base_dir):
    if spec is None:
        spec = DEFAULT_BACKGROUND
    if isinstance(spec, str):
        if spec in RECORDLY_WALLPAPERS:
            path = RECORDLY_CACHE / f'{spec}.jpg'
            if not path.exists():
                sys.exit(f'{spec} is not downloaded yet: ask the user, then run render_demo.py --fetch-recordly')
            return cover(Image.open(path).convert('RGB'), size)
        if spec in MACOS_BACKGROUNDS:
            return cover(Image.open(macos_wallpaper(spec)).convert('RGB'), size)
        if spec not in BACKGROUNDS:
            names = RECORDLY_WALLPAPERS + list(BACKGROUNDS) + list(MACOS_BACKGROUNDS)
            sys.exit(f'Unknown background "{spec}". Presets: {", ".join(names)}')
        return mesh_background(size, *BACKGROUNDS[spec])
    if 'image' in spec:
        img = cover(Image.open(base_dir / spec['image']).convert('RGB'), size)
        return img.filter(ImageFilter.GaussianBlur(spec['blur'])) if spec.get('blur') else img
    if 'gradient' in spec:
        a, b = spec['gradient']
        return mesh_background(size, a, [((0.0, 0.0, 0.9), a), ((1.0, 1.0, 0.9), b)])
    if 'solid' in spec:
        return Image.new('RGB', size, hex_rgb(spec['solid']))
    sys.exit(f'Unsupported background: {spec}')


class Scene:
    """Wallpaper + framed window, precomputed once per screenshot."""

    def __init__(self, size, background, images):
        self.size = size
        w, h = size
        iw, ih = images[0].size
        scale = min(w * 0.86 / iw, h * 0.84 / ih)
        self.win_w, self.win_h = int(iw * scale), int(ih * scale)
        self.win_x, self.win_y = (w - self.win_w) // 2, (h - self.win_h) // 2
        radius = max(12, int(self.win_w * 0.012))

        mask = Image.new('L', (self.win_w, self.win_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, self.win_w - 1, self.win_h - 1), radius, fill=255)
        shadow = Image.new('L', size, 0)
        ImageDraw.Draw(shadow).rounded_rectangle(
            (self.win_x, self.win_y + 22, self.win_x + self.win_w, self.win_y + self.win_h + 22), radius, fill=160
        )
        base = background.copy()
        base.paste((0, 0, 0), (0, 0), shadow.filter(ImageFilter.GaussianBlur(34)))
        rim = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(rim).rounded_rectangle(
            (self.win_x - 1, self.win_y - 1, self.win_x + self.win_w, self.win_y + self.win_h), radius + 1,
            outline=(255, 255, 255, 60), width=1,
        )

        self.frames = []
        for img in images:
            scene = base.copy().convert('RGBA')
            scene.paste(img.resize((self.win_w, self.win_h), Image.LANCZOS), (self.win_x, self.win_y), mask)
            scene.alpha_composite(rim)
            self.frames.append(scene)

    def to_scene(self, point, coord_frame):
        cw, ch = coord_frame
        return (self.win_x + point[0] / cw * self.win_w, self.win_y + point[1] / ch * self.win_h)


def cursor_sprite(scale):
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.6), (9.8, 18.4), (7.1, 12.2), (12.4, 12.2)]
    pad = 6
    pts = [(x * scale + pad, y * scale + pad) for x, y in pts]
    w, h = int(13 * scale + pad * 2), int(21 * scale + pad * 2)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 1.5, y + 2.5) for x, y in pts], fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=(255, 255, 255, 255))
    d.line(pts + [pts[0]], fill=(12, 12, 12, 255), width=max(1, round(scale * 0.9)), joint='curve')
    return img, pad


def build_timeline(board, scene, coord_frames):
    """Segments with camera/cursor targets; motion is smoothed later per frame."""
    w, h = scene.size
    default_zoom = board.get('zoom', 1.6)
    steps = board['steps']
    segs = []
    cam = (w / 2, h / 2, steps[0].get('zoom', 1.0))
    cur = (scene.win_x + scene.win_w * 0.62, scene.win_y + scene.win_h * 0.72)

    def add(**kw):
        segs.append(kw)

    for i, step in enumerate(steps):
        caption = step.get('caption')
        tip = step.get('tip')
        for action in step.get('actions', []):
            at = scene.to_scene(action['at'], coord_frames[i - 1])
            target = (at[0], at[1], action.get('zoom', step.get('zoom', default_zoom)))
            add(frame=i - 1, dur=MOVE_S, cam=target, cur0=cur, cur1=at, caption=caption)
            add(frame=i - 1, dur=CLICK_S, cam=target, cur0=at, cur1=at, click=True, caption=caption)
            if action.get('type') == 'type':
                add(frame=i - 1, dur=TYPE_S, cam=target, cur0=at, cur1=at, badge=action.get('text', ''),
                    caption=caption)
            cam, cur = target, at
        hold = float(step.get('hold', 1.5))
        if 'focus' in step:
            f = scene.to_scene(step['focus'], coord_frames[i])
            cam = (f[0], f[1], step.get('focus_zoom', cam[2]))
        elif not step.get('actions') and 'zoom' in step and i:
            cam = (cam[0], cam[1], step['zoom'])
        add(frame=i, dur=hold, cam=cam, cur0=cur, cur1=cur, caption=caption, tip=tip)

    last_caption, last_tip = steps[-1].get('caption'), steps[-1].get('tip')
    add(frame=len(steps) - 1, dur=OUTRO_S, cam=(w / 2, h / 2, 1.0), cur0=cur, cur1=cur, caption=last_caption,
        tip=last_tip)
    add(frame=len(steps) - 1, dur=END_HOLD_S, cam=(w / 2, h / 2, 1.0), cur0=cur, cur1=cur, caption=last_caption,
        tip=last_tip)
    return segs


def arc_point(p0, p1, t):
    """Quadratic Bezier with a gentle bend, like a hand moving a mouse."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist < 1:
        return p1
    bend = min(0.14 * dist, 90)
    cx, cy = (p0[0] + p1[0]) / 2 - dy / dist * bend, (p0[1] + p1[1]) / 2 + dx / dist * bend
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * cx + t * t * p1[0], u * u * p0[1] + 2 * u * t * cy + t * t * p1[1])


class Spring:
    """Critically damped spring, implicit integration (stable at any frame rate)."""

    def __init__(self, value, omega):
        self.x, self.v, self.omega = value, 0.0, omega

    def step(self, target, dt):
        o = self.omega
        f = 1 + 2 * dt * o
        hoo, hhoo = dt * o * o, dt * dt * o * o
        inv = 1 / (f + hhoo)
        self.x, self.v = (f * self.x + dt * self.v + hhoo * target) * inv, (self.v + hoo * (target - self.x)) * inv
        return self.x


def crop_box(cx, cy, z, size):
    w, h = size
    z = max(1.0, z)
    cw, ch = w / z, h / z
    x0 = min(max(cx - cw / 2, 0.0), w - cw)
    y0 = min(max(cy - ch / 2, 0.0), h - ch)
    return (x0, y0, x0 + cw, y0 + ch)


def draw_pill(img, text, center_x, bottom_y, font, fill, alpha=1.0):
    d = ImageDraw.Draw(img)
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    pad_x, pad_y = int(font.size * 0.9), int(font.size * 0.55)
    bw, bh = r - l + pad_x * 2, b - t + pad_y * 2
    x0, y0 = int(center_x - bw / 2), int(bottom_y - bh)
    overlay = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((0, 0, bw - 1, bh - 1), bh // 2, fill=fill[:3] + (int(fill[3] * alpha),))
    od.text((pad_x - l, pad_y - t), text, font=font, fill=(255, 255, 255, int(255 * alpha)))
    img.alpha_composite(overlay, (x0, y0))
    return y0


def load_mono(size):
    for candidate in ('/System/Library/Fonts/Menlo.ttc', '/System/Library/Fonts/Monaco.ttf',
                      '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def draw_tip(img, tip, fonts, alpha):
    """Annotation card in the top-right corner - clearly the video's note, not part of the app's UI."""
    title_font, body_font, mono_font = fonts
    w, h = img.size
    pad, gap, max_w = int(h * 0.022), int(h * 0.008), int(w * 0.34)
    d = ImageDraw.Draw(img)
    lines = [(tip.get('title', 'Note'), title_font, (255, 255, 255))]
    for text in tip.get('lines', []):
        lines.append((text, body_font, (226, 232, 240)))
    for text in tip.get('code', []):
        lines.append((text, mono_font, (186, 230, 253)))
    wrapped = []
    for text, font, color in lines:
        words, cur = text.split(' '), ''
        for word in words:
            trial = (cur + ' ' + word).strip()
            if d.textlength(trial, font=font) > max_w - 2 * pad and cur:
                wrapped.append((cur, font, color))
                cur = word
            else:
                cur = trial
        wrapped.append((cur, font, color))
    heights = [d.textbbox((0, 0), t or ' ', font=f)[3] for t, f, _ in wrapped]
    card_h = pad * 2 + sum(heights) + gap * (len(wrapped) - 1) + int(h * 0.006)
    x0, y0 = w - max_w - int(w * 0.02), int(h * 0.03)
    card = Image.new('RGBA', (max_w, card_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, max_w - 1, card_h - 1), int(h * 0.016), fill=(15, 23, 42, int(228 * alpha)),
                         outline=(56, 189, 248, int(200 * alpha)), width=2)
    cd.rectangle((0, int(h * 0.016), 5, card_h - int(h * 0.016)), fill=(56, 189, 248, int(255 * alpha)))
    y = pad
    for (text, font, color), lh in zip(wrapped, heights):
        cd.text((pad + 6, y), text, font=font, fill=color + (int(255 * alpha),))
        y += lh + gap
    img.alpha_composite(card, (x0, y0))


def render(board_path, preview):
    board_path = Path(board_path).resolve()
    board = json.loads(board_path.read_text())
    base_dir = board_path.parent
    size = tuple(board.get('size', [1920, 1080]))
    fps = int(board.get('fps', 60))
    dt = 1 / fps
    out = (base_dir / board['output']).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    images = [Image.open(base_dir / s['frame']).convert('RGB') for s in board['steps']]
    sizes = {img.size for img in images}
    if len(sizes) != 1:
        sys.exit(f'All frames must share one size, got {sorted(sizes)}')
    coord_frames = [tuple(board.get('coord_frame', img.size)) for img in images]

    # Build the scene at up to 2x the output size when the screenshots are sharp enough, so camera
    # zoom crops into real pixels instead of upscaling a downscaled copy.
    ss = max(1.0, min(2.0, images[0].width / (size[0] * 0.86)))
    scene_size = (round(size[0] * ss), round(size[1] * ss))
    scene = Scene(scene_size, make_background(board.get('background'), scene_size, base_dir), images)
    segs = build_timeline(board, scene, coord_frames)
    cursor, cursor_pad = cursor_sprite(scale=size[0] / 1920 * 1.9)
    caption_font = load_font(int(size[1] * 0.029))
    badge_font = load_font(int(size[1] * 0.033))
    tip_fonts = (load_font(int(size[1] * 0.024)), load_font(int(size[1] * 0.02)), load_mono(int(size[1] * 0.018)))

    first = segs[0]['cam']
    cam_x, cam_y = Spring(first[0], CAMERA_OMEGA), Spring(first[1], CAMERA_OMEGA)
    cam_z = Spring(math.log(first[2]), CAMERA_OMEGA)

    ffmpeg = subprocess.Popen(
        ['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{size[0]}x{size[1]}',
         '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-preset', 'medium',
         '-movflags', '+faststart', str(out)],
        stdin=subprocess.PIPE,
    )
    total_frames = sum(max(1, round(s['dur'] * fps)) for s in segs)
    sample_every = max(1, total_frames // 12)
    samples, n = [], 0
    prev_frame_idx, fade_from, fade_left = segs[0]['frame'], None, 0
    caption_text, caption_age = None, 0.0
    tip_key, tip_age = None, 0.0

    for seg in segs:
        frames = max(1, round(seg['dur'] * fps))
        if seg['frame'] != prev_frame_idx:
            fade_from, fade_left = scene.frames[prev_frame_idx], round(CROSSFADE_S * fps)
            prev_frame_idx = seg['frame']
        for k in range(frames):
            p = k / max(1, frames - 1)
            cx = cam_x.step(seg['cam'][0], dt)
            cy = cam_y.step(seg['cam'][1], dt)
            cz = math.exp(cam_z.step(math.log(seg['cam'][2]), dt))
            cur = arc_point(seg['cur0'], seg['cur1'], ease_in_out(p)) if seg['cur0'] != seg['cur1'] else seg['cur1']

            base = scene.frames[seg['frame']]
            if fade_left > 0:
                done = 1 - fade_left / round(CROSSFADE_S * fps)
                base = Image.blend(fade_from, base, ease_in_out(done))
                fade_left -= 1
            box = crop_box(cx, cy, cz, scene.size)
            frame = base.resize(size, Image.BICUBIC, box=box)
            to_out = size[0] / (box[2] - box[0])
            zoom = max(1.0, cz)

            def to_screen(pt):
                return ((pt[0] - box[0]) * to_out, (pt[1] - box[1]) * to_out)

            sx, sy = to_screen(cur)
            if seg.get('click'):
                rp = ease_out(p)
                r = (10 + 30 * rp) * zoom
                ring = Image.new('RGBA', size, (0, 0, 0, 0))
                ImageDraw.Draw(ring).ellipse((sx - r, sy - r, sx + r, sy + r),
                                             fill=(139, 92, 246, int(70 * (1 - rp))),
                                             outline=(139, 92, 246, int(220 * (1 - rp))), width=max(2, int(3 * zoom)))
                frame.alpha_composite(ring)
            press = 1 - 0.18 * math.sin(math.pi * min(1.0, p * 1.6)) if seg.get('click') else 1.0
            scale = min(1.6, 0.85 + 0.25 * zoom) * press
            sprite = cursor.resize((max(1, round(cursor.width * scale)), max(1, round(cursor.height * scale))),
                                   Image.LANCZOS)
            frame.alpha_composite(sprite, (round(sx - cursor_pad * scale), round(sy - cursor_pad * scale)))

            if seg.get('caption') != caption_text:
                caption_text, caption_age = seg.get('caption'), 0.0
            caption_age += dt
            bottom = size[1] - int(size[1] * 0.035)
            if caption_text:
                bottom = draw_pill(frame, caption_text, size[0] / 2, bottom, caption_font, (17, 17, 27, 215),
                                   ease_out(caption_age / TEXT_FADE_S)) - int(size[1] * 0.014)
            if seg.get('tip') != tip_key:
                tip_key, tip_age = seg.get('tip'), 0.0
            tip_age += dt
            if tip_key:
                draw_tip(frame, tip_key, tip_fonts, ease_out((tip_age - 0.4) / 0.35))
            if seg.get('badge') is not None:
                fade = min(ease_out(k * dt / 0.15), ease_out((frames - k) * dt / 0.15))
                draw_pill(frame, f"Typed  {seg['badge']}", size[0] / 2, bottom, badge_font, (124, 58, 237, 235), fade)

            rgb = frame.convert('RGB')
            ffmpeg.stdin.write(rgb.tobytes())
            if preview and n % sample_every == 0:
                samples.append(rgb.resize((size[0] // 4, size[1] // 4)))
            n += 1
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        sys.exit('ffmpeg failed')

    if preview and samples:
        write_sheet(samples, None, str(out) + '.preview.png')
    print(f'{out}  {n / fps:.1f}s  {n} frames @ {fps}fps  {size[0]}x{size[1]}  (scene supersampled {ss:.2f}x)')


def write_sheet(images, labels, path, cols=4):
    sw, sh = images[0].size
    label_h = int(sh * 0.16) if labels else 0
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new('RGB', (sw * cols, (sh + label_h) * rows), (255, 255, 255))
    font = load_font(max(12, int(label_h * 0.55))) if labels else None
    d = ImageDraw.Draw(sheet)
    for idx, img in enumerate(images):
        x, y = (idx % cols) * sw, (idx // cols) * (sh + label_h)
        sheet.paste(img, (x, y))
        if labels:
            d.text((x + 10, y + sh + label_h * 0.18), labels[idx], font=font, fill=(24, 24, 27))
    sheet.save(path)


def background_sheet(path):
    size = (480, 270)
    tiles, names, missing = [], [], []
    keys = [k for k in RECORDLY_WALLPAPERS if (RECORDLY_CACHE / f'{k}.jpg').exists()] + list(BACKGROUNDS) + [
        k for k in MACOS_BACKGROUNDS
                                if (WALLPAPER_CACHE / f'{k}.jpg').exists() or find_macos_source(MACOS_BACKGROUNDS[k][1])]
    missing = [MACOS_BACKGROUNDS[k][0] for k in MACOS_BACKGROUNDS if k not in keys]
    for name in keys:
        bg = make_background(name, size, Path('.'))
        d = ImageDraw.Draw(bg)
        d.rounded_rectangle((52, 38, 428, 232), 8, fill=(250, 250, 250))
        d.rectangle((52, 38, 428, 56), fill=(15, 23, 42))
        tiles.append(bg)
        names.append(name + (' (default)' if name == DEFAULT_BACKGROUND else ''))
    write_sheet(tiles, names, path, cols=6)
    print(path)
    if not (RECORDLY_CACHE / f'{RECORDLY_WALLPAPERS[0]}.jpg').exists():
        print('Recordly wallpapers not downloaded (render_demo.py --fetch-recordly, after asking the user)')
    if missing:
        print('Not on this Mac yet (select once in System Settings > Wallpaper to download): ' + ', '.join(missing))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('storyboard', nargs='?')
    parser.add_argument('--preview', action='store_true', help='also write a contact sheet next to the output')
    parser.add_argument('--backgrounds', metavar='PNG', help='write a swatch sheet of the background presets')
    parser.add_argument('--fetch-recordly', action='store_true',
                        help="download Recordly's default wallpapers (~12 MB) into ~/.cache/demo-video/recordly")
    args = parser.parse_args()
    if args.fetch_recordly:
        fetch_recordly()
    elif args.backgrounds:
        background_sheet(args.backgrounds)
    elif args.storyboard:
        render(args.storyboard, args.preview)
    else:
        parser.error('give a storyboard or --backgrounds')
