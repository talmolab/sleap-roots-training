# Proposal: Carry bundled selectors on one card per physical model

## Why

**Issue #39 is the source of truth for the redundancy analysis**; the numbers below are reproduced
here only so this proposal stands alone, and #39 wins if the two ever disagree. All of them are
regenerable from `src/sleap_roots_training/registry/data/model_selection.yaml` with this repo's own
expansion code (see `tasks.md` §3.8 and §3.10, which pin them as assertions so they cannot drift
silently).

The live `wandb-registry-sleap-roots-models` registry holds **13 `ModelCard` registrations backed by
only 8 physically distinct model files**. Each registration is a full, separate ~75MB wandb artifact,
so one generalist primary-root model is stored **four times** (~300MB for four copies of one file):

| copies | model | registered as |
|---|---|---|
| 4x | `canola_pennycress_arabidopsis/primary/240611_102513...n=743` | canola / pennycress / arabidopsis-multiplant / arabidopsis cylinder |
| 2x | `arabidopsis/lateral/240130_140452...n=337` | arabidopsis cylinder + arabidopsis multiplant cylinder |
| 2x | `canola/lateral/240611_083419...n=631` | canola + pennycress cylinder |

This is **not a seeding bug**. It faithfully mirrors a deliberate original modeling choice (one
generalist primary-root model trained across arabidopsis/canola/pennycress). The duplication exists
because `ModelCard.species` is a single required `str`, so the seeding path has no way to say "this
one artifact selects for several species" and must register the same weights once per matrix row.

Cost is storage plus **maintenance drift**: replacing that generalist model means updating N
registrations, and it worsens as more generalist models are promoted.

**Why not simply widen `species` to a tuple.** Measured against the real matrix, that removes only
**1 of the 5** redundant registrations (13 → 12, ~75MB of ~375MB), because species is not the only
axis the same weights are registered across:

- the `arabidopsis/lateral` pair differs **only by mode** (`cylinder` vs `multiplant cylinder`), same
  species, so a species tuple does nothing;
- the `canola`/`pennycress` lateral pair differs by species **and** age window (2–13 vs 2–14), so
  tupling species leaves the age difference behind and the two still cannot merge — age is the
  *residual* axis, not the only one;
- only the pennycress/arabidopsis cylinder primary pair shares species+mode+age and actually merges.

**Why not tuple `species` and `mode` independently.** That would make a card match the *cross
product* of its axes, advertising combinations nobody trained or validated — for example canola in
`multiplant cylinder` mode. Silent, wrong matches in `choose_models` are worse than duplicated
storage.

## What Changes

Introduce a **bundled selector** so one card describes one physical model and lists the exact
(species, mode, age-window) combinations it was validated for.

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

- **Affected specs:** `model-registry` — one requirement renamed, three modified, three added
  (Collection Identifier Scheme, Orphaned Collection Reporting, Re-Publish Metadata Refresh).
- **Affected code:** `registry/cards.py` (expansion, `card_to_metadata`, `collection_id`, and its
  docstrings, which currently describe per-row/per-species semantics as fact), `registry/__init__.py`
  (same in the subpackage docstring), `cli.py` (the `--only` / orphan-report interaction), and the
  `--verify` path. `registry/publish.py` needs **no** structural change — it is entirely card-driven,
  so 8 cards yield 8 artifacts with a zero-line diff, and its docstrings are shape-agnostic.
- **Affected tests:** `test_registry_cards.py`, `test_registry_chooser.py`, `test_registry_smoke.py`,
  `test_registry_publish.py` (hardcodes `== 13`), `test_registry_cli.py`, `tests/conftest.py`. The
  last three are **not** deferrable to a later commit — simulating just the collection-id change
  reddens 9 tests across `test_registry_publish.py` and `test_registry_cli.py`.
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
