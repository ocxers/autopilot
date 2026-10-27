# Mode: clip (a short proof of one fix or feature)

The rules in SKILL.md apply. A clip uses the same recorder (`scripts/walkthrough/lib.mjs`) and post-production (`post.sh`) as a walkthrough, with other defaults: `camera=studio frame=wallpaper voice=off music=off`, a tip card where it helps, and 15–30 s.

The job is fully delegated: plan, record, edit, check and deliver without asking the user to click, open apps, restore files or pick tools. Recording is always possible: headless with a saved session, or a tab in a Chrome the owner signed in to (§2).

Hard rules for every clip:
- Never put text of yours into the app's UI. What the app shows stays as the app shows it; payloads and explanations go into a **tip card** (`R.tip`) or a caption.
- End on the app's **real** proof (its own success toast, the saved row, the fixed state). A video that ends on an error toast proves nothing.
- Writes: if the proof needs a write (save, create, delete), do the real write on local/dev/test data without asking, and restore the test case afterwards when others reuse it. Block writes (`R.blockWrites()`) only in the rehearsal. Never write to production.
- Record the page the way users reach it (with the app shell), e.g. `/settings?tab=ai-provider`, not a bare route without the sidebar and header.
- Pace for a first-time viewer: actions at human speed, captions per SKILL.md rule 3, the proof still on screen ≥ 1.5 s before the end.
- Nothing secret in the frame: `url=` (the address bar text) is the in-app route without tokens or auth codes; only test data on the page.
- Background: the saved preference (memory), else `ventura` when the Recordly wallpapers are downloaded, else `aurora`. The swatch sheet (§6) only when the user asks to choose.
- A bug fix gets a **before** cut (§1b) as well as the fix cut; both are delivered. Before/after key screens (§4b) only when asked.
- Nothing is delivered before the independent review (§7) has no must-fix items left.

`S=<this skill's directory>/scripts` below (the directory holding SKILL.md: `~/.claude/skills/demo-video` after `install.sh`, or the plugin's `skills/demo-video`). Template: `assets/example/rec-clip.mjs`; Jira text: `assets/example/comment.txt`.

## 0. Setup

`bash $S/setup.sh` (first use, or when something fails to load). Delete old runs (SKILL.md rule 4). Work dir: `~/.cache/demo-video/work/<app>/<KEY>`; copy the scripts there and run everything from it:
`cp $S/walkthrough/* $S/post/* $S/studio/* $S/render_demo.py <work dir>/`

## 1. Plan

Take the flow from the request, else the ticket's repro steps / ACs: start state → each meaningful action → the proof (what the ticket says was wrong, now right). Run the app locally on the branch with the change, as the profile says.

## 1b. Before the fix

For a bug fix, record the same flow on the code without the fix, before recording the fix itself:

1. `git worktree add ../<repo>-before $(git merge-base HEAD origin/main)` (or the commit the ticket names); symlink each package's `node_modules` from the main checkout instead of installing.
2. Stop the branch's servers and start the worktree's on the **same ports** (same origin, so the session stays valid). Start only the side(s) the fix touched.
3. Run §3–§4 with the same script; the cut is `<KEY>-before-vN.mp4`. Captions say what is wrong ("Before: the start date resets to 2026"). Never fake the broken state in the UI.
4. Stop the worktree's servers, restart the branch's, record the fix. Remove the worktree at the end (`git worktree remove`).

## 2. A signed-in browser

The profile says which one the app needs:
- **Headless with a saved session** (the default; sharp and steady): `createRecorder({ storageState: 'auth.json' })`. Make `auth.json` once by signing in with a script (test account from the profile) and `context.storageState({ path })`.
- **A Chrome the owner signed in to** (SSO, sessionStorage tokens, 2FA): that Chrome runs with `--remote-debugging-port=<port> --user-data-dir=<its own profile>`; the owner signs in there by hand, never you. `createRecorder({ cdp: 'http://127.0.0.1:<port>' })` opens a new tab at the recording size and DPR 2 whatever the screen, and `R.close()` closes only that tab.

## 3. Script, rehearse, record

Write `rec-<KEY>.mjs` from `assets/example/rec-clip.mjs`:
- `R.click(loc, { expect })`: `expect` is the locator of the click's real result (menu, dialog, popover, toast, row). The click waits for it, and the camera frames it next to the control, or pans to it when they are far apart.
- `R.type(loc, text)`, `R.cap(text, 'bottom' | 'top')`.
- `R.look(loc, { hold })`: a push-in without input, for a proof that is small at full frame (a focus ring, a colour, an underline, one cell). Frame the whole control, a full row rather than its left half.
- `R.tip({ title, lines, code })` … `R.tip(null)`: the tip card, top right. Why the app shows what it shows, and the request payload as `code` lines when it proves the fix. A top caption and a tip are never on screen together.

1. Rehearse with `--rehearse` (`R.blockWrites()`): every non-GET request is answered with an empty 418 and kept in `R.captured`. Check the selectors and the payload. A real write is one-shot, so get everything right first.
2. Reset what the rehearsal changed, then the take: `node rec-<KEY>.mjs --run runs/<KEY>-a`. `echo runs/<KEY>-a > runs-<KEY>.txt`.

## 4. Cut

```bash
bash post.sh <KEY> --check lang=en      # captions too fast or too short; fix in edits-<KEY>.json
bash post.sh <KEY> <repo>/docs/videos/<KEY>-fix-vN.mp4 lang=en camera=studio frame=wallpaper \
  background=<preference> url=<in-app URL> voice=off music=off
```

- `camera=static` keeps the full page on the wallpaper; `frame=none` drops the wallpaper and window (the recording's own 3200×1800 pixels). `voice=female music=on` add the Kokoro voice-over and the music bed.
- The camera moves only where something is clicked, typed or looked at; scrolling and reading stay at full frame.
- A long app wait is fast-forwarded by `R.waitFor` (badge "Fast-forward ×N"), or by `R.ffOn()` / `R.ffOff()` around it.
- The renderer writes `camera.json` (camera keyframes) into `$TMPDIR/demo-video-post/<KEY>-session/` for the review.

## 4b. Before/after key screens (only when asked)

Pick the 1–3 moments that show the difference (usually the proof; `timeline-<KEY>.json` has the caption times) and write `docs/videos/<KEY>/compare.json`:

```json
{ "before": "../<KEY>-before-v1.mp4", "after": "../<KEY>-fix-v1.mp4", "output": "../<KEY>-before-after.png",
  "pairs": [{ "before": 12.3, "after": 11.8, "caption": "After Renew: the start date" }] }
```

`python3 $S/compare_key_screens.py docs/videos/<KEY>/compare.json` writes one PNG per pair, the two frames side by side under "Before the fix" / "After the fix". Both frames must show the same step; read every PNG before using it.

## 5. Static framing

`camera=static` (on the wallpaper) or `camera=static frame=none` (the plain recording). Nothing else changes.

## 6. Backgrounds

Swatch sheet: `python3 $S/render_demo.py --backgrounds docs/videos/backgrounds.png`
- Recordly's wallpapers (`tahoe-light`, `ventura`, `sonoma-*`, `sequoia-*`, …) in `~/.cache/demo-video/recordly/`; if missing, ask before `render_demo.py --fetch-recordly` (~12 MB). Mostly Apple wallpapers re-shared without a clear licence: internal tickets and PRs only, never bundled or committed.
- Original gradients, safe for public videos: `aurora`, `violet`, `sunset`, `ocean`, `mint`, `lavender`, `peach`, `graphite`. Also an image path or `#hex`.

## 7. Independent review, then deliver

1. Quick self-check first: a 2 fps contact sheet, the last frame, and the frame-diff spike scan (mean abs diff per frame vs the neighbours' median; app transitions are fine, scroll jumps are not).
2. Dispatch a fresh subagent (Agent tool, `general-purpose`) to review against `references/final-review.md`. Its prompt holds only: the absolute path of that file with "follow it exactly", the absolute paths of every cut, each cut's `timeline-<name>.json` and `camera.json`, the `url=` value, the ticket key, one sentence of what was wrong and the AC/repro it must prove, and a scratch directory for its frames. Never tell it what you fixed, why something looks the way it does, or what you expect.
3. Fix every must-fix item, re-cut (rendering is cheap), and send the new cut to a new reviewer the same way. Repeat until no must-fix items remain. Should-fix items: fix them unless the fix would change what the user approved; say which you skipped.

Clean up: stop servers you started, close tabs you opened, delete the reviewer's frame directory and the unused runs (SKILL.md rule 4). Give the user the clickable path to each new version.

## 8. Post to Jira (only when asked)

Every recorded cut goes into **one** comment: the before video, then the fix video, under one short description. Never one comment per video, never leave a recorded cut out, no screenshots unless the user asked for key screens.

Write `docs/videos/<KEY>/comment.txt` (wiki markup, English; a `{before}` line marks the before video, `{video}` the fix video, `{images}` only for requested key screens; say what was recorded against). Run with `--dry-run`, show the preview, wait for a clear yes, then run without it. The script picks the site and its credentials from `~/.config/demo-video/jira-sites.json` by the ticket's project prefix, uploads, checks the size, posts the comment, rewrites each video node to Jira's editor format (the wiki conversion alone leaves "Creating preview..." forever) and verifies every embed:

```bash
python3 $S/post_jira_video.py <KEY> docs/videos/<KEY>-fix-vN.mp4 docs/videos/<KEY>/comment.txt \
  --before docs/videos/<KEY>-before-vN.mp4 --dry-run
```

Once every embed is verified, offer the cleanup in the same turn: run `bash $S/clean.sh --key <KEY>` from the app's repo (it lists this ticket's work dir, videos and temp files with sizes, and deletes nothing), show the list, and ask with AskUserQuestion: "Yes, delete" or "No, keep them". Only on yes, run it again with `--yes` and report what it freed; any other answer deletes nothing. Other tickets' files are never touched here.

## Fallback: rendered from screenshots

Only when no browser can be scripted at all. Capture each state at 2x with claude-in-chrome tiles (hide `#claude-phantom-cursor, #claude-agent-glow-border` first; four `computer zoom` calls with `save_to_disk: true, scale: 1` over the quarters from `$S/stitch_tiles.py --frame WxH --regions`, then stitch), confirm the DOM state before each capture, write `storyboard.json` (docstring of `$S/render_demo.py`) and run `render_demo.py storyboard.json --preview`. Tell the user it is a reconstruction from screenshots, not a recording.
