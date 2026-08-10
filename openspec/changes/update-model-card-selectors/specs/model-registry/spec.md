## RENAMED Requirements

- FROM: `### Requirement: Per-Species, Per-Root-Type Card Expansion`
- TO: `### Requirement: Per-Physical-Model, Per-Root-Type Card Expansion`

## MODIFIED Requirements

### Requirement: Per-Physical-Model, Per-Root-Type Card Expansion

The package SHALL expand the selection matrix into **one card per physical model per root type**,
not one card per matrix row. Rows naming the same `source_model_id` in the same root-type slot SHALL
collapse into a single card whose `selectors` list carries each contributing row's own `species`,
`mode`, and age window **verbatim and bundled together**, so no selection combination is advertised
that no row declared. Selectors SHALL be de-duplicated and emitted in a deterministic order derived
only from the selector values themselves — never from matrix row order, dict insertion order, or
salted `hash()` — so the emitted metadata is reproducible across processes and machines. Empty
(`null`) root-type slots SHALL produce no card. Each card's `root_type` SHALL remain scalar, and the
expansion SHALL fail loudly if any single physical model resolves to more than one `root_type`,
since the one-card-per-physical-model identity rests on that assumption.

#### Scenario: Row with primary and lateral models

- **WHEN** a row lists a `primary_model_id` and a `lateral_model_id` and a `null` `crown_model_id`
- **THEN** that row contributes a selector to exactly two cards, with `root_type` `"primary"` and
  `"lateral"`
- **AND** no card is produced for the `null` crown slot

#### Scenario: Primary-plus-crown row with no lateral

- **WHEN** a row lists a `primary_model_id` and a `crown_model_id` and a `null` `lateral_model_id`
  (for example rice cylinder age 2–5)
- **THEN** it contributes a selector to exactly two cards, with `root_type` `"primary"` and
  `"crown"`
- **AND** no card is produced for the `null` lateral slot

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
- **AND** its `selectors` equal exactly that set of four `(species, mode, age_min, age_max)` tuples,
  each preserving its own row's age window (so canola keeps `age_max = 13` while the other three
  keep `age_max = 14`, and no selector advertises a window no row declared)
- **AND** that single card records the shared `source_model_id` every contributing row named
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

#### Scenario: Identical rows do not produce a duplicate selector

- **WHEN** two matrix rows would contribute the same (species, mode, age_min, age_max) selector to
  one card
- **THEN** that selector appears exactly once on the card

#### Scenario: Selector order is deterministic across processes

- **WHEN** the same matrix is expanded in two separate processes started with different
  `PYTHONHASHSEED` values
- **THEN** each card's `selectors` are emitted in the same order both times
- **AND** the emitted metadata mapping is byte-identical, so any metadata difference a re-seed
  reports is a real change rather than an ordering artifact

#### Scenario: Selector order does not depend on matrix row order

- **WHEN** the same set of matrix rows is expanded in a different row order
- **THEN** each card's `selectors` are emitted in the same order as before

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a metadata mapping containing **exactly** the selection dimensions the
consumer reads — a scalar `root_type` (one of `"primary"`,
`"lateral"`, `"crown"`) and a non-empty `selectors` list, where each selector carries `species`
(str), `mode` (a member of the contract-owned `Mode` vocabulary, stored raw with its space preserved
and never the hyphenated collection-id slug), `age_min` (int ≥ 0), and `age_max` (int ≥ 0) — plus a
non-contract `source_model_id` for traceability, and `sleap_nn_version` where the model was produced
by `sleap-nn` (legacy models omit it, leaving `ModelCard.sleap_nn_version` as `None`). It SHALL NOT
include the wandb-intrinsic keys `registry_id`, `version`, or `weights_checksum`, and SHALL NOT carry
card-level `species`, `mode`, `age_min`, or `age_max` fields, since a card may serve several
selection contexts. This mapping is the **complete** stored artifact metadata (producer lineage lives
in the run config, not per-artifact — see Seed Run Lineage). The mapping SHALL validate against the
`ModelCard` schema from `sleap-roots-contracts`, which matches `mode` exactly and normalizes neither
case nor whitespace.

Because `sleap_nn_version` describes the physical weights rather than a selection context, it stays a
scalar card-level field and is NOT moved into `Selector`.

The "no card-level `species`/`mode`/`age_min`/`age_max`" clause deliberately rules out emitting both
shapes at once. New-shape metadata is therefore **not** readable by a consumer still pinned to the
pre-`selectors` contract, whose `ModelCard` is `extra="ignore"` with those four fields required — it
would drop `selectors` and then fail on the missing required fields. Forward compatibility (new code
reading old published metadata) is handled by the tolerant read; **backward** compatibility is
handled operationally instead, by not overwriting the collections old consumers read until their
upgrade is confirmed deployed — see `design.md` "Reverse compatibility" and the retirement gate in
`tasks.md`.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains **exactly** `root_type`, `selectors`, and `source_model_id` — plus
  `sleap_nn_version` for a `sleap-nn`-produced model and nothing else
- **AND** it omits `registry_id`, `version`, and `weights_checksum`
- **AND** it carries no card-level `species`, `mode`, `age_min`, or `age_max`
- **AND** constructing the real `sleap_roots_contracts.ModelCard` from the metadata plus placeholder
  `registry_id`/`version`/`weights_checksum` succeeds despite the extra `source_model_id`
  (contract `extra="ignore"`)

#### Scenario: Every accepted mode survives the round trip

- **WHEN** a card is built for each mode the matrix loader accepts
- **THEN** its metadata mapping validates against the real `ModelCard` for every one of them
- **AND** each validated selector's `mode` equals the raw stored value

#### Scenario: Legacy models carry no sleap_nn_version

- **WHEN** a card is produced for a legacy (non-`sleap-nn`) model
- **THEN** the metadata mapping does not include a `sleap_nn_version` key
- **AND** the resulting `ModelCard.sleap_nn_version` is `None`

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
checked for collection-id uniqueness and duplicate ids SHALL fail the seed before any publish. (Note:
the consumer stores `artifact.digest` as `weights_checksum`, which downstream Bloom uses as a
compute-idempotency key; because the whole directory is added, that digest is a whole-artifact
checksum, not weights-only. For the **SHA256-pinned archive form**, byte-identical zip → identical
junk-free contents → identical `add_dir` manifest → **deterministic** published digest **under the
pinned wandb writer** (`<0.29`), so a legitimate re-seed does not churn `weights_checksum` and cause
Bloom double-counting; a `--force` re-seed whose source checksum differs is the intended signal that
the weights genuinely changed. The unpinned dir form does not carry this guarantee, which is why
production writes use the archive form. Artifact **metadata is not an input to that manifest digest
at all**, so moving the selection dimensions into `selectors` neither stabilizes nor churns
`weights_checksum` — it is the pinned archive form, not the metadata layout, that keeps the digest
deterministic.)

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
  crown age 2–5, `rice/younger/crown/220821_163331.multi_instance.n=867`, and age 6–10,
  `rice/older/crown/221208_113552.multi_instance.n=574`)
- **THEN** they remain **two distinct cards**, because they are two distinct physical models
- **AND** each is linked into its own distinct collection, whose ids are the two distinct ids the
  Collection Identifier Scheme yields for those two model ids
- **AND** both carry the production alias simultaneously (linking the second does not move the alias
  off the first)

#### Scenario: Duplicate collection ids fail before any publish

- **WHEN** the expanded card set would produce two cards with the same collection id (a guard
  against future matrix edits)
- **THEN** the seed fails fast, naming the colliding cards, before any artifact is published

## ADDED Requirements

### Requirement: Collection Identifier Scheme

Because a card no longer has a single `species`/`mode`/age window to name itself with, the package
SHALL derive each card's collection id from a **single documented scheme implemented in one
function**, used by publishing, `--only`, and `--verify` alike, so the producer cannot compute one id
when writing and a different one when reading back. The id SHALL be a deterministic function of the
card alone, SHALL be unique across the expanded card set (the existing duplicate-id fail-fast guard
still applies), and SHALL be a **legal wandb artifact name** — in particular it SHALL NOT contain
`/`, which `wandb.sdk.artifacts._validators.validate_artifact_name` rejects outright and which every
`source_model_id` in the committed matrix contains. The scheme SHOULD also be stable against a
metadata-only edit, so that adding a selector to an existing card does not rename a live production
collection.

The concrete formula is the subject of decision 0.2 in `tasks.md` (recommendation: derive from
`source_model_id`); this requirement fixes the properties any chosen formula must satisfy, and the
formula itself is recorded here once 0.2 is agreed.

#### Scenario: Collection ids are legal wandb artifact names

- **WHEN** collection ids are computed for every card the committed matrix expands to
- **THEN** each id is accepted by wandb's own artifact-name validator rather than a hand-rolled
  regex (a test double that validates nothing cannot catch this)
- **AND** no id contains a `/` inherited from its `source_model_id`

#### Scenario: One scheme serves publish, --only, and --verify

- **WHEN** a card's collection id is computed on the publish path and on the verification path
- **THEN** both paths call the same function and obtain the same id
- **AND** a `--only` value matching a card's id therefore selects that card on every mode

### Requirement: Orphaned Collection Reporting

The `--verify` mode SHALL additionally **report any production-aliased collection in the registry
that the current expansion no longer produces**, so that collections orphaned by an expansion change
are surfaced rather than silently ignored. Orphan reporting SHALL NOT delete a collection or move any
alias — retirement stays a separate, human-gated act. Because `--verify --only <id>` narrows the
expected set, orphan reporting SHALL be **suppressed under `--only`** (where every unnamed
collection would otherwise be reported as orphaned, including the ones the canary has not reached
yet) and SHALL state in its output that the orphan check was skipped for that reason. Orphans SHALL
NOT affect the exit code: a missing production alias on an *expected* collection is a failure, while
an orphan is an advisory finding a human must act on.

#### Scenario: Verify reports collections the expansion no longer produces

- **WHEN** the registry holds a production-aliased collection whose id is absent from the current
  expanded card set (as every collection named under the previous id scheme is, once the ids are
  derived from `source_model_id`)
- **THEN** `--verify` names that collection as orphaned in its report
- **AND** it does not delete the collection or move its production alias
- **AND** the orphan does not by itself make the command exit non-zero

#### Scenario: Orphan reporting is suppressed under --only

- **WHEN** `--verify --only <collection_id>` is run during a canary, so most in-registry collections
  are outside the narrowed expected set
- **THEN** the report does not list those collections as orphaned
- **AND** it states that the orphan check was skipped because `--only` narrowed the scope

### Requirement: Re-Publish Metadata Refresh

Because artifact metadata is not part of the `add_dir` manifest digest, re-logging unchanged weights
can be a content-level no-op, leaving the previously published metadata live. A re-seed that reports
a collection as `published` SHALL therefore confirm that the metadata actually visible on the
production-aliased artifact is the new-shape metadata, and SHALL report the collection as failed —
not published — if the artifact still carries the old flat metadata. `--force` alone SHALL NOT be
treated as sufficient evidence of a metadata refresh, since it bypasses the idempotency read rather
than guaranteeing a new stored metadata blob.

#### Scenario: Re-publish that leaves stale metadata is reported as a failure

- **WHEN** a card is re-published over an existing collection whose weights are byte-identical, and
  the production-aliased artifact still reads back with card-level `species`/`mode`/`age_min`/
  `age_max` and no `selectors`
- **THEN** the seed reports that collection as failed rather than published, naming it
- **AND** the reported failure distinguishes "weights unchanged" from "metadata not refreshed"

#### Scenario: Successful re-publish reads back the new shape

- **WHEN** a card is re-published and the production-aliased artifact reads back carrying
  `selectors` and no card-level selection fields
- **THEN** the seed reports that collection as published
