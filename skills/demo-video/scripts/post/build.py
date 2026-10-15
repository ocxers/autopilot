#!/usr/bin/env python3
"""Edit recorded runs into one MP4: plain screen recording (no wallpaper, no camera), captions,
fast-forward segments with a badge, cuts, chapter pills.

    python3 build.py OUT.mp4 RUN_DIR [RUN_DIR ...] [--preview] [--from S --to S]

Each RUN_DIR has frames.jsonl / frames/*.jpg / events.jsonl written by lib.mjs.
"""
import bisect
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
def _font_path():
    import glob
    for p in [os.environ.get('CAPTION_FONT'), str(HERE / 'PingFang.ttc'),
              *glob.glob('/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc'),
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
              'C:/Windows/Fonts/msyh.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if p and Path(p).exists():
            return p
    raise SystemExit('No caption font found: set CAPTION_FONT to a .ttf/.ttc (with CJK glyphs for zh)')


FONT = _font_path()
MONO = next((p for p in ('/System/Library/Fonts/Menlo.ttc', '/System/Library/Fonts/Monaco.ttf',
                         '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 'C:/Windows/Fonts/consola.ttf') if Path(p).exists()), None)
TMP = Path(os.environ.get('TMPDIR', '/tmp')) / 'demo-video-post'
FPS = 30
W, H = 3200, 1800
CHAPTER_S = 3.2


def font(size, weight='medium'):
    # PingFang.ttc holds the weights by index; any other font is used as it is.
    idx = {'regular': 3, 'medium': 7, 'semibold': 11}[weight] if 'PingFang' in FONT else 0
    return ImageFont.truetype(FONT, size, index=idx)


def mono(size):
    return ImageFont.truetype(MONO, size) if MONO else font(size, 'regular')


def draw_tip(img, tip):
    """Tip card in the top-right corner: clearly the video's note, not part of the app's UI."""
    d = ImageDraw.Draw(img)
    pad, gap, max_w = 40, 22, int(W * 0.34)
    lines = [(tip.get('title') or 'Note', font(58, 'semibold'), (255, 255, 255))]
    lines += [(t, font(50, 'regular'), (226, 232, 240)) for t in tip.get('lines', [])]
    lines += [(t, mono(44), (186, 230, 253)) for t in tip.get('code', [])]
    wrapped = []
    for text, f, color in lines:
        for line in wrap(d, text, f, max_w - 2 * pad - 12):
            wrapped.append((line, f, color))
    heights = [d.textbbox((0, 0), t or ' ', font=f)[3] for t, f, _ in wrapped]
    card_h = pad * 2 + sum(heights) + gap * (len(wrapped) - 1) + 10
    x0, y0 = W - max_w - 64, 54
    d.rounded_rectangle((x0, y0, x0 + max_w, y0 + card_h), 28, fill=(15, 23, 42, 228), outline=(56, 189, 248, 200), width=3)
    d.rectangle((x0, y0 + 28, x0 + 8, y0 + card_h - 28), fill=(56, 189, 248, 255))
    y = y0 + pad
    for (text, f, color), lh in zip(wrapped, heights):
        d.text((x0 + pad + 12, y), text, font=f, fill=color + (255,))
        y += lh + gap


def load_run(spec):
    d, _, opt = str(spec).partition('@')
    d = Path(d).resolve()
    frames = [json.loads(l) for l in (d / 'frames.jsonl').read_text().splitlines() if l.strip()]
    events = [json.loads(l) for l in (d / 'events.jsonl').read_text().splitlines() if l.strip()]
    # "@end=<epoch>": cut the run there (a failed tail); "@start=<epoch>": begin there;
    # "hold=<s>": freeze the last frame that long after the end
    opts = dict(part.split('=') for part in filter(None, opt.split(',')))
    if 'end' in opts:
        end = float(opts['end'])
        frames = [f for f in frames if f['ts'] <= end]
        events = [e for e in events if e['t'] < end and e['type'] != 'end'] + [{'t': end + float(opts.get('hold', 0)), 'type': 'end'}]
    if 'start' in opts:
        start = float(opts['start'])
        events = [{'t': start, 'type': 'start'}] + [e for e in events if e['type'] != 'start' and e['t'] >= start]
    events = apply_edits(d.name, events)
    return d, frames, events


_EP = HERE / os.environ.get('EDITS', 'edits.json')
EDITS = json.loads(_EP.read_text()) if _EP.exists() else {}


def apply_edits(run, events):
    out = []
    for e in events:
        e = dict(e)
        for key in ('text', 'name'):
            if e.get(key):
                for a, b in EDITS.get('replace', {}).items():
                    e[key] = e[key].replace(a, b)
        if e['type'] == 'caption' and e.get('text'):
            if any(x in e['text'] for x in EDITS.get('pos_top', [])):
                e['pos'] = 'top'
            for x, dt in EDITS.get('shift', {}).items():
                if x in e['text']:
                    e['t'] += dt
            if any(x in e['text'] for x in EDITS.get('drop', [])):
                continue
            if any(abs(e['t'] - x) < 0.01 for x in EDITS.get('drop_t', [])):
                continue
        out.append(e)
    for a, b in EDITS.get('cuts', {}).get(run, []):
        out += [{'t': a, 'type': 'cut', 'on': True}, {'t': b, 'type': 'cut', 'on': False}]
    lo = min((e['t'] for e in out if e['type'] == 'start'), default=0)
    hi = max((e['t'] for e in out if e['type'] == 'end'), default=1e12)
    for add in EDITS.get('add', []):
        if add['run'] == run and lo <= add['t'] <= hi:
            out.append({k: v for k, v in add.items() if k != 'run'})
    return sorted(out, key=lambda e: (e['t'], e['type'] != 'start'))


def intervals(events):
    """[(src_a, src_b, speed or None for cut)] covering start..end."""
    start = next(e['t'] for e in events if e['type'] == 'start')
    end = next(e['t'] for e in reversed(events) if e['type'] == 'end')
    out = []
    cur_t, speed, cut = start, 1.0, False
    for e in events:
        if e['type'] not in ('ff', 'cut') or e['t'] < start:
            continue
        t = min(e['t'], end)
        if t > cur_t:
            out.append((cur_t, t, None if cut else ff_speed(speed, t - cur_t)))
            cur_t = t
        if e['type'] == 'ff':
            speed = float(e.get('speed', 20)) if e['on'] else 1.0
        else:
            cut = e['on']
    if end > cur_t:
        out.append((cur_t, end, None if cut else ff_speed(speed, end - cur_t)))
    return start, end, out


def ff_speed(speed, src_dur, min_out=1.6):
    """A fast-forward lasts at least `min_out` s on screen (badge readable); very short waits play at 1x."""
    if speed <= 1:
        return speed
    if src_dur < 4:
        return 1.0
    return float(max(2, min(speed, int(src_dur / min_out))))


def wrap(draw, text, f, max_w):
    lines, cur = [], ''
    for ch in text:
        if draw.textlength(cur + ch, font=f) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


_cache = {}


def overlay_png(state, tmp):
    """Transparent full-frame PNG for (caption, pos, badge, chapter[, tip])."""
    key = hashlib.md5(json.dumps([state, os.environ.get('CAP_ALPHA'), os.environ.get('CAP_STROKE'), os.environ.get('CAPTIONS')], ensure_ascii=False).encode()).hexdigest()[:16]
    if key in _cache:
        return _cache[key]
    path = tmp / f'ov_{key}.png'
    if not path.exists():
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        cap, pos, badge, chapter = state[:4]
        tip = state[4] if len(state) > 4 else None
        if os.environ.get('CAPTIONS', 'on') == 'off':
            cap = None
        if cap:
            f = font(54)
            lines = wrap(dr, cap, f, 2500)
            lh = 80
            tw = max(dr.textlength(l, font=f) for l in lines)
            bw, bh = int(tw + 96), int(lh * len(lines) + 52)
            x0 = (W - bw) // 2
            y0 = 64 if pos == 'top' else H - 72 - bh
            dr.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=26, fill=(17, 24, 39, int(os.environ.get('CAP_ALPHA', 150))))
            for i, l in enumerate(lines):
                lw = dr.textlength(l, font=f)
                dr.text(((W - lw) / 2, y0 + 26 + i * lh + 2), l, font=f, fill=(255, 255, 255, 255),
                        stroke_width=int(os.environ.get('CAP_STROKE', 3)), stroke_fill=(17, 24, 39, 200))
        if badge:
            f = font(42, 'semibold')
            tw = dr.textlength(badge, font=f)
            bw, bh = int(tw + 64), 76
            x0, y0 = W - bw - 40, 40 if not (cap and pos == 'top') else 40
            if cap and pos == 'top':
                y0 = H - 40 - bh
            dr.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=38, fill=(220, 38, 38, 225))
            dr.text((x0 + 32, y0 + 13), badge, font=f, fill=(255, 255, 255, 255))
        if chapter:
            f = font(48, 'semibold')
            tw = dr.textlength(chapter, font=f)
            bw, bh = int(tw + 88), 92
            x0 = (W - bw) // 2
            y0 = 36 if not (cap and pos == 'top') else 220
            dr.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=46, fill=(79, 70, 229, 235))
            dr.text((x0 + 44, y0 + 18), chapter, font=f, fill=(255, 255, 255, 255))
        if tip:
            draw_tip(img, json.loads(tip) if isinstance(tip, str) else tip)
        img.save(path)
    _cache[key] = path
    return path


def redact(jpeg, rects, pad=6):
    """Pixelates the given CSS-px boxes (frames are at 2x)."""
    if not rects:
        return jpeg
    import io
    img = Image.open(io.BytesIO(jpeg)).convert('RGB')
    sx = img.width / 1600
    for x, y, w, h in rects:
        box = (max(0, int((x - pad) * sx)), max(0, int((y - pad) * sx)),
               min(img.width, int((x + w + pad) * sx)), min(img.height, int((y + h + pad) * sx)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        region = img.crop(box)
        small = region.resize((max(1, region.width // 18), max(1, region.height // 18)), Image.BILINEAR)
        img.paste(small.resize(region.size, Image.NEAREST), box)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def build(out, run_dirs, preview=False, t_from=None, t_to=None):
    tmp = TMP / 'build-tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    frame_list = []  # (path, nframes)
    ov_list = []
    total = 0
    report = []
    for d in run_dirs:
        d, frames, events = load_run(d)
        start, end, ivs = intervals(events)
        frames = [f for f in frames if f['ts'] <= end]
        fts = [f['ts'] for f in frames]
        # output-time layout of the intervals
        layout = []
        ot = 0.0
        for a, b, sp in ivs:
            if sp is None:
                continue
            dur = (b - a) / sp
            layout.append((ot, ot + dur, a, sp))
            ot += dur
        run_len = ot

        def src_at(tau):
            for o0, o1, a, sp in layout:
                if tau < o1:
                    return a + (tau - o0) * sp, sp
            o0, o1, a, sp = layout[-1]
            return a + (o1 - o0) * sp, sp

        def out_of(t):
            o = 0.0
            for a, b, sp in ivs:
                if t <= a:
                    return o
                if sp is None:
                    if t < b:
                        return o
                    continue
                if t < b:
                    return o + (t - a) / sp
                o += (b - a) / sp
            return o

        # caption / chapter timeline in output time
        caps = []  # (out_t, text, pos)
        chaps = []
        for e in events:
            if e['type'] == 'caption':
                caps.append((out_of(e['t']), e['text'], e.get('pos', 'bottom')))
            elif e['type'] == 'chapter':
                chaps.append((out_of(e['t']), e['name']))
                caps.append((out_of(e['t']), None, 'bottom'))
        caps.sort(key=lambda c: c[0])
        cap_t = [c[0] for c in caps]
        tips = sorted((out_of(e['t']), json.dumps(e['tip'], ensure_ascii=False) if e.get('tip') else None)
                      for e in events if e['type'] == 'tip')
        tip_t = [t[0] for t in tips]
        reds = [(e['t'], e['rects']) for e in events if e['type'] == 'redact']
        red_t = [r[0] for r in reds]

        def rects_at(src):
            i = bisect.bisect_right(red_t, src + 0.3) - 1
            return reds[i][1] if i >= 0 else []
        n = int(run_len * FPS)
        prev_idx, prev_state, run_f, run_o = None, None, 0, 0
        for k in range(n):
            tau = k / FPS
            src, sp = src_at(tau)
            idx = max(0, bisect.bisect_right(fts, src) - 1)
            rk = json.dumps([[round(v) for v in r] for r in rects_at(src)])
            ident = (idx, rk)
            ci = bisect.bisect_right(cap_t, tau) - 1
            cap = caps[ci] if ci >= 0 else (0, None, 'bottom')
            chap = next((c[1] for c in reversed(chaps) if c[0] <= tau < c[0] + CHAPTER_S), None)
            badge = os.environ.get('BADGE', 'Fast-forward ×{n}').format(n=int(sp)) if sp > 1 else None
            ti = bisect.bisect_right(tip_t, tau) - 1
            state = (cap[1], cap[2], badge, chap, tips[ti][1] if ti >= 0 else None)
            if ident == prev_idx:
                run_f += 1
            else:
                if prev_idx is not None:
                    frame_list.append((d / frames[prev_idx[0]]['file'], run_f, prev_idx[1]))
                prev_idx, run_f = ident, 1
            if state == prev_state:
                run_o += 1
            else:
                if prev_state is not None:
                    ov_list.append((overlay_png(prev_state, tmp), run_o))
                prev_state, run_o = state, 1
        frame_list.append((d / frames[prev_idx[0]]['file'], run_f, prev_idx[1]))
        ov_list.append((overlay_png(prev_state, tmp), run_o))
        report.append(f'{d.name}: src {end - start:.0f}s -> out {run_len:.1f}s')
        total += run_len
    print('\n'.join(report), f'\ntotal {total:.1f}s ({total / 60:.1f} min)')

    def write_concat(items, name):
        p = tmp / name
        with p.open('w') as fh:
            for path, nf in items:
                fh.write(f"file '{path}'\nduration {nf / FPS:.6f}\n")
            fh.write(f"file '{items[-1][0]}'\n")
        return p

    oc = write_concat(ov_list, 'overlay.txt')
    scale = ',scale=1600:900:flags=lanczos' if preview else ''
    dur = (t_to if t_to is not None else total) - (t_from or 0)
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning', '-stats',
           '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-']
    if t_from is not None:
        cmd += ['-ss', str(t_from)]
    cmd += ['-f', 'concat', '-safe', '0', '-i', str(oc),
            '-filter_complex',
            f'[1:v]fps={FPS},format=yuva420p[o];[0:v]format=yuv420p[v];[v][o]overlay=0:0:format=yuv420:eof_action=repeat{scale}[out]',
            '-map', '[out]', '-r', str(FPS), '-c:v', 'libx264',
            '-preset', 'veryfast' if preview else os.environ.get('PRESET', 'medium'),
            '-crf', '23' if preview else os.environ.get('CRF', '18'),
            '-movflags', '+faststart', '-t', f'{dur:.3f}', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    skip = int((t_from or 0) * FPS)
    budget = int(dur * FPS) + 2
    cache = {}
    n = 0
    try:
        for path, nf, rk in frame_list:
            if n >= skip + budget:
                break
            if n + nf <= skip:
                n += nf
                continue
            data = cache.get((path, rk))
            if data is None:
                data = redact(Path(path).read_bytes(), json.loads(rk))
                cache = {(path, rk): data}
            reps = min(nf, skip + budget - n) - max(0, skip - n)
            for _ in range(reps):
                proc.stdin.write(data)
            n += nf
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() != 0:
        raise SystemExit('ffmpeg failed')
    print('wrote', out)


if __name__ == '__main__':
    args = sys.argv[1:]
    preview = '--preview' in args
    t_from = t_to = None
    if '--from' in args:
        t_from = float(args[args.index('--from') + 1])
    if '--to' in args:
        t_to = float(args[args.index('--to') + 1])
    pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--from', '--to'))]
    build(pos[0], pos[1:], preview, t_from, t_to)
