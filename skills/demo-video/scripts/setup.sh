#!/bin/bash
# bash setup.sh [--check] [--voice]
# Gets this machine ready to record and edit: checks every tool, installs what is missing, and says
# what it could not install. Safe to run again; it skips what is there.
#   --check   only report, install nothing
#   --voice   also download the Kokoro voice model now (~330 MB, otherwise on the first voiced video)
# Not fetched here: Recordly wallpapers (licence unclear, ~12 MB); ask the user, then
#   python3 scripts/render_demo.py --fetch-recordly
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SKILL=$(dirname "$HERE")
CHECK=; VOICE=
for a in "$@"; do case "$a" in --check) CHECK=1 ;; --voice) VOICE=1 ;; *) echo "unknown: $a"; exit 1 ;; esac; done
NODE_DIR=${DEMO_NODE_DIR:-$HOME/.cache/demo-video/node}
MISSING=()
ok() { printf '  ✓ %s\n' "$1"; }
bad() { printf '  ✗ %s\n' "$1"; MISSING+=("$1"); }
try() { [ -z "$CHECK" ] && printf '  … %s\n' "$1" && return 0; return 1; }
OS=$(uname -s)

echo "demo-video setup ($OS)"
[ -z "$CHECK" ] && mkdir -p "$HOME/.cache/demo-video" && echo "$SKILL" > "$HOME/.cache/demo-video/skill-dir"  # work-dir copies find tts/ here

# ffmpeg / ffprobe
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then ok "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')"
elif [ "$OS" = Darwin ] && command -v brew >/dev/null && try "brew install ffmpeg"; then brew install ffmpeg >/dev/null && ok ffmpeg || bad "ffmpeg (brew install ffmpeg failed)"
else bad "ffmpeg: install it (macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg)"; fi

# Python 3 + Pillow
if ! command -v python3 >/dev/null; then bad "python3"
elif python3 -c 'import PIL' 2>/dev/null; then ok "python3 + Pillow"
elif try "pip install Pillow"; then python3 -m pip install --user --quiet Pillow 2>/dev/null || python3 -m pip install --user --quiet --break-system-packages Pillow
  python3 -c 'import PIL' 2>/dev/null && ok "python3 + Pillow" || bad "Pillow (python3 -m pip install Pillow)"
else bad "Pillow (python3 -m pip install Pillow)"; fi

# Caption font (PingFang on macOS; elsewhere Noto CJK / DejaVu, or CAPTION_FONT)
if python3 -c "import sys; sys.path.insert(0, '$HERE/post'); import build" >/dev/null 2>&1; then
  ok "caption font $(python3 -c "import sys; sys.path.insert(0, '$HERE/post'); import build; print(build.FONT.rsplit('/', 1)[-1])")"
else bad "caption font: set CAPTION_FONT to a .ttf/.ttc with CJK glyphs (Linux: apt install fonts-noto-cjk)"; fi

# Node 18+
if command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ]; then ok "node $(node -v)"
else bad "node 18+ (https://nodejs.org or brew install node)"; fi

# Playwright + its Chrome (shared install in $NODE_DIR unless PLAYWRIGHT_MODULE points elsewhere)
if command -v node >/dev/null; then
  PW=${PLAYWRIGHT_MODULE:-$NODE_DIR/node_modules/playwright/index.mjs}
  if [ ! -e "$PW" ] && [ -z "${PLAYWRIGHT_MODULE:-}" ] && try "npm install playwright in $NODE_DIR"; then
    mkdir -p "$NODE_DIR" && (cd "$NODE_DIR" && { [ -f package.json ] || echo '{"private":true}' > package.json; } && npm install --silent playwright >/dev/null 2>&1)
  fi
  if [ -e "$PW" ] || node -e "import('${PW}')" 2>/dev/null; then ok "playwright ($PW)"; else bad "playwright (npm install playwright, or set PLAYWRIGHT_MODULE)"; fi
  if [ -n "${DEMO_CHROME:-}" ] && [ -x "$DEMO_CHROME" ]; then ok "Chrome: DEMO_CHROME"
  elif compgen -G "$HOME/Library/Caches/ms-playwright/chromium-*" >/dev/null || compgen -G "$HOME/.cache/ms-playwright/chromium-*" >/dev/null; then ok "Chrome for Testing (Playwright)"
  elif [ -e "$PW" ] && try "playwright install chromium"; then
    (cd "$NODE_DIR" && npx --yes playwright install chromium >/dev/null 2>&1) && ok "Chrome for Testing (Playwright)" || bad "Chrome (npx playwright install chromium)"
  else bad "Chrome (npx playwright install chromium, or set DEMO_CHROME)"; fi
fi

# Kokoro voice (English only for now)
TTS=${DEMO_TTS_DIR:-$SKILL/tts}
if [ -d "$TTS/node_modules/kokoro-js" ]; then ok "kokoro-js"
elif command -v npm >/dev/null && try "npm install in $TTS"; then (cd "$TTS" && npm install --silent >/dev/null 2>&1) && ok "kokoro-js" || bad "kokoro-js (cd $TTS && npm install)"
else bad "kokoro-js (cd $TTS && npm install)"; fi
if [ -n "$VOICE" ] && [ -z "$CHECK" ] && [ -d "$TTS/node_modules/kokoro-js" ]; then
  J=${TMPDIR:-/tmp}/demo-video-warm.json; W=${TMPDIR:-/tmp}/demo-video-warm.wav; rm -f "$W"
  echo "[{\"text\": \"Ready.\", \"out\": \"$W\"}]" > "$J"
  (cd "$TTS" && node gen.mjs "$J" >/dev/null 2>&1) && [ -s "$W" ] && ok "Kokoro model downloaded" || bad "Kokoro model download (network?)"
fi

# Music bed (Mixkit Stock Music Free License)
MDIR=${DEMO_MUSIC_DIR:-$HOME/.cache/demo-video/music}
if [ -s "$MDIR/chain.wav" ]; then ok "music bed"
elif command -v ffmpeg >/dev/null && try "download the music bed"; then bash "$HERE/post/music.sh" >/dev/null 2>&1 && [ -s "$MDIR/chain.wav" ] && ok "music bed" || bad "music bed (bash scripts/post/music.sh)"
else bad "music bed (bash scripts/post/music.sh)"; fi

# Wallpapers: optional
if ls "$HOME"/.cache/demo-video/recordly/*.jpg >/dev/null 2>&1; then ok "Recordly wallpapers"
else echo "  - Recordly wallpapers not downloaded: frame=wallpaper uses the original gradients (aurora, …) until the user agrees to fetch them"; fi

if [ ${#MISSING[@]} -eq 0 ]; then echo "ready"; else echo "missing ${#MISSING[@]}:"; printf '  - %s\n' "${MISSING[@]}"; exit 1; fi
