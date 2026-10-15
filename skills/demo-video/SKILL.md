---
name: demo-video
description: Use when asked to record a demo video, a screen recording or a walkthrough of a web app (录视频, 录屏, 演示视频, 录个 demo). It covers a short clip proving a bug fix or feature for a ticket, PR or Jira, and a longer narrated walkthrough, product tour or team-workflow video with captions, voice-over (配音) or music. It accepts parameters such as lang=, voice=, music=, captions=, camera=.
---

# Demo video

One skill with two modes, one recorder and one post-production. App-specific setup lives in app profiles.
First use on a machine: `bash scripts/setup.sh` (checks and installs ffmpeg, Pillow, Playwright and its Chrome, the Kokoro voice, the music bed; `--check` only reports).

## Parameters

Read them as `key=value` after `/demo-video`, or from plain words ("英文，不要配音"). An unset parameter takes its mode's default.

| Parameter | Values | clip default | walkthrough default |
|---|---|---|---|
| `mode` | `clip`: a short proof of one fix or feature. `walkthrough`: several features, a team workflow, agents at work, narration. | Inferred from the request. | Inferred from the request. |
| `lang` | `en` or `zh` (UI, captions, voice) | Ask. | Ask. |
| `captions` | `on` / `off` | on | on |
| `voice` | `off` / `female` / `male`. English only for now. | off | `female` (Kokoro `af_heart`) for `en`; `off` for `zh` |
| `music` | `off` / `on`, optional `lufs=` | off | on, -42 LUFS, ducked under the voice |
| `camera` | `studio` (push-ins on what is clicked, typed or looked at) / `static` | studio | static |
| `frame` | `wallpaper` (browser window on a wallpaper) / `none` (the page fills the video) | wallpaper (saved preference, else `ventura` when downloaded, else `aurora`) | none |
| `ff` | fast-forward long waits: `auto` / `off` | Sped up by hand (`modes/clip.md` §4) | `auto` (waits over 3 s) |
| `post` | `none` / `jira` | none | none |

**Questions.** Before recording you ask at most two things:
- `lang`, when it is missing, in both modes.
- `mode`, only when the request leaves it open.

The confirmations a mode needs before publishing (a Jira post's preview) or before a download (Recordly wallpapers) still apply.

**Combinations that do not work yet.** Say so in one line and go ahead with the nearest option unless the user objects:
- `voice` on with `lang=zh`: use `voice=off`, captions only. The voice-over is English only for now.

`ff=off` in a walkthrough: record the waits in real time with `R.waitFor(fn, {ffAfter: Infinity})`.

## Choose the mode

- **clip**: one ticket, PR or fix, 15–30 s, ending on the app's real proof. Follow `modes/clip.md`.
- **walkthrough**: chapters, minutes long, real work that may take a while (agents, jobs), narration. Follow `modes/walkthrough.md`.

## Rules for every video

1. **The flow really works.** Rehearse on test data or a disposable copy before recording. The video ends on the app's real result: its success state, the saved row, the merged change.
2. **Nothing secret in frame.** Use test data only, and redact tokens and keys.
3. **Captions are readable.** Each one stays at least 2 s.
   - A voiced caption has at most 2.6 words/s (English) or 5 characters/s (Chinese).
   - A silent caption, in any mode, gets at least 0.3 s per English word or 0.2 s per Chinese character.
   - Captions follow `lang`. A Jira comment stays in English.
   - Write each caption after reading the actual result, never from the expected one.
4. **Delivery** goes to the recorded app's repo, in `docs/videos/`. Never commit it.
   - Clip names: `<KEY>-before-vN.mp4` and `<KEY>-fix-vN.mp4` for a fix, `<KEY>-vN.mp4` for a feature.
   - Walkthrough names: `<app>-<topic>-<lang>-vN.mp4`, for example `shop-checkout-en-v1`.
   - Each cut keeps only its newest delivered version. A fix's before cut and fix cut are separate cuts, so both stay.
   - Renders made during review and never delivered are deleted at delivery.
5. **Blocking bugs.** A product bug that blocks the flow is fixed first (failing test, fix, push), then the flow is recorded. Report the other problems at delivery.
6. **Progress.** One line after each step.

## Default look

- **clip:** studio camera, browser window on the wallpaper (saved preference), captions and a tip card. The background swatch sheet appears only when the user asks to choose one.
- **walkthrough:**
  - plain screen recording, with translucent captions (`CAP_ALPHA=150`, `CAP_STROKE=3`) and chapter pills
  - a "Fast-forward ×N" badge
  - the voice `af_heart`
  - music at -42 LUFS, ducked under the voice

## App profiles

Some setup is specific to one app: starting a disposable copy, signing in, waiting for long work, resetting after a rehearsal. A profile holds that setup.
Profiles are not part of this skill. Look for one in this order:
1. `<app repo>/.demo-video/PROFILE.md`
2. `~/.config/demo-video/profiles/<app>/PROFILE.md`

If there is none, write one before recording.
- **Clip section:** how to serve the app on the branch, how the recorder gets signed in (a saved session for headless, or the CDP port of a Chrome the owner signed in to), the toast library, and the Jira project.
- **Walkthrough section:**
  - the work dir under `~/.cache/demo-video/work/<app>`
  - how to start a recording copy and a disposable copy, and how to sign in
  - how to tell that long work is done
  - how to reset after a rehearsal
  - the UI facts that cost a retake, and the example scripts
  - `PLAYWRIGHT_MODULE` if Playwright lives in the app's `node_modules`
  - `speech-fixes.json` for spoken forms of the app's terms

Jira sites for `post=jira` are in `~/.config/demo-video/jira-sites.json`.

## Shared recorder and post-production

- **Recorder:** `scripts/walkthrough/lib.mjs` (Playwright, CDP screencast at DPR 2, drawn cursor, event log, `actions.json` for the camera). Headless with a saved session, or a tab in a signed-in Chrome over CDP.
- **Post:** `post.sh` runs captions, tips, fast-forward, camera, frame, music and voice in one step, from the work dir: `bash post.sh <name> <out.mp4> lang= voice= music= captions= camera= frame= background= url= offset= lufs=`. `offset=` (default 60 s) and `lufs=` only matter with music on.
  - `camera=static frame=none`: `build.py`, the plain recording.
  - Anything else: `to_session.py` + `studio/render.py` (own renderer: eased push-ins on each target and its result, browser window, wallpaper).
  - Sound: `audio.sh`, usable on any finished cut.

## Platform

- **Voice-over:** English only for now (Kokoro-82M, local and offline after the first download). It runs anywhere Node runs; it is not tied to macOS.
- Everything else runs on macOS and Linux with Node 18+, Python 3 with Pillow, ffmpeg and a Chrome (`setup.sh` gets them).
- **macOS defaults with fallbacks:** the caption font (PingFang; elsewhere Noto CJK or DejaVu, or `CAPTION_FONT`), the Chrome lookup in `~/Library/Caches/ms-playwright` (elsewhere Playwright's own, or `DEMO_CHROME`).
