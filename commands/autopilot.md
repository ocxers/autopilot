# /autopilot — Unattended, completion-driven (JS/TS fullstack)

When the user hands off a JavaScript / TypeScript fullstack task to run **unattended** and wants it driven to **100% completion with no self-narrowed scope** — until the task is genuinely complete, blocked by a real external dependency, or explicitly stopped by the user. Continuation is driven by adopting the CONDITION as a standing directive (Step 0), reinforced at stop-time by any Stop hook the project has installed.

**Usage:** `/autopilot <task description or path to a requirements/spec file>`

This command is intentionally strict. It is designed for situations where the user is away — after hours, travel, meetings, or any period where follow-up questions are unlikely.

---

## Step 0 — Adopt the Completion Condition FIRST (before doing anything)

Your VERY FIRST action: read the **CONDITION block at the bottom of this file** and adopt it as your **standing directive** for this run, with `<task>` filled in from `$ARGUMENTS`. These rules OVERRIDE your default stopping behavior for the rest of the session — re-read and re-assert the CONDITION every time you are tempted to stop, and treat "I think I'm done" as a trigger to re-check it, not to stop.

(Do not try to "invoke `/goal`" — a slash command is a user-input feature and cannot be called by the assistant mid-turn; adopting the CONDITION directly is the equivalent and avoids a dead-end. If this project has a completion Stop hook installed, it will additionally enforce this at stop-time; if not, the CONDITION is self-enforced. Either way, never treat the absence of a hook as permission to narrow scope or stop early.)

## The task

$ARGUMENTS

---

## Operating Protocol — follow exactly (the user is away and cannot answer)

### 1. Preflight Before Coding

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

### 2. Map the Full Surface FIRST

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

### 3. Convert Requirements Into a Full Checklist

Your task checklist (TodoWrite / update_plan / equivalent task-tracking tool) = the **FULL** requirement set — one item per requirement line, acceptance criterion, bug symptom, user-visible behavior, and implied compatibility requirement in the source.

Never shrink the list to match what you happened to do. Keep reused or pre-existing behavior **on** the checklist until it has been live-verified.

### 4. Safety Boundaries for Unattended Work

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

### 5. Implementation Discipline

Run the discovered **non-mutating** pre-coding checks/conventions first (read-only lint/typecheck/status — never a command that edits files or starts side-effecting services while unattended). Implement in **small batches**. After each batch:

- Run the smallest relevant verification first.
- Review the diff adversarially (see §9).
- Fix issues before expanding scope.
- Keep the checklist updated.

Prefer existing project patterns over new abstractions. Add dependencies only when they remove real complexity and are justified by the task. If dependencies change, verify lockfile changes and run the relevant build/test matrix.

### 6. JS/TS Verification Matrix

Discover the repo's **actual** commands and run the applicable matrix:

- Type checking: `tsc`, framework typecheck, or `yarn build` if typecheck is embedded there.
- Lint and format: project script if present; otherwise documented local tooling. Do not invent a script that does not exist.
- Unit tests: Jest, Vitest, React Testing Library, or the repo equivalent.
- Integration tests: API, service, database, MSW, contract, schema, or generated-client tests when touched.
- E2E tests: Cypress or Playwright in unattended/headless mode where available. Prefer `cypress run` over an interactive runner.
- Production build: run the production build command for frontend or server bundles when relevant.
- Preview/smoke: serve the built app or start the server and verify the changed flow.

If a command is missing, broken before your change, or documented but not executable, record the evidence and use the closest valid alternative. **`tsc` / build / lint / unit tests are necessary but NOT sufficient.**

### 7. Real Browser Verification — MANDATORY for web apps

**If the project is a web application** (has a frontend that runs in a browser — React, Vue, Angular, Next.js, or any HTML/JS UI), browser verification is **mandatory, not optional.** This is the single most important verification step for web apps — builds and tests pass on broken UIs all the time.

For **any** change in a web app — frontend OR backend (UI, routing, styling, auth, API endpoints, data fetching, permissions, validation, websocket, or any code that affects what the user sees or can do in the browser) — verify in a **real browser** using whatever browser-driving capability your runtime has (chrome-devtools-mcp, a Browser plugin, Playwright, the project's in-app browser, or equivalent) and verify the actual rendered behavior with your own eyes:

- Start the correct local dev server or preview server. Use mock mode or local backend when live credentials are unavailable; if a flow needs the backend running, start it / confirm it.
- Navigate to the actual route.
- Interact with the changed controls.
- Check visible UI state, loading state, empty state, error state, and success state.
- Check console errors and relevant network requests.
- Capture screenshots or browser evidence for the run report. Save them alongside the run log at `docs/autopilot-runs/<run>/screenshots/`; only use `.screenshots/` if the project already has that convention. Never scatter screenshots at the repo root.
- Smoke-test at least one desktop viewport and one mobile/narrow viewport for visual changes.

Don't ask the user to check; don't accept "should work".

**Tripwire:** if you are about to mark any web-app requirement (FE or BE) as `[LIVE]` without having verified the affected flow in a browser, STOP — that is `[CODE]`, not `[LIVE]`. A backend API change is not `[LIVE]` until you've seen the frontend consume it correctly in the browser. If you skip browser verification for a web app, you MUST state the specific reason in the evidence log (e.g. "dev server requires Redis + ES which are not running locally") — "not needed" or "build passed" is not a valid reason. Even without a full backend, you can still verify: page renders without crash, no console errors, correct components appear, routing works.

### 8. Fullstack Runtime Verification

For backend or fullstack changes, verify the runtime path end to end:

- Start required local services, containers, databases, queues, or workers if available.
- Apply local migrations or schema setup only to local/test databases.
- Exercise the API with tests, browser flow, or HTTP calls.
- Confirm request validation, auth/permission behavior, success response, failure response, and persistence side effects.
- Verify websocket / SignalR or background-job behavior where touched.
- Check logs for unexpected errors.

If the real runtime cannot be started because credentials, infrastructure, or external services are missing, prove what was verified locally and mark the remaining path as **⛔ BLOCKED**.

### 9. Adversarial Self-Review Loop — mandatory after every code change

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

### 10. Evidence Log

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

### 11. NO Self-Authored Deferrals + Scope-Narrowing Tripwires

You may **not** decide on your own to skip, defer, or rule anything "later / out of scope / needs a decision". The user is away and cannot approve a cut. **Default = DO IT.**

Do not stop for ordinary difficulty. Work around missing local convenience where possible. For flaky tests or transient services: retry once after a clean restart or cache cleanup; if the same failure repeats, capture logs and classify it as **caused by your change** vs **pre-existing/external** — fix the former before continuing.

The only allowed non-completion is a **hard external blocker you genuinely cannot create or bypass**:

- Missing credentials or no access to a required service.
- Dead external infrastructure or tunnel.
- Required private package unavailable.
- Required product decision absent and no safe default exists.
- Non-local database or production-side operation that would violate §4.

When blocked: fix everything you can around it, then record it as **⛔ BLOCKED** with the exact blocker and what would unblock it — never relabel a blocker as "done" or "not needed".

**Tripwires.** If you catch yourself thinking _"this is just FE" / "the backend already handles it" / "this is good enough" / "I'll note it as a follow-up" / "this decision lets me skip it"_ — **STOP.** That is the failure mode. Re-open the full surface (§2) and either prove no-change with `file:line` or do the work.

### 12. Git Rules

Never run `git add`, `git commit`, `git push`, or open a PR unless the user explicitly asks. Modify files only; the user reviews and commits.

Do not revert user changes. If unrelated files are dirty, leave them alone. If dirty files overlap with your task, read them carefully and work with the current contents.

### 13. Completion Criteria — per-line accounting before claiming done

Mark every requirement line **in the run log (§10)** — this accounting is *recorded* there, not recited in the chat (see §15 for what the user actually sees):

- **✅ `[LIVE]`** — verified end to end in the running app/service.
- **☑️ `[CODE]`** — code verified but live verification was impossible; include **why**, and why this is **not** laziness.
- **⛔ `[BLOCKED]`** — blocked by a real external dependency; include the exact blocker and unblock path.

You may stop **only** when every requirement line is ✅ `[LIVE]` or ⛔ `[BLOCKED]`. A ☑️ `[CODE]`-only item is **not** completion unless live verification is impossible for a documented external reason — anything ☑️ because you were lazy (not blocked) is NOT done; go verify it live.

No "core complete" / "mostly done" / "should work" / "ready for user testing" summaries unless the per-requirement accounting in the run log supports that claim.

The bar for stopping is unchanged by §15 — §15 governs only how much of this reaches the chat.

### 14. Auto-eval as the final step — grade this run independently

As the **last step before your report** (§15) — after all coding and verification, before you write the chat summary — invoke `/autopilot-eval` to score this run and append one row to `~/.claude/autopilot-eval.md`. This is automatic — the user does not trigger it manually.

- **The grader must be independent, not you.** `/autopilot-eval` spawns a fresh judge subagent and re-verifies your ✅ claims hands-on (re-runs tests / re-drives the browser). Do **not** grade from your own `summary.md` — that inherits any lie you made. Let the eval do its job.
- **Report the eval the same short way (§15): its verdict, plus any ✅ item that did not reproduce — nothing else.** No score tables, no dimension breakdowns, no per-criterion commentary. The eval row in `~/.claude/autopilot-eval.md` is the full record; point at it.
- This inline self-eval keeps a fresh-subagent buffer but is still orchestrated by this run, so it is **weaker than a separate manual eval**. If the eval surfaces ✅ items that don't reproduce, those count against completion (§13) — go fix them, don't bury them.
- If `/autopilot-eval` is unavailable, say so once and skip; do not fabricate a scorecard.

### 15. Reporting to the user — short, and in one code block

The full accounting lives in the run log (§10). Emit this block **after §14's eval returns** — it is the last thing you write. What reaches the chat is a SHORT summary inside ONE fenced code block (4 backticks, so nested ``` survive), containing this and nothing beyond it:

- one line per requirement group: what now works
- anything NOT done, and why (blockers, `[CODE]`-only items) — a sentence each
- anything the user must decide or do next
- the eval verdict from §14 (one line), plus any ✅ item that did not reproduce
- the path to the run log

Do NOT put in chat unless asked: command transcripts, test pass/fail counts, pre-existing failures, screenshot paths, the surface map, per-file diffs, or a restatement of what each fix did. Point at the run log instead.

A run where everything worked is a handful of lines, not a screenful.

**This applies to every later turn, not just the final report.** When the user pastes review findings and you fix them, a fixed item is ONE line. Only three things earn more: a finding you believe is a false positive (give the evidence), one you disagree with, and one you did not fix (say why). Do not volunteer test counts, pre-existing failures, or a `[CODE]` vs `[LIVE]` inventory.

**This governs REPORTS only.** It does not apply to output the protocol elsewhere tells you to print — e.g. §14's one-line notice when `/autopilot-eval` is unavailable, or any warning/prompt a step explicitly instructs you to show the user. Print those as specified, outside the block.

**This section changes only what is SAID — never what is DONE or RECORDED.** Every verification in §1–§14 still runs in full, and the run log still carries the complete evidence. Brevity in chat is never a reason to skip a check or thin out the log.

---

## CONDITION (your standing directive — re-read and re-assert it every time you are tempted to stop)

Drive `<task>` to 100% unattended completion for a JavaScript / TypeScript fullstack codebase. These rules OVERRIDE your default stopping behavior. (a) **Preflight first:** inspect repo status, local instructions (CLAUDE.md/AGENTS.md), package manager + lockfile, available npm scripts, runtime versions, env templates, CI/test/build config; trust executable config over docs and note mismatches. (b) **Map ALL layers** — FE / BE / API contracts / SDK+shared types / auth+permissions / websocket+SignalR / workers+jobs / DB+schema+migrations+cache / build+runtime+env / tests+mocks / observability — and justify every "no change" with a `file:line` you actually read; never conclude "not needed / already exists / out of scope / good enough" from a hunch. (c) **The task checklist (TodoWrite / update_plan / equivalent) must cover EVERY requirement line**, not your convenient subset; keep reused/pre-existing behavior on the list until live-verified. (d) **Safety boundaries:** default to DOING, but never deploy to prod/staging/shared, mutate prod/shared data, run irreversible non-local migrations, send real emails/SMS/payments/KYC/sanctions side effects, commit secrets/.env, do broad dependency upgrades, or run destructive git commands without explicit user instruction; prefer local mocks/fixtures/test creds. (e) **Implement in batches**, run the smallest relevant verification after each, and run an **adversarial diff-review loop** (assume the diff is wrong: bugs, regressions, wrong-file/wrong-layer, type holes, auth/validation/XSS, API contract mismatch, broken responsive/a11y, mock-hidden integration bugs) until a full pass finds zero actionable issues. (f) **Run the repo's actual JS/TS verification matrix:** typecheck, lint/format if available, unit tests, integration/contract tests where touched, unattended e2e where available, production build, preview/smoke. (g) **Verify in a real browser yourself** (chrome-devtools-mcp / Browser plugin / Playwright / in-app browser — whatever the runtime has) — start the app (mock mode or local backend), navigate the actual route, interact, check console/network and loading/empty/error/success states, capture screenshots to `docs/autopilot-runs/<run>/screenshots/` (or the project's existing `.screenshots/`), smoke-test desktop + narrow viewport; tests/builds alone are NOT enough. (h) **For backend/fullstack**, start required local services and verify API/runtime/persistence/websocket behavior end to end. (i) **NO self-authored deferrals** — only a hard external blocker (dead infra / missing credentials / no API access / unsafe-without-decision) may leave an item undone, recorded as ⛔ with the exact blocker; never relabel a blocker as "done / not needed". (j) **Maintain** `docs/autopilot-runs/<timestamp>-<task>/summary.md` with checklist, surface map, commands, browser evidence, blockers, and final accounting, excluding secrets/sensitive payloads. (k) **Git:** never add/commit/push/PR unless explicitly asked; never revert unrelated dirty files. (l) **Finish with per-line `[LIVE]` / `[CODE]` / `[BLOCKED]` accounting, written in the run log — not recited in the chat (see §15)**; "exists / implemented" ≠ done, every item (including reused ones) must be LIVE end-to-end verified with evidence. Stop only when every line is ✅ `[LIVE]` or ⛔ `[BLOCKED]`-with-a-real-blocker; `[CODE]`-only is not completion unless live verification is impossible for a documented external reason. If you start thinking "just FE / backend's fine / good enough / follow-up later / a decision lets me skip", that IS the scope-narrowing failure — re-open the full surface and prove-with-`file:line` or do it. (m) **As the last step before your report, run `/autopilot-eval`** to independently grade this run (fresh judge subagent, hands-on re-verification of ✅ claims) and append one row to `~/.claude/autopilot-eval.md`; if it finds ✅ items that don't reproduce, those are NOT done — fix them, don't bury them; never self-grade from your own summary. **Report the eval in one or two lines: its verdict plus any ✅ item that did not reproduce — nothing else** (no score table, no dimension breakdown); the row in `~/.claude/autopilot-eval.md` is the record. (n) **Keep the chat SHORT — §15.** The run log holds the full accounting; what reaches the user is ONE fenced code block (4 backticks), emitted after the eval returns, with one line per requirement group on what now works, a sentence each for anything not done and why, anything they must decide or do next, the eval verdict, and the run-log path — and nothing beyond that. This governs REPORTS only: output a step explicitly tells you to print (a warning, a prompt, the eval-unavailable notice) is printed as specified, outside the block. Do NOT put command transcripts, test pass/fail counts, pre-existing failures, screenshot paths, the surface map, per-file diffs, or a restatement of each fix into the chat unless asked — point at the run log. A run where everything worked is a handful of lines, not a screenful. **This holds on every later turn too:** when the user pastes review findings and you fix them, a fixed item is ONE line; only a suspected false positive (give the evidence), a finding you disagree with, or one you did not fix (say why) earns more. §15 changes only what is SAID — never what is DONE or RECORDED; every check above still runs in full and the log still carries the full evidence.
