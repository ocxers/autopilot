#!/usr/bin/env python3
"""Voice-over for an English demo: local Kokoro-82M (Apache-2.0, voice af_heart) reads the
captions, timed to the cut, over a quiet music bed that ducks while she speaks.

    python3 voiceover.py timeline.json video.mp4 music.wav out.mp4 [--dry-run] [--voice-only]

The Kokoro engine lives in $DEMO_TTS_DIR (default: this skill's tts/; `npm install` runs there on
first use). Clips are cached in ~/.cache/demo-video/tts.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path(os.environ.get('DEMO_TTS_CACHE', Path.home() / '.cache/demo-video/tts'))
# The skill's tts/ when run from the skill. Copies in a work dir use the skill that setup.sh last ran from
# (it writes ~/.cache/demo-video/skill-dir; plugin installs live outside ~/.claude/skills), else the usual path.


def _engine():
    here_tts = Path(__file__).resolve().parent.parent.parent / 'tts'
    if (here_tts / 'gen.mjs').exists():
        return here_tts
    pointer = Path.home() / '.cache/demo-video/skill-dir'
    if pointer.exists() and (Path(pointer.read_text().strip()) / 'tts/gen.mjs').exists():
        return Path(pointer.read_text().strip()) / 'tts'
    return Path.home() / '.claude/skills/demo-video/tts'


ENGINE = Path(os.environ.get('DEMO_TTS_DIR') or _engine())
SPEECH_FIXES = [
    ('→', ', then'), (' / ', ' or '), ('Cmd + K', 'Command K'), ('package.json', 'package dot json'),
    ('npm', 'N P M'), ('MCP', 'M C P'), ('2FA', 'two-factor'), ('PRD', 'P R D'),
]
# App-specific spoken forms: speech-fixes.json next to this script (a profile copies its own), [[from, to], …].
_EXTRA = HERE / 'speech-fixes.json'
if _EXTRA.exists():
    SPEECH_FIXES = [tuple(x) for x in json.loads(_EXTRA.read_text())] + SPEECH_FIXES


def speech_text(t):
    for a, b in SPEECH_FIXES:
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


def duration(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def kokoro_batch(texts):
    """Local Kokoro-82M (Apache-2.0) voice af_heart; returns {text: wav path}."""
    CACHE.mkdir(exist_ok=True)
    voice = os.environ.get('KVOICE', 'af_heart')
    jobs, paths = [], {}
    for t in texts:
        key = hashlib.sha1(f'kokoro|{voice}|{t}'.encode()).hexdigest()[:16]
        out = CACHE / f'k-{key}.wav'
        paths[t] = out
        jobs.append({'text': t, 'out': str(out)})
    jf = CACHE / 'jobs.json'
    jf.write_text(json.dumps(jobs))
    if not (ENGINE / 'node_modules' / 'kokoro-js').exists():
        subprocess.run(['npm', 'install', '--silent'], cwd=ENGINE, check=True)
    subprocess.run(['node', str(ENGINE / 'gen.mjs'), str(jf)], cwd=ENGINE, check=True,
                   env={**os.environ, 'VOICE': voice})
    return paths


def plan(timeline):
    caps = timeline['captions']
    chapters = sorted(c['at'] for c in timeline['chapters'])
    chap_of = lambda t: sum(1 for a in chapters if a <= t + 0.01)
    lines, said = [], {}
    for i, c in enumerate(caps):
        ch = chap_of(c['from'])
        if said.get(c['text']) == ch:
            continue  # the same caption again in the same chapter: say it once
        said[c['text']] = ch
        nxt = caps[i + 1]['from'] if i + 1 < len(caps) else timeline['duration']
        lines.append({'start': c['from'], 'slot_end': max(c['to'], nxt), 'caption': c['text'], 'say': speech_text(c['text'])})
    return lines


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    timeline = json.loads(Path(args[0]).read_text())
    video, music, out = args[1], args[2], args[3]
    lines = plan(timeline)
    prev_end = 0.0
    kpaths = {} if dry else kokoro_batch([l['say'] for l in lines])
    for ln in lines:
        p = None if dry else kpaths[ln['say']]
        d = len(ln['say'].split()) / 2.9 + 0.2 if dry else duration(p)
        t = max(ln['start'], prev_end + 0.15)
        room = ln['slot_end'] + 0.6 - t
        tempo = 1.0
        if d > room:
            tempo = min(1.15, d / max(room, 0.5))
        ln.update(path=str(p) if p else None, at=round(t, 3), dur=d, tempo=round(tempo, 3), end=t + d / tempo)
        prev_end = ln['end']
    drift = [(round(l['at'] - l['start'], 2), l['caption'][:50]) for l in lines if l['at'] - l['start'] > 0.4]
    print(f'{len(lines)} lines; speech {sum(l["dur"] / l["tempo"] for l in lines):.0f}s; '
          f'sped up {sum(1 for l in lines if l["tempo"] > 1)}; late >0.4s: {len(drift)}')
    for x in drift[:20]:
        print('  late', x)
    Path(out + '.plan.json').write_text(json.dumps(lines, indent=1))
    if dry:
        return
    # voice track: each clip normalised, sped up when needed, placed at its time
    tmp = Path(os.environ.get('TMPDIR', '/tmp')) / 'demo-video-vo'
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(exist_ok=True)
    inputs, filters = [], []
    for i, ln in enumerate(lines):
        clip = tmp / f'c{i:03d}.wav'
        af = f'loudnorm=I=-17:TP=-2:LRA=7,aresample=48000' + (f',atempo={ln["tempo"]}' if ln['tempo'] > 1 else '')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', ln['path'], '-af', af, '-ac', '1', str(clip)], check=True)
        inputs += ['-i', str(clip)]
        ms = int(ln['at'] * 1000)
        filters.append(f'[{i}:a]adelay=delays={ms}:all=1[v{i}]')
    mix = ''.join(f'[v{i}]' for i in range(len(lines)))
    filters.append(f'{mix}amix=inputs={len(lines)}:normalize=0:dropout_transition=0,aformat=channel_layouts=stereo,apad=whole_dur={timeline["duration"]}[voice]')
    voice = tmp / 'voice.wav'
    (tmp / 'graph.txt').write_text(';'.join(filters))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filters),
                    '-map', '[voice]', '-t', str(timeline['duration']), str(voice)], check=True)
    if '--voice-only' in sys.argv:
        print('voice track', voice)
        return
    # final mix: quiet music under the voice, ducked a little more while she speaks
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', str(voice), '-i', music, '-filter_complex',
                    '[2:a]aformat=channel_layouts=stereo[m];[1:a]asplit=2[vo][sc];'
                    '[m][sc]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=400[duck];'
                    '[vo][duck]amix=inputs=2:normalize=0,alimiter=limit=0.9[a]',
                    '-map', '0:v:0', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)


if __name__ == '__main__':
    main()
