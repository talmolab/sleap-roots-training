## MODIFIED Requirements

### Requirement: Per-Species, Per-Root-Type Card Expansion

The package SHALL expand the selection matrix into **one card per physical model per root type**,
not one card per matrix row. Rows naming the same `source_model_id` in the same root-type slot SHALL
collapse into a single card whose `selectors` list carries each contributing row's own `species`,
`mode`, and age window **verbatim and bundled together**, so no selection combination is advertised
that no row declared. Selectors SHALL be de-duplicated and emitted in a deterministic order. Empty
(`null`) root-type slots SHALL produce no card. Each card's `root_type` SHALL remain scalar, and the
expansion SHALL fail loudly if any single physical model resolves to more than one `root_type`.

#### Scenario: Row with primary and lateral models

- **WHEN** a row lists a `primary_model_id` and a `lateral_model_id` and a `null` `crown_model_id`
- **THEN** that row contributes a selector to exactly two cards, with `root_type` `"primary"` and
  `"lateral"`
- **AND** no card is produced for the `null` crown slot

#### Scenario: Crown-only row contributes a single crown selector

- **WHEN** a row lists a `null` `primary_model_id`, a `null` `lateral_model_id`, and a non-null
  `crown_model_id` (for example rice cylinder age 6–10)
- **THEN** it contributes a selector to exactly one card, with `root_type` `"crown"`
- **AND** no card is produced for the `null` primary or lateral slots

#### Scenario: A model shared across species collapses to one card

- **WHEN** the same physical model id appears as the primary model in four rows (canola cylinder age
  2–13, pennycress cylinder age 2–14, arabidopsis multiplant-cylinder age 2–14, arabidopsis cylinder
  age 2–14)
- **THEN** exactly **one** `primary` card is produced for that model
- **AND** its `selectors` contain exactly those four (species, mode, age_min, age_max) tuples, each
  preserving its own row's age window
- **AND** the committed matrix as a whole expands to exactly **8** cards over 8 physical models

#### Scenario: A model shared across modes of one species collapses to one card

- **WHEN** the same lateral model id appears under one species in two different modes (arabidopsis
  `cylinder` and arabidopsis `multiplant cylinder`, both age 2–14)
- **THEN** exactly one `lateral` card is produced, carrying both selectors
- **AND** the two selectors differ only in `mode`

#### Scenario: A physical model spanning two root types is rejected

- **WHEN** a matrix edit causes one `source_model_id` to appear in two different root-type slots
- **THEN** expansion fails fast, naming the offending model id
- **AND** no cards are produced

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a metadata mapping containing a scalar `root_type` (one of `"primary"`,
`"lateral"`, `"crown"`) and a non-empty `selectors` list, where each selector carries `species`
(str), `mode` (a member of the contract-owned `Mode` vocabulary, stored raw with its space preserved
and never the hyphenated collection-id slug), `age_min` (int ≥ 0), and `age_max` (int ≥ 0) — plus a
non-contract `source_model_id` for traceability. It SHALL NOT include the wandb-intrinsic keys
`registry_id`, `version`, or `weights_checksum`, and SHALL NOT carry card-level `species`, `mode`,
`age_min`, or `age_max` fields, since a card may serve several selection contexts. This mapping is
the **complete** stored artifact metadata (producer lineage lives in the run config, not
per-artifact). The mapping SHALL validate against the `ModelCard` schema from
`sleap-roots-contracts`, which matches `mode` exactly and normalizes neither case nor whitespace.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains exactly `root_type`, `selectors`, and `source_model_id`
- **AND** it omits `registry_id`, `version`, and `weights_checksum`
- **AND** it carries no card-level `species`, `mode`, `age_min`, or `age_max`
- **AND** constructing the real `sleap_roots_contracts.ModelCard` from the metadata plus placeholder
  `registry_id`/`version`/`weights_checksum` succeeds despite the extra `source_model_id`
  (contract `extra="ignore"`)

#### Scenario: Every accepted mode survives the round trip

- **WHEN** a card is built for each mode the matrix loader accepts
- **THEN** its metadata mapping validates against the real `ModelCard` for every one of them
- **AND** each validated selector's `mode` equals the raw stored value

#### Scenario: A card with no selectors is rejected

- **WHEN** a metadata mapping carries an empty `selectors` list
- **THEN** validation against the `ModelCard` contract fails

### Requirement: Production Model Publishing and Registry Linking

The package SHALL publish **one wandb artifact of `type="model"` per physical model**, whose metadata
is that card's selection metadata, adding the resolved (junk-free) model directory via `add_dir`,
logging it to a run, and linking it into that card's collection under the configured registry with
the configured production alias, using the registry target path
`f"{entity}-org/wandb-registry-{registry}/{collection}"` built with literal forward slashes on all
platforms. The same weights SHALL NOT be uploaded more than once. Each card SHALL map to its own
distinct collection so the production alias is unique per collection; the full card set SHALL be
checked for collection-id uniqueness and duplicate ids SHALL fail the seed before any publish.

#### Scenario: Publish a card and link it as production

- **WHEN** a card is published
- **THEN** a wandb artifact of type `"model"` is created carrying exactly the card's selection
  metadata, including its full `selectors` list
- **AND** the resolved (junk-free) model directory is added via `add_dir`
- **AND** the artifact is linked into its collection under the registry with the production alias,
  using a target path built with forward slashes

#### Scenario: Shared weights are published exactly once

- **WHEN** several matrix rows resolve to the same physical model directory for one root type
- **THEN** exactly one artifact is published for those weights, carrying every one of those rows'
  selectors
- **AND** the same directory is not uploaded a second time under a different collection

#### Scenario: Two age-window crown models of the same species are both production

- **WHEN** two crown models of the same species and mode cover different age windows (rice cylinder
  crown age 2–5 and age 6–10)
- **THEN** they remain **two distinct cards**, because they are two distinct physical models
- **AND** each is linked into its own distinct collection, and both carry the production alias
  simultaneously

#### Scenario: Duplicate collection ids fail before any publish

- **WHEN** the expanded card set would produce two cards with the same collection id (a guard
  against future matrix edits)
- **THEN** the seed fails fast, naming the colliding cards, before any artifact is published
