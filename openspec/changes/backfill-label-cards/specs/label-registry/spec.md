## ADDED Requirements

### Requirement: Label Collection Backfill onto LabelCard

The package SHALL map each of the 8 existing `wandb-registry-sleap-roots-labels` collections onto
the `LabelCard` contract from `sleap-roots-contracts`. Provenance is reconstructed **once, by hand**
(the archaeology pass) and **committed to the repository as a checked-in mapping**; the package
SHALL then build every card from that committed mapping plus values read programmatically from the
artifact's `.slp` content, and SHALL NOT depend on a human repeating the reconstruction. Where the
two disagree — a committed count against the same count read from the blob — the backfill SHALL
fail naming the collection and the field rather than silently preferring either.

Provenance fields that cannot be recovered from the artifact or cross-referenced against Bloom
SHALL be set to `null` — no values SHALL be
fabricated to satisfy the schema. This applies to the fields the contract declares `Optional`; a
required field SHALL NOT be satisfied with a placeholder, and a collection whose required fields
cannot all be sourced SHALL fail loudly rather than be stamped. Each collection SHALL be verified as
single-species content before a `LabelCard` is stamped onto it.

#### Scenario: Backfilled card with full provenance

- **WHEN** an existing label collection's artifact description and Bloom cross-reference yield a
  recoverable `bloom_experiment_id`, accession IDs, and species
- **THEN** the `LabelCard` is constructed with those values populated
- **AND** the card validates against the `LabelCard` contract

#### Scenario: Backfilled card with unrecoverable provenance

- **WHEN** an existing label collection's provenance cannot be fully reconstructed (deleted temp
  `data_path`, no Bloom cross-reference)
- **THEN** the unrecoverable `Optional` fields are set to `null`
- **AND** the card still validates against the `LabelCard` contract
- **AND** no fabricated values appear in the metadata

#### Scenario: A required field with no recoverable source fails loudly

- **WHEN** a collection's `age_min`, `age_max`, `n_plants`, or `n_scans` cannot be recovered and the
  contract still declares that field required
- **THEN** the backfill reports that collection and the missing field by name and stamps no card
- **AND** no placeholder, sentinel, or zero value is written in its place

#### Scenario: Single-species verification rejects mixed content

- **WHEN** the backfill runs against a collection whose committed mapping records more than one
  species, or whose blob-derived species set has more than one member
- **THEN** the backfill rejects that collection by name with a clear error
- **AND** no `LabelCard` is stamped onto it
- **AND** the check runs as code on every invocation, not as a one-time manual inspection

#### Scenario: The committed mapping and the blob must agree

- **WHEN** a value present in both the committed mapping and the artifact blob disagrees between
  them (for example `node_count`, `n_frames`, or species)
- **THEN** the backfill fails naming the collection and the field
- **AND** neither value is silently preferred

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

### Requirement: Canonical Root Types, With No Label-Side Vocabulary

Every backfilled `LabelCard` SHALL record a `root_type` drawn from the contract-owned
`sleap_roots_contracts.RootType` — `primary`, `lateral`, or `crown`. A collection whose *name*
carries a species-specific nickname for one of those root types SHALL be recorded under the
canonical value, not the nickname: the wheat collection named `seminal` is stamped `crown`. This
change SHALL NOT introduce a label-side root-type vocabulary, SHALL NOT widen `RootType`, and SHALL
NOT re-annotate `LabelCard.root_type`. `chooser.ROOT_TYPE_VOCAB`, `registry/cards.py`'s
`_ROOT_SLOTS`, and the `experiment.root_type` field of a training config SHALL all continue to
accept exactly `primary`, `lateral`, and `crown`, on both the label and the model side.

Because the nickname is dropped from the normalized collection name, the original collection name
SHALL be recorded on the card as recovered provenance, so a collection remains discoverable by the
name it was published under.

#### Scenario: A nickname root type is recorded under its canonical value

- **WHEN** the collection named `wheat_5-14DAG_seminal_6nodes_labels` is backfilled
- **THEN** its `LabelCard` records `root_type` `crown`
- **AND** the card validates against the `LabelCard` contract with no contract change
- **AND** its original collection name is recorded on the card

#### Scenario: No root type outside the contract vocabulary is emitted

- **WHEN** the full set of label cards is expanded
- **THEN** every card's `root_type` is a member of `sleap_roots_contracts.RootType`
- **AND** no card carries `seminal`

#### Scenario: Root-type vocabularies are unchanged on both sides

- **WHEN** the label-side and model-side root-type vocabularies are compared after this change
- **THEN** they are the same object, `chooser.ROOT_TYPE_VOCAB`, derived from the contract
- **AND** `seminal` is rejected as a labeling package `root_types` entry
- **AND** `seminal` is rejected as an `experiment.root_type` in a training config

### Requirement: Label Species Vocabulary

The label-side species vocabulary SHALL be a strict superset of the model-side `SPECIES_VOCAB`,
adding `wheat`, `sorghum`, and `medicago` — species with published label data and no trained model.
It SHALL be defined in terms of `SPECIES_VOCAB` rather than as an independent list, so the superset
relation cannot drift. Both vocabularies remain owned by this package, as the contract models no
species vocabulary for either card type.

The label-side vocabulary SHALL govern a labeling package's `species` and the labeling skeleton
table. The model-side `SPECIES_VOCAB` SHALL continue to govern the model selection matrix and the
`experiment.species` field of a training config, and SHALL NOT be widened by this change.

#### Scenario: Species with published labels is accepted

- **WHEN** a label collection is built for a species with published label data (e.g. `wheat`,
  `sorghum`, `medicago`)
- **THEN** the species validates against the label-side vocabulary
- **AND** a `LabelCard` can be constructed for that species
- **AND** a labeling skeleton table row may be declared for it

#### Scenario: A label-only species is not a valid training config or matrix species

- **WHEN** a training config declares `experiment.species: wheat`, or a selection-matrix row names
  `wheat`
- **THEN** validation fails naming the offending field and the model-side vocabulary
- **AND** the model selection matrix accepts exactly the species it accepted before this change

### Requirement: Label Registry Seeding CLI

The package SHALL provide a `seed-label-registry` subcommand that reads the backfill mapping,
constructs `LabelCard` metadata, and — by default — runs a dry run printing planned collections
and metadata without contacting wandb. Publishing SHALL require `--execute`, which SHALL check for
a resolvable wandb credential before proceeding. The CLI SHALL accept `--only <collection_id>` for
canary migration, `--verify` for read-back, and `--force` to re-link and re-point an
already-migrated collection, following the same patterns as the model `seed-registry` command.
The network layer SHALL accept an injected wandb API object (defaulting to `None` and created
lazily) and SHALL import `wandb` only on the network path, so every behaviour above is testable
without a live registry — the same seam `registry/publish.py` already uses.

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
report it, unless `--force` is given. Because linking is additive and W&B collections cannot be
renamed or deleted, a migration that fails partway SHALL be recoverable by re-running rather than by
any undo step — the original artifact versions and old collections SHALL be left untouched
throughout.

#### Scenario: Re-run skips already-migrated collections

- **WHEN** `seed-label-registry --execute` is run and a collection has already been migrated
- **THEN** the migration skips that collection and reports it as skipped

#### Scenario: Force re-links and re-aliases

- **WHEN** `seed-label-registry --execute --force` is run for an already-migrated collection
- **THEN** the artifact is re-linked and the production alias is re-pointed

#### Scenario: A migration that fails partway is resumable

- **WHEN** `seed-label-registry --execute` fails after migrating some but not all collections
- **THEN** the already-migrated collections carry their `production` alias and metadata
- **AND** the un-migrated collections are unchanged, with their artifacts still resolvable under
  their old names
- **AND** re-running `--execute` migrates only what remains
