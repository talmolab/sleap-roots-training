# Design: bundled selectors, one card per physical model

## Context

`ModelCard.species` is a scalar `str`, so a model validated for several species must be registered
once per species. Measured on the committed matrix: 7 rows expand to 13 cards over 8 physical
models, giving 5 redundant ~75MB artifacts. See `proposal.md` for the counts and for why neither a
bare `species` tuple (removes 1 of 5) nor independent `species`/`mode` tuples (admits unvalidated
combinations) is the right shape.

## Goals / non-goals

**Goals.** Express "one artifact, several validated selection contexts" in the contract; get
registrations to one per physical model; keep `choose_models` obvious, with no surprise matches.

**Non-goals.** Deciding whether canola's window should extend to age 14 (#46 tracks deriving windows
from `LabelCard`s). Changing what any model actually does. Re-training anything.

## Decisions

### 1. Bundle the selector; do not tuple axes independently

A card carries `selectors: tuple[Selector, ...]`, each a whole `(species, mode, age_min, age_max)`.
Matching is "**any** selector matches all four fields", never a cross product. Independent tuples
would let `species=(canola, arabidopsis)` × `mode=(cylinder, multiplant cylinder)` advertise canola
in multiplant cylinder, which was never trained or validated. A silently wrong match is worse than a
duplicated file.

### 2. `root_type` stays scalar

Intrinsic to the weights, and verified: each of the 8 physical models has exactly one `root_type`.
Keeping it scalar also keeps the "one card per physical model" identity exact — the grouping key is
`(source_model_id, root_type)`, and in practice `source_model_id` alone already determines it.

### 3. Grouping key for expansion

Group matrix rows by `source_model_id` per root-type slot. Each group yields one card; each
contributing row contributes one selector, verbatim. Selectors are de-duplicated (identical rows
would otherwise produce a duplicate selector) and emitted in a deterministic order — sorted on the
selector values themselves, so the order survives a different matrix row order and a different
`PYTHONHASHSEED`. The payoff is reproducible, reviewable metadata: any difference a re-seed reports is
a real change rather than an ordering artifact. It is explicitly **not** a digest-stability measure
(metadata is not in the artifact digest — see Risks).

## Open question: the collection id

**This is the sharpest unresolved design point and needs a decision before implementation.**

`collection_id` is currently `f"{species}-{mode_slug}-{root_type}"` plus the age window, e.g.
`canola-cylinder-primary-age2-13`. Those strings are **live production registry identifiers**. With
one card per physical model, a card no longer has *a* species/mode/age to name itself with.

Candidates:

1. **Derive from the physical model.** Slugify `source_model_id` (e.g.
   `canola-pennycress-arabidopsis-primary-240611-102513`). Stable, honest about identity, and
   changes as rarely as the file does. Cost: the id stops being human-readable as a *selection*
   label, and every existing id changes.
2. **Join the distinct species.** e.g. `arabidopsis-canola-pennycress-cylinder-primary`. Readable,
   but the age windows differ across selectors so the age suffix no longer applies cleanly, and
   adding a species to a card renames its collection — churning a production identifier for a
   metadata change.
3. **Canonical selector.** Pick one selector (first row) to name the collection. Stable-ish but
   arbitrary, and misleading: `canola-...` naming a card that also serves arabidopsis.

**Recommendation: option 1.** The card's identity is now the physical model, so the id should track
the model, and it is the only option where adding a species to an existing card does not rename a
live collection. Needs sign-off, since it renames all 13 production collections.

**Two constraints on option 1 that are easy to miss.**

- *The slug must be a legal wandb artifact name.* Every `source_model_id` in the committed matrix
  contains `/` (e.g. `rice/younger/crown/220821_163331.multi_instance.n=867`), and
  `wandb.sdk.artifacts._validators.INVALID_ARTIFACT_NAME_CHARS` is exactly `{"/"}` — so a naive
  `source_model_id` → id mapping produces names wandb rejects. (`=` and `.` are *not* in that set, so
  the `n=743` suffix and the timestamp dots are fine as far as the validator is concerned.) The
  existing tests cannot catch a violation because `_FakeArtifact` validates nothing, so the check has
  to be an explicit assertion against wandb's own validator.
- *The rename cannot ship before the collapse.* Under the current per-row expansion, 13 cards map
  onto only 8 distinct `source_model_id`s, so an id derived from the model id yields duplicates and
  `publish.py`'s duplicate-id guard aborts the seed. The id change is therefore **downstream** of the
  expansion change, never a standalone step — see "Sequencing inside this repo".

## Investigated: the wandb link-into-many-collections path

Checked against the pinned writer (`wandb>=0.28.0,<0.29.0`, 0.28.0 installed). This was the
alternative that would have deduplicated storage **without** a contract change, so it is worth
recording why it does not substitute for this proposal — and why it becomes *more* usable once this
proposal lands.

**Linking does not duplicate storage.** `Run.link_artifact(artifact, target_path, aliases)` states
plainly: "W&B does not duplicate artifacts when you link an artifact to a collection." So one logged
artifact can be linked into N collections for one upload.

**But a collection cannot carry its own structured metadata.** `ArtifactCollection` exposes only
`description` (a free string) and `tags` (strings) as settable fields — there is **no `metadata`
property**. The structured `ModelCard` metadata lives on `Artifact.metadata`, which is shared by
every collection the artifact is linked into.

**Therefore, under the *old* flat schema, link-many was unusable**: four collections would share one
metadata blob whose single `species` is whichever card published it, silently breaking
`choose_models` for the other three. That is exactly the constraint that forced the duplication in
the first place, and it confirms the framing in `proposal.md` — the duplication is a *contract*
limitation, not a wandb one.

**Under the selector-list design the objection disappears.** One card already describes every
(species, mode, age) it serves, so an artifact linked into several collections would carry metadata
that is *correct* in all of them rather than wrong in all but one. So link-many becomes a viable
future option for per-species **discoverability** (a browsable collection per species pointing at
shared weights) if that is ever wanted. It is **not needed for storage**, because one card per
physical model already means one upload.

Caveat on confidence: this is API-surface introspection performed offline, not a live test against
the production registry, and registry collections may differ from ordinary project artifact
collections in ways the local classes do not reveal. Treat it as strong evidence about the shape,
and verify against the live registry before building anything on it.

## Migration: the live registry is the real risk

The 13 already-published artifacts carry the **old flat** metadata (`species`, `mode`, `age_min`,
`age_max`, `root_type`). Once `ModelCard` requires `selectors`, **those existing artifacts stop
validating**, so a consumer upgraded past the contract bump cannot read the current production
registry. Ordering therefore matters more than usual:

1. `sleap-roots-contracts`: add `Selector`, change `ModelCard`, release a new pre-release version.
2. `sleap-roots-predict`: generalize `choose_models` to "any selector matches", pin the new
   contracts.
3. This repo: bump the pin, rewrite expansion/metadata/publishing, re-seed the registry so all 8
   collections carry new-shape cards.
4. Retire the now-orphaned collections — **decide explicitly**, do not leave it implicit.

**How many collections are orphaned depends entirely on the 0.2 id decision, and it is not 5.**

- **Under the recommended option 1** (id derived from `source_model_id`), *every* id changes, so the
  re-seed is purely **additive**: 8 brand-new collections appear and **all 13** existing collections
  are orphaned. Nothing is overwritten.
- Only under option 3 (canonical selector, ids preserved for the 8 surviving names) is the count 5 —
  8 collections get re-seeded in place and the other 5 fall away. The design rejects option 3.

Every acceptance gate that names a number therefore has to read it off the 0.2 decision rather than
hardcode it; `tasks.md` §6.2 states the count as "13 under option 1, 5 under option 3" for exactly
this reason, and the delta spec's orphan scenario avoids a literal count altogether.

**On step 4, the recommendation is to explicitly retire the orphans** (drop the `production` alias)
after the 8 new collections verify **and** the upgraded consumer is confirmed deployed. Leaving them
in place indefinitely is *not* the neutral option it looks like: once the schema tightens, predict's
registry lister is believed to skip an old-shape collection with only a logged warning, so those
models stop being selectable **silently** — a regression that surfaces as "the pipeline picked a
different model" rather than as an error. Retiring makes the removal deliberate and greppable.
`--verify` gains orphan reporting (see the delta spec) precisely so this cannot be missed, but
reporting is not deleting: the retirement stays a human-gated step.

**That skip-with-a-warning claim is unverified and load-bearing.** It is the reason the additive
re-seed is safe to run before predict upgrades. If predict's lister **raises** on an
unparseable card instead of skipping it, then the moment the first new-shape collection appears the
canary itself is the outage, and the whole rollout order changes. Verify it in the predict repo
before the canary, not after.

Two viable transition strategies, to be chosen with the contracts owner:

- **Flag day.** Contracts requires `selectors`; predict and the re-seed land together. Simplest to
  reason about, but there is a window where production metadata does not match the contract.
- **Tolerant read.** Contracts accepts either shape for one release (a validator that lifts a flat
  card into a single-selector card), letting predict upgrade before the re-seed and removing the
  flag-day window. More code, but no moment where the live registry is unreadable.

**Recommendation: tolerant read**, because the registry is production data consumed by a pipeline we
do not control the deploy timing of. Revisit if the contracts owner prefers a clean break.

## Reverse compatibility: the tolerant read only covers one direction

The tolerant read solves **new code reading old data**. The opposite direction is a real gap and is
not solved by it.

Verified against the installed contract: `ModelCard.model_config` is `{'frozen': True, 'extra':
'ignore'}`, and `species`, `mode`, `age_min`, `age_max`, `root_type`, `registry_id`, `version` are all
required. So a consumer **still pinned to the pre-`selectors` contract** that reads a new-shape card
silently drops the unknown `selectors` key (`extra="ignore"`) and then fails validation on four
missing required fields. The failure is at least loud rather than a wrong match — but it is a failure.

The obvious fix, dual-writing both shapes for one release, is **ruled out by the delta spec on
purpose**: the metadata requirement says a card SHALL NOT carry card-level `species`/`mode`/`age_min`/
`age_max`, because a card serving four species has no honest value to put in a scalar `species`. Any
value chosen would be wrong for three of them, and an old consumer would then make a *silently wrong*
selection instead of failing — strictly worse than the validation error.

**So reverse compatibility is handled operationally, not in the schema, and option 1 supplies it for
free:** because option 1 renames every id, the re-seed only *adds* collections and never touches the
13 an old consumer is reading. An un-upgraded consumer keeps working against the old collections for
as long as they carry the `production` alias. That makes the retirement step (0.4 / §6.3) the actual
compatibility cliff, so it MUST be gated on **confirmed deployment of the upgraded predict**, not on
producer-side `--verify` passing. Verifying the 8 new collections proves the producer wrote them
correctly; it says nothing about whether anything is able to read them yet.

This is a genuine argument for option 1 over option 2/3 that is independent of the naming argument:
options that preserve ids overwrite live data in place and delete the fallback.

**Decisions are settled here, not in PR comments.** Because 0.2/0.3/0.4 rename live production
identifiers and change what is selectable, the agreed answers are folded back into this document
(and `tasks.md`) before implementation starts, matching this repo's precedent for past breaking
changes. A decision recorded only in a review thread is not a decision.

## Sequencing inside this repo

Cross-repo ordering (contracts → predict → here) is a hard dependency. *Within* this repo the commit
boundary is also constrained, but **not** for the reason an earlier draft of this document gave. That
draft said splitting the pin bump from the test rewrite "would redden `main`". It would not: this repo
squash-merges, so intermediate commits never land on `main` individually, and CI runs on PR sync
rather than per-commit. The constraint is real for two other reasons.

- **`uv sync --locked`.** `pyproject.toml` and `uv.lock` must move together or the lockfile check
  fails, so the pin bump is inseparable from its lock update.
- **A pin bump alone is already red.** `tests/test_registry_chooser.py:180` asserts
  `ModelCard.model_fields["species"].annotation is str`. Once the contract drops card-level `species`,
  that subscript raises `KeyError` — so the pin bump cannot be green without touching tests, whatever
  else it is bundled with.

So the pin bump, the expansion/metadata rewrite, the collection-id change, and the matching test
rewrite are **one atomic commit** (`tasks.md` §3).

**The publish tests belong in that same commit, and this was proven rather than reasoned.** Changing
the collection-id scheme in isolation and running the suite produces **11 failures, 9 of them in
`tests/test_registry_publish.py` and `tests/test_registry_cli.py`** (baseline: 64 passed) — the two
files an earlier draft deferred to commit 2. Both build their expectations from `collection_id()`, and
`tests/conftest.py`'s `tiny_matrix` uses `soy/p` / `soy/l` as model ids, which an id derived from
`source_model_id` has to slug. Those two test files therefore move into §3.

What is genuinely left for a second commit is the `--verify` orphan report and the metadata-refresh
check (§4) — new behavior with new tests, green on its own. Docs (§5) are safe standalone.

Finally, the ordering *within* §3 is not free either: the id rename cannot precede the collapse, since
13 cards over 8 model ids collide on the duplicate-id guard. Decision 0.2 is thus a hard input to the
commit boundary, not an independent choice made afterwards.

## Risks

- **Digest churn — and the opposite risk, which is the more likely one.** `weights_checksum` is
  `artifact.digest` and Bloom uses it as a compute-idempotency key. An earlier draft justified stable
  digests by pointing at deterministic selector ordering. That is a non-sequitur: read in
  `wandb/sdk/artifacts/artifact_manifests/artifact_manifest_v1.py`, `digest()` hashes only
  `b"wandb-artifact-manifest-v1\n"` followed by the sorted `f"{path}:{entry.digest}"` lines —
  **metadata is not an input to the digest at all**. The conclusion (unchanged weights → unchanged
  digest) still holds, but it is carried entirely by the SHA256-pinned archive form and the junk-
  filtered `add_dir`; selector ordering is irrelevant to it. Determinism is still worth having, for
  reproducible and reviewable metadata, just not for this reason.

  The *inverse* risk follows from the same fact and is unmentioned in earlier drafts: since metadata
  sits outside the digest, re-logging identical weights with **new** metadata may be treated as a
  content-level no-op, so the old flat metadata can stay live on the production-aliased artifact while
  the seed report cheerfully says `published`. That is a silent half-migration. `--force` does not
  close it — `publish.py:146` shows `--force` bypassing the idempotency *read*, which is not the same
  as guaranteeing a new stored metadata blob. Hence the Re-Publish Metadata Refresh requirement in the
  delta spec and the read-back assertion in `tasks.md` §4: verify the metadata actually landed, do not
  infer it from an exit code.
- **Age-window semantics unchanged.** A card serving canola (2–13) and pennycress (2–14) advertises
  neither window globally. `choose_models` must match the age against the *matching selector*, not
  against a card-level min/max, or canola silently gains a year of coverage.
- **Collection-id uniqueness guard** must be kept: with fewer, differently-named collections the
  existing duplicate-id fail-fast check still applies and its test needs updating, not deleting.
