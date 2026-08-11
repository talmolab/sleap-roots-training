# Design: bundled selectors, one card per physical model

## Context

`ModelCard.species` is a scalar `str`, so a model validated for several species must be registered
once per species. Measured on the committed matrix: 7 rows expand to 13 cards over 8 physical
models, giving 5 redundant *registrations* of already-stored weights — the cost is maintenance drift,
not bytes, since wandb content-addresses the blobs (see `proposal.md`). See `proposal.md` for the
counts and for why neither a
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
Matching is "**any** selector matches all four fields", never a cross product — see `proposal.md`
"Why not tuple `species` and `mode` independently" for the argument and the worked example.

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

**Three constraints on option 1 that are easy to miss.**

- *The slug must satisfy wandb's real name rule, which is stricter than the obvious one.* A
  `source_model_id` looks like `rice/younger/crown/220821_163331.multi_instance.n=867`, and the
  tempting check is `wandb.sdk.artifacts._validators.INVALID_ARTIFACT_NAME_CHARS`, which is exactly
  `{"/"}`. **That check is wrong**, and an earlier draft of this document asserted from it that "the
  `n=743` suffix and the timestamp dots are fine". Verified against the pinned writer:
  `wandb.Artifact.__init__` applies `re.match(r"^[a-zA-Z0-9_\-.]+$", name)` **before** it delegates to
  `validate_artifact_name`, so `=` is rejected too. Run against the real thing:

  ```
  validate_artifact_name('...240611_102513.multi_instance.n=743')  -> ACCEPTED
  wandb.Artifact(name='...240611_102513.multi_instance.n=743')     -> ValueError: Artifact name may
      only contain alphanumeric characters, dashes, underscores, and dots.
  ```

  So a slug that only strips `/` passes `validate_artifact_name` and then **aborts the live seed on
  the first card**. `_` `-` `.` are legal; `/` and `=` are not; the bound is `NAME_MAXLEN` = 128 and
  the longest current id is well inside it. The legality test must construct a real
  `wandb.Artifact` (offline, no credential needed) — the existing `_FakeArtifact` validates nothing,
  so nothing in the suite catches this today.
- *The rename cannot ship before the collapse.* Under the current per-row expansion, 13 cards map
  onto only 8 distinct `source_model_id`s, so an id derived from the model id yields duplicates and
  `publish.py`'s duplicate-id guard aborts the seed. The id change is therefore **downstream** of the
  expansion change, never a standalone step — see "Sequencing inside this repo".
- *It silently retires a safety guard, which has to be re-established explicitly.* Today
  `collection_id` is built from `(species, mode_slug, root_type, age)`, so the duplicate-id check
  doubles as a check that **no two physical models claim the same selection context**. Derive the id
  from the model instead and two models with an identical selector get two distinct ids: both
  publish, both take the production alias, and the consumer finds two production cards matching one
  query. Verified that no such collision exists in the committed matrix today — so this is a lost
  *future* guard, exactly the class the existing "guard against future matrix edits" scenario exists
  for. The delta therefore restates the guard on the **selectors** rather than leaving it to depend on
  the id scheme.

## Investigated: the wandb link-into-many-collections path

This was the alternative that would have deduplicated storage **without** a contract change. Checked
against the pinned writer (`wandb>=0.28.0,<0.29.0`, 0.28.0 installed).

Linking one artifact into N collections genuinely does not duplicate storage. But **a collection
cannot carry its own structured metadata** — `ArtifactCollection` exposes only `description` and
`tags`, with no `metadata` property, so the `ModelCard` blob lives on `Artifact.metadata` and is
shared by every collection the artifact is linked into. Under the *old* flat schema that made
link-many unusable: four collections would share one blob whose single `species` is whichever card
published it, silently breaking `choose_models` for the other three. So the duplication was a
*contract* limitation, not a wandb one — which is the framing `proposal.md` uses.

Under the selector-list design the objection disappears, because one card already describes every
context it serves. Link-many therefore becomes a viable future option for per-species
**discoverability** (a browsable collection per species over shared weights), but it is **not** needed
for storage: one card per physical model already means one upload.

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
2. This repo: bump the pin, rewrite expansion/metadata/publishing, re-seed the registry so all 8
   collections carry new-shape cards.
3. `sleap-roots-predict`: generalize `choose_models` to "any selector matches", pin the new contracts,
   and **deploy only after step 2 is live and verified**. Merging and pinning can happen earlier; it is
   the deploy that is ordered. See "Reverse compatibility" for why this reverses the order an earlier
   draft gave.
4. Retire the now-orphaned collections — **decide explicitly**, do not leave it implicit.

**How many collections are orphaned depends entirely on the 0.2 id decision, and it is not 5.**

- **Under the recommended option 1** (id derived from `source_model_id`), *every* id changes, so the
  re-seed is purely **additive**: 8 brand-new collections appear and **all 13** existing collections
  are orphaned. Nothing is overwritten.
- Only under option 3 (canonical selector, ids preserved for the 8 surviving names) is the count 5 —
  8 collections get re-seeded in place and the other 5 fall away. The design rejects option 3.

Every acceptance gate that names a number therefore reads it off the 0.2 decision (`tasks.md` §6.2)
rather than hardcoding it, and the delta spec's orphan scenario carries no literal count.

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

**Recommendation, reversed on 2026-08-11: no tolerant read.** The argument above is wrong, and it was
wrong because it reasoned about the contract in isolation instead of about the consumer that reads it.
Elizabeth resolved task 2.5 against predict's actual code and two facts settle it: predict **skips** a
card it cannot validate, with a warning, isolated per artifact, without aborting the listing; and
`choose_models` **raises** when more than one card matches a context.

Work the four states through, with the additive re-seed in place (8 new collections, 13 old ones still
production-aliased):

| consumer contract | old 13 flat cards | new 8 selector cards | matches per context | outcome |
|---|---|---|---|---|
| old pin | valid, listed | fail on 4 missing required fields, skipped | 1 | works |
| new pin **with** tolerant read | lifted to one selector, valid, listed | valid, listed | **2** | **raises** |
| new pin **without** tolerant read | `selectors` missing, skipped | valid, listed | 1 | works |

The tolerant read is the only row that breaks. Skip-with-warning already provides the graceful
degradation the tolerant read was supposed to provide, and it provides it in **both** directions, so
adding the tolerant read does not remove a window, it manufactures an outage inside one. Dropping it
also deletes a task from the contracts change and permanently removes the "two valid production cards
for one selection context" state instead of merely surviving it.

What the tolerant read really bought was insensitivity to **deploy order**, and that cost does not
disappear: without it, the re-seed must land **before** the upgraded predict is deployed, or that
consumer skips all 13 old collections, finds nothing, and cannot select a model. So the cross-repo
order is contracts, then this repo's re-seed, then predict's deploy, then retirement — not the
contracts-predict-here order stated earlier in this document. Predict may merge and pin whenever; the
constraint is on its deploy. The failure mode if that slips is loud and immediate (no model found, not
a wrong model), it destroys nothing in the registry, and it is undone by rolling back predict's deploy.
That is a coordination commitment rather than a technical guarantee, which is why it gets an owner in
`tasks.md` 0.8.

The alternative worth recording: keep the tolerant read and change `choose_models` to dedupe matches
that share a `weights_checksum` rather than raising. It is robust to deploy order, since the competing
cards point at identical weights. It was not chosen because it needs a contracts change *and* a predict
behavior change to ship before the window, and because raising on an ambiguous selection is a guard
worth keeping in general rather than one to relax for a migration.

## Reverse compatibility: both directions, and why neither needs a schema fix

Once the tolerant read is dropped (see above), *both* directions of mismatch are handled by the same
consumer behavior: predict skips a card it cannot validate, with a warning, per artifact. What follows
is why the schema deliberately does not try to help.

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

**The trap this avoids.** Had the tolerant read gone in, the additive window would have carried two
*valid* production cards for one selection context: a query for (canola, cylinder, age 2–13, primary)
would match both the old `canola-cylinder-primary-age2-13` card and the new physical-model card, both
production-aliased, both pointing at the same weights. The only precedent for two simultaneous
production aliases in this spec is the two rice crown models, which cover *disjoint* contexts; this
would have been the same context twice, and `choose_models` raises on exactly that (task 2.5d). So the
window would have thrown an unhandled `ValueError` on live traffic the moment the first new collection
picked up the alias, not merely confused the canary. Dropping the tolerant read removes the state
entirely rather than managing it.

Decisions 0.3, 0.4 and 0.7 are therefore **coupled**, and 0.7 records the reasoning so it is not
re-derived as an emergent property of three decisions made separately. The canary still asserts on the
*selected* card's `registry_id` (§6.1), not merely that selection succeeded — cheap, and it is the
assertion that proves this analysis against live data rather than only on paper.

**Decisions are settled here, not in PR comments.** Because 0.2/0.3/0.4 rename live production
identifiers and change what is selectable, the agreed answers are folded back into this document
(and `tasks.md`) before implementation starts, matching this repo's precedent for past breaking
changes. A decision recorded only in a review thread is not a decision.

## Sequencing inside this repo

Cross-repo ordering (contracts, then this repo's re-seed, then predict's deploy) is a hard dependency. *Within* this repo the commit
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

**How far that atomicity extends depends on decision 0.3.** The two reasons above force
`pyproject.toml` + `uv.lock` + the contract-facing test assertions together, three or four files rather
than nine. Whether more comes with them turns on 0.3, and the recommendation there reversed on
2026-08-11:

- Under **no tolerant read** (now recommended), it is **one commit**. The instant the pin moves, the new
  `ModelCard` rejects the flat mapping `card_to_metadata` still emits, so every test that validates
  card metadata against the real contract goes red and `cards.py` has to move with the pin.
- Under **tolerant read** (no longer recommended), the pin bump can stand alone and green: verified that
  all 13 *unchanged* flat cards still validate against a tolerant-read `ModelCard`, so `cards.py` need
  not move in the same commit, and the expansion, metadata and id rewrite is a second commit.

An earlier draft asserted the split unconditionally while recommending the tolerant read, which was the
wrong pairing in both directions. `tasks.md` §3 carries both branches.

**The publish tests belong in that same commit, and this was proven rather than reasoned.** Changing
the collection-id scheme in isolation and running the suite produces **11 failures, 9 of them in
`tests/test_registry_publish.py` and `tests/test_registry_cli.py`** (against the full 226-test suite:
11 failed, 215 passed, and nothing outside those two files plus `test_registry_cards.py`) — the two
files an earlier draft deferred to commit 2. Both build their expectations from `collection_id()`, and
`tests/conftest.py`'s `tiny_matrix` uses `soy/p` / `soy/l` as model ids, which an id derived from
`source_model_id` has to slug. Those two test files therefore move into §3.

What is genuinely left for a second commit is the `--verify` orphan report and the metadata-refresh
check (§4) — new behavior with new tests, green on its own. Docs (§5) are safe standalone.

Finally, the ordering *within* §3 is not free either: the id rename cannot precede the collapse, since
13 cards over 8 model ids collide on the duplicate-id guard. Decision 0.2 is thus a hard input to the
commit boundary, not an independent choice made afterwards.

**PR split.** §3 and §4 go in **separate PRs**, not one. Together they are ~44 tasks over 9 files with
roughly 37 test edits, and a reviewer cannot separate a behavior change from test churn at that size.
§4 is self-contained once §3 lands, because §4.12 owns its own test updates. So: PR 1 = §3 (as one or
two commits per 0.3), PR 2 = §4, PR 3 = §5 docs (rebased last), PR 4 = §6 migration + archive.

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

  **Under option 1 this migration never hits the no-op path** — every id is new, so every sequence is
  new and nothing dedupes. The Re-Publish Metadata Refresh requirement therefore is not migration
  insurance; it is the guarantee that the *next* metadata-only edit works, which is adding a selector
  to an existing card — precisely the operation option 1 is chosen to make cheap.

  The mechanism: wandb documents on `Artifact.digest` that "if an artifact has the same digest as the
  current `latest` version, then `log_artifact` is a no-op". So re-logging identical weights with
  **new** metadata creates no new version, and the old flat metadata can stay live on the
  production-aliased artifact while the seed report says `published` — a silent half-migration.
  `--force` does not close it: `publish.py:146` bypasses the idempotency *read*, which is not the same
  as guaranteeing a new stored metadata blob. (Do not cite `ArtifactSaver` for this; verified that in
  0.28.0 it is reached only from `wandb/sdk/internal/sender.py`, which nothing imports — the live path
  runs through wandb-core. The docstring plus the live observation in `tasks.md` §6.5 are the evidence.)

  There *is* a supported remedy, which the requirement names rather than dead-ending at "report a
  failure": setting `Artifact.metadata` and calling `Artifact.save()` on a committed artifact issues an
  `updateArtifact` mutation — a metadata-only write that does not involve the digest at all. Verified
  it also works through a registry **link**, since the mutation targets the source artifact id and the
  metadata blob is shared.

- **Metadata coercion, which fails silently in the worst possible way.**
  `wandb.Artifact(metadata=...)` runs the mapping through `validate_metadata`, which **coerces rather
  than rejects** non-JSON-native values. Verified against the pinned writer: a tuple of `Selector`
  *pydantic models* — the most natural implementation, reusing the contract type directly — comes back
  as a list of `repr` **strings** (`"species='canola' …"`), and a `NamedTuple` comes back as a
  positional list with the field names gone. Both publish unreadable selection metadata with a
  successful exit code, and no existing test can see it because `_FakeArtifact` stores metadata
  verbatim and the one assertion that checks it compares `card_to_metadata` against itself. Hence the
  explicit JSON-native clause and the post-coercion scenario in the delta spec.
- **The id rename resets every Bloom idempotency key, and `weights_checksum` does not protect you.**
  Surfaced by Elizabeth resolving task 2.5(e) on 2026-08-11; it was unflagged in every earlier draft,
  including the risk list it belongs in. `sleap-roots-contracts`' `compute_idempotency_key` hashes
  `(registry_id, version, weights_checksum)`, so renaming all 8 collections changes every downstream
  key **even though the weights are byte-identical**. Bloom will therefore not recognize a post-rename
  run as identical to a pre-rename one for the same scan, weights and parameters, and will recompute.
  This is a cost, not a bug: redundant compute, once, as a step change rather than ongoing churn. Note
  the earlier risk analysis in this document worried about the *opposite* failure — digest churn
  causing Bloom double-counting — and concluded the pinned archive form keeps `weights_checksum`
  stable. That conclusion still holds and is simply not sufficient, because `weights_checksum` is only
  one of three inputs to the key. It also does not argue for a different id scheme: any scheme that
  lets one card carry several species has to rename these ids. Accept it knowingly (`tasks.md` 0.2).
- **Age-window semantics unchanged.** A card serving canola (2–13) and pennycress (2–14) advertises
  neither window globally. `choose_models` must match the age against the *matching selector*, not
  against a card-level min/max, or canola silently gains a year of coverage.
- **Collection-id uniqueness guard** must be kept: with fewer, differently-named collections the
  existing duplicate-id fail-fast check still applies and its test needs updating, not deleting.
