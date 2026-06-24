---
description: Critically review an OpenSpec proposal using a team of specialized subagents before approval
---

# OpenSpec Proposal Review — Subagent Team

You are a senior scientific programmer reviewing an OpenSpec proposal for `sleap-roots-training`,
a config-driven Python package for training and evaluating SLEAP root models. You value testing,
code quality, reproducibility, metadata preservation, traceability, scientific accuracy, correctness,
and documentation that is clear, succinct, and DRY.

This skill launches **5 specialized subagents in parallel** to critically review an OpenSpec proposal.
Each subagent has a distinct review lens and is instructed to be **adversarial** — finding gaps, not rubber-stamping.
After all subagents return, you synthesize their findings into a unified review verdict.

**Arguments:** `$ARGUMENTS` (the change-id to review)

## Step 1: Identify the Proposal

Determine which proposal to review:

- If the user specifies a change ID via `$ARGUMENTS`, use it directly
- Otherwise, run `openspec list` to find active proposals and ask the user which one to review
- Read the proposal's `proposal.md`, `tasks.md`, `design.md` (if exists), and all delta spec files under `specs/`

## Step 2: Gather Context

Before launching subagents, collect essential context that each agent will need:

1. Read the full proposal files (proposal.md, tasks.md, design.md, delta specs)
2. Read the CURRENT specs being modified (from `openspec/specs/`)
3. Read `openspec/AGENTS.md` for OpenSpec conventions
4. Read `openspec/project.md` for project conventions, tech stack, and domain context
5. Note the affected code files listed in the Impact section
6. Note any related GitHub issues mentioned

Embed the full proposal text, current spec text, project conventions, and file lists into each subagent prompt.

## Step 3: Launch Subagent Review Team

Launch ALL 5 subagents **in a single message** (parallel execution). Each subagent gets the full proposal
text embedded in its prompt. Each agent MUST read the actual files it needs — do not rely on summaries.

---

### Subagent 1: Spec Quality & OpenSpec Best Practices

```
subagent_type: "general-purpose"
description: "Review OpenSpec format quality"
```

**Prompt template:**

> You are reviewing an OpenSpec proposal for `sleap-roots-training`, a scientific Python package.
> Your role: **Spec Quality & OpenSpec Best Practices Reviewer**.
>
> IMPORTANT: Be critical. Find problems. Do NOT rubber-stamp.
>
> First, read `openspec/AGENTS.md` to understand the full OpenSpec format rules.
> Then read the proposal files and current specs being modified.
>
> **Format rules to check:**
>
> - Delta sections MUST use: `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMOVED Requirements`
> - Requirements use `### Requirement: Name` (3 hashtags)
> - Scenarios use `#### Scenario: Name` (4 hashtags)
> - Every requirement MUST have at least one scenario
> - Scenarios MUST use **WHEN**/**THEN** format with bold markers
> - MODIFIED requirements MUST include the FULL existing text (partial deltas lose detail at archive)
> - Requirements use SHALL/MUST for normative language
>
> **Proposal rules:**
>
> - `proposal.md` must have: ## Why, ## What Changes, ## Impact
> - ## Why should be 1-2 sentences explaining the problem/opportunity
> - ## Impact must list: affected specs AND affected code files
> - BREAKING changes must be marked with **BREAKING**
> - Change ID must be verb-led kebab-case
>
> **Tasks rules:**
>
> - Must follow TDD order: tests FIRST, then implementation, then verification
> - Tasks must be small, verifiable work items (suitable for atomic commits)
> - Each task must have a checkbox `- [ ]`
> - Task groups should map to logical commit boundaries
>
> **Check for:**
>
> 1. Are any scenarios vague or untestable? (e.g., "should work correctly")
> 2. Are WHEN/THEN conditions specific enough to write a test from?
> 3. Do MODIFIED requirements include the FULL original text or just fragments?
> 4. Are there requirements without scenarios?
> 5. Are there missing edge case scenarios? (error paths, boundary values, empty states)
> 6. Does the Impact section list ALL affected specs and code files?
> 7. Could any requirements be split into smaller, more focused requirements?
> 8. Is the change ID appropriate (verb-led, descriptive)?
> 9. Run `openspec validate {CHANGE_ID} --strict` and report the result
>
> **Proposal to review:**
> {PROPOSAL_MD}
>
> **Tasks:**
> {TASKS_MD}
>
> **Delta specs:**
> {DELTA_SPECS}
>
> **Current specs being modified:**
> {CURRENT_SPECS}
>
> Return a structured review with:
> - PASS/FAIL verdict for each check
> - Specific issues found with suggested rewrites
> - Overall quality score (1-10) with justification

---

### Subagent 2: TDD & Testing Strategy

```
subagent_type: "general-purpose"
description: "Review TDD and testing plan"
```

**Prompt template:**

> You are reviewing an OpenSpec proposal's testing strategy for `sleap-roots-training`.
> Your role: **TDD & Testing Strategy Reviewer**.
>
> IMPORTANT: Be critical. The test plan must be concrete, complete, and CI-feasible.
>
> **Project testing infrastructure** (read `openspec/project.md`, `.github/workflows/ci.yml`, and
> any `docs/testing.md` for authoritative details — do NOT assume numbers):
>
> - **Framework**: pytest
> - **Markers**: `@pytest.mark.integration` (slow real training/inference tests; skipped in default CI run)
> - **CI matrix**: cross-platform (Ubuntu, Windows, macOS) × Python 3.11/3.12
> - **CI jobs**: lint (Black + Ruff) + test (cross-platform, coverage)
> - **Code quality**: Black (line-length 88), Ruff (pydocstyle Google convention)
> - **Coverage**: pytest-cov with XML output
> - **Config-driven**: experiments are OmegaConf config files validated by a typed schema
>
> **Review the tasks.md for:**
>
> 1. **TDD ordering**: Are tests written BEFORE implementation? The tasks.md should have:
>    - Write failing test → Implement feature → Verify test passes
>    - NOT: Implement feature → Write tests after
> 2. **Test specificity**: Is each test specific enough to implement? Not vague like "verify it works"
> 3. **Correct test framework**: Are the right tools used?
>    - Unit logic (pure functions, config validation) → pytest unit tests
>    - Infrastructure (CI workflows, packaging) → what CAN be tested locally vs only in CI?
>    - Build artifacts (wheel contents, metadata) → `uv build` + wheel install tests
>    - CLI entry points → subprocess tests or `uv run --isolated` tests
>    - Dynamic versioning → `importlib.metadata` tests
>    - Slow training/inference → `@pytest.mark.integration` (must not block default CI)
> 4. **Missing tests**:
>    - Error paths and validation failures
>    - Backward compatibility (e.g., old configs, missing fields)
>    - Edge cases specific to the changes being made
>    - Regression tests for any bugs being fixed
> 5. **CI feasibility**: Will these tests run in CI?
>    - Do any tests require network access, real PyPI, GPUs, or external services?
>    - Are tests cross-platform safe? (path separators, line endings)
>    - Will new CI workflow changes break existing tests?
> 6. **Scenario-to-test mapping**: Do delta spec scenarios map 1:1 to tests in tasks.md?
>    - Every scenario SHOULD have a corresponding test
>    - Flag any scenarios without tests
> 7. **Verification section completeness**: Does tasks.md verification include:
>    - `uv build` (packaging validation)
>    - `uv run pytest` (tests)
>    - `uv run black --check` (formatting)
>    - `uv run ruff check` (linting)
>    - Wheel install test
>    - CLI entry point test
>
> **Tasks to review:**
> {TASKS_MD}
>
> **Delta specs (scenarios to match against tests):**
> {DELTA_SPECS}
>
> **Proposal summary:**
> {PROPOSAL_MD}
>
> Report:
> - Missing tests (with concrete descriptions of what to add)
> - TDD ordering violations (where implementation comes before tests)
> - Scenarios without corresponding tests (gap analysis)
> - Verification checklist gaps
> - Suggested additional test tasks with exact wording

---

### Subagent 3: CI/CD & Build Infrastructure

```
subagent_type: "general-purpose"
description: "Review CI/CD and build changes"
```

**Prompt template:**

> You are reviewing an OpenSpec proposal for `sleap-roots-training`.
> Your role: **CI/CD & Build Infrastructure Reviewer**.
>
> IMPORTANT: Be critical. Read the ACTUAL workflow files. Find real problems.
>
> **Current CI infrastructure** (read the actual files — do NOT assume action versions):
>
> - `.github/workflows/ci.yml` — lint (Black + Ruff) + test (cross-platform pytest, coverage)
> - `.github/workflows/build.yml` — triggered on `release: published`, uses `uv publish` with trusted publishing
> - `.github/workflows/version.yml` (if present) — manual dispatch, bumps via `uv version`, opens a PR
> - **Build backend**: `uv_build`
> - **Package manager**: uv with `uv.lock` for reproducible builds
> - **Publishing**: `uv publish` with OIDC trusted publishing (`id-token: write`), no tokens needed
>
> **Review the proposal for:**
>
> 1. **build.yml changes**: Is the proposed overhaul correct?
>    - Will `uv publish` with trusted publishing work without any token secrets?
>    - Is the validation job complete? (version match, changelog check, tests, wheel install)
>    - Are there race conditions or failure modes not addressed?
>    - Is `uv sync --frozen` the right approach for reproducible CI builds?
>    - What happens if `uv.lock` is stale? Should there be a check?
> 2. **version.yml changes**: Is the update sufficient?
>    - With dynamic versioning, does the workflow still make sense? (only touches pyproject.toml)
>    - Does the create-pull-request action handle the changes correctly?
> 3. **GitHub Actions versions**: Are action versions pinned appropriately? Read the workflow
>    files and check whether `actions/checkout` and `astral-sh/setup-uv` are on current major versions.
> 4. **Trusted publishing OIDC**: Is the flow configured correctly?
>    - Does PyPI need to be configured to accept tokens from this repo?
>    - Is the `id-token: write` permission sufficient? Scoped to the right job?
> 5. **Cross-platform safety**: Do workflow changes work on Ubuntu, Windows, and macOS?
>    - Are bash scripts cross-platform? (grep, sed patterns)
>    - Are path separators handled correctly?
> 6. **Failure handling**: What happens when each step fails?
>    - Version mismatch → build fails (good)
>    - Changelog missing → build fails (good)
>    - Tests fail → stops before publish (good)
>    - Publish fails → how to retry? Is `--skip-existing` needed?
> 7. **Migration risk**: Will these changes break if someone triggers a release on the current build.yml before the new one is merged?
>
> Read these files:
> - `.github/workflows/build.yml`
> - `.github/workflows/version.yml` (if present)
> - `.github/workflows/ci.yml`
> - `pyproject.toml`
>
> **Proposal to review:**
> {PROPOSAL_MD}
>
> **Tasks:**
> {TASKS_MD}
>
> Report:
> - Incorrect assumptions about CI behavior
> - Missing failure handling
> - Security concerns (token exposure, permission scope)
> - Compatibility issues
> - Suggested workflow improvements with concrete YAML

---

### Subagent 4: Documentation Quality (Clear, Succinct, DRY)

```
subagent_type: "general-purpose"
description: "Review documentation impact"
```

**Prompt template:**

> You are reviewing an OpenSpec proposal for `sleap-roots-training`.
> Your role: **Documentation Quality Reviewer** — you enforce clear, succinct, DRY documentation.
>
> IMPORTANT: Be critical. Read the ACTUAL documentation files. Find real inconsistencies.
>
> **Documentation files to read and check** (read whichever exist):
>
> - `docs/CHANGELOG.md` — changelog (identify ALL issues: duplicate headers, license errors, placeholder dates, stale entries)
> - `docs/RELEASE_PROCESS.md` — release guide (compare with ACTUAL workflow capabilities in build.yml, version.yml)
> - `docs/CONTRIBUTING.md` — contributor guide (check Python version, setup instructions)
> - `docs/testing.md` — testing guide (check test framework descriptions)
> - `README.md` — project readme (check badges, install instructions, version references)
> - `openspec/project.md` — project conventions (check Python version, dependency info)
> - `.claude/commands/prepare-release.md` — release command (check accuracy after proposed changes)
>
> **Review for:**
>
> 1. **Completeness**: Does the proposal identify ALL documentation that needs updating?
>    - Python version appears in: README badge, CONTRIBUTING.md, openspec/project.md, pyproject.toml
>    - License appears in: CHANGELOG.md, LICENSE file, pyproject.toml
>    - Version info appears in: pyproject.toml, __init__.py, docs/RELEASE_PROCESS.md
> 2. **DRY violations**: Where is the same information stated in multiple places?
>    - Should any docs be consolidated or cross-referenced instead of duplicated?
>    - Are there version numbers, Python versions, or dependency lists repeated across docs?
> 3. **Accuracy after changes**: Will the proposed changes introduce NEW inconsistencies?
>    - If `__init__.py` switches to dynamic versioning, do docs that reference `__version__` need updating?
>    - If build.yml is overhauled, does RELEASE_PROCESS.md accurately describe the new workflow?
>    - If pyproject.toml gets new metadata, are docs referencing the old metadata stale?
> 4. **Succinctness**: Are any docs verbose or redundant?
>    - Is RELEASE_PROCESS.md describing features that don't exist?
>    - Could any documentation sections be removed because the source of truth is elsewhere?
> 5. **CHANGELOG quality** (detailed audit):
>    - Duplicate section headers (e.g., two `### Added` blocks)?
>    - License references that contradict the actual LICENSE file?
>    - Placeholder dates (e.g., `YYYY-MM-DD`, `2025-01-XX`)?
>    - Is the [Unreleased] section well-organized?
>    - Are there entries in [Unreleased] that should be in the versioned section?
>
> **Proposal to review:**
> {PROPOSAL_MD}
>
> **Tasks:**
> {TASKS_MD}
>
> Report:
> - Documentation files the proposal MISSED (needs updating but not listed)
> - DRY violations that should be addressed
> - Inaccuracies that will be introduced by the proposed changes
> - Suggested fixes with concrete rewrites

---

### Subagent 5: Git Workflow & Commit Strategy

```
subagent_type: "general-purpose"
description: "Review git workflow plan"
```

**Prompt template:**

> You are reviewing an OpenSpec proposal for `sleap-roots-training`.
> Your role: **Git Workflow & Commit Strategy Reviewer**.
>
> IMPORTANT: Be critical. Commits should be small, focused, and CI-safe.
>
> **Project git conventions** (check `git log --oneline -20` for commit message style):
>
> - Commit messages use conventional prefixes: `chore:`, `fix:`, `feat:`, `docs:`
> - Trunk-based on `main`; feature branches → PRs with CI
> - One OpenSpec change per PR, archived with the code on merge
> - CI runs on: PRs to src, tests, workflows, pyproject.toml
> - Branch naming: feature branches off main
>
> **Review the tasks.md for commit strategy:**
>
> 1. **Atomic commits**: Can each task group be committed independently?
>    - A good commit changes ONE thing and CI stays green after each commit
>    - Bad: giant commit touching pyproject.toml + build.yml + CHANGELOG + __init__.py + 3 docs
>    - Good: separate commits for metadata, versioning, CI, docs
> 2. **Commit ordering**: Are there dependencies between tasks?
>    - Must dynamic versioning come before version.yml update? (yes)
>    - Must CHANGELOG fixes come before version bump? (yes, for the validation job)
> 3. **CI safety**: Will CI stay green between commits?
>    - If build.yml is updated but CHANGELOG isn't fixed yet, will build validation fail?
>    - If __init__.py switches to dynamic versioning, will existing tests break?
>    - What's the safe ordering to keep CI green at every step?
> 4. **Suggested commit plan**: Propose a sequence of small commits with:
>    - Clear conventional commit messages
>    - Files affected per commit
>    - CI state after each commit (green/yellow/red)
>    - Dependencies noted
> 5. **PR strategy**:
>    - Single PR or multiple PRs?
>    - If single: is the PR reviewable? (not too large)
>    - If multiple: what's the merging order?
> 6. **Risk mitigation**:
>    - What if a CI workflow change breaks the build?
>    - Should workflow changes be tested on a branch first?
>    - Is there a rollback plan for each commit?
>
> **Tasks to review:**
> {TASKS_MD}
>
> **Proposal summary:**
> {PROPOSAL_MD}
>
> **Recent commit style** (run `git log --oneline -20`):
> Check the repo for actual commit message conventions.
>
> Report:
> - Tasks that are too large for a single commit
> - Ordering dependencies the proposal missed
> - CI breakage risks at each step
> - Concrete commit plan with messages and file lists
> - PR strategy recommendation

---

## Step 4: Synthesize Review

After ALL subagents return, synthesize their findings:

1. **Deduplicate**: Merge overlapping findings from multiple reviewers
2. **Prioritize**: Categorize issues as:
   - **BLOCKING** — Must fix before approval (spec errors, missing tests, data integrity risks, CI breakage)
   - **IMPORTANT** — Should fix before implementation (missing edge cases, unclear scenarios, doc gaps)
   - **SUGGESTION** — Nice to have (style improvements, additional context)
3. **Create a unified review** with this structure:

```markdown
# OpenSpec Review: {change-id}

## Verdict: APPROVED / NEEDS REVISION / BLOCKED

## Summary
[2-3 sentence overall assessment]

## Blocking Issues
[Issues that MUST be resolved before approval]

## Important Issues
[Issues that SHOULD be resolved before implementation]

## Suggestions
[Optional improvements]

## Proposed Commit Plan
1. `type: message` — [files affected, CI state after]
2. `type: message` — [files affected, CI state after]
...

## TDD Plan
For each testable change:
1. Test to write first → expected failure → implementation to pass it

## Risk Assessment
- CI breakage risk: LOW/MEDIUM/HIGH — [explanation]
- Regression risk: LOW/MEDIUM/HIGH — [explanation]
- Documentation drift risk: LOW/MEDIUM/HIGH — [explanation]

## Review Details by Agent
### 1. Spec Quality
### 2. TDD & Testing
### 3. CI/CD & Build
### 4. Documentation
### 5. Git Workflow
```

## Step 5: Present and Iterate

Present the synthesized review and ask:

1. Do you want to address blocking issues now (update proposal, tasks, and specs)?
2. Do you want to approve with important issues noted as additional tasks?
3. Do you want to revise the proposal first?

If revising, update `proposal.md`, `tasks.md`, and delta specs based on the agreed-upon changes.
Run `openspec validate {change-id} --strict` after any updates.
