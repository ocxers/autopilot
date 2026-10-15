#!/bin/bash
# bash post.sh <name> <out.mp4 | --check> [key=value …]
#   lang=en|zh  voice=female|male|off  music=on|off  captions=on|off  offset=<s>  lufs=<-42>  preview=1
#   camera=static|studio  frame=none|wallpaper  background=<wallpaper name|image|#hex>  url=<address bar text>
# From runs-<name>.txt (one run spec per line: runs/<dir>[@start=…,end=…,hold=…]) and
# edits-<name>.json (caption replace / drop / shift / cuts), in this directory:
#   1. timeline-<name>.json, and every caption too fast to be read aloud
#      (en: > 2.6 words/s, zh: > 5 characters/s)
#   2. the cut: captions (unless captions=off), tips, fast-forward badge in the language, chapter pills, redactions;
#      camera=static frame=none is the plain recording (build.py); anything else goes through
#      to_session.py + render.py (push-ins with camera=studio, the browser window on a wallpaper with frame=wallpaper)
#   3. audio.sh: the music bed and the Kokoro voice-over (English only) → <out.mp4>
# Defaults: lang=en voice=female music=on captions=on offset=60 lufs=-42 camera=static frame=none;
# for lang=zh voice=off. --check stops after 1. Fix fast captions in edits-<name>.json until the list is empty.
set -e
cd "$(dirname "$0")"
N=$1; OUT=$2
[ -n "$N" ] && [ -n "$OUT" ] || { echo "usage: bash post.sh <name> <out.mp4|--check> [lang= voice= music= captions= offset= lufs=]"; exit 1; }
shift 2
LANGV=en; VOICE=; MUSIC=on; CAPS=on; OFF=60; LUFS=-42; PREVIEW=; CAMERA=static; FRAME=none; BG=; URL=
for a in "$@"; do
  case "$a" in
    lang=*) LANGV=${a#*=} ;; voice=*) VOICE=${a#*=} ;; music=*) MUSIC=${a#*=} ;;
    captions=*) CAPS=${a#*=} ;; offset=*) OFF=${a#*=} ;; lufs=*) LUFS=${a#*=} ;; preview=*) PREVIEW=${a#*=} ;;
    camera=*) CAMERA=${a#*=} ;; frame=*) FRAME=${a#*=} ;; background=*) BG=${a#*=} ;; url=*) URL=${a#*=} ;;
    [0-9]*) OFF=$a ;;
    *) echo "unknown parameter: $a"; exit 1 ;;
  esac
done
[ -n "$VOICE" ] || { [ "$LANGV" = zh ] && VOICE=off || VOICE=female; }
if [ "$LANGV" = zh ] && [ "$VOICE" != off ]; then
  echo "The voice-over is English only for now: use voice=off with lang=zh."; exit 1
fi

[ -f "edits-$N.json" ] || echo '{"replace": {}, "cuts": {}}' > "edits-$N.json"
EDITS="edits-$N.json" python3 timeline.py "runs-$N.txt" "timeline-$N.json" | head -2
python3 - "$N" "$LANGV" <<'PY'
import json, sys
d = json.load(open(f'timeline-{sys.argv[1]}.json'))
zh = sys.argv[2] == 'zh'
for c in d['captions']:
    dur = c['to'] - c['from']
    n = len(c['text'].replace(' ', '')) if zh else len(c['text'].split())
    if n / dur > (5 if zh else 2.6):
        print(f'FAST {c["from"]:.1f}s {dur:.1f}s {n} {"chars" if zh else "words"}: {c["text"]}')
PY
[ "$OUT" = "--check" ] && exit 0

TMP=${TMPDIR:-/tmp}/demo-video-post; mkdir -p "$TMP"
BADGE_TEXT='Fast-forward ×{n}'; [ "$LANGV" = zh ] && BADGE_TEXT='快进 ×{n}'
export BADGE=${BADGE:-$BADGE_TEXT} CAPTIONS=$CAPS EDITS="edits-$N.json"
if [ "$CAMERA" = static ] && [ "$FRAME" = none ]; then
  python3 build.py "$TMP/$N-base.mp4" $(cat "runs-$N.txt") ${PREVIEW:+--preview} > "build-$N.log" 2>&1 || { tail -5 "build-$N.log"; exit 1; }
else
  python3 to_session.py "runs-$N.txt" "$TMP/$N-session" > "build-$N.log" 2>&1 || { tail -5 "build-$N.log"; exit 1; }
  python3 render.py "$TMP/$N-session" "$TMP/$N-base.mp4" --timeline "timeline-$N.json" --camera "$CAMERA" --frame "$FRAME" \
    ${BG:+--background "$BG"} ${URL:+--url "$URL"} ${PREVIEW:+--preview} >> "build-$N.log" 2>&1 || { tail -5 "build-$N.log"; exit 1; }
fi
tail -1 "build-$N.log"

bash audio.sh "$TMP/$N-base.mp4" "timeline-$N.json" "$OUT" voice=$VOICE music=$MUSIC offset=$OFF lufs=$LUFS lang=$LANGV
