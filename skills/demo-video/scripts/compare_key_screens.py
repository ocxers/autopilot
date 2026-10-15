#!/usr/bin/env python3
"""Put the key screens of a "before the fix" and an "after the fix" recording side by side, one PNG per pair.

    python3 compare_key_screens.py compare.json

compare.json: {"before": "before.mp4", "after": "after.mp4", "output": "../ABC-123-before-after.png",
               "pairs": [{"before": 12.3, "after": 11.8, "caption": "After Renew: the start date"}]}
`before` / `after` in a pair are times (s) in each video at the same step of the flow. Paths are relative to the
json. `output` names the set without a version; each run writes "<stem>-vN-<i>.png" for the next free N and never
overwrites an earlier set.
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_demo import draw_pill, load_font  # noqa: E402

FRAME_W = 1280
GAP = 48
BG = (241, 242, 246, 255)
LABELS = (('Before the fix', (190, 48, 48, 235)), ('After the fix', (30, 132, 73, 235)))

cfg_path = Path(sys.argv[1]).resolve()
cfg = json.loads(cfg_path.read_text())
base = cfg_path.parent
videos = [base / cfg['before'], base / cfg['after']]
named = (base / cfg['output']).resolve()
named.parent.mkdir(parents=True, exist_ok=True)
stem = re.sub(r'-v\d+$', '', named.stem)
taken = [int(m.group(1)) for f in named.parent.glob(f'{stem}-v*-*.png') if (m := re.fullmatch(rf'{re.escape(stem)}-v(\d+)-\d+', f.stem))]
version = max(taken, default=0) + 1


def frame_at(video, t):
    png = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(video), '-frames:v', '1', '-f', 'image2pipe',
                          '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    if not png:
        sys.exit(f'No frame at {t} s in {video}')
    img = Image.open(io.BytesIO(png)).convert('RGBA')
    return img.resize((FRAME_W, round(img.height * FRAME_W / img.width)), Image.LANCZOS)


label_font, caption_font = load_font(34), load_font(30)
for i, pair in enumerate(cfg['pairs'], 1):
    frames = [frame_at(videos[0], pair['before']), frame_at(videos[1], pair['after'])]
    fh = max(f.height for f in frames)
    top, bottom = 110, 110 if pair.get('caption') else GAP
    canvas = Image.new('RGBA', (FRAME_W * 2 + GAP * 3, top + fh + bottom), BG)
    for col, (frame, (label, color)) in enumerate(zip(frames, LABELS)):
        x = GAP + col * (FRAME_W + GAP)
        draw_pill(canvas, label, x + FRAME_W / 2, top - 22, label_font, color)
        ImageDraw.Draw(canvas).rounded_rectangle((x - 2, top - 2, x + FRAME_W + 1, top + frame.height + 1), 10, outline=(200, 202, 210, 255), width=2)
        canvas.alpha_composite(frame, (x, top))
    if pair.get('caption'):
        draw_pill(canvas, pair['caption'], canvas.width / 2, canvas.height - 28, caption_font, (17, 17, 27, 215))
    out = named.with_name(f'{stem}-v{version}-{i}.png')
    canvas.convert('RGB').save(out, optimize=True)
    print(out)
