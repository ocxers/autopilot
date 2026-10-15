# Dump the output-time timeline (captions, chapter pills, fast-forward) of a cut, same mapping as build.py
import json, sys
import build

def run_timeline(spec, offset):
    d, frames, events = build.load_run(spec)
    start, end, ivs = build.intervals(events)
    def out_of(t):
        o = 0.0
        for a, b, sp in ivs:
            if t <= a: return o
            if sp is None:
                if t < b: return o
                continue
            if t < b: return o + (t - a) / sp
            o += (b - a) / sp
        return o
    total = out_of(end + 1)
    caps, chaps, ffs, tips = [], [], [], []
    for e in events:
        if e['type'] == 'tip': tips.append([offset + out_of(e['t']), e.get('tip')])
        if e['type'] == 'caption': caps.append([offset + out_of(e['t']), e['text'], e.get('pos', 'bottom')])
        if e['type'] == 'chapter':
            chaps.append([offset + out_of(e['t']), e['name']]); caps.append([offset + out_of(e['t']), None, 'bottom'])
    o = 0
    for a, b, sp in ivs:
        if sp is None: continue
        if sp > 1: ffs.append([round(offset + o, 2), round(offset + o + (b - a) / sp, 2), sp])
        o += (b - a) / sp
    caps.sort(key=lambda c: c[0])
    return total, caps, chaps, ffs, tips

off = 0
allc, allch, allff, allt = [], [], [], []
for spec in open(sys.argv[1]).read().split():
    total, c, ch, ff, tp = run_timeline(spec, off)
    allc += c; allch += ch; allff += ff; allt += tp; off += total
allt.sort(key=lambda x: x[0])
tips = [{'from': round(t, 2), 'to': round(allt[i + 1][0] if i + 1 < len(allt) else off, 2), **card}
        for i, (t, card) in enumerate(allt) if card]
out = []
for i, (t, text, pos) in enumerate(allc):
    nxt = allc[i + 1][0] if i + 1 < len(allc) else off
    if text and nxt - t > 0.05: out.append({'from': round(t, 2), 'to': round(nxt, 2), 'text': text, 'pos': pos})
json.dump({'duration': round(off, 2), 'captions': out, 'chapters': [{'at': round(t, 2), 'name': n} for t, n in allch],
           'fast_forward': [{'from': a, 'to': b, 'speed': s} for a, b, s in allff], 'tips': tips}, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print('duration', round(off, 1), 'captions', len(out), 'ff', len(allff))
short = [c for c in out if c['to'] - c['from'] < 2.0]
print('captions shorter than 2s:', [(c['from'], round(c['to'] - c['from'], 2), c['text'][:20]) for c in short])
