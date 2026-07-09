---
description: Generate a self-contained adversarial review prompt (requirements or code) to hand to another reviewer
argument-hint: "[requirements|code] [optional target: path | git ref | topic]"
---

# /make-review-prompt — generate an adversarial Review Prompt

Produce a **self-contained, copy-pasteable adversarial review prompt** that the user can hand to
another reviewer (a human, a fresh agent session, or a code-review subagent) to stress-test either a
**requirements/spec document** or a **code change**. The generated prompt must assume the artifact
is wrong until proven right, demand `file:line` evidence, forbid praise, and end with an explicit
verdict.

**This command does NOT perform the review.** It only generates the prompt. Do not edit or create
any files, and do not run the review yourself.

**Usage:** `/make-review-prompt [requirements|code] [target]`
- `$ARGUMENTS` = an optional mode keyword followed by an optional target.
- Mode keywords → **requirements**: `requirements`, `req`, `spec`, `prd`, `design`, `plan`.
  **code**: `code`, `diff`, `pr`, `impl`, `implementation`, `review`.
- Target (optional): a file path, a git ref/range (e.g. `HEAD~3..HEAD`, `main...`), or a free-text
  topic. If omitted, infer it (see Step 1).
- Examples:
  - `/make-review-prompt requirements tickets/EDU-2605/requirements.md`
  - `/make-review-prompt code`  (auto-targets the current uncommitted diff)
  - `/make-review-prompt src/components/Foo/Foo.tsx`  (mode auto-detected → code)
  - `/make-review-prompt`  (both mode and target auto-detected)

---

## Step 1 — Resolve mode and target (do this first)

1. **Mode.** If a mode keyword is present in `$ARGUMENTS`, use it. Otherwise **auto-detect**:
   - If the target is a path ending in a source extension (`.ts .tsx .js .jsx .py .go .rs .java .rb
     .css .scss .vue .svelte …`) or is a git ref/range → **code**.
   - If the target is a `.md`/`.txt` under `tickets/`, `docs/`, `spec*`, `plan*`, or its name/heading
     reads as a requirements/spec/PRD/design doc → **requirements**.
   - If no target: run `git status --porcelain` and `git diff --stat`. If there are uncommitted code
     changes (or staged changes) → **code**, targeting that diff. If the most recent thing worked on
     in this conversation is a spec/requirements/plan doc → **requirements**, targeting it.
   - If still genuinely ambiguous, ask the user once (AskUserQuestion) which mode they want. Do not
     guess blindly.

2. **Target.** Resolve to something concrete and name it explicitly in the generated prompt:
   - requirements → the exact doc path (and any sibling assets, e.g. `*.png` screenshots in the same
     folder — list them so the reviewer opens them).
   - code → the exact git range or file list. Prefer a diff range (`git diff`, a branch range, or a
     PR). If none is obvious, ask.

3. **Read enough to specialize the prompt — but do NOT do the review.** Skim the target and the key
   files/symbols it names so the generated prompt can call out the artifact's most load-bearing and
   most fragile assumptions by name (specific files, functions, decisions). A generic template is
   weak; a prompt that names *this* artifact's riskiest claims is strong. Spend a few tool calls
   here, no more.

---

## Step 2 — Build the prompt

Pick the matching template below and fill in the bracketed slots with real, specific values from
Step 1. The reviewer may be a fresh session with zero conversation context — include the absolute
repo path and exact branch/ref so they can locate everything on their own. Bake in
**artifact-specific attack vectors**: after the shared checklist, add 3–8 numbered items that target
the load-bearing assumptions, riskiest decisions, and likely-incomplete areas you found while
skimming. Name real files, functions, and decisions — no placeholders.

Keep these invariants in every generated prompt:
- Opens by framing the reviewer as adversarial ("break it, assume wrong until proven right").
- "Rules of engagement": read the real source before asserting; cite `file:line`; re-verify the
  artifact's own references rather than trusting them; no praise/summary of what's good; mark
  UNVERIFIED when it can't be checked; do not edit anything.
- Ends with a fixed output format: findings grouped **BLOCKER / MAJOR / MINOR / QUESTION**, each with
  a one-line title, `file:line` evidence, why it breaks or is unproven, and a concrete fix; then an
  explicit **verdict**.

### Template A — Requirements / spec review

    You are an adversarial reviewer. BREAK this requirements document; do not praise it. Assume it
    is wrong until proven right. This is a spec review BEFORE code is written — every flawed
    assumption caught now saves a rework round.

    # Context
    - Repo: [absolute repo path] — [stack one-liner], branch [name].
    - Spec under review: [exact path].
    - Supporting assets: [screenshots / linked docs / tickets — exact paths].
    - The spec's central claim(s): [1–3 load-bearing claims, in your words].

    # Rules of engagement
    - READ the actual source/design before asserting anything. Every claim MUST cite file:line.
    - Do NOT trust the spec's own file/line references — re-verify them against the code.
    - No praise, no "what's good" summary. Only defects, gaps, wrong assumptions, risks.
    - If something can't be verified from available material, say so and mark it UNVERIFIED.
    - Do not edit any file. Review only.

    # Attack vectors — work through EACH
    1. Hidden/unstated assumptions — list them and test each against codebase reality.
    2. Scope inventory completeness — independently enumerate (grep/search) the things the spec
       claims to cover; find anything missing, mislabeled, or wrongly declared out-of-scope.
    3. Feasibility — can the proposed solution actually be built as described in THIS codebase?
       Find the load-bearing technical assumption and try to falsify it with code evidence.
    4. Edge cases & failure modes the spec ignores (async/late data, empty/zero, error paths,
       responsive/mobile, concurrency, permissions/access).
    5. Acceptance criteria — are they objectively testable and sufficient to catch the risks above?
       Name any missing criterion.
    6. Non-functionals — performance, accessibility, security, i18n, theming — omitted or hand-waved?
    7. Internal contradictions & ambiguity — anywhere two parts of the spec disagree or a term is
       undefined.
    8. Decision soundness — for each explicit decision the spec locks in, argue the strongest case
       AGAINST it. Which decision is most likely wrong?
    [+ artifact-specific vectors naming the real riskiest claims]

    # Output format
    Findings grouped BLOCKER / MAJOR / MINOR / QUESTION. Each: one-line title, file:line evidence,
    why it breaks or is unproven, concrete fix or spec change. End with an explicit verdict:
    "Implementable as written" OR "Needs these changes before coding: …". If a locked decision is
    unsound, say which and why.

### Template B — Code change review

    You are an adversarial reviewer. Try to BREAK this change; do not praise it. Assume it is buggy
    until proven correct. Your job is to find real defects before they merge.

    # Context
    - Repo: [absolute repo path] — [stack one-liner], branch [name].
    - Change under review: [git range / PR / file list].
    - What it claims to do: [1–2 lines].
    - Highest-risk areas you spotted while skimming: [named files/functions].

    # Rules of engagement
    - READ the actual diff AND the surrounding code it touches. Every claim MUST cite file:line.
    - Do NOT trust the PR description or comments — verify behavior against the code.
    - Trace at least one concrete failing input/state → wrong output for each correctness finding.
    - No praise, no summary of what's good. Only defects, risks, gaps.
    - If a concern can't be confirmed, mark it UNVERIFIED rather than asserting it.
    - Do not edit any file. Review only.

    # Attack vectors — work through EACH
    1. Correctness & edge cases — null/undefined, empty, boundary, off-by-one, unexpected types;
       construct a concrete input that breaks it.
    2. Error handling & failure paths — swallowed errors, unhandled rejections, partial failure,
       retry/rollback correctness.
    3. Concurrency / ordering / races — async ordering, stale closures, effect deps, cache/state
       consistency.
    4. Security — injection, authz/IDOR, secret handling, unsafe input trust, over-broad access.
    5. Performance — N+1, unnecessary re-renders/allocations, blocking work, missing memoization
       where it matters (and NOT where it doesn't).
    6. API/contract & backward compatibility — callers, schemas, cross-system messages, migrations.
    7. Regression surface — existing behaviors this could break; name each and whether the change
       touches it.
    8. Reuse/duplication & convention adherence — does it re-implement something that exists; does it
       follow the project's patterns (types, naming, no forbidden anti-patterns)?
    9. Test coverage — what's untested that should be; is any test weakened/skipped to pass?
    [+ artifact-specific vectors naming the real riskiest functions/decisions]

    # Output format
    Findings grouped BLOCKER / MAJOR / MINOR / QUESTION. Each: one-line title, file:line evidence, a
    concrete failure scenario (input/state → wrong result), and a concrete fix. End with an explicit
    verdict: "Safe to merge" OR "Fix these before merge: …".

---

## Step 3 — Output

Emit the finished prompt as **one fenced code block** so the user can copy it in a single click. Do
not nest triple backticks inside it — use indentation for any inline examples. Outside the block,
add at most 2–3 short lines (in the language the user is conversing in) noting: the detected
**mode** and **target**, and where you deliberately sharpened the prompt (the artifact-specific
vectors you added). Then offer to dispatch a reviewer agent with this prompt if the user wants.
