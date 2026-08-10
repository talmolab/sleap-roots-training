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
would otherwise produce a duplicate selector) and emitted in a deterministic order so metadata is
stable across re-seeds — important because the artifact digest feeds `weights_checksum`, which Bloom
uses as a compute-idempotency key.

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
4. Retire or leave-in-place the 5 now-orphaned collections — **decide explicitly**, do not leave it
   implicit. They still hold the `production` alias, so a consumer that resolves by collection name
   would keep getting an old-shape card.

Two viable transition strategies, to be chosen with the contracts owner:

- **Flag day.** Contracts requires `selectors`; predict and the re-seed land together. Simplest to
  reason about, but there is a window where production metadata does not match the contract.
- **Tolerant read.** Contracts accepts either shape for one release (a validator that lifts a flat
  card into a single-selector card), letting predict upgrade before the re-seed and removing the
  flag-day window. More code, but no moment where the live registry is unreadable.

**Recommendation: tolerant read**, because the registry is production data consumed by a pipeline we
do not control the deploy timing of. Revisit if the contracts owner prefers a clean break.

## Risks

- **Digest churn.** Re-seeding republishes artifacts; `weights_checksum` is a whole-artifact digest
  and Bloom uses it as an idempotency key. Deterministic selector ordering plus the SHA256-pinned
  archive form should keep digests stable for unchanged weights, but this must be **verified against
  a real re-seed**, not assumed.
- **Age-window semantics unchanged.** A card serving canola (2–13) and pennycress (2–14) advertises
  neither window globally. `choose_models` must match the age against the *matching selector*, not
  against a card-level min/max, or canola silently gains a year of coverage.
- **Collection-id uniqueness guard** must be kept: with fewer, differently-named collections the
  existing duplicate-id fail-fast check still applies and its test needs updating, not deleting.
