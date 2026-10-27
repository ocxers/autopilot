#!/bin/bash
# bash clean.sh [--all] [--yes] [--dry-run] [--force]
#   Deletes everything recording leaves behind: the work dirs (~/.cache/demo-video/work: frames,
#   script copies, auth.json) and the temp files ($TMPDIR/demo-video-*). --all also deletes the
#   delivered videos in docs/videos of the repo you run it from (the recorded app). Keeps the downloads under ~/.cache/demo-video
#   (node, tts, music, recordly). Refuses while a recording or render is running, unless --force.
#   Lists first and deletes only after a "y" at the prompt, or with --yes; anything else gives up.
# bash clean.sh --key <KEY> [--yes] [--dry-run]
#   After the Jira post: only this ticket's work dir, videos and temp files. Same confirmation.
# bash clean.sh --old [--dry-run]
#   Before a new video: runs and temp files older than 7 days.
# bash clean.sh --unused <work dir> [--dry-run]
#   At delivery: the runs in <work dir> that no runs-*.txt lists. The listed runs stay for re-renders.
set -u
WORK=$HOME/.cache/demo-video/work
REPO=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$REPO" ] && [ -n "$(git -C "$REPO" ls-files docs/videos)" ]; then
  echo "docs/videos has files tracked by git; leaving it alone." >&2; REPO=
fi
TMP=${TMPDIR:-/tmp}; TMP=${TMP%/}
MODE=all; DIR=; DRY=; FORCE=; VIDEOS=; YES=; KEY=
while [ $# -gt 0 ]; do case "$1" in
  --all) VIDEOS=1 ;;
  --yes) YES=1 ;;
  --key) MODE=key; KEY=${2:-}; [[ "$KEY" =~ ^[A-Z][A-Z0-9]*-[0-9]+$ ]] || { echo "--key needs a ticket key like EDU-1234"; exit 1; }; shift ;;
  --old) MODE=old ;;
  --unused) MODE=unused; DIR=${2:-}; [ -d "$DIR" ] || { echo "--unused needs an existing work dir"; exit 1; }; shift ;;
  --dry-run) DRY=1 ;;
  --force) FORCE=1 ;;
  *) echo "unknown: $1"; exit 1 ;;
esac; shift; done

if [ $MODE = all ] && [ -z "$FORCE" ] && pgrep -f 'post\.sh|render\.py|build\.py|to_session\.py|rec-[^ ]*\.mjs' >/dev/null; then
  echo "A recording or render is running; finish it first, or pass --force."; exit 1
fi
if [ $MODE = unused ] && ! ls "$DIR"/runs-*.txt >/dev/null 2>&1; then
  echo "No runs-*.txt in $DIR, so no run is known to be used; nothing deleted."; exit 1
fi

targets() {
  case $MODE in
    all)
      [ -d "$WORK" ] && echo "$WORK"
      [ -n "$VIDEOS" ] && [ -n "$REPO" ] && [ -d "$REPO/docs/videos" ] && echo "$REPO/docs/videos"
      ls -d "$TMP"/demo-video-* 2>/dev/null ;;
    key)
      ls -d "$WORK"/*/"$KEY" "$TMP/demo-video-post/$KEY"-* 2>/dev/null
      [ -n "$REPO" ] && ls -d "$REPO/docs/videos/$KEY" "$REPO/docs/videos/$KEY"-* 2>/dev/null ;;
    old)
      [ -d "$WORK" ] && find "$WORK" -mindepth 3 -maxdepth 4 -type d -path '*/runs/*' ! -path '*/runs/*/*' -mtime +7
      [ -d "$TMP/demo-video-post" ] && find "$TMP/demo-video-post" -mindepth 1 -maxdepth 1 -mtime +7 ;;
    unused)
      for r in "$DIR"/runs/*/; do
        [ -d "$r" ] || continue
        r=${r%/}
        grep -qsxE "(.*/)?runs/$(basename "$r")(@.*)?" "$DIR"/runs-*.txt || echo "$r"
      done ;;
  esac
}

LIST=$(targets)
[ -z "$LIST" ] && { echo "Nothing to delete."; exit 0; }
echo "$LIST" | while IFS= read -r p; do du -sh "$p" 2>/dev/null; done
echo "Total: $(echo "$LIST" | tr '\n' '\0' | xargs -0 du -shc 2>/dev/null | tail -1 | cut -f1)"
[ -n "$DRY" ] && { echo "(dry run, nothing deleted)"; exit 0; }
if [[ $MODE = all || $MODE = key ]] && [ -z "$YES" ]; then
  [ -t 0 ] || { echo "Nothing deleted; run again with --yes to delete these."; exit 0; }
  read -r -p "Delete these? [y/N] " a
  case "$a" in y|Y|yes|YES) ;; *) echo "Gave up, nothing deleted."; exit 0 ;; esac
fi
echo "$LIST" | tr '\n' '\0' | xargs -0 rm -rf
echo "Deleted."
