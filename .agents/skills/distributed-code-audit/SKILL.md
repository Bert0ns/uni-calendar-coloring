---
name: distributed-code-audit
description: >-
  Conducts an in-depth, scalable code audit across a large or growing codebase by
  semantically partitioning the repository, launching dual-persona review subagents
  in parallel, synthesizing findings into an interactive HTML dashboard, and
  authoring an incremental remediation master plan. Use when the user requests
  a comprehensive audit, deep review, full codebase quality inspection, or
  multi-agent health assessment.
---

# Distributed Code Audit & Progressive Remediation Skill

This skill guides the agent through a structured process to audit and remediate complex codebases without context window degradation or superficial reviews.

**Phases 1–3 (Audit)** run standalone to produce an interactive scorecard report. **Phases 4–6 (Remediation)** are optional and only executed when the user explicitly requests fixes.

---

## Workflow Overview

```text
                        ┌─────────────────────────────────────────────────────┐
                        │              AUDIT (always)                         │
                        │                                                     │
                        │  1. Semantic       2. Parallel        3. HTML       │
                        │     Partitioning ──► Dual-Persona ──► Dashboard     │
                        │                      Audits            Report       │
                        └──────────────────────────────┬──────────────────────┘
                                                       │
                                          (only if user requests fixes)
                                                       │
                        ┌──────────────────────────────▼──────────────────────┐
                        │            REMEDIATION (on request)                 │
                        │                                                     │
                        │  4. Master          5. Incremental    6. Verify     │
                        │     Remediation ──►    Partition  ──►    &          │
                        │     Plan               Fixes           Commit       │
                        └─────────────────────────────────────────────────────┘
```

---

## Phase 1: Semantic Partitioning (Divide et Impera)

When a codebase exceeds ~15 source files, reviewing everything in a single prompt causes context saturation and missed edge cases. Partition the repository into cohesive domains.

1. **Discover Boundaries:** Inspect the repository layout (package manifest, route hierarchy, store directories, API clients, config files).
2. **Cluster into 4–8 Semantic Partitions** based on the actual domain of the project. Example partition categories (adapt to each project):
   - Entry points, navigation, routing & authentication
   - Core business logic, real-time engines & state management
   - External API clients, data ingestion & caching layers
   - Rich interactive components (media players, maps, editors)
   - Content presentation layers (feeds, lists, grids, transformers)
   - Settings, preferences, notifications & shared utilities
3. **Map Exact File Lists:** For each partition, explicitly list every source file, hook, component, test, and type definition. If a single partition exceeds ~40 files, split it further.

---

## Phase 2: Parallel Dual-Persona Review

For each semantic partition, spawn **two distinct review subagents** with complementary adversarial personas using `invoke_subagent` (recommended `TypeName: "code-reviewer"` or `inherit`).

> **Resource guideline:** Launch at most 3–4 partitions in parallel (6–8 subagents). If there are more partitions, batch them in waves and wait for earlier waves to complete before launching the next. This prevents context budget exhaustion and ensures findings are preserved.

**Before spawning subagents**, the orchestrating agent must:

1. Extract the 5-axis evaluation framework and severity table from the inlined reference in [references/persona-prompts.md](./references/persona-prompts.md).
2. Inline the relevant checklist and severity definitions directly into each subagent's prompt (subagents cannot self-activate skills).

### Subagent Persona A: The Systems & Reliability Architect

- **Mandate:** Fault tolerance, memory leaks, unclosed listeners/timers, race conditions, API retry backoffs, deadlocks.
- **Scrutiny:**
  - Strict TypeScript: Zero `any`, safe nullish assertions, exhaustive unions.
  - SOLID Principles: Single Responsibility (SRP) in stores/hooks, Dependency Inversion (DIP) in API clients.
  - Resource Cleanup: `clearTimeout`, `clearInterval`, event listener deregistration in cleanup functions.
  - Defensive Handling: Unhandled promise rejections, network offline states, rate-limit (429) backoffs.

### Subagent Persona B: The UX, Performance & Code Elegance Purist

- **Mandate:** Re-render hygiene, animation smoothness, layout shifts, accessible controls, localization integrity, and DX/API ergonomics.
- **Scrutiny (Frontend):** Re-render loops, store selectors, safe-area insets, a11y roles/labels, 100% dictionary parity, dead code elimination.
- **Scrutiny (Backend / Non-UI):** API ergonomics, option shapes, error messages, hot-path allocations, CLI progress feedback, docstrings.

See [references/persona-prompts.md](./references/persona-prompts.md) for complete prompt templates and output schemas.

---

## Phase 3: Synthesis & Interactive HTML Dashboard

1. **Collect & Deduplicate:** Gather findings from all subagents, combine duplicate findings from both personas on the same code, and classify severities:
   - **Critical (P0):** Crashes, memory leaks, unclosed hardware listeners, data loss, session wipes, security leaks.
   - **Important (P1):** Unhandled API rate limits, race conditions, missing localizations, safe-area clipping, render storms.
   - **Suggestion (P2):** Code duplication, missing a11y labels, sub-optimal memoization.
   - **Nit (P3):** Formatting, minor naming inconsistencies.
2. **Generate Interactive Scorecard:** Use [references/audit-scorecard-template.html](./references/audit-scorecard-template.html) to author `docs/reports/codebase-audit-and-review-report.html`.
3. **HTML Entity Safety:** When rendering code snippets inside `.code-block`, always escape HTML entities (`<` as `&lt;`, `>` as `&gt;`, `&` as `&amp;`) so JSX, TypeScript generics, and boolean expressions render properly in the browser.
4. **Interactive Controls:** Ensure each `<tr>` in `{{FINDINGS_TABLE_ROWS}}` includes `data-severity`, `data-partition`, and `data-axis` attributes so the table's multi-filter script (Partition dropdown, Axis dropdown, Severity buttons, Search input) operates correctly.

**After delivering the report, stop and present it to the user.** Do not proceed to remediation unless the user explicitly requests it.

---

## Phase 4: Master Remediation Planning (on user request)

1. Author a comprehensive master plan in `docs/plans/codebase-remediation-master-plan.md`.
2. Group all planned tasks by phase matching the semantic partitions.
3. Use Markdown task checkboxes (`[ ]`) to track progress.
4. **Include explicit sketches of required unit tests** for all modified logic and previously untested modules.
5. **Always request explicit confirmation from the human before writing or modifying code.**

---

## Phase 5: Incremental Partition Remediation

1. Implement fixes partition by partition (never attempt to rewrite the entire codebase in one turn).
2. Check off completed items in the master plan (`[x]`).
3. Add unit tests covering all business logic, error states, and edge cases.
4. Keep edits clean, modular, and adhering strictly to the project's coding standards.

---

## Phase 6: Automated Verification & Commit

Execute the project's verification pipeline. Use the commands configured in the project's `AGENTS.md` or `package.json` scripts. Typical steps:

1. **Unit Test Suite:** Run the project's test runner (e.g., `pnpm test`, `npm test`, `yarn test`).
2. **Strict Typecheck:** Run the project's type checker (e.g., `pnpm typecheck`, `tsc --noEmit`).
3. **Linter & Formatting:** Run the project's lint and format checks (e.g., `pnpm lint`, `pnpm format:check`).
4. **Dead Code & Boundaries Audit:** If available, run a dead-code analysis tool (e.g., `pnpm fallow audit`).
5. **Human Approval for Git Commit:**
   - Present a clear bulleted summary of all resolved issues.
   - Await explicit user instruction before staging and committing.

---

## Reference Documents

- **[Scorecard HTML Template](./references/audit-scorecard-template.html):** Standalone, interactive dashboard template with multi-dimensional filtering (Severity, Partition, Quality Axis) and search.
- **[Persona Prompts & Evaluation Framework](./references/persona-prompts.md):** Complete prompt scaffolds, invocation specs, output schemas, and non-frontend adaptations.
