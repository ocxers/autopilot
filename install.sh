#!/usr/bin/env bash
#
# install.sh — symlink the autopilot commands into ~/.claude/commands/ and the skills into
# ~/.claude/skills/, so you can call the bare `/autopilot`, `/autopilot-eval`, `/autopilot-auto`,
# `/make-review-prompt`, `/demo-video` and `/flow-check` (no plugin namespace).
#
# Idempotent: safe to re-run. Pass --copy to copy instead of symlink,
# or --uninstall to remove the links.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CMD_DIR="$CLAUDE_DIR/commands"
SKILL_DIR="$CLAUDE_DIR/skills"
EVAL_LOG="$CLAUDE_DIR/autopilot-eval.md"

MODE="symlink"
case "${1:-}" in
  --copy)      MODE="copy" ;;
  --uninstall) MODE="uninstall" ;;
  "" )         ;;
  * ) echo "Usage: $0 [--copy|--uninstall]" >&2; exit 2 ;;
esac

link_one() {
  local src="$1" dst="$2"
  if [ "$MODE" = "uninstall" ]; then
    if [ -L "$dst" ] || [ -f "$dst" ]; then rm -f "$dst"; echo "removed  $dst"; fi
    return
  fi
  mkdir -p "$(dirname "$dst")"
  rm -f "$dst"
  if [ "$MODE" = "copy" ]; then cp "$src" "$dst"; echo "copied   $dst";
  else ln -s "$src" "$dst"; echo "linked   $dst -> $src"; fi
}

# Skills are directories. Only a link or copy this script made is replaced or removed; an existing
# real directory (your own copy of the skill) is never deleted.
link_skill() {
  local src="$1" dst="$2"
  if [ "$MODE" = "uninstall" ]; then
    if [ -L "$dst" ]; then rm -f "$dst"; echo "removed  $dst";
    elif [ -f "$dst/.installed-by-autopilot" ]; then rm -rf "$dst"; echo "removed  $dst";
    elif [ -d "$dst" ]; then echo "kept     $dst (not installed by this script — remove it yourself)"; fi
    return
  fi
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then rm -f "$dst";
  elif [ -f "$dst/.installed-by-autopilot" ]; then rm -rf "$dst";
  elif [ -e "$dst" ]; then
    echo "kept     $dst (already exists and was not installed by this script — move it away and re-run to use the repo version)"
    return
  fi
  if [ "$MODE" = "copy" ]; then
    mkdir -p "$dst" && (cd "$src" && tar cf - --exclude node_modules --exclude __pycache__ .) | (cd "$dst" && tar xf -)
    touch "$dst/.installed-by-autopilot"; echo "copied   $dst"
  else ln -s "$src" "$dst"; echo "linked   $dst -> $src"; fi
}

link_one "$REPO_DIR/commands/autopilot.md"      "$CMD_DIR/autopilot.md"
link_one "$REPO_DIR/commands/autopilot-eval.md" "$CMD_DIR/autopilot-eval.md"
link_one "$REPO_DIR/commands/autopilot-auto.md" "$CMD_DIR/autopilot-auto.md"
link_one "$REPO_DIR/commands/make-review-prompt.md"  "$CMD_DIR/make-review-prompt.md"
link_skill "$REPO_DIR/skills/demo-video"          "$SKILL_DIR/demo-video"
link_skill "$REPO_DIR/skills/flow-check"          "$SKILL_DIR/flow-check"

# Seed the cross-project eval log from the template ONLY if it doesn't exist —
# never overwrite an existing log (it holds your private run history).
if [ "$MODE" != "uninstall" ]; then
  if [ ! -f "$EVAL_LOG" ]; then
    cp "$REPO_DIR/templates/autopilot-eval.md" "$EVAL_LOG"
    echo "seeded   $EVAL_LOG (empty log)"
  else
    echo "kept     $EVAL_LOG (already exists — not touched)"
  fi
fi

echo "Done ($MODE). Restart Claude Code or run /help to pick up the commands."
[ "$MODE" = "uninstall" ] || echo "First /demo-video on this machine: bash $SKILL_DIR/demo-video/scripts/setup.sh"
