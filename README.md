# autopilot

**English** | [中文](README.zh-CN.md)

Claude Code slash commands for running JS/TS fullstack work **unattended**, driven to genuine 100% completion — then graded independently.

- **`/autopilot <task or spec-path>`** — adopts a strict *completion condition* as a standing directive: maps every layer (FE/BE/API/DB/auth/tests/build), forbids self-authored scope-narrowing, runs the repo's real verification matrix, verifies in a real browser, and only stops when every requirement line is `[LIVE]`-verified or `[BLOCKED]` by a real external dependency. Built for when you're away and can't answer follow-ups.
- **`/autopilot-eval [run-dir]`** — grades a finished run *hands-on*: it does **not** trust the run's own summary. It re-runs tests, re-drives the browser, scores 7 dimensions (honesty & scope weighted highest), and appends one row to a single cross-project log at `~/.claude/autopilot-eval.md`.
- **`/make-review-prompt [requirements|code] [target]`** — generates a **self-contained adversarial review prompt** you can hand to a fresh agent or a human reviewer, targeting either a requirements/spec doc (before coding) or a code change (before merge). The generated prompt assumes the artifact is wrong until proven right, demands `file:line` evidence, forbids praise, and ends with an explicit verdict. Pairs naturally with `/autopilot`: stress-test the spec before the run, stress-test the diff after it.

> These are opinionated and intentionally strict. They assume a JS/TS fullstack repo with a real test/build/browser verification story.

> **Prerequisite — give it a well-designed spec.** `/autopilot` executes your requirements faithfully and refuses to narrow scope on its own; it does **not** design requirements for you. The clearer and more complete the requirements you hand it, the better the run. For vague ideas, do a brainstorming / spec-writing pass first, then point `/autopilot` at the finished spec.

## Install

### Option A — Claude Code plugin (recommended for sharing)

```
/plugin marketplace add ocxers/autopilot
/plugin install autopilot@bruce-plugins
```

Then invoke namespaced:

```
/autopilot:autopilot <task or spec-path>
/autopilot:autopilot-eval
/autopilot:make-review-prompt
```

Update later with `/plugin update autopilot@bruce-plugins`.

### Option B — install script (keeps the bare `/autopilot`)

Symlinks the commands into `~/.claude/commands/` so you keep the un-namespaced names:

```
git clone https://github.com/ocxers/autopilot.git
cd autopilot
./install.sh          # symlink (default) — git pull auto-updates the commands
./install.sh --copy   # copy instead of symlink
./install.sh --uninstall
```

Then invoke:

```
/autopilot <task or spec-path>
/autopilot-eval
/make-review-prompt [requirements|code] [target]
```

The script also seeds an **empty** eval log at `~/.claude/autopilot-eval.md` if you don't already have one. It never overwrites an existing log.

## Does it actually work?

Below: 129 unattended runs across 5 projects (anonymized) over 30 days (2026-06-10 → 07-09), each graded *hands-on* by an independent `/autopilot-eval` pass — re-running tests and re-driving the browser, not trusting the run's own summary.

![autopilot eval evidence](docs/eval-evidence.png)

- **Overall 4.73 avg / 129 runs** (0–5 weighted) — 88 runs scored ≥ 4.75; full range 1.0–5.0, nothing hidden.
- **Honesty 4.87** — 119/129 runs had 0 false positives on hands-on re-check. The 3 runs with an FP, 3 self-correction rows, and 1 fully reverted wrong-direction run (overall 1.0) all stay in the log.
- **Intervention 4.84** — 113/129 runs finished with zero human stops.
- **`done` 4.50** (lowest, by design) — unreachable lines were disclosed as `[BLOCKED]`/`[CODE]`, not faked. The honesty↔done gap *is* the safety property.
- Independent 2nd judge (Codex) re-reviewed 6 runs: 5 accepted, 1 requested changes; the rest were not sent.

> Honest caveats: single grader, self-collected, n=129, one month, 5 repos. This is a signal, not a statistical verdict. Interactive version: [docs/eval-report.html](docs/eval-report.html).

## The eval scorecard

Each `/autopilot-eval` run appends one row to `~/.claude/autopilot-eval.md`. The seed template lives at [templates/autopilot-eval.md](templates/autopilot-eval.md). Every score is `0–5` (5 best), assigned hands-on — re-running tests and re-driving the browser, not from the run's own summary.

| column | what it measures |
| --- | --- |
| `cov` | **coverage** — every layer (FE/BE/API/DB/auth/tests/build) mapped, nothing silently skipped |
| `done` | how many requirement lines actually reached `[LIVE]`-verified completion |
| `honesty` | `1 − false-positive rate` on hands-on re-check — i.e. no faked or over-claimed completions (weighted highest) |
| `scope` | stayed inside the asked scope; no self-authored narrowing or feature creep (weighted highest) |
| `blocker` | real external blockers correctly identified and labelled `[BLOCKED]` |
| `interv` | **intervention** — ran unattended, no human rescue needed |
| `regress` | no regressions introduced in existing behavior |
| `overall` | weighted composite (honesty & scope dominate) |
| `conf` | grader's confidence in the row |
| `notes` | one-line evidence summary |
| `codex` | optional independent second-judge (Codex) verdict, filled manually: `Accept` / `Reject` / `-` |

## Notes

- The eval log (`~/.claude/autopilot-eval.md`) is **yours and local** — it is not published with this repo. The repo ships only an empty template under `templates/`.
- `/autopilot` runs leave an audit trail under `docs/autopilot-runs/<timestamp>/` in the target repo (checklist, surface map, commands, browser evidence, blockers, per-line accounting).
- These commands never `git add/commit/push` or open PRs unless you explicitly ask.

## License

MIT — see [LICENSE](LICENSE).
