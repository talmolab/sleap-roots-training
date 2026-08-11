## REMOVED Requirements

### Requirement: Per-Species, Per-Root-Type Card Expansion

**Reason**: This change inverts the requirement's core rule. It mandated one card **per matrix row**
("a model shared across species yields one card per species"); the replacement mandates one card
**per physical model**. Its scenarios `Shared model expands per species` and `Crown-only row produces
a single crown card` assert the per-row behavior by name, so they cannot be carried forward under a
MODIFIED block without leaving statements in the permanent spec that the change makes false.

**Migration**: Replaced in full by `Per-Physical-Model, Per-Root-Type Card Expansion` below, which
retains every null-slot and per-root-type guarantee and adds the collapse, de-duplication, ordering,
and single-`root_type` rules.

### Requirement: Production Model Publishing and Registry Linking

**Reason**: Same inversion on the publishing side. Its scenario `Shared weights are published as
distinct per-species artifacts` requires the opposite of what this change delivers ("neither is a
single artifact linked into two collections") and cannot be preserved by name.

**Migration**: Replaced in full by `Per-Physical-Model Publishing and Registry Linking` below, which
re-states the target-path rule, the per-collection uniqueness rule, the duplicate-id fail-fast guard,
and the whole digest-determinism guarantee verbatim, and changes only the per-row → per-model
publishing rule.

## MODIFIED Requirements

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a metadata mapping containing **exactly** the selection dimensions the
consumer reads — a scalar `root_type` (one of `"primary"`, `"lateral"`, `"crown"`) and a non-empty
`selectors` list, where each selector carries `species` (str), `mode` (a member of the contract-owned
`Mode` vocabulary, stored raw with its space preserved and never the hyphenated collection-id slug),
`age_min` (int ≥ 0), and `age_max` (int ≥ 0) — plus a non-contract `source_model_id` for
traceability. It SHALL NOT include the wandb-intrinsic keys `registry_id`, `version`, or
`weights_checksum`, and SHALL NOT carry card-level `species`, `mode`, `age_min`, or `age_max` fields,
since a card may serve several selection contexts. This mapping is the **complete** stored artifact
metadata (producer lineage lives in the run config, not per-artifact — see Seed Run Lineage). The
mapping SHALL validate against the `ModelCard` schema from `sleap-roots-contracts`, which matches
`mode` exactly and normalizes neither case nor whitespace.

`sleap_nn_version` remains a **scalar card-level** key and SHALL NOT be moved into `Selector`,
because it describes the physical weights rather than a selection context. Every model in the
committed matrix is legacy, so no card emits it today and `ModelCard.sleap_nn_version` stays `None`;
the key is specified here so that a future `sleap-nn`-trained model has one defined home.

Selector values SHALL be emitted as **JSON-native** types — a list of plain mappings of primitives —
not as `Selector` model instances, `NamedTuple`s, or other objects. This is a correctness
requirement, not a style preference: `wandb.Artifact(metadata=...)` passes the mapping through
`wandb.sdk.artifacts._validators.validate_metadata`, which **coerces rather than rejects** anything
non-JSON-native, degrading a pydantic model to its `repr` string and a `NamedTuple` to a positional
list. Either degradation publishes unreadable selection metadata with a successful exit code.

The "no card-level `species`/`mode`/`age_min`/`age_max`" clause deliberately rules out emitting both
shapes at once. New-shape metadata is therefore **not** readable by a consumer still pinned to the
pre-`selectors` contract, whose `ModelCard` is `extra="ignore"` with those four fields required — it
would drop `selectors` and then fail on the missing required fields. Neither direction of mismatch is
repaired in the schema, because the consumer already degrades safely in both: it skips a card it
cannot validate, per artifact, with a warning. What the producer SHALL guarantee instead is
operational: the collections an old-pinned consumer reads SHALL NOT be overwritten or have their
production alias dropped until that consumer's upgrade is confirmed deployed.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains **exactly** `root_type`, `selectors`, and `source_model_id` — and nothing else
  beyond a scalar `sleap_nn_version` for a `sleap-nn`-produced model
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

#### Scenario: Metadata survives wandb's own coercion unchanged

- **WHEN** a card's metadata mapping is passed through the coercion `wandb.Artifact(metadata=...)`
  applies (`validate_metadata`)
- **THEN** the returned mapping is unchanged, and each selector is still a mapping carrying
  `species`, `mode`, `age_min`, and `age_max`
- **AND** the coerced mapping still validates against the real `ModelCard`, so a selector emitted as
  a model instance (silently degraded to a `repr` string) or as a `NamedTuple` (degraded to a
  positional list) fails this check rather than reaching the registry

### Requirement: Idempotent Re-Seed

Re-running the seed SHALL be safe on a shared registry: for each card, if the target collection
already holds an artifact carrying the production alias, the seed SHALL skip that card and report it,
unless `--force` is given. With `--force`, the seed SHALL re-log the artifact and re-point the
production alias. Re-running after a partial failure SHALL therefore resume by skipping the
already-seeded collections.

Because `log_artifact` is a no-op when the content digest matches the collection's latest version
(wandb documents this on `Artifact.digest`), `--force` SHALL NOT be specified or documented as
guaranteeing a **new version** for unchanged weights: what it guarantees is the alias re-point and an
*attempted* metadata refresh, whose success is established by read-back and never inferred from
`--force` having been passed (see Re-Publish Metadata Refresh). A skipped card SHALL still have its stored
metadata shape checked, because the skip path is the default path on every re-run and is therefore
exactly where a half-migrated collection would otherwise sit undetected.

#### Scenario: Re-seed skips already-seeded collections

- **WHEN** `seed-registry --execute` runs and a card's target collection already has a
  production-aliased artifact
- **THEN** the seed skips that card and reports it as skipped
- **AND** it does not move the production alias

#### Scenario: Force re-points the production alias

- **WHEN** `seed-registry --execute --force` runs for a card whose collection already has a
  production-aliased artifact
- **THEN** the seed re-logs the artifact and re-points the production alias
- **AND** it reports the move
- **AND** when the content digest is unchanged, no new version is created — so the alias re-point and
  an attempted metadata refresh, not a new version, are what `--force` delivers
- **AND** whether that refresh actually landed is decided by the read-back, not by `--force` having
  been passed

#### Scenario: A skipped collection carrying legacy metadata is still reported

- **WHEN** a card is skipped because its collection already carries the production alias, and that
  artifact's stored metadata is the legacy flat shape rather than `selectors`
- **THEN** the seed reports that collection as carrying stale metadata, distinctly from an ordinary
  skip
- **AND** the report is actionable without re-running with `--force`

### Requirement: Registry Verification Command

The CLI SHALL provide a `seed-registry --verify` mode that re-runs the consumer read path against the
live registry — using the same registry project string the consumer uses
(`f"{entity}-org/wandb-registry-{registry}"`, **not** the seed run's project) — and reports, for
every expected collection (derived from the selection matrix), whether an artifact carrying the
production alias is present. It is read-only, so it requires only the selection matrix + registry
config (not `--models-root`), but it SHALL check for a resolvable wandb credential (`WANDB_API_KEY`
or a netrc entry for `api.wandb.ai`) before contacting wandb. This is real, re-runnable software (not
a one-time procedure), so post-seed verification is embodied by a command rather than an
unimplemented spec clause.

Under `--only`, the expected set SHALL narrow to the named collection(s), exactly as the validation
and publish sets do — so a canary can be verified in isolation. This narrowing is what makes orphan
reporting meaningless under `--only` (see Orphaned Collection Reporting).

Verification SHALL additionally report, for each expected collection whose production-aliased
artifact is present, whether that artifact's metadata is the current `selectors`-bearing shape or the
legacy flat shape, and SHALL exit non-zero when an expected collection is present but carries the
legacy shape. Alias presence alone is **not** sufficient evidence of a completed migration: without
the shape check, `--verify` reports `present` for a collection an upgraded consumer cannot read, and
there is then no re-runnable way to ask whether the registry has actually been migrated. The shape
check SHALL be **structural** — `selectors` present and no card-level `species`/`mode`/`age_min`/
`age_max` — and SHALL NOT be implemented as "does this validate against `ModelCard`", because a
tolerant-read contract accepts the legacy flat shape by design and would report every stale
collection as current.

#### Scenario: Verify reads back the production alias

- **WHEN** `seed-registry --verify` is run after a seed
- **THEN** it iterates `api.artifact_collections(project_name=<registry project>, type_name="model")`
  and, for each expected collection, `api.artifacts(type_name="model",
  name=f"{<registry project>}/{collection.name}")`
- **AND** it reports every collection whose production-aliased artifact is present or missing
- **AND** it exits non-zero if any expected collection lacks the production alias

#### Scenario: Verify reports a present-but-legacy-shape collection as a failure

- **WHEN** an expected collection's production-aliased artifact is present but its metadata carries
  card-level `species`/`mode`/`age_min`/`age_max` and no `selectors`
- **THEN** `--verify` names that collection as carrying the legacy shape
- **AND** the command exits non-zero
- **AND** the determination is made structurally, so a tolerant-read contract that accepts the legacy
  shape does not mask it

### Requirement: Registry Seeding CLI with Confirmed Execution

The CLI SHALL provide a `seed-registry` subcommand that reads the selection matrix, expands cards,
resolves model directories, and — by default — runs a **dry run** that prints the planned
collections and per-card metadata and resolves every model directory on the filesystem (reporting
any missing model) **without** contacting wandb. Actually publishing SHALL require an explicit
`--execute`, which SHALL check for a resolvable wandb credential (`WANDB_API_KEY` or a netrc entry
for `api.wandb.ai`) **before** confirming the target entity/registry (interactive, bypassed with
`--yes`), and SHALL validate that every card **in the invocation's scope** resolves before publishing
any artifact, so a partial production seed is not left in a shared registry. The CLI SHALL accept a
repeatable `--only <collection_id>` filter so a single card can be seeded first as a canary (verify
the consumer can read it across the producer/consumer wandb version skew); with `--only`, the
validation set, the publish set, **and the `--verify` expected set** all narrow to the named card(s)
(so a canary needs only its own model staged, and can be verified without the rest of the registry
counting as missing), and an `--only` value naming no known collection SHALL fail fast. A subsequent
full `--execute` publishes the rest and skips the already-seeded canary. The `--models-root` is
required for dry-run and `--execute`; `--verify` is a distinct read-only mode that requires only the
selection matrix + registry config (not `--models-root`) and SHALL check for a resolvable wandb
credential. A selection-matrix rejection — an unreadable file, an out-of-vocabulary `species` or
`mode`, a non-contiguous `age` window — SHALL reach the operator as a clean CLI error carrying the
loader's row-numbered message, not as an unhandled traceback.

Because this change renames every collection id, an `--only` value written against the previous
scheme SHALL fail fast under the existing unknown-id check rather than silently matching nothing, so
a stale id in an operator runbook is reported rather than acted on as an empty scope.

#### Scenario: Only-filter seeds a single canary card, validating only its scope

- **WHEN** `seed-registry --execute --yes --only <collection_id>` is run with only that card's model
  staged
- **THEN** only that card is validated and published and linked with the production alias
- **AND** a subsequent full `seed-registry --execute --yes` skips the canary and publishes the rest

#### Scenario: Unknown --only collection fails fast

- **WHEN** `--only` names a collection id not in the expanded card set — including an id valid under
  the previous naming scheme
- **THEN** the command fails fast naming the unknown id, publishing nothing

#### Scenario: Default run is a dry run that resolves models without network

- **WHEN** `seed-registry --models-root <dir>` is run without `--execute`
- **THEN** the planned collections and per-card metadata are printed
- **AND** each card's model directory is resolved on the filesystem and any missing model is
  reported
- **AND** no wandb network call is made
- **AND** the command exits with status code 0

#### Scenario: Missing credential fails before the confirmation prompt

- **WHEN** `seed-registry --execute` is run with neither `WANDB_API_KEY` set nor a netrc entry for
  `api.wandb.ai`
- **THEN** the command fails fast with a clear error before prompting for confirmation
- **AND** no wandb network call is made

#### Scenario: Execution requires confirmation

- **WHEN** `seed-registry --execute` is run with a resolvable wandb credential but without `--yes`
- **THEN** the command names the target entity and registry and requires confirmation before
  publishing
- **AND** declining performs no publish

#### Scenario: Execution validates all in-scope cards before publishing any

- **WHEN** `seed-registry --execute --yes` is run and any in-scope card's model cannot be resolved
  (checksum, missing, or missing essential file)
- **THEN** the seed fails fast, naming the offending card, before any artifact is published
- **AND** no partial set of production artifacts is left in the registry

#### Scenario: Successful execution publishes and reports collections

- **WHEN** `seed-registry --execute --yes` is run with valid credentials and a complete models-root
- **THEN** each not-yet-seeded card is published and linked with the production alias
- **AND** the command reports the published and skipped collections

#### Scenario: A rejected selection matrix is reported as a CLI error

- **WHEN** `seed-registry` is run against a matrix whose row is out of vocabulary (for example
  `mode: teacup`)
- **THEN** the command exits non-zero with the loader's row-numbered message rendered as a CLI error
- **AND** no traceback is printed and no wandb call is made

#### Scenario: An unreadable or unparseable selection matrix is reported as a CLI error

- **WHEN** `--selection-matrix` names a path that cannot be loaded as a matrix — a directory, a
  file that is not valid YAML, or YAML whose top level is not a mapping
- **THEN** the command exits non-zero with a message naming the path and what was wrong with it
- **AND** no traceback is printed and no wandb call is made

## ADDED Requirements

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

Expansion SHALL additionally fail fast if two **different** physical models of the same `root_type`
would carry an identical `(species, mode, age_min, age_max)` selector. Under the previous per-row
naming this was caught incidentally, because the collection id was built from exactly those four
fields and the duplicate-id guard therefore rejected two models claiming one selection context. An id
derived from the physical model gives the two models distinct ids, so both would publish, both would
carry the production alias, and the consumer would find two production cards matching one query and
choose between them arbitrarily. The guard SHALL therefore be restated on the selectors themselves
rather than left to depend on the id scheme.

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
- **AND** the matrix as a whole yields exactly one card per distinct
  `(source_model_id, root_type)` pair

#### Scenario: A model shared across modes of one species collapses to one card

- **WHEN** the same lateral model id appears under one species in two different modes (arabidopsis
  `cylinder` and arabidopsis `multiplant cylinder`, both age 2–14)
- **THEN** exactly one `lateral` card is produced, carrying both selectors
- **AND** the two selectors differ only in `mode`

#### Scenario: One lateral model serving two species keeps each species' own age window

- **WHEN** one lateral model serves canola (cylinder, age 2–13) and pennycress (cylinder, age 2–14)
- **THEN** one `lateral` card is produced carrying both selectors
- **AND** the two selectors differ in **both** `species` and `age_max`, and neither window is
  widened to cover the other

#### Scenario: A physical model spanning two root types is rejected

- **WHEN** a matrix edit causes one `source_model_id` to appear in two different root-type slots
- **THEN** expansion fails fast, naming the offending model id
- **AND** no cards are produced

#### Scenario: Two different models claiming one selection context are rejected

- **WHEN** a matrix edit gives two different `source_model_id`s of the same `root_type` an identical
  `(species, mode, age_min, age_max)` selector
- **THEN** expansion fails fast, naming the colliding selector and both model ids
- **AND** no cards are produced, so two production-aliased cards cannot both match one query

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

### Requirement: Per-Physical-Model Publishing and Registry Linking

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
  against future matrix edits, and against a lossy slug mapping two distinct model ids onto one id)
- **THEN** the seed fails fast, naming the colliding cards, before any artifact is published

### Requirement: Collection Identifier Scheme

The package SHALL derive each card's collection id from a **single documented scheme implemented in
one function**, used by publishing, `--only`, and `--verify` alike, so the producer cannot compute one
id when writing and a different one when reading back. A scheme is needed at all because a card no
longer has a single `species`/`mode`/age window to name itself with. The id SHALL be a deterministic function of the
card alone and SHALL be unique across the expanded card set (the duplicate-id fail-fast guard in
Per-Physical-Model Publishing and Registry Linking still applies, and now also guards against a lossy
slug collapsing two distinct model ids).

The id SHALL be accepted by the `wandb.Artifact(name=..., type="model")` constructor itself, which is
the effective rule: it enforces `^[a-zA-Z0-9_\-.]+$` **before** delegating to
`wandb.sdk.artifacts._validators.validate_artifact_name`, so it rejects the `=` that every
`source_model_id` in the committed matrix contains (from the `n=<count>` suffix) as well as the `/`
that `validate_artifact_name` catches. `validate_artifact_name` and `INVALID_ARTIFACT_NAME_CHARS`
(which is exactly `{"/"}`) SHALL NOT be used as the legality oracle, because both accept names the
constructor rejects — a slug that only strips `/` would pass such a check and then abort the live
seed on the first card. The id SHALL also respect the 128-character `NAME_MAXLEN` bound.

The scheme SHOULD be stable against a metadata-only edit, so that adding a selector to an existing
card does not rename a live production collection.

The concrete formula is the subject of decision 0.2 in `tasks.md` (recommendation: derive from
`source_model_id`); this requirement fixes the properties any chosen formula must satisfy. *(This
paragraph is replaced by the agreed formula in task 0.6, before this change is archived — it must not
reach the permanent spec as a pointer into `changes/archive/`.)*

#### Scenario: Collection ids are legal wandb artifact names

- **WHEN** collection ids are computed for every card the committed matrix expands to
- **THEN** each id is accepted by the real `wandb.Artifact(name=<id>, type="model")` constructor,
  which needs no credential and no network
- **AND** the check is not delegated to `validate_artifact_name` or a hand-rolled regex, either of
  which would accept an id the constructor rejects
- **AND** no id exceeds the 128-character name bound

#### Scenario: One scheme serves publish, --only, and --verify

- **WHEN** a card's collection id is computed on the publish path and on the verification path
- **THEN** the two paths yield equal ids for every card
- **AND** an `--only` value matching a card's id therefore selects that card in every mode

### Requirement: Orphaned Collection Reporting

The `--verify` mode SHALL additionally **report any production-aliased collection in the registry
that the current expansion no longer produces**, so that collections orphaned by an expansion change
are surfaced rather than silently ignored. Orphan reporting SHALL NOT delete a collection or move any
alias — retirement stays a separate, human-gated act.

Because `--verify --only <id>` narrows the expected set (see Registry Verification Command), orphan
reporting SHALL be **suppressed under `--only`** — where every collection outside the canary's scope
would otherwise be reported as orphaned — and SHALL state in its output that the orphan check was
skipped for that reason. An orphan count SHALL therefore only ever be read from a full `--verify`
run.

Orphans SHALL NOT affect the exit code: a missing production alias on an *expected* collection, or an
expected collection carrying the legacy metadata shape, is a failure, while an orphan is an advisory
finding a human must act on. A collection whose alias membership cannot be determined SHALL be
reported as indeterminate and SHALL likewise not affect the exit code, so a transient read error on
an unrelated collection cannot fail a verification that previously could not see that collection at
all.

Orphan detection SHALL determine alias membership without paginating every artifact version of every
collection in the registry. The registry holds far more collections than cards — most of them
non-production sweep and training-run artifacts — so a per-version scan is proportional to every
version in the registry rather than to the card set. Alias membership SHALL be read from the
per-collection alias query (`ArtifactCollection.aliases`), which is one lightweight call per
collection. The registry-wide membership query (`Api.registry(...).versions(...)`) MAY be used instead
where it is available, but SHALL NOT be assumed available: it is gated on a server feature flag and
raises when the flag is absent, and it additionally requires an `organization` that this package's
registry configuration does not carry. Any use of it SHALL therefore sit behind a
capability probe with the per-collection path as the documented fallback. Only collections carrying
the production alias SHALL be named; non-production collections SHALL be excluded silently rather
than reported as orphans.

#### Scenario: Verify reports collections the expansion no longer produces

- **WHEN** the registry holds a production-aliased collection whose id is absent from the current
  expanded card set
- **THEN** `--verify` names that collection as orphaned in its report
- **AND** it does not delete the collection or move its production alias
- **AND** the orphan does not by itself make the command exit non-zero

#### Scenario: Non-production collections are not reported as orphans

- **WHEN** the registry holds collections that carry no production alias (sweep and training-run
  artifacts)
- **THEN** they are excluded from the orphan report
- **AND** determining this does not require reading every version of every collection

#### Scenario: Orphan reporting is suppressed under --only

- **WHEN** `--verify --only <collection_id>` is run during a canary, so the expected set is narrowed
  to one collection
- **THEN** the report does not list the out-of-scope collections as orphaned
- **AND** it states that the orphan check was skipped because `--only` narrowed the scope

### Requirement: Re-Publish Metadata Refresh

A re-seed that reports a collection as `published` SHALL confirm that the metadata visible on the
production-aliased artifact is the new-shape metadata. This is required because artifact metadata is
not part of the `add_dir` manifest digest, so re-logging unchanged weights is a content-level no-op
that can leave the previously published metadata live. `--force` SHALL NOT be treated as sufficient
evidence of a refresh, since it bypasses the idempotency read rather than guaranteeing a new stored
metadata blob.

Where the read-back shows stale metadata, the seed SHALL refresh it in place through the artifact's
own metadata-update path (setting `Artifact.metadata` and calling `Artifact.save()`, which issues an
`updateArtifact` mutation) and re-read to confirm, rather than requiring another `--force` re-log,
which cannot create a new version while the digest is unchanged. The refresh SHALL NOT re-upload the
model directory. If the refresh fails — whether it **raises** or the re-read still shows the legacy
shape — the collection SHALL be reported in a distinct `failed` bucket, the command SHALL exit
non-zero, and the remaining cards SHALL still be attempted, so that neither a stale collection nor a
transient error on one collection aborts the seed.
The determination SHALL use the same structural shape test the Registry Verification Command
requirement defines, and SHALL NOT be restated independently — one definition, so the publish path and
the verification path cannot drift apart on what counts as migrated.

#### Scenario: Re-publish that leaves stale metadata is refreshed in place

- **WHEN** a card is re-published over an existing collection whose weights are byte-identical, and
  the production-aliased artifact still reads back with card-level `species`/`mode`/`age_min`/
  `age_max` and no `selectors`
- **THEN** the seed updates that artifact's metadata in place and re-reads it to confirm
- **AND** it does not re-upload the model directory

#### Scenario: A refresh that does not take is reported as failed

- **WHEN** the in-place metadata refresh is attempted and the artifact still reads back with the
  legacy flat shape
- **THEN** the seed reports that collection in a `failed` bucket, naming it, distinctly from
  `published` and `skipped`
- **AND** the command exits non-zero
- **AND** the remaining cards are still attempted

#### Scenario: Successful re-publish reads back the new shape

- **WHEN** a card is re-published and the production-aliased artifact reads back carrying
  `selectors` and no card-level selection fields
- **THEN** the seed reports that collection as published
- **AND** it is not reported as failed, so the check discriminates rather than failing everything

#### Scenario: A tolerant-read contract does not mask stale metadata

- **WHEN** the read-back metadata is the legacy flat shape and the pinned contract accepts it by
  lifting it into a single-selector card
- **THEN** the collection is still classified as stale, because the check is structural rather than a
  contract validation
