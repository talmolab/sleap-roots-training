## ADDED Requirements

### Requirement: Label Collection Backfill onto LabelCard

The package SHALL map each of the 8 existing `wandb-registry-sleap-roots-labels` collections onto
the `LabelCard` contract from `sleap-roots-contracts`, constructing metadata from the artifact's
existing description, metadata keys, and `.slp` content. Provenance fields that cannot be recovered
from the artifact or cross-referenced against Bloom SHALL be set to `null` — no values SHALL be
fabricated to satisfy the schema. Each collection SHALL be verified as single-species content before
a `LabelCard` is stamped onto it.

#### Scenario: Backfilled card with full provenance

- **WHEN** an existing label collection's artifact description and Bloom cross-reference yield a
  recoverable `bloom_experiment_id`, accession IDs, and species
- **THEN** the `LabelCard` is constructed with those values populated
- **AND** the card validates against the `LabelCard` contract

#### Scenario: Backfilled card with unrecoverable provenance

- **WHEN** an existing label collection's provenance cannot be fully reconstructed (deleted temp
  `data_path`, no Bloom cross-reference)
- **THEN** the unrecoverable fields are set to `null`
- **AND** the card still validates against the `LabelCard` contract
- **AND** no fabricated values appear in the metadata

#### Scenario: Single-species verification rejects mixed content

- **WHEN** a collection is found to contain frames from more than one species
- **THEN** the backfill process rejects that collection with a clear error
- **AND** no `LabelCard` is stamped onto it

### Requirement: Normalized Label Collection Naming

The package SHALL create new wandb collections following the `{species}-{mode}-{root_type}` naming
convention (hyphens, matching the model registry pattern) for each backfilled label set. Existing
artifact versions SHALL be linked into the new collection (not re-published), preserving the
original artifact digest. The old collections SHALL remain resolvable (not deleted or orphaned) but
SHALL NOT carry the `production` alias — only the normalized collections SHALL carry it.

#### Scenario: Existing artifact linked into normalized collection

- **WHEN** an existing label artifact is migrated to a normalized collection name
- **THEN** the artifact version is linked (not re-published) into the new collection
- **AND** the artifact digest is identical before and after linking
- **AND** the new collection carries the `production` alias

#### Scenario: Old collection remains resolvable

- **WHEN** an artifact has been linked into a new normalized collection
- **THEN** the old collection name still resolves the artifact
- **AND** the old collection does not carry the `production` alias

#### Scenario: No duplicate collection ids

- **WHEN** the full set of label cards is expanded
- **THEN** every card maps to a unique collection id
- **AND** duplicate ids fail the migration before any artifact is linked

### Requirement: Label Root-Type Vocabulary

The label-side root-type vocabulary SHALL be a superset of the model-side vocabulary, including
`seminal` in addition to `primary`, `lateral`, and `crown`. A label collection MAY describe a root
type for which no trained model exists. The model-side `_ROOT_SLOTS` SHALL NOT be modified by this
change.

#### Scenario: Seminal is a valid label root type

- **WHEN** a label collection is built for root type `seminal`
- **THEN** the root type validates against the label vocabulary
- **AND** a `LabelCard` can be constructed with `root_type="seminal"`

#### Scenario: Model vocabulary is unchanged

- **WHEN** a model card is expanded from the selection matrix
- **THEN** only `primary`, `lateral`, and `crown` are valid root types
- **AND** `seminal` is not accepted in the model-side vocabulary

### Requirement: Label Species Vocabulary

The species vocabulary SHALL include all species with published label data in the
`sleap-roots-labels` registry, including `wheat`, `sorghum`, and `medicago` alongside the
existing species.

#### Scenario: Species with published labels is accepted

- **WHEN** a label collection exists for a species with published label data (e.g. `wheat`,
  `sorghum`, `medicago`)
- **THEN** the species validates against the vocabulary
- **AND** a `LabelCard` can be constructed for that species

### Requirement: Label Registry Seeding CLI

The package SHALL provide a `seed-label-registry` subcommand that reads the backfill mapping,
constructs `LabelCard` metadata, and — by default — runs a dry run printing planned collections
and metadata without contacting wandb. Publishing SHALL require `--execute`, which SHALL check for
a resolvable wandb credential before proceeding. The CLI SHALL accept `--only <collection_id>` for
canary migration and `--verify` for read-back, following the same patterns as the model
`seed-registry` command.

#### Scenario: Dry run prints plan without network

- **WHEN** `seed-label-registry` is run without `--execute`
- **THEN** the planned normalized collection names and per-card metadata are printed
- **AND** no wandb network call is made

#### Scenario: Canary migration with --only

- **WHEN** `seed-label-registry --execute --only <collection_id>` is run
- **THEN** only that collection is migrated
- **AND** a subsequent full `--execute` skips the already-migrated collection

#### Scenario: Verify reads back the production alias

- **WHEN** `seed-label-registry --verify` is run after migration
- **THEN** it reports every expected normalized collection and whether its production-aliased
  artifact is present
- **AND** it exits non-zero if any expected collection lacks the production alias

### Requirement: Idempotent Label Registry Migration

Re-running the label migration SHALL be safe: for each card, if the target normalized collection
already holds an artifact carrying the `production` alias, the migration SHALL skip that card and
report it, unless `--force` is given.

#### Scenario: Re-run skips already-migrated collections

- **WHEN** `seed-label-registry --execute` is run and a collection has already been migrated
- **THEN** the migration skips that collection and reports it as skipped

#### Scenario: Force re-links and re-aliases

- **WHEN** `seed-label-registry --execute --force` is run for an already-migrated collection
- **THEN** the artifact is re-linked and the production alias is re-pointed
