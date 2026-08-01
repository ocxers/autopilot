# /autopilot-auto — Unattended coding + automated adversarial review loop

When the user hands off a task to run **fully unattended** — coding to completion AND adversarial review with OpenAI Codex (CLI or Cursor plugin), looping fix→review until Codex approves or safety limits are reached.

**Usage:** `/autopilot-auto <task description or spec path> [--session <id>] [--max-rounds N] [--timeout H]`

This command is intentionally strict, in the same spirit as `/autopilot`. It is designed for situations where the user is away and wants both the coding AND the adversarial review round-tripped with Codex (running as a CLI session or as a Cursor plugin tab) to happen without them shuttling text between two terminals.

---

## Step 0 — Adopt the Completion Condition FIRST (before doing anything)

Your VERY FIRST action: read the **CONDITION block at the bottom of this file** and adopt it as your **standing directive** for this run, with `<task>` filled in from the parsed task description (see Step 1). These rules OVERRIDE your default stopping behavior for the rest of the session — re-read and re-assert the CONDITION every time you are tempted to stop, and treat "I think I'm done" as a trigger to re-check it, not to stop. Completion for this command means: coding done, review loop reached a terminal state (`APPROVED`, `MAX_ROUNDS`, `TIMEOUT`, or `ABORTED`), audit log written, and `/autopilot-eval` run.

(Do not try to "invoke `/autopilot`" or `/make-review-prompt` as slash commands — a slash command is a user-input feature and cannot be called by the assistant mid-turn. This file adopts the entire `/autopilot` operating protocol and the `/make-review-prompt` Template B logic directly, inline, below. Adopting them directly is the equivalent and avoids a dead-end. If this project has a completion Stop hook installed, it will additionally enforce this at stop-time; if not, the CONDITION is self-enforced. Either way, never treat the absence of a hook as permission to narrow scope or stop early.)

## The task

$ARGUMENTS

---

## Step 1 — Parse arguments and session setup

1. **Extract flags** from `$ARGUMENTS`: `--session <id>`, `--max-rounds N` (default `10`), `--timeout H` (default `5`). Everything else, in order, is the task description (or path to a spec file). **Validate numeric flags:** `--max-rounds` must be a positive integer (≥ 1); `--timeout` must be a positive number (> 0). If a flag is present but its value is missing, non-numeric, zero, or negative, stop and report the error — do not silently use the default. If the remaining task description is empty (no non-flag arguments), stop and report that a task is required.
2. **Session ID.**
   - If `--session <id>` was given, use it as-is.
   - Otherwise generate one: `<YYYY-MM-DD-HHMM>-<task-slug>`, where `<task-slug>` = the first 3–4 words of the task description, lowercased, non-alphanumeric characters replaced with hyphens, collapsed, trimmed — such that the full session id (including the timestamp prefix) is at most 64 chars.
3. **Validate** the session ID: it must match `^[A-Za-z0-9-]{1,64}$` (alphanumeric + hyphens only, max 64 chars). If a user-provided `--session` value fails this, stop and report the invalid value — do not silently mutate a user-provided id; you may auto-sanitize only an id you generated yourself.
4. **Create** the directory `.autopilot/reviews/<session-id>/` if it does not already exist.
5. **Gitignore.** Check the repo's `.gitignore` for an entry covering `.autopilot/reviews/`. If missing, add a `.autopilot/reviews/` line (create `.gitignore` if the project has none). This is a file edit, not a git command — it does not violate the "never commit" rule.
6. **Resume check.** Check whether `.autopilot/reviews/<session-id>/channel.md` already exists:
   - **If the file exists but its YAML frontmatter cannot be parsed** (missing/malformed delimiters, invalid YAML, missing `status` field) — treat the file as corrupted. Warn the user (report the session id and the parse error), set `status: ABORTED` in a best-effort rewrite of the frontmatter, and stop. The user must pass a new `--session` value to start fresh.
   - If it exists and its frontmatter `status` is a **non-terminal** state (`IDLE`, `REVIEW_REQUESTED`, `REVIEW_DONE`, `FIX_COMPLETED`) — this is a **resume**. Skip the coding phase (Step 2) and Step 3 (which would re-append a Round 1 request); jump directly into the review loop (Step 4) starting from the state recorded in the frontmatter. Do not re-initialize the file.
     - **Special case: `status` is `IDLE`.** This means the coding phase (Step 2) was not completed before the session was interrupted — there is no code change yet for Codex to review, and the review loop cannot make progress from here (both sides would wait for each other forever). Re-run the coding phase (Step 2) from the beginning, then proceed to Step 3.
   - If it exists and its `status` is a **terminal** state (`APPROVED`, `MAX_ROUNDS`, `TIMEOUT`, `ABORTED`) — warn the user this session already completed (report the terminal status and the summary path) and stop; do not silently overwrite a finished session. If the user explicitly wants to restart, they must pass a new `--session` value.
   - If it does not exist, this is a fresh session — continue to step 7.
7. **Initialize `channel.md`** (fresh sessions only) with YAML frontmatter followed by a markdown body:

   ```yaml
   ---
   session_id: "<session-id>"
   task: "<task description>"
   ticket: "<ticket number if detected, otherwise empty>"
   status: IDLE
   round: 0
   max_rounds: <N>
   timeout_hours: <H>
   started_at: "<ISO 8601 timestamp>"
   updated_by: claude-code
   updated_at: "<ISO 8601 timestamp>"
   ---

   # Review Channel — <session-id>
   ```

   Detect `ticket` by scanning the task description for a ticket-shaped token (e.g. `[A-Z]+-\d+`); leave it empty if none is found. **YAML safety:** ensure all string values (`task`, `ticket`, `session_id`) are properly quoted or use YAML block scalars if they contain characters that would break bare YAML strings (colons, quotes, newlines, `#`, `{`, `[`, etc.).
8. **Print the Codex prompt template** (the exact template in Step 5, below) inside a fenced code block, with `<session-id>` and `<project-path>` substituted for their real values (`<project-path>` = the absolute repository root). After the block, tell the user: "Copy the prompt above into your Codex interactive session. When ready, the review loop will begin automatically after coding completes." Do this even on resume, in case the user needs to re-paste it into a fresh Codex session.

## Step 2 — Coding phase (adopt the `/autopilot` protocol inline)

Skip this step entirely on resume (see Step 1.6). Otherwise, run the full operating protocol below — this is `/autopilot`'s Steps 1–13, adopted directly, not invoked as a slash command. `<task>` = the task description parsed in Step 1.

### 2.1 Preflight Before Coding

Before editing files, inspect and record the project operating context:

- Current working directory and repository root.
- `git status --short`, including unrelated dirty files that must **not** be reverted.
- Applicable local instructions: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, or equivalent.
- Package manager and lockfile: `yarn.lock`, `package-lock.json`, `pnpm-lock.yaml`, or `bun.lockb`.
- Runtime versions from `.nvmrc`, `.node-version`, `package.json#engines`, Docker files, or CI config.
- Available scripts in `package.json`; do **not** assume README commands exist until verified.
- Test, lint, typecheck, build, e2e, and preview commands actually available in the repo.
- Environment templates such as `.env.example`; never read, print, or commit secrets from `.env` unless the user explicitly asks and it is necessary.
- CI workflow files, Docker/compose files, deployment config, and generated-code config if relevant.

If documentation and `package.json` disagree, trust the executable project configuration first and note the mismatch in the final report.

### 2.2 Map the Full Surface FIRST

Before coding, enumerate **every** layer the task could touch:

- Frontend: routes, pages, components, state, hooks, API clients, styles, assets, i18n, accessibility.
- Backend: routes, controllers, services, validation, auth, permissions, jobs, queues, workers.
- Data layer: schemas, migrations, seeds, indexes, ORM models, cache, persistence, search.
- API contracts: DTOs, OpenAPI/GraphQL schema, generated clients, SDKs, shared types.
- Realtime: websocket, SignalR, SSE, reconnect behavior, event schemas.
- Build/runtime: Vite, Next.js, Node server, bundling, env vars, Docker, CI, deploy path.
- Testing: unit, integration, e2e, fixtures, mocks, MSW handlers, test data.
- Observability: logging, metrics, tracing, error boundaries, user-facing error states.

For each layer, decide **`change` / `no change` with code evidence (`file:line` you actually read)**. The phrases **"already enough" / "already exists" / "backend not needed" / "out of scope" / "good enough" are FORBIDDEN as conclusions** unless backed by a cited `file:line`. When uncertain → assume it's in scope and investigate. If the task truly cannot touch a layer, prove it with code evidence.

### 2.3 Convert Requirements Into a Full Checklist

Your task checklist (TodoWrite / update_plan / equivalent task-tracking tool) = the **FULL** requirement set — one item per requirement line, acceptance criterion, bug symptom, user-visible behavior, and implied compatibility requirement in the source.

Never shrink the list to match what you happened to do. Keep reused or pre-existing behavior **on** the checklist until it has been live-verified.

### 2.4 Safety Boundaries for Unattended Work

Default to doing the work, but do **not** cross these boundaries without explicit user instruction:

- Do not deploy to production, staging, or shared environments.
- Do not mutate production or shared customer data.
- Do not run irreversible database migrations against non-local databases.
- Do not send real emails, SMS, payments, **KYC checks, sanctions/AML checks**, or other external side-effect operations unless the task explicitly authorizes that target environment.
- Do not commit secrets, certificates, `.env`, private keys, tokens, or local credentials.
- Do not perform broad dependency upgrades or framework migrations unless required by the task.
- Do not rewrite unrelated architecture or reformat unrelated files.
- Do not use destructive git commands (`reset --hard`, `checkout --`, branch deletion) unless explicitly instructed.

Use local mocks, fixtures, test credentials, local databases, or documented sandbox environments where possible. If a real external dependency is required and unavailable, mark the item as **⛔ BLOCKED** with exact details.

### 2.5 Implementation Discipline

Run the discovered **non-mutating** pre-coding checks/conventions first (read-only lint/typecheck/status — never a command that edits files or starts side-effecting services while unattended). Implement in **small batches**. After each batch:

- Run the smallest relevant verification first.
- Review the diff adversarially (see §2.9).
- Fix issues before expanding scope.
- Keep the checklist updated.

Prefer existing project patterns over new abstractions. Add dependencies only when they remove real complexity and are justified by the task. If dependencies change, verify lockfile changes and run the relevant build/test matrix.

### 2.6 JS/TS Verification Matrix

Discover the repo's **actual** commands and run the applicable matrix:

- Type checking: `tsc`, framework typecheck, or `yarn build` if typecheck is embedded there.
- Lint and format: project script if present; otherwise documented local tooling. Do not invent a script that does not exist.
- Unit tests: Jest, Vitest, React Testing Library, or the repo equivalent.
- Integration tests: API, service, database, MSW, contract, schema, or generated-client tests when touched.
- E2E tests: Cypress or Playwright in unattended/headless mode where available. Prefer `cypress run` over an interactive runner.
- Production build: run the production build command for frontend or server bundles when relevant.
- Preview/smoke: serve the built app or start the server and verify the changed flow.

If a command is missing, broken before your change, or documented but not executable, record the evidence and use the closest valid alternative. **`tsc` / build / lint / unit tests are necessary but NOT sufficient.**

### 2.7 Real Browser Verification — you do it yourself

For any UI, routing, styling, auth, API wiring, or user-flow change, verify in a **real browser** using whatever browser-driving capability your runtime has (chrome-devtools-mcp, a Browser plugin, Playwright, the project's in-app browser, or equivalent) and verify the actual rendered behavior with your own eyes:

- Start the correct local dev server or preview server. Use mock mode or local backend when live credentials are unavailable; if a flow needs the backend running, start it / confirm it.
- Navigate to the actual route.
- Interact with the changed controls.
- Check visible UI state, loading state, empty state, error state, and success state.
- Check console errors and relevant network requests.
- Capture screenshots or browser evidence for the run report. Save them alongside the run log at `docs/autopilot-runs/<run>/screenshots/`; only use `.screenshots/` if the project already has that convention. Never scatter screenshots at the repo root.
- Smoke-test at least one desktop viewport and one mobile/narrow viewport for visual changes.

Don't ask the user to check; don't accept "should work".

### 2.8 Fullstack Runtime Verification

For backend or fullstack changes, verify the runtime path end to end:

- Start required local services, containers, databases, queues, or workers if available.
- Apply local migrations or schema setup only to local/test databases.
- Exercise the API with tests, browser flow, or HTTP calls.
- Confirm request validation, auth/permission behavior, success response, failure response, and persistence side effects.
- Verify websocket / SignalR or background-job behavior where touched.
- Check logs for unexpected errors.

If the real runtime cannot be started because credentials, infrastructure, or external services are missing, prove what was verified locally and mark the remaining path as **⛔ BLOCKED**.

### 2.9 Adversarial Self-Review Loop — mandatory after every code change

Review your own diff **as if it is wrong**. Hunt for:

- Wrong file or wrong layer / wrong-service mistakes.
- Missed requirement or acceptance criterion.
- Regression in existing behavior.
- Type holes, null/undefined cases, race conditions, stale state, cache invalidation.
- Auth, permission, validation, injection, XSS, CSRF, data leakage, secret exposure.
- API contract mismatch between frontend and backend.
- Broken responsive layout, accessibility, keyboard flow, focus state, or loading/error state.
- Flaky test, insufficient fixture, or mock that hides a real integration issue.

Fix every issue found → review **AGAIN** → repeat **until a full pass turns up zero actionable problems**. Do not move on after a single review. Optionally spawn a `code-reviewer` subagent for a second adversarial pass.

Note: this is your own self-review during coding, distinct from the external Codex adversarial review loop that starts in Step 3 below. Both are required — self-review does not replace the Codex loop.

### 2.10 Evidence Log

Create or update an unattended run log:

`docs/autopilot-runs/<YYYY-MM-DD-HHMM>-<short-task-name>/summary.md`

Include:

- Task source and parsed checklist.
- Preflight findings.
- Surface map with `change` / `no change` and `file:line` evidence.
- Commands run, exit status, and important output summary.
- Browser verification steps and screenshot paths (screenshots under `docs/autopilot-runs/<run>/screenshots/`).
- Known blockers with exact unblock conditions.
- Final per-requirement accounting.

Do not paste secrets, tokens, private URLs, or customer-sensitive payloads into the log.

### 2.11 NO Self-Authored Deferrals + Scope-Narrowing Tripwires

You may **not** decide on your own to skip, defer, or rule anything "later / out of scope / needs a decision". The user is away and cannot approve a cut. **Default = DO IT.**

Do not stop for ordinary difficulty. Work around missing local convenience where possible. For flaky tests or transient services: retry once after a clean restart or cache cleanup; if the same failure repeats, capture logs and classify it as **caused by your change** vs **pre-existing/external** — fix the former before continuing.

The only allowed non-completion is a **hard external blocker you genuinely cannot create or bypass**:

- Missing credentials or no access to a required service.
- Dead external infrastructure or tunnel.
- Required private package unavailable.
- Required product decision absent and no safe default exists.
- Non-local database or production-side operation that would violate §2.4.

When blocked: fix everything you can around it, then record it as **⛔ BLOCKED** with the exact blocker and what would unblock it — never relabel a blocker as "done" or "not needed".

**Tripwires.** If you catch yourself thinking _"this is just FE" / "the backend already handles it" / "this is good enough" / "I'll note it as a follow-up" / "this decision lets me skip it"_ — **STOP.** That is the failure mode. Re-open the full surface (§2.2) and either prove no-change with `file:line` or do the work.

### 2.12 Git Rules

Never run `git add`, `git commit`, `git push`, or open a PR unless the user explicitly asks. Modify files only; the user reviews and commits.

Do not revert user changes. If unrelated files are dirty, leave them alone. If dirty files overlap with your task, read them carefully and work with the current contents.

### 2.13 Completion Criteria — per-line accounting before claiming coding is done

Mark every requirement line:

- **✅ `[LIVE]`** — verified end to end in the running app/service.
- **☑️ `[CODE]`** — code verified but live verification was impossible; include **why**, and why this is **not** laziness.
- **⛔ `[BLOCKED]`** — blocked by a real external dependency; include the exact blocker and unblock path.

The coding phase (Step 2) is only complete when every requirement line is ✅ `[LIVE]` or ⛔ `[BLOCKED]`. A ☑️ `[CODE]`-only item is **not** completion unless live verification is impossible for a documented external reason — anything ☑️ because you were lazy (not blocked) is NOT done; go verify it live.

No "core complete" / "mostly done" / "should work" / "ready for user testing" summaries unless the per-requirement accounting supports that claim.

Important: unlike plain `/autopilot`, do **not** run `/autopilot-eval` at the end of this coding phase — that only happens once at the very end of the whole command, after the review loop terminates (Step 6). Proceed straight to Step 3.

## Step 3 — Transition to review loop

Skip this step on resume (see Step 1.6) — a resumed session already has its Round N review request in the channel file.

1. Generate a code review prompt by following the `/make-review-prompt` **Template B** (code change review) logic inline — do not invoke `/make-review-prompt` as a slash command:
   - Read the current diff (`git diff`, plus `git diff --stat` for a file list; include staged and unstaged changes made during Step 2).
   - Identify: the absolute repo path, a one-line stack description, the current branch name, and what the change claims to do (1–2 lines).
   - Identify the highest-risk areas spotted while skimming the diff (named files/functions).
   - Fill in Template B with these real values, and add 3–8 artifact-specific attack vectors naming the real riskiest functions/decisions from this diff (in addition to Template B's 9 standard attack vectors).
   - Follow Template B's rules of engagement and output format exactly (adversarial framing, `file:line` evidence requirement, no praise, BLOCKER/MAJOR/MINOR/QUESTION output grouping, explicit verdict).
2. Append the review prompt to `channel.md`'s markdown body:

   ```markdown
   ## Round 1

   ### Review Request (claude-code, <timestamp>)

   <review prompt content>
   ```

3. Update the frontmatter: `status: REVIEW_REQUESTED`, `round: 1`, `updated_by: claude-code`, `updated_at: <timestamp>`.

If `git diff` shows no code changes at all (task required no code changes), skip the review loop entirely — go directly to Step 6 (Wrap-up), noting in the audit log that the review loop was skipped because there was nothing to review.

## Step 4 — Review loop (poll for Codex feedback)

Poll every **30 seconds**. On each poll iteration:

1. Read `channel.md` and parse the YAML frontmatter: `status`, `round`, `started_at`, `max_rounds`, `timeout_hours`. **If the channel file cannot be read, or its YAML frontmatter fails to parse** (missing/malformed delimiters, invalid YAML, missing required fields) — do not guess or repair it silently: log the error (append a note under a `### Error (claude-code, <timestamp>)` heading to whatever body content is salvageable, or create a minimal new file with just an error note and a best-effort frontmatter block if the file is unreadable/empty), set `status: ABORTED`, `updated_by: claude-code`, `updated_at: <timestamp>`, and go to Step 6 immediately — skip the rest of this polling iteration.
2. **Safety checks — run these FIRST, every poll, before anything else:**
   - If `round > max_rounds` → update frontmatter to `status: MAX_ROUNDS`, `updated_by: claude-code`, `updated_at: <timestamp>`. Go to Step 6.
   - If current time minus `started_at` exceeds `timeout_hours` hours → update frontmatter to `status: TIMEOUT`, `updated_by: claude-code`, `updated_at: <timestamp>`. Go to Step 6.
   - If `status` is `APPROVED`, `ABORTED`, `MAX_ROUNDS`, or `TIMEOUT` → go to Step 6 (this covers both Claude Code's own transitions and a user-triggered `ABORTED`, or Codex-triggered `APPROVED`).
3. **If `status == REVIEW_DONE`** (Codex has written feedback — it is Claude Code's turn):
   - Read the latest "Review Feedback" section from the markdown body (the most recent round).
   - Parse findings grouped by BLOCKER / MAJOR / MINOR / QUESTION, and Codex's stated verdict.
   - **If there are NO BLOCKER or MAJOR findings** (Codex set `REVIEW_DONE` but only listed MINOR/QUESTION items — severity classification governs, not Codex's verdict text):
     - Update frontmatter: `status: APPROVED`, `updated_by: claude-code`, `updated_at: <timestamp>`.
     - Append an acknowledgment section to `channel.md` (e.g. "All remaining findings are MINOR/QUESTION; acknowledged, no code changes required: ..." with a one-line justification per item).
     - Go to Step 6.
   - **If there ARE BLOCKER or MAJOR findings:**
     - Fix each BLOCKER and MAJOR finding. Apply the same implementation discipline as the coding phase (§2.5–2.9): small batches, run tests/typecheck, browser verification if UI changes, adversarial self-review of the fix itself.
     - After all fixes, append a fix summary to `channel.md`:

       ```markdown
       ### Fix Summary (claude-code, <timestamp>)

       **Findings addressed:**
       - [BLOCKER] <title>: <what was done>
       - [MAJOR] <title>: <what was done>

       **MINOR/QUESTION acknowledged:**
       - [MINOR] <title>: <response>

       **Verification:** <tests run, results>
       ```

     - Increment `round`. Append a new round heading `## Round <new-round-number>` to the channel file body, then append the fix summary section under it (the `### Fix Summary` block above goes inside this round).
     - Update frontmatter: `status: FIX_COMPLETED`, `round: <new value>`, `updated_by: claude-code`, `updated_at: <timestamp>`.
     - Continue polling (do not go to Step 6 — wait for Codex's re-review).
4. **If `status` is anything else** (`REVIEW_REQUESTED`, `FIX_COMPLETED` — it is Codex's turn, Claude Code is waiting):
   - Check for a stall: if `updated_at` is more than 30 minutes in the past and the expected writer is Codex, print a warning in the chat session (not in the channel file): "⚠️ No response from Codex for 30+ minutes. Is the Codex session still running?" Print this warning at most once per stall episode — do not repeat it every poll; only print a new one if `updated_at` has changed since the last warning.
   - Wait 30 seconds and re-check from step 1.

Never skip a round. Never write to the channel file when it is not your turn (i.e. never write while `status` is `REVIEW_REQUESTED` or `FIX_COMPLETED`), with one exception: the safety-check transitions in sub-step 4.2 (`MAX_ROUNDS`/`TIMEOUT`), which are Claude Code's exclusive responsibility at any time. The stall warning (sub-step 4.4) is printed to the chat session only — it never touches the channel file.

## Step 5 — Codex prompt template

This is the exact template printed at session setup (Step 1.8) and reprinted here for reference. It must always be printed inside a fenced code block for easy copying. `<session-id>` and `<project-path>` are literal placeholders in the text below — when printing it to the user, substitute in the real session id and the absolute repository root.

```
You are an adversarial code reviewer participating in an automated review loop.
Your communication channel is a shared file in the project repository.

## Your Role
- You are the REVIEWER. You do NOT write or fix code. You only review and
  provide feedback.
- You communicate through: <project-path>/.autopilot/reviews/<session-id>/channel.md
- You share this channel with Claude Code, which is the CODER on the other end.

## Protocol

1. Read the channel file at <project-path>/.autopilot/reviews/<session-id>/channel.md
2. Check the `status` field in the YAML frontmatter.
3. Act based on the status:

   - If status is `REVIEW_REQUESTED` or `FIX_COMPLETED`:
     a. Read the latest section in the markdown body (Review Request or Fix Summary).
     b. Read the actual code changes: run `git diff` in <project-path> to see
        the current state.
     c. If this is a re-review (FIX_COMPLETED), focus on:
        - Whether previous findings were actually fixed
        - Whether fixes introduced new issues
        - Any remaining issues from prior rounds
     d. Perform an adversarial code review. Assume the code is buggy until
        proven correct. Follow the attack vectors in the review prompt (Round 1)
        for guidance.
     e. Write your findings in the channel file:
        - Append a new section: `### Review Feedback (codex, <timestamp>)`
        - Group findings as BLOCKER / MAJOR / MINOR / QUESTION
        - Each finding: one-line title, file:line evidence, failure scenario,
          concrete fix
        - End with verdict: "Safe to merge" or "Fix these before merge: ..."
     f. Update the YAML frontmatter:
        - If safe to merge: set `status: APPROVED`
        - If fixes needed: set `status: REVIEW_DONE`
        - Set `updated_by: codex` and `updated_at: <current ISO timestamp>`

   - If status is `REVIEW_DONE` or `IDLE`: wait — it is Claude Code's turn.
   - If status is `APPROVED`, `MAX_ROUNDS`, `TIMEOUT`, or `ABORTED`: stop,
     the loop is over.

4. After acting (or if it is not your turn), wait 30 seconds and check the
   file again.
5. Continue this loop until the status is a terminal state (APPROVED,
   MAX_ROUNDS, TIMEOUT, ABORTED).

## Rules
- Do NOT edit any source code files. Only read code and write to the channel file.
- Do NOT trust the coder's claims — verify by reading the actual code.
- Cite file:line for every finding.
- No praise. Only defects, risks, and gaps.
- Be thorough but fair — only flag real issues, not style preferences.
```

## Step 6 — Wrap-up

1. Write the final audit log to `.autopilot/reviews/<session-id>/summary.md`:
   - Session ID, task, ticket number.
   - Total rounds completed.
   - Per-round summary: findings count by severity, fixes applied.
   - Final verdict and termination reason (`APPROVED` / `MAX_ROUNDS` / `TIMEOUT` / `ABORTED`).
   - Total elapsed time (from `started_at` to now).
2. Report the outcome to the user in the chat, including the termination reason and a pointer to both `channel.md` (full transcript) and `summary.md` (audit log). If the outcome is `MAX_ROUNDS`, `TIMEOUT`, or `ABORTED`, clearly state the remaining unresolved findings so the user knows exactly what's outstanding.
3. Run `/autopilot-eval` as the final grading step (same as `/autopilot` Step 14) — this grades the whole run (coding + review loop), not just the coding phase. If `/autopilot-eval` is unavailable, say so once and skip; do not fabricate a scorecard.

---

## CONDITION (your standing directive — re-read and re-assert it every time you are tempted to stop)

Drive `<task>` to 100% unattended completion for a JavaScript / TypeScript fullstack codebase, followed by a fully automated adversarial review loop with Codex via the shared channel file, and only then finish. These rules OVERRIDE your default stopping behavior. (a) **Preflight first:** inspect repo status, local instructions (CLAUDE.md/AGENTS.md), package manager + lockfile, available npm scripts, runtime versions, env templates, CI/test/build config; trust executable config over docs and note mismatches. (b) **Map ALL layers** — FE / BE / API contracts / SDK+shared types / auth+permissions / websocket+SignalR / workers+jobs / DB+schema+migrations+cache / build+runtime+env / tests+mocks / observability — and justify every "no change" with a `file:line` you actually read; never conclude "not needed / already exists / out of scope / good enough" from a hunch. (c) **The task checklist (TodoWrite / update_plan / equivalent) must cover EVERY requirement line**, not your convenient subset; keep reused/pre-existing behavior on the list until live-verified. (d) **Safety boundaries:** default to DOING, but never deploy to prod/staging/shared, mutate prod/shared data, run irreversible non-local migrations, send real emails/SMS/payments/KYC/sanctions side effects, commit secrets/.env, do broad dependency upgrades, or run destructive git commands without explicit user instruction; prefer local mocks/fixtures/test creds. (e) **Implement in batches**, run the smallest relevant verification after each, and run an **adversarial diff-review loop** (assume the diff is wrong: bugs, regressions, wrong-file/wrong-layer, type holes, auth/validation/XSS, API contract mismatch, broken responsive/a11y, mock-hidden integration bugs) until a full pass finds zero actionable issues. (f) **Run the repo's actual JS/TS verification matrix:** typecheck, lint/format if available, unit tests, integration/contract tests where touched, unattended e2e where available, production build, preview/smoke. (g) **Verify in a real browser yourself** (chrome-devtools-mcp / Browser plugin / Playwright / in-app browser — whatever the runtime has) — start the app (mock mode or local backend), navigate the actual route, interact, check console/network and loading/empty/error/success states, capture screenshots to `docs/autopilot-runs/<run>/screenshots/` (or the project's existing `.screenshots/`), smoke-test desktop + narrow viewport; tests/builds alone are NOT enough. (h) **For backend/fullstack**, start required local services and verify API/runtime/persistence/websocket behavior end to end. (i) **NO self-authored deferrals** — only a hard external blocker (dead infra / missing credentials / no API access / unsafe-without-decision) may leave an item undone, recorded as ⛔ with the exact blocker; never relabel a blocker as "done / not needed". (j) **Maintain** `docs/autopilot-runs/<timestamp>-<task>/summary.md` with checklist, surface map, commands, browser evidence, blockers, and final accounting, excluding secrets/sensitive payloads. (k) **Git:** never add/commit/push/PR unless explicitly asked; never revert unrelated dirty files. (l) **Coding phase finishes with per-line `[LIVE]` / `[CODE]` / `[BLOCKED]` accounting**; "exists / implemented" ≠ done, every item (including reused ones) must be LIVE end-to-end verified with evidence. The coding phase is complete only when every line is ✅ `[LIVE]` or ⛔ `[BLOCKED]`-with-a-real-blocker; `[CODE]`-only is not completion unless live verification is impossible for a documented external reason. If you start thinking "just FE / backend's fine / good enough / follow-up later / a decision lets me skip", that IS the scope-narrowing failure — re-open the full surface and prove-with-`file:line` or do it. (m) **After coding is complete, enter the review loop.** Generate a code review prompt (Template B logic from `/make-review-prompt`, adopted inline — never invoked as a slash command), write it to the channel file at `.autopilot/reviews/<session-id>/channel.md`, and poll for Codex feedback every 30 seconds. When Codex writes feedback: parse findings, fix all BLOCKER/MAJOR issues, run verification, write a fix summary to the channel file, and wait for Codex's re-review. Loop until Codex approves (`APPROVED`), max rounds is reached (default 10), timeout expires (default 5 hours), or the user aborts. Never skip the review loop — coding without review is NOT complete for this command. (n) **Channel file is the single source of truth for review state.** Read and write the YAML frontmatter `status` field to coordinate turns. Only write when it is your turn (status `REVIEW_DONE` means it is your turn to fix; status `REVIEW_REQUESTED` or `FIX_COMPLETED` means it is Codex's turn — do not write in that case), with one exception: the safety-check transitions to `MAX_ROUNDS`/`TIMEOUT`, which are exclusively yours at any time. Stall warnings go to the chat session, never to the channel file. Never skip a round, never overwrite Codex's feedback without reading and acting on it first. (o) **Fix discipline during the review loop.** Apply the same rigor as the coding phase: run tests, typecheck, browser verification if UI. An adversarial reviewer will catch sloppy fixes — do it right the first time, not the fast way. (p) **As the final action, run `/autopilot-eval`** to independently grade the complete run — coding AND the review loop (fresh judge subagent, hands-on re-verification of ✅ claims) — and append one row to `~/.claude/autopilot-eval.md`; if it finds ✅ items that don't reproduce, those are NOT done — fix them, don't bury them; never self-grade from your own `summary.md`.
