# Mode: walkthrough (chapters, real work, narration)

The rules and parameters in SKILL.md apply. Everything app-specific comes from the app's profile, which tells you:
- the work dir, and how to start, copy and reset the app
- how to sign in
- how to tell that long work is done
- the UI facts

You need all of that before starting, so read the profile first.

## How it works

- **Recording:** a scripted headless Chrome (Playwright) drives the app at 1600×900, DPR 2. CDP screencast frames go to disk with an event log: captions, chapters, fast-forward, cuts and redactions. `scripts/walkthrough/lib.mjs` does this.
- **Long waits:** the script polls the app's real state (for example a database row) and marks them as fast-forward.
- **Post-production:** `scripts/post/` turns frames and events into the cut, then adds the music bed and the Kokoro voice-over.

## Workflow

1. **Work dir.** Run `bash scripts/setup.sh` on first use. Copy `scripts/walkthrough/*`, `scripts/post/*`, `scripts/studio/*`, `scripts/render_demo.py` and the profile's scripts into the profile's work dir (`~/.cache/demo-video/work/<app>`). Run everything from there.
2. **App up.** Start the recording copy of the app (profile).
3. **Explore and rehearse.**
   - On a disposable copy (profile), walk the flow by hand until the real work finishes and its output is good. The profile's explore helper runs snippets against a signed-in browser.
   - A product bug that blocks the flow is fixed first (SKILL.md rule 5).
4. **Script.**
   - Write `rec-<x>.mjs` from the profile's example, with the long texts in `<x>-texts.json`.
   - Run the whole script on a fresh copy, then check frames at every caption end: `python3 frames_at.py runs/<run> sheet.jpg <t1> <t2> …` (seconds from the run start).
   - Fix and repeat until you get one clean pass.
5. **Reset** everything the rehearsal changed (profile).
6. **Record.**
   - Snapshot first if a retake would be costly (profile).
   - Run `node rec-<x>.mjs --stack <recording copy> --run runs/<x>-a`.
   - If a chapter fails, re-run it with `--from N --start-url …` into `runs/<x>-b`. List the runs in `runs-<x>.txt`: one spec per line, `runs/<dir>[@start=<epoch>,end=<epoch>,hold=<s>]`.
7. **Post-production.**
   - Run `bash post.sh <x> --check lang=<lang>` and fix every FAST caption in `edits-<x>.json`.
   - Run `bash post.sh <x> <out.mp4> lang= voice= music= captions= offset=`. No voice line may be reported "late"; if one is, shorten the caption before it.
8. **Check and deliver.**
   - Make a contact sheet of the final mp4 (`ffmpeg -ss <t> -frames:v 1` at about 8 points): captions match the screen, the proof is at the end, nothing secret shows.
   - Deliver the file (SKILL.md rule 4).
   - Report the path and length, the music offset (when music is on), the bugs you fixed (commits), and the issues still open.

## camera=studio and frame=wallpaper

`lib.mjs` writes each run's `actions.json`: the pointer path, every click, typing and `look` target with its box and the result it opened. `post.sh` turns that into push-ins:

```bash
bash post.sh <x> <out.mp4> lang=<lang> camera=studio frame=wallpaper background=<name> url=<address bar text>
```

- `to_session.py` maps the runs into output time (fast-forward and cuts applied, redactions burned in), so the camera follows the cut; `render.py` draws the camera, the browser window on the wallpaper, the captions, chapter pills, tips and the badge.
- `camera=studio frame=none`: push-ins on the full-bleed page. `camera=static frame=wallpaper`: the plain recording inside the window.
- Tested on a 14 s clip and an 18 s walkthrough excerpt (2026-10-15). On a long walkthrough check the contact sheet for push-ins on things nobody needs to read, and pass `look`/`click` only where the camera should go.

## Recorder API (`scripts/walkthrough/lib.mjs`)

`const R = await createRecorder({ outDir, locale: 'en-US' | 'zh-CN', storageState: 'auth-<copy>.json' })`
Other options: `cdp: 'http://127.0.0.1:<port>'` (record a tab in a Chrome the owner signed in to; DPR 2 is forced), `width`/`height` (1600×900), `dpr` (2), `timezoneId` (the machine's), `clipboardOrigin`.

| Call | What it does |
|---|---|
| `R.start()` / `R.stop()` / `R.close()` | Start or stop the screencast; close the browser (only our tab with `cdp`). |
| `R.chapter('2 · Agents')` | Chapter pill. It also clears the caption. |
| `R.cap(text, 'bottom' \| 'top')` | Caption until the next one. It is also the voice-over line. |
| `R.tip({title, lines, code})` / `R.tip(null)` | Tip card, top right. Not read aloud. |
| `R.click(loc, {before, after, expect, timeout})`, `R.type(loc, text, {delay})`, `R.hover(loc, {hold})`, `R.press(key, ms)`, `R.wheel(dy, {at})` | Human-paced input with a drawn cursor and click ripples. `expect`: the click's result, waited for and framed by the camera. |
| `R.look(loc, {hold})` | No input; camera=studio pushes in on `loc`. |
| `R.reveal(loc, {block})` | Smooth scroll into view. An element clipped inside a scrolling side panel counts as visible, so use `tap()` there. |
| `R.waitFor(fn, {ffAfter: 3, speed: 20, timeout, interrupt: {check, act}})` | Polls `fn`. Fast-forwards after `ffAfter` s. `interrupt` handles something that needs an answer mid-wait. |
| `R.blockWrites()` / `R.allowWrites()`, `R.captured` | Rehearsal guard: non-GET requests get an empty 418 and are kept in `R.captured`. |
| `R.trackRedact(regex)` / `R.untrackRedact()` | Pixelates matching on-screen text (tokens). |
| `R.ffOn/ffOff`, `R.cutOn/cutOff`, `R.event({...})` | Manual fast-forward, a cut, or a raw event. |

Playwright: `PLAYWRIGHT_MODULE`, else `playwright` from the work dir, else setup.sh's shared install in `~/.cache/demo-video/node`. Chrome: the newest Playwright Chrome for Testing on the machine, or `DEMO_CHROME=<path>`.

## Script patterns

- **Arguments:** `--stack --web --run --from --to --start-url`. Ids go to a `state-*.json`, so `--from N` resumes a chapter.
- **Waiting:** wait on the app's state, never on fixed sleeps. List every state the work can reach next, including a send-back loop.
- **Captions that depend on the result:** read the result first (a level, which item comes first), then write the caption.
- **Helpers:**
  - `pick(combo, option)` picks from a combobox.
  - `tap(loc)` scrolls to the centre, then clicks; use it in scrolling side panels.
  - `retype(loc, text)` clicks, selects the text, types and presses Tab.
  - `closePanel()` clicks Close, else presses Escape.
  - `toLatest()` jumps a thread to its newest entry, so live work stays in view.

## Post-production (`scripts/post/`)

- **`post.sh`:**
  - Parameters: `lang` (FAST check: en 2.6 words/s, zh 5 chars/s; badge "Fast-forward ×N" or "快进 ×N"), `voice` (`female` = `af_heart`, `male` = `am_michael`, `off`), `music`, `lufs`, `captions`, `offset`, `camera`, `frame`, `background`, `url`, `preview=1`.
  - For `lang=zh`, `voice` defaults to `off`.
- **`edits-<x>.json`:**
  - `replace` `{old: new}` rewrites caption text.
  - `drop` lists captions to remove; `drop_t` removes by time.
  - `shift` `{text: seconds}` moves a caption.
  - `pos_top` lists captions to show at the top.
  - `cuts` `{run: [[a, b]]}` removes time ranges from a run.
  - `add` lists events to insert.
- **Settings:** environment `CAP_ALPHA` (150), `CAP_STROKE` (3), `CRF` (18), `PRESET`, `CAPTION_FONT` (PingFang is found automatically), `BADGE`.
- **Music:**
  - `music.sh` builds `~/.cache/demo-video/music/chain.wav` once: four Mixkit technology tracks, under the Mixkit Stock Music Free License.
  - Use a different offset per video. `audio.sh` logs every offset to `music/offsets.log`; pick one that is not there.
- **Voice:**
  - Kokoro-82M (Apache-2.0) in the skill's `tts/`. The first run installs it and downloads the model.
  - Spoken forms are set in `SPEECH_FIXES` in `voiceover.py`.
- **Intermediate files** go to `$TMPDIR/demo-video-post/`.
- **Sound only:** `audio.sh <video> <timeline.json> <out> voice= music= offset= lufs= lang=` adds music and voice to any finished cut. `post.sh` calls it.

## Common mistakes

| Mistake | What happens | Do instead |
|---|---|---|
| Recording without a rehearsal | Retakes, and captions that do not match the outcome. | Rehearse on a copy until one clean pass. |
| A caption that assumes the result | It contradicts the screen. | Read the result, then write the caption. |
| Fixed sleeps during long work | There is nothing to fast-forward, and the script breaks when the work is fast. | Use `waitFor` on the real state. |
| `R.click` on a control in a scrolled side panel | The click misses. | Use `tap()`. |
| A thread left scrolled up | The live work is out of view. | Call `toLatest()` at each step. |
| Long captions | The voice lags behind ("late"). | Respect the pace limit; shorten the line before. |
| Rehearsal changes left in place | The recording finds the work already done. | Reset after every rehearsal (profile). |
