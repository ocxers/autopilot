#!/bin/bash
# bash music.sh — builds the background-music bed once: ~/.cache/demo-video/music/chain.wav
# Four Mixkit "technology" tracks (Mixkit Stock Music Free License: free for commercial and
# personal use, no attribution required — https://mixkit.co/license/#musicFree): each loudness-
# normalised, its leading/trailing silence trimmed, then chained twice with 3 s crossfades (~25 min).
set -e
DIR=${DEMO_MUSIC_DIR:-$HOME/.cache/demo-video/music}
mkdir -p "$DIR" && cd "$DIR"
[ -s chain.wav ] && { echo "exists: $DIR/chain.wav"; exit 0; }
IDS="744 1167 609 464"
for id in $IDS; do
  [ -s "m$id.mp3" ] || curl -sfL -m 60 -A "Mozilla/5.0" -o "m$id.mp3" "https://assets.mixkit.co/music/$id/$id.mp3"
  ffmpeg -v error -y -i "m$id.mp3" -af "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" -ac 2 "t$id.wav"
  ffmpeg -v error -y -i "t$id.wav" -af "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1,areverse" "s$id.wav"
done
ffmpeg -v error -y -i s744.wav -i s1167.wav -i s609.wav -i s464.wav -i s744.wav -i s1167.wav -i s609.wav -i s464.wav \
  -filter_complex "[0][1]acrossfade=d=3:c1=tri:c2=tri[a1];[a1][2]acrossfade=d=3:c1=tri:c2=tri[a2];[a2][3]acrossfade=d=3:c1=tri:c2=tri[a3];[a3][4]acrossfade=d=3:c1=tri:c2=tri[a4];[a4][5]acrossfade=d=3:c1=tri:c2=tri[a5];[a5][6]acrossfade=d=3:c1=tri:c2=tri[a6];[a6][7]acrossfade=d=3:c1=tri:c2=tri[a7]" \
  -map "[a7]" chain.wav
echo "wrote $DIR/chain.wav ($(ffprobe -v error -show_entries format=duration -of csv=p=0 chain.wav)s)"
