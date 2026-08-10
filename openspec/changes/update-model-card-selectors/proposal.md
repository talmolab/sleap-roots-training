# Proposal: Carry bundled selectors on one card per physical model

## Why

The live registry holds **13 `ModelCard` registrations backed by only 8 physically distinct model
files** (issue #39), because `ModelCard.species` is a single required `str` and the seeding path
therefore has no way to say "this one artifact selects for several species". Give a card a bundled
selector list instead, and one card describes one physical model — taking registrations to exactly 8
and making a generalist model editable in one place.

## Background

**Issue #39 is the source of truth for the storage finding** (13 registrations, 8 files, the 4x/2x/2x
breakdown). The *axis analysis* below — the 1-of-5 measurement, and which pairs merge under which
shape — is regenerated here from `src/sleap_roots_training/registry/data/model_selection.yaml` with
this repo's own expansion code, and `tasks.md` §3.8/§3.10 pin it as assertions so it cannot drift.
Where the two disagree, **this document is correct**: #39's 2026-08-10 comment describes the
canola/pennycress lateral pair as differing "only by `age`" when it differs by species *and* age.
`tasks.md` §6.4 posts that correction on #39, so the declared source of truth stops contradicting the
landed design.

One generalist primary-root model is registered **four times**:

| copies | model | registered as |
|---|---|---|
| 4x | `canola_pennycress_arabidopsis/primary/240611_102513...n=743` | canola / pennycress / arabidopsis-multiplant / arabidopsis cylinder |
| 2x | `arabidopsis/lateral/240130_140452...n=337` | arabidopsis cylinder + arabidopsis multiplant cylinder |
| 2x | `canola/lateral/240611_083419...n=631` | canola + pennycress cylinder |

This is **not a seeding bug**. It faithfully mirrors a deliberate original modeling choice (one
generalist primary-root model trained across arabidopsis/canola/pennycress).

**The cost is maintenance drift, not storage.** Replacing that generalist model means updating N
registrations, and it worsens as more generalist models are promoted. Earlier drafts quoted "~300MB
for four copies of one file"; that is very likely wrong, because wandb content-addresses file blobs —
`store_file` reports a duplicate and skips the upload when the server already holds the hash, and V1
download URLs are keyed on the content hash — so the four artifacts almost certainly reference one
stored copy. What is duplicated is the artifact/collection *records* and the staging and hashing work,
not the bytes. `tasks.md` §6.2 records the registry's actual storage figures rather than quoting an
inferred number. The argument does not need it: the contract simply cannot express a generalist model,
and `design.md` shows a collection cannot carry its own metadata either.

**Why not simply widen `species` to a tuple.** Measured against the real matrix, that removes only
**1 of the 5** redundant registrations (13 → 12), because species is not the only axis the same
weights are registered across:

- the `arabidopsis/lateral` pair differs **only by mode** (`cylinder` vs `multiplant cylinder`), same
  species, so a species tuple does nothing;
- the `canola`/`pennycress` lateral pair differs by species **and** age window (2–13 vs 2–14), so
  tupling species leaves the age difference behind and the two still cannot merge — age is the
  *residual* axis, not the only one;
- only the pennycress and arabidopsis-cylinder primary rows agree on **mode and age window**
  (`cylinder`, 2–14) and therefore differ *only* in species — that single pair is all a species tuple
  merges.

**Why not tuple `species` and `mode` independently.** That would make a card match the *cross
product* of its axes, advertising combinations nobody trained or validated — for example canola in
`multiplant cylinder` mode. Silent, wrong matches in `choose_models` are worse than duplicated
storage.

## What Changes

**BREAKING** (contract shape, and every live collection id). Introduce a **bundled selector** so one
card describes one physical model and lists the exact (species, mode, age-window) combinations it was
validated for.

```python
class Selector(BaseModel):
    species: str
    mode: Mode
    age_min: int
    age_max: int

class ModelCard(BaseModel):
    root_type: RootType
    selectors: tuple[Selector, ...]
    registry_id: str
    version: str
    weights_checksum: str | None = None
    sleap_nn_version: str | None = None   # stays card-level: describes the weights, not a context
```

- **`root_type` stays scalar.** It is intrinsic to the physical weights — a primary-root model is
  never also a lateral one. Verified: every one of the 8 physical models maps to exactly one
  `root_type`.
- **Card expansion becomes per physical model, not per matrix row.** Rows that name the same
  `source_model_id` for the same root type collapse into one card whose `selectors` are those rows'
  own (species, mode, age) triples, each preserved verbatim.
- **`choose_models` (sleap-roots-predict) generalizes** from three flat equality checks to "does
  **any** selector on this card match all of (species, mode, age)?" — no cross-product, so no
  unvalidated combination can match.
- **Publishing collapses to one artifact per physical model**, removing all 5 redundant uploads.

Result: **13 registrations → exactly 8, one per physical file.** The full fix, not the 1-of-5
partial reduction a bare species tuple gives.

The canola age-13-vs-14 question is deliberately **not** decided here: under this design it does not
need to be. Canola keeps its own age 2–13 selector while pennycress/arabidopsis keep 2–14, all on one
card pointing at one artifact. Deriving/validating age windows from the associated `LabelCard`(s)
instead of hand-curating them is tracked separately in #46.

## Blocked on

Two of the three repos involved are outside this one, and nothing here can mark their work done. They
are listed as prerequisites rather than tickable tasks so this change stays archivable; `tasks.md`
§1 and §2 record the acceptance conditions, and the items that genuinely are ours stay checkboxes
there (filing the two tracking issues, 1.0 / 2.0, and verifying predict's lister behavior, 2.5).

- **`sleap-roots-contracts`** — add `Selector`, reshape `ModelCard`, release a pre-release. Must land
  first; this repo cannot bump a pin that does not exist. Owner unassigned as of this proposal
  (`tasks.md` 0.5). Issue: *to be filed.*
- **`sleap-roots-predict`** — generalize `choose_models`, match age against the *matching* selector,
  pin the new contracts. Must be deployed before the old collections are retired, not merely merged.
  Issue: *to be filed*; cross-link predict#14.

## Impact

- **Affected specs:** `model-registry` — two requirements replaced (removed + re-added under
  per-physical-model names, because their scenarios assert the per-row behavior by name and OpenSpec's
  archiver refuses a MODIFIED block that drops a scenario name), three modified in place
  (`ModelCard Selection Metadata`, `Idempotent Re-Seed`, `Registry Verification Command`,
  `Registry Seeding CLI with Confirmed Execution`), three added (Collection Identifier Scheme,
  Orphaned Collection Reporting, Re-Publish Metadata Refresh).
- **Affected code:** `registry/cards.py` (expansion, `card_to_metadata`, `collection_id`, and its
  docstrings, which currently describe per-row/per-species semantics as fact), `registry/__init__.py`
  and `registry/chooser.py` (docstrings asserting the flat shape as fact), `registry/publish.py`
  (`verify_registry` gains orphan reporting and the metadata-shape check; `seed_registry` gains the
  read-back and a `failed` bucket), and `cli.py` (`--only` scoping, the orphan report, the new
  bucket, `--only` help text). `publish.py`'s **publish path** needs no structural change — it is
  card-driven, so 8 cards yield 8 artifacts with no diff to `publish_card`.
- **Affected tests:** `test_registry_cards.py`, `test_registry_chooser.py`, `test_registry_smoke.py`,
  `test_registry_publish.py` (hardcodes `== 13`), `test_registry_cli.py`, and `test_config.py` if
  `cards._ROOT_SLOTS` moves. Also `scripts/regen_model_checksums.py`, which consumes the `Card` API
  and is outside CI's path filters, outside the lint targets, and untested — a break there is silent.
  The publish and CLI tests are **not** deferrable: simulating just the collection-id change reddens
  9 tests across them, and the `--verify`/read-back work reddens them again.
- **Affected docs:** `README.md` "Notes for downstream consumers" currently states the **opposite**
  of this design; `docs/roadmap.md`; `docs/CHANGELOG.md`; and the `model-registry` spec Purpose, still
  a literal `TBD` placeholder.
- **BREAKING, cross-repo, and ordered.** See "Blocked on" above and `design.md` for sequencing plus
  the live-registry migration, which is the sharpest risk. Forward: the 13 already-published
  artifacts carry old flat metadata and stop validating against the new `ModelCard` (handled by the
  tolerant read). Backward: an old-pinned consumer cannot read a new-shape card either, and the schema
  cannot fix that without a dishonest scalar `species` — so it is handled operationally, by the
  recommended id scheme leaving the 13 old collections untouched and gating their retirement on the
  consumer's confirmed deployment.
- **Related:** sleap-roots-predict#14 (warm cache materializing shared weights up to 4x) becomes
  largely moot for the shared-primary case once this lands, though its checksum-dedup remains
  reasonable defense-in-depth. #46 tracks LabelCard-derived age windows.
