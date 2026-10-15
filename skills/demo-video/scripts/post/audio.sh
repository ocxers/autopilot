#!/bin/bash
# bash audio.sh <video.mp4> <timeline.json> <out.mp4> [voice=female|male|off] [music=on|off] [offset=<s>] [lufs=<-42>] [lang=en|zh]
# Adds the sound to a finished cut (post.sh calls it after the picture is done):
#   music: the bed from chain.wav at the offset, faded, at <lufs> LUFS, ducked under the voice;
#   voice: Kokoro reads the timeline's captions at their times (female af_heart, male am_michael).
# The voice-over is English only for now; with lang=zh, voice must be off.
# Every music offset used is appended to music/offsets.log, so the next video can take another.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
VIDEO=$1; TL=$2; OUT=$3
[ -n "$VIDEO" ] && [ -n "$TL" ] && [ -n "$OUT" ] || { echo "usage: bash audio.sh <video> <timeline.json> <out> [voice= music= offset= lufs= lang=]"; exit 1; }
shift 3
VOICE=female; MUSIC=on; OFF=60; LUFS=-42; LANGV=en
for a in "$@"; do
  case "$a" in
    voice=*) VOICE=${a#*=} ;; music=*) MUSIC=${a#*=} ;; offset=*) OFF=${a#*=} ;; lufs=*) LUFS=${a#*=} ;; lang=*) LANGV=${a#*=} ;;
    *) echo "unknown parameter: $a"; exit 1 ;;
  esac
done
if [ "$LANGV" = zh ] && [ "$VOICE" != off ]; then
  echo "The voice-over is English only for now: use voice=off with lang=zh."; exit 1
fi
case "$VOICE" in female) KV=af_heart ;; male) KV=am_michael ;; off) KV= ;; *) echo "voice=$VOICE?"; exit 1 ;; esac
TMP=${TMPDIR:-/tmp}/demo-video-post; mkdir -p "$TMP"
B=$(basename "$OUT" .mp4)
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
MUSICWAV="$TMP/$B-music.wav"
if [ "$MUSIC" = on ]; then
  MDIR=${DEMO_MUSIC_DIR:-$HOME/.cache/demo-video/music}
  [ -s "$MDIR/chain.wav" ] || bash "$HERE/music.sh"
  ffmpeg -v error -y -ss "$OFF" -i "$MDIR/chain.wav" -af "atrim=0:$D,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=2,afade=t=out:st=$(python3 -c "print(max(0,$D-3))"):d=3" "$TMP/$B-trim.wav"
  I=$(ffmpeg -hide_banner -i "$TMP/$B-trim.wav" -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | tail -1 | awk '{print $2}')
  ffmpeg -v error -y -i "$TMP/$B-trim.wav" -af "volume=$(python3 -c "print(round($LUFS-($I),2))")dB" "$MUSICWAV"
  echo "$(date +%F) $B offset=$OFF" >> "$MDIR/offsets.log"
else
  ffmpeg -v error -y -f lavfi -i anullsrc=r=48000:cl=stereo -t "$D" "$MUSICWAV"
fi
if [ -n "$KV" ]; then
  KVOICE=$KV python3 "$HERE/voiceover.py" "$TL" "$VIDEO" "$MUSICWAV" "$OUT" 2>&1 | tail -4
elif [ "$MUSIC" = on ]; then
  ffmpeg -v error -y -i "$VIDEO" -i "$MUSICWAV" -map 0:v:0 -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
  echo "wrote $OUT (music, no voice)"
else
  ffmpeg -v error -y -i "$VIDEO" -map 0:v:0 -c copy -movflags +faststart "$OUT"
  echo "wrote $OUT (no voice, no music)"
fi
