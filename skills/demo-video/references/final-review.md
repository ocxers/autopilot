# Final review — independent check of a demo video

Run by a subagent with a clean context that took no part in recording or editing. The maker has confirmation bias: the first check never goes to the user, and never to the maker alone.

## What the reviewer gets

Give exactly these, nothing about how the video was made, what was fixed during editing or what you expect it to find:

- The cut(s): absolute paths of every MP4 to deliver (before and after).
- The claim: the ticket key, one sentence of what was wrong, and what the video must prove (the ticket's AC or repro, pasted).
- `timeline-<name>.json` (captions, chapters, tips and fast-forward with their times) and `camera.json` (camera keyframes: time, centre, zoom) of each cut.
- The `url=` value (the text in the drawn address bar).

A missing input is reported as "cannot verify", not guessed.

## How the reviewer looks

- A contact sheet at 2 fps: `ffmpeg -i <cut> -vf "fps=2,scale=480:-1,tile=6x5" sheet-%02d.png`.
- Full-size frames at each caption's midpoint and at the last second: `ffmpeg -ss <t> -i <cut> -frames:v 1 f<t>.png`.
- Each of those frames again scaled to 720 px wide (`-vf scale=720:-1`), the size of Jira's inline player.
- A frame-diff spike scan (mean absolute difference per frame vs the median of its neighbours); look at every spike.

## Checklist

Each item gets ✓, ✗ or "cannot verify", and every ✗ cites the cut and a timestamp (and the frame file).

**P — Proof**
- P1 The video ends on the app's own real proof (success toast, saved row, fixed state). It does not end on an error toast, and nothing in the app's UI was written by us.
- P2 The proof is what the claim says was wrong, now right. A viewer who has not read the ticket can tell what changed.
- P3 The proof is on screen and still for at least 1.5 s before the video ends, with no long frozen tail.
- P4 For a bug fix with a before cut: both cuts show the same flow at the same viewport, and the before cut shows the real broken state, not a staged one.

**F — Flow**
- F1 Every action the claim depends on is visible: the click target is inside the frame when it is clicked, and its result is inside the frame next.
- F2 Interactions run at human speed: a viewer could repeat each step from the video. Nothing important happens inside a single caption change.
- F3 No step repeats information already shown. Total length is roughly 15–25 s, unless the claim needs more.
- F4 The page is shown as users reach it (app shell, header, sidebar), not a bare route.

**C — Captions and tips**
- C1 Every caption matches what is on screen while it is shown, and changes only after the previous result has closed.
- C2 At 720 px wide every caption and every tip line can be read. Text meant to be read is never half-legible.
- C3 Each caption stays at least 2 s, or 0.3 s per word if longer. A tip stays long enough to read all its lines twice.
- C4 Captions and tips do not cover the proof or the clicked control. A top caption and a tip are never shown at the same time.
- C5 Short English sentences; no internal jargon a QA or PO would not know.

**M — Motion**
- M1 Exactly one cursor, and it moves along human paths. No OS pointer appears.
- M2 The camera pushes in only where something is clicked or typed. Segments that only scroll or read stay at zoom 1 (check `camera.json`).
- M3 No scroll jumps or teleports: every frame-diff spike is an app-owned transition (drawer slide, loading overlay, page change).
- M4 The frame does not cut off the target or the result during a push-in.

**D — Data safety**
- D1 No token, code, session id or secret anywhere: the drawn address bar, page content, tips and captions.
- D2 Only test data: no real customer, applicant or employee personal data (names, ID numbers, documents, faces from real people).
- D3 No other window, notification, menu-bar app or desktop content leaks into the frame.

**J — Delivery**
- J1 Each file is an MP4 under the repo's `docs/videos/` with a new `-vN`; no earlier cut was overwritten.
- J2 If a Jira comment is drafted: one comment holds every cut (before, then after) with one short description; no comparison screenshots unless the user asked for them.

## Report

One fenced block, items in checklist order, then the verdict:

```text
P1 ✓ Ends on the "Saved" toast and the updated row (after-v3 18.2 s).
C2 ✗ after-v3 9.4 s: tip line 3 unreadable at 720 px (f9.4-720.png).
M3 ✗ after-v3 6.1 s: the drawer jumps 400 px in one frame; not an app transition (spike 6.07 s).
D1 cannot verify: url= not provided.

Must fix: C2, M3
Should fix: —
Cannot verify: D1
```

No overall "looks good" without the per-item lines, and no ✓ without having looked at the frames.
