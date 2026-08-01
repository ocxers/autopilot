#!/usr/bin/env bash
#
# install.sh — symlink the autopilot commands into ~/.claude/commands/
# so you can call the bare `/autopilot`, `/autopilot-eval`, `/autopilot-auto` and `/make-review-prompt`
# (no plugin namespace).
#
# Idempotent: safe to re-run. Pass --copy to copy instead of symlink,
# or --uninstall to remove the links.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CMD_DIR="$CLAUDE_DIR/commands"
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

link_one "$REPO_DIR/commands/autopilot.md"      "$CMD_DIR/autopilot.md"
link_one "$REPO_DIR/commands/autopilot-eval.md" "$CMD_DIR/autopilot-eval.md"
link_one "$REPO_DIR/commands/autopilot-auto.md" "$CMD_DIR/autopilot-auto.md"
link_one "$REPO_DIR/commands/make-review-prompt.md"  "$CMD_DIR/make-review-prompt.md"

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
