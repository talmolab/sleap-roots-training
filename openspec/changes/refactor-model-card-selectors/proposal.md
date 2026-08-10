# Proposal: Carry bundled selectors on one card per physical model

## Why

The live `wandb-registry-sleap-roots-models` registry holds **13 `ModelCard` registrations backed by
only 8 physically distinct model files** (talmolab/sleap-roots-training#39). Each registration is a
full, separate ~75MB wandb artifact, so one generalist primary-root model is stored **four times**
(~300MB for four copies of one file). Verified against
`src/sleap_roots_training/registry/data/model_selection.yaml` by expanding the matrix with this
repo's own code:

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
- the `canola`/`pennycress` lateral pair differs **only by age window** (2–13 vs 2–14);
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

## Impact

- **Affected specs:** `model-registry`.
- **Affected code:** `registry/cards.py` (expansion, `card_to_metadata`, `collection_id`),
  `registry/publish.py` (one artifact per model), `registry/models.py`, and their tests.
- **BREAKING, cross-repo, and ordered.** The `Selector` / `ModelCard.selectors` shape lands in
  **`sleap-roots-contracts`** first and must be released before this repo can pin it;
  **`sleap-roots-predict`** must adopt the generalized `choose_models` before or with the re-seed.
  See `design.md` for sequencing and the live-registry migration, which is the sharpest risk: the 13
  already-published artifacts carry the old flat metadata and will not validate against the new
  `ModelCard`.
- **Related:** sleap-roots-predict#14 (warm cache materializing shared weights up to 4x) becomes
  largely moot for the shared-primary case once this lands, though its checksum-dedup remains
  reasonable defense-in-depth. #46 tracks LabelCard-derived age windows.
