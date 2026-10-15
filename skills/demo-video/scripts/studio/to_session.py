#!/usr/bin/env python3
"""The recorded runs as one session in output time, for render.py (camera=studio, frame=wallpaper).

    EDITS=edits-<name>.json python3 to_session.py runs-<name>.txt <session dir> [--url URL]

Reads each run's frames.jsonl / frames/ / events.jsonl / actions.json (lib.mjs) and maps every time
through the same fast-forward and cut intervals as build.py, so the camera follows the cut:
  <session>/frames/%06d.jpg   the frames (redacted where the run tracked redactions; others are symlinks)
  <session>/timeline.json     frames, viewport, points, clicks, focuses, steps, scrolls, duration
Captions, chapters, tips and the fast-forward badge come from post.sh's timeline-<name>.json at render time.
"""
import bisect
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'post')]
import build  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
runs_file, out = args[0], Path(args[1])
url = opt('--url', '')
if out.exists():
    shutil.rmtree(out)
(out / 'frames').mkdir(parents=True)

frames_out, acts = [], {'points': [], 'clicks': [], 'focuses': [], 'steps': [], 'scrolls': [], 'cursors': []}
viewport = None
offset = 0.0
n = 0
for spec in Path(runs_file).read_text().split():
    d, frames, events = build.load_run(spec)
    start, end, ivs = build.intervals(events)

    def out_of(t, ivs=ivs, offset=offset):
        """Output time of source epoch t, or None inside a cut."""
        o = 0.0
        for a, b, sp in ivs:
            if t < a:
                return offset + o
            if sp is None:
                if t < b:
                    return None
                continue
            if t < b:
                return offset + o + (t - a) / sp
            o += (b - a) / sp
        return offset + o

    total = 0.0
    for a, b, sp in ivs:
        if sp is not None:
            total += (b - a) / sp
    redacts = [(e['t'], e.get('rects', [])) for e in events if e['type'] == 'redact']
    rts = [r[0] for r in redacts]
    for f in frames:
        if not (start <= f['ts'] <= end):
            continue
        t = out_of(f['ts'])
        if t is None or (frames_out and t <= frames_out[-1]['t']):
            continue
        src = d / f['file']
        dst = out / 'frames' / f'{n:06d}.jpg'
        i = bisect.bisect_right(rts, f['ts']) - 1
        rects = redacts[i][1] if i >= 0 else []
        if rects:
            dst.write_bytes(build.redact(src.read_bytes(), rects))
        else:
            dst.symlink_to(src.resolve())
        frames_out.append({'t': round(t, 4), 'file': f'frames/{n:06d}.jpg'})
        n += 1
    a_path = d / 'actions.json'
    if a_path.exists():
        raw = json.loads(a_path.read_text())
        viewport = viewport or raw.get('viewport')

        def m(obj, keys):
            o = dict(obj)
            for k in keys:
                if o.get(k) is not None:
                    v = out_of(o[k])
                    if v is None:
                        return None
                    o[k] = round(v, 4)
            return o
        acts['points'] += [p for p in (m(x, ['t']) for x in raw['points']) if p]
        acts['clicks'] += [c for c in (m(x, ['t', 'up']) for x in raw['clicks']) if c]
        for f in raw['focuses']:
            g = m(f, ['t', 'readyAt', 'end', 'interactionEnd', 'typingStart', 'approachStart'])
            if not g:
                continue
            if g.get('result'):
                r = m(g['result'], ['t'])
                g['result'] = r if r else None
                if not r:
                    g.pop('result')
            acts['focuses'].append(g)
        acts['steps'] += [s for s in (m(x, ['start', 'actionStart', 'interactionEnd', 'expectationEnd', 'end']) for x in raw['steps']) if s]
        acts['scrolls'] += [s for s in (m(x, ['start', 'end']) for x in raw['scrolls']) if s]
        acts['cursors'] += [c for c in (m(x, ['t']) for x in raw.get('cursors', [])) if c]
    offset += total

duration = round(offset, 4)
timeline = {
    'version': 1,
    'viewport': viewport or {'width': 1600, 'height': 900},
    'frames': frames_out,
    **{k: sorted(v, key=lambda x: x.get('t', x.get('start', 0))) for k, v in acts.items()},
    'keys': [],
    'duration': duration,
    'status': 'complete',
    'capture': {'scale': 2, 'format': 'jpg'},
    'url': url,
}
if not timeline['points']:
    timeline['points'] = [{'t': 0, 'x': 800, 'y': 450}]
(out / 'timeline.json').write_text(json.dumps(timeline, indent=1))

print(json.dumps({'frames': len(frames_out), 'duration': duration, 'clicks': len(acts['clicks']),
                  'focuses': len(acts['focuses']), 'session': str(out)}))
