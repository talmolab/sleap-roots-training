## ADDED Requirements

### Requirement: Per-Row Publication Status

A selection-matrix row SHALL accept an optional `status` key. Its value SHALL be exactly the string
`production` (the default alias) or the string `candidate`. A row without a `status` key SHALL be
`production`, so existing matrices load unchanged. Any other value SHALL be rejected at load time with
a row-numbered error naming the two allowed values. That includes `null`, an empty string, a
non-string, a differently cased spelling and a whitespace-padded one. The status check SHALL run after
the row's `source` check and before `origins` coverage.

Each card SHALL carry the status of the rows it was expanded from. A model referenced by rows of
different status SHALL be rejected during card expansion with an error naming the model, alongside the
other cross-row expansion checks (see Per-Physical-Model, Per-Root-Type Card Expansion). One collection
cannot be both expected in production and kept out of it. Two rows of the same status that share a
model SHALL expand as before.

`status` SHALL be matrix-local. It SHALL NOT appear in the published card metadata, and every card's
metadata SHALL be identical to what it would be if its row had no `status` key.

#### Scenario: A row without status is production

- **WHEN** a matrix row has no `status` key
- **THEN** the loaded row and its cards have status `production`

#### Scenario: Explicit statuses load

- **WHEN** a matrix row has `status: candidate`, and another has `status: production`
- **THEN** both load, and their cards have status `candidate` and `production` respectively

#### Scenario: An invalid status is rejected

- **WHEN** a matrix row's `status` is `staging`, `null`, `""`, `1`, `Candidate` or `" candidate "`
- **THEN** loading fails with an error naming the row index and both allowed values

#### Scenario: A model under rows of mixed status is rejected

- **WHEN** one model id is referenced by a `production` row and a `candidate` row
- **THEN** card expansion fails with an error naming that model
- **AND WHEN** two `candidate` rows reference one model
- **THEN** they expand to one `candidate` card without error

#### Scenario: Status is not published

- **WHEN** a card from a `candidate` row is converted to card metadata
- **THEN** the metadata has no `status` key and is equal to the metadata of the same card with status
  `production`

### Requirement: Candidate Rows Are Never Linked to Production

Under the **default** alias, `seed-registry --execute` SHALL never publish a card whose row status is
`candidate`:

- **Without `--only`**, candidate-status cards SHALL be out of the run's scope. The run SHALL print
  each one as `skipped (status: candidate)`, and SHALL publish the production-status cards exactly as
  before.
- **With `--only` naming one or more candidate-status collections**, the command SHALL refuse with
  exit status 1, as a CLI error, publishing nothing. The error SHALL name those collections, and say
  that promoting one requires changing its row's `status` in a reviewed change to the committed
  matrix, and that a production re-seed should name only production-status collections.

Neither `--promote` nor `--force` SHALL override this. The decision SHALL be made from the matrix
alone. It SHALL run after:

- the blank-alias check;
- the matrix load;
- the unknown-`--only` check;
- the `--promote` usage validation.

It SHALL run before:

- the non-default-alias guard;
- the credential check;
- the promotion check;
- the confirmation prompt;
- model resolution;
- `wandb.init`.

A refused run therefore makes no wandb call. These SHALL NOT be refused or narrowed by it:

- a dry run, which SHALL list candidate-status cards marked `status: candidate`, so an operator sees
  what a default `--execute` would skip;
- `--verify`, with or without `--execute`;
- `--execute` under a non-default alias.

#### Scenario: Naming a candidate collection under production is refused

- **WHEN** `seed-registry --execute --yes --only <candidate-status collection> --promote` runs under the
  default alias
- **THEN** it exits with status 1 naming that collection and the row's `status`
- **AND** no credential check, `wandb.Api`, promotion check, confirmation prompt, model resolution or
  `wandb.init` happens

#### Scenario: Neither force nor omitting promote changes the refusal

- **WHEN** the refused invocation above is repeated with `--force`, or without `--promote`
- **THEN** it is refused in the same way, by this check and not by the promotion check

#### Scenario: Losing the candidate alias variable cannot publish a candidate row

- **WHEN** the candidate publish command, `seed-registry --models-root <dir> --only <candidate ids>
  --execute --yes`, is run without its `SLEAP_ROOTS_MODEL_ALIAS=candidate` setting
- **THEN** it is refused by this check before any wandb call

#### Scenario: An unscoped production re-seed skips candidate rows

- **WHEN** `seed-registry --models-root <dir> --execute --yes` runs under the default alias, without
  `--only`, over a matrix with a candidate-status row
- **THEN** each candidate-status card is printed as `skipped (status: candidate)`, and is not checked
  for promotion, resolved or published
- **AND** the production-status cards proceed exactly as they would over a matrix without that row

#### Scenario: Candidate rows publish under the candidate alias

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --models-root <dir> --execute --yes --only
  <candidate-status collections>` runs
- **THEN** this check does not fire, and each named card is linked with exactly the `candidate` alias

#### Scenario: Verify and dry run are not affected

- **WHEN** `seed-registry --verify --execute`, or a dry run, runs under the default alias over a matrix
  with a candidate-status row
- **THEN** this check does not refuse it
- **AND** the dry run lists the candidate-status cards marked `status: candidate`

### Requirement: Reproducible Model Archive Build

The repository SHALL provide `scripts/build_model_zip.py`, which builds a `<model_id>.zip` from a
trained model directory and prints its SHA256. The archive SHALL be byte-reproducible from the same
directory contents. To achieve that:

- entries SHALL be stored uncompressed;
- entries SHALL be in sorted path order;
- every entry SHALL have the same fixed timestamp and permission bits;
- every file SHALL sit under one top-level directory named after the model directory.

A checksum committed to the matrix can therefore be re-derived from the source directory, without
keeping the archive. The script SHALL refuse to overwrite an existing output file.

#### Scenario: Two builds are byte-identical

- **WHEN** the script builds an archive twice from the same model directory, at different times
- **THEN** both archives have the same SHA256

#### Scenario: The archive resolves as a pinned model

- **WHEN** an archive built by the script is placed at `<models-root>/<model_id>.zip`, with its SHA256
  in the matrix's `checksums`
- **THEN** `resolve_model_dir(model_id, models_root, checksums, require_pinned=True)` returns a
  directory containing `best_model.h5` and `training_config.json`

#### Scenario: An existing output is not overwritten

- **WHEN** the output path already exists
- **THEN** the script exits non-zero without modifying it

### Requirement: Committed Matrix Totals

The committed selection matrix's row, checksum, card and status counts SHALL be pinned by test. Adding
or removing a row then fails a test, rather than silently changing the published set. Requirements
for individual committed rows SHALL NOT restate these totals.

#### Scenario: Committed matrix totals

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** it has 10 rows and 13 checksums, and yields 13 cards over 13 distinct physical models
- **AND** exactly 2 cards have status `candidate`, and the other 11 have status `production`

### Requirement: Committed Arabidopsis Plate Row

The committed selection matrix SHALL carry the arabidopsis plate row decided for
talmolab/sleap-roots-training#3, with its exact models, window, root types, source-zip checksums and
`candidate` status. A later edit that changes any of them then fails a test, rather than silently
re-pointing a card. Promoting these cards changes `status`, and so SHALL modify this requirement.

#### Scenario: Committed matrix includes the plate cards

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** `arabidopsis_plates/primary/230804_133809.multi_instance.n=606` is one `primary` card with
  checksum `ac0ca83ee8292ede4e45973437bf439334244e93325329d071ad306dd294a764`
- **AND** `arabidopsis_plates/lateral/231130_135922.multi_instance.n=38` is one `lateral` card with
  checksum `d30d5eb1dbef798e58b640b7d34632854496a67b6bedb7a35cdd2766127f39bc`
- **AND** each has the single selector (`arabidopsis`, `plate`, 2, 7) and status `candidate`
- **AND** their collection ids are `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` and
  `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38`
- **AND** both origins have `snapshot` `null` and a `location` that is not a share path

## MODIFIED Requirements

### Requirement: Registry Verification Command

The CLI SHALL provide a `seed-registry --verify` mode that re-runs the consumer read path against the
live registry. It SHALL use the same registry project string the consumer uses
(`f"{entity}-org/wandb-registry-{registry}"`), **not** the seed run's project. For every expected
collection, which is derived from the selection matrix, it SHALL report whether an artifact carrying
the configured alias is present.

`--verify` is read-only. It requires only the selection matrix and the registry config, not
`--models-root`. It SHALL still check for a resolvable wandb credential (`WANDB_API_KEY`, or a netrc
entry for `api.wandb.ai`) before contacting wandb. This is real, re-runnable software, not a one-time
procedure, so post-seed verification is embodied by a command rather than an unimplemented spec
clause.

Without `--only`, the expected set SHALL be the cards whose row status (see Per-Row Publication Status)
equals the configured alias. A default `--verify` therefore checks the `production`-status cards, and
`SLEAP_ROOTS_MODEL_ALIAS=candidate --verify` checks the `candidate`-status cards.

When that expected set is empty, verification SHALL say that no row has the configured alias as its
status, and SHALL exit non-zero without contacting wandb. A mistyped alias variable therefore cannot
produce a passing verification.

Under `--only`, the expected set SHALL narrow to the named collection(s), exactly as the validation and
publish sets do, so a canary can be verified in isolation. There is one exception: under the default
alias, a named `candidate`-status collection SHALL be checked only as described in the next paragraph,
never as expected. This narrowing is what makes orphan reporting meaningless under `--only` (see
Orphaned Collection Reporting).

Under the default alias, verification SHALL also check every in-scope `candidate`-status collection.
It SHALL report as an **unexpected production link** each one that carries the default alias. This
check SHALL behave as follows:

- A collection absent from the registry's collection listing is not linked, and its versions SHALL NOT
  be read. The wandb client raises when asked for the versions of a collection that does not exist.
- A read error while checking a collection SHALL be reported for that collection, and SHALL make the
  command exit non-zero, so that the check fails closed.
- An unexpected production link SHALL make the command exit non-zero, because it means a model the
  matrix keeps out of production is live for the consumer.

Verification SHALL additionally report, for each expected collection whose aliased artifact is present,
whether that artifact's metadata is the current `selectors`-bearing shape or the legacy flat shape. It
SHALL exit non-zero when an expected collection is present but carries the legacy shape. Alias presence
alone is **not** sufficient evidence of a completed migration: without the shape check, `--verify`
reports `present` for a collection an upgraded consumer cannot read, and there is then no re-runnable
way to ask whether the registry has actually been migrated.

The shape check SHALL be **structural**: `selectors` present, and no card-level `species`, `mode`,
`age_min` or `age_max`. It SHALL NOT be implemented as "does this validate against `ModelCard`",
because a tolerant-read contract accepts the legacy flat shape by design and would report every stale
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

#### Scenario: Default verify does not expect candidate rows

- **WHEN** every `production`-status collection carries `production`, and the `candidate`-status
  collections either carry only `candidate` or are absent from the registry, and a default-alias
  `--verify` is run without `--only`
- **THEN** it reports the `production`-status collections as present, and exits zero
- **AND** it does not report the `candidate`-status collections as missing, orphaned or linked
- **AND** it reads no versions of an absent collection

#### Scenario: Candidate-alias verify checks the candidate rows

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --verify` is run without `--only`
- **THEN** it reports each `candidate`-status collection as present or missing, and checks no
  `production`-status collection as expected
- **AND** it exits zero only when every `candidate`-status collection is present with the current shape

#### Scenario: An alias no row carries fails verification

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidtae seed-registry --verify` is run without `--only`
- **THEN** it reports that no row has status `candidtae`, makes no wandb call, and exits non-zero

#### Scenario: A candidate row linked to production fails verification

- **WHEN** a `candidate`-status collection carries `production`, and a default-alias `--verify` is run,
  with or without that collection named by `--only`
- **THEN** it reports that collection as an unexpected production link, and not as present or orphaned
- **AND** the command exits non-zero

#### Scenario: A read error on the candidate check fails closed

- **WHEN** reading a `candidate`-status collection's versions raises during a default-alias `--verify`
- **THEN** it reports that collection as unreadable, and the command exits non-zero

### Requirement: Orphaned Collection Reporting

The `--verify` mode SHALL additionally **report any collection in the registry that carries the
configured alias but that the current expansion no longer produces**, so that collections orphaned by
an expansion change are surfaced rather than silently ignored. A collection the expansion produces
SHALL NOT be reported as an orphan, whatever its row status. Under a non-default alias, for example,
collections from `production`-status rows that still carry that alias are leftovers of their candidate
window, not orphans. Orphan reporting SHALL NOT delete a collection or move any alias. Retirement stays
a separate, human-gated act.

Because `--verify --only <id>` narrows the expected set (see Registry Verification Command), orphan
reporting SHALL be **suppressed under `--only`**, where every collection outside the canary's scope
would otherwise be reported as orphaned. The output SHALL state that the orphan check was skipped for
that reason. An orphan count SHALL therefore only ever be read from a full `--verify` run.

Orphans SHALL NOT affect the exit code. These are failures:

- a missing alias on an *expected* collection;
- an expected collection carrying the legacy metadata shape;
- an unexpected production link.

An orphan, by contrast, is an advisory finding a human must act on. A collection whose alias membership
cannot be determined SHALL be reported as indeterminate and SHALL likewise not affect the exit code, so
a transient read error on an unrelated collection cannot fail a verification that previously could not
see that collection at all.

Orphan detection SHALL determine alias membership without paginating every artifact version of every
collection in the registry. The registry holds far more collections than cards, most of them
non-production sweep and training-run artifacts, so a per-version scan is proportional to every version
in the registry rather than to the card set. Alias membership SHALL be read from the per-collection
alias query (`ArtifactCollection.aliases`), which is one lightweight call per collection.

The registry-wide membership query (`Api.registry(...).versions(...)`) MAY be used instead where it is
available, but SHALL NOT be assumed available, for two reasons:

- it is gated on a server feature flag and raises when the flag is absent;
- it additionally requires an `organization` that this package's registry configuration does not carry.

Any use of it SHALL therefore sit behind a capability probe, with the per-collection path as the
documented fallback. Only collections carrying the configured alias SHALL be named. Collections that do
not carry it SHALL be excluded silently, not reported as orphans.

#### Scenario: Verify reports collections the expansion no longer produces

- **WHEN** the registry holds a production-aliased collection whose id is absent from the current
  expanded card set
- **THEN** `--verify` names that collection as orphaned in its report
- **AND** it does not delete the collection or move its production alias
- **AND** the orphan does not by itself make the command exit non-zero

#### Scenario: Collections without the configured alias are not reported as orphans

- **WHEN** the registry holds collections that do not carry the configured alias (sweep and
  training-run artifacts)
- **THEN** they are excluded from the orphan report
- **AND** determining this does not require reading every version of every collection

#### Scenario: Collections the matrix produces are never orphans

- **WHEN** a `candidate`-alias `--verify` is run, and `production`-status collections from an earlier
  candidate window still carry `candidate`
- **THEN** those collections are not reported as orphans
- **AND** a `candidate`-carrying collection the matrix does not produce is still reported as an orphan

#### Scenario: Orphan reporting is suppressed under --only

- **WHEN** `--verify --only <collection_id>` is run during a canary, so the expected set is narrowed
  to one collection
- **THEN** the report does not list the out-of-scope collections as orphaned
- **AND** it states that the orphan check was skipped because `--only` narrowed the scope

### Requirement: Registry Seeding CLI with Confirmed Execution

The CLI SHALL provide a `seed-registry` subcommand that reads the selection matrix, expands cards, and
resolves model directories. By default it SHALL run a **dry run**: it prints the planned collections
and per-card metadata, and resolves every model directory on the filesystem, reporting any missing
model, **without** contacting wandb.

Actually publishing SHALL require an explicit `--execute`, which SHALL:

- check for a resolvable wandb credential (`WANDB_API_KEY`, or a netrc entry for `api.wandb.ai`)
  **before** confirming the target entity and registry;
- confirm that target interactively, a step `--yes` bypasses;
- validate that every card **in the invocation's scope** resolves before publishing any artifact, so a
  partial production seed is not left in a shared registry.

Under the default alias, candidate-status cards are not in an `--execute` run's scope (see Candidate
Rows Are Never Linked to Production).

The CLI SHALL accept a repeatable `--only <collection_id>` filter, so that a single card can be seeded
first as a canary, which verifies that the consumer can read it across the producer/consumer wandb
version skew. With `--only`, the validation set, the publish set **and the `--verify` expected set**
all narrow to the named card(s). A canary therefore needs only its own model staged, and can be
verified without the rest of the registry counting as missing. An `--only` value naming no known
collection SHALL fail fast.

A subsequent `--execute` whose scope includes the canary publishes the rest and skips the canary.
Under the default alias, any first-time card in that scope requires `--promote`, which requires
`--only`, so that run lists its collections (see First-Time Production Link Requires Promotion).

`--models-root` is required for a dry run and for `--execute`. `--verify` is a distinct read-only
mode: it requires only the selection matrix and the registry config, not `--models-root`, and SHALL
check for a resolvable wandb credential.

A selection-matrix rejection SHALL reach the operator as a clean CLI error carrying the loader's row-
or model-naming message, not as an unhandled traceback. That covers an unreadable file, an
out-of-vocabulary `species` or `mode`, an invalid `status`, a non-contiguous `age` window, and missing
or mistyped provenance.

Every invocation SHALL print a target line as its first output, once the alias resolves and before any
wandb contact, prompt or publish. The line SHALL name:

- the entity;
- the registry;
- the alias, ASCII-escaped so hidden characters show and any console can print it;
- whether the alias came from `SLEAP_ROOTS_MODEL_ALIAS` or the default;
- the seed project.

A `SLEAP_ROOTS_MODEL_ALIAS` that is set but blank (see Environment-Driven Registry Configuration) SHALL
be a CLI error for `seed-registry` in every mode, before any wandb call. It SHALL NOT fall back to
`production`.

`--execute` under a **non-default alias** SHALL require `--only`. Without it, the command SHALL fail as
a usage error **before** the credential check, the confirmation prompt or any wandb call, including
under `--force`. The reason: without `--only`, the idempotency check finds no card seeded under the
new alias, and re-publishes every card in the matrix under it. A dry run and `--verify` under a
non-default alias SHALL remain allowed, since neither writes. `--verify` checks the cards whose row
status equals that alias (see Registry Verification Command).

The collection-id scheme changed in update-model-card-selectors. An `--only` value written against the
previous scheme SHALL therefore fail fast under the existing unknown-id check, rather than silently
matching nothing. A stale id in an operator runbook is then reported, not acted on as an empty scope.

#### Scenario: Only-filter seeds a single canary card, validating only its scope

- **WHEN** `seed-registry --execute --yes --only <collection_id> --promote` is run under the default
  alias, for a `production`-status collection, with only that card's model staged
- **THEN** only that card is validated, published and linked with the production alias
- **AND** a subsequent `seed-registry --execute --yes --only <canary> --only <each remaining
  production-status id> --promote` reports the canary as skipped and publishes the rest

#### Scenario: Unknown --only collection fails fast

- **WHEN** `--only` names a collection id not in the expanded card set, including an id valid under
  the previous naming scheme
- **THEN** the command fails fast naming the unknown id, publishing nothing

#### Scenario: Default run is a dry run that resolves models without network

- **WHEN** `seed-registry --models-root <dir>` is run without `--execute`
- **THEN** the target line and the planned collections and per-card metadata are printed
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
- **THEN** the command names the target entity, registry and alias and requires confirmation before
  publishing
- **AND** declining performs no publish

#### Scenario: Execution validates all in-scope cards before publishing any

- **WHEN** `seed-registry --execute --yes` is run and any in-scope card's model cannot be resolved,
  because of its checksum, a missing archive or a missing essential file
- **THEN** the seed fails fast, naming the offending card, before any artifact is published
- **AND** no partial set of production artifacts is left in the registry

#### Scenario: Successful execution publishes and reports collections

- **WHEN** `seed-registry --execute --yes` is run with valid credentials and a complete models-root,
  and the promotion check passes
- **THEN** each in-scope, not-yet-seeded card is published and linked with the configured alias
- **AND** the command reports the published and skipped collections, including, under the default
  alias, the candidate-status cards it skipped

#### Scenario: A rejected selection matrix is reported as a CLI error

- **WHEN** `seed-registry` is run against a matrix that has an out-of-vocabulary row (for example
  `mode: teacup` or `status: staging`), or that lacks a row's `source` or a referenced model's
  `origins` entry
- **THEN** the command exits non-zero with the loader's row- or model-naming message rendered as a CLI
  error
- **AND** no traceback is printed and no wandb call is made

#### Scenario: An unreadable or unparseable selection matrix is reported as a CLI error

- **WHEN** `--selection-matrix` names a path that cannot be loaded as a matrix: a directory, a file
  that is not valid YAML, or YAML whose top level is not a mapping
- **THEN** the command exits non-zero with a message naming the path and what was wrong with it
- **AND** no traceback is printed and no wandb call is made

#### Scenario: Non-default alias without --only is refused before any write

- **WHEN** `seed-registry --models-root <dir> --execute` is run with `SLEAP_ROOTS_MODEL_ALIAS=candidate`
  and no `--only`, with or without `--yes` or `--force`
- **THEN** the command exits with click's usage-error status (2) naming `candidate` and `--only`
- **AND** no credential check, confirmation prompt, `wandb.init` or `wandb.Api` call happens

#### Scenario: Non-default alias with --only publishes only the named cards under that alias

- **WHEN** `seed-registry --models-root <dir> --execute --yes --only <id> ...` is run with
  `SLEAP_ROOTS_MODEL_ALIAS=candidate`
- **THEN** only the named cards are validated and published
- **AND** each is linked with exactly the `candidate` alias, and no card is linked with `production`

#### Scenario: Non-default alias still allows a dry run and verify

- **WHEN** `seed-registry` is run with `SLEAP_ROOTS_MODEL_ALIAS=candidate` and no `--only`, either as a
  dry run (no `--execute`) or with `--verify`
- **THEN** the alias guard does not fire
- **AND** the dry run behaves as it does under the default alias, and `--verify` checks the
  `candidate`-status cards

#### Scenario: A blank alias is refused and a padded one is the default

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS` is set to `""` or only whitespace and `seed-registry` runs in any
  mode
- **THEN** it exits non-zero with a CLI error naming the variable, before any wandb call
- **AND WHEN** it is `" production "` and `--execute` runs without `--only`
- **THEN** the non-default-alias guard does not fire, and the candidate-row scoping and the promotion
  check apply

#### Scenario: Default verify reports not-yet-linked production rows as missing

- **WHEN** some `production`-status cards have been published under a non-default alias only, every
  other `production`-status collection carries `production`, and a default-alias `--verify` is run
  without `--only`
- **THEN** it reports exactly those not-yet-linked collections as missing and exits non-zero, which is
  the expected state until they are promoted
- **AND** it reports every other `production`-status collection as present

### Requirement: First-Time Production Link Requires Promotion

Under the **default** alias (`production`), `seed-registry --execute` SHALL first determine, read-only,
which in-scope collections are absent from the registry or hold no version carrying that alias. It
SHALL then refuse, unless `--promote` is given. The refusal SHALL exit with status 1 as a CLI error
(not a usage error), name those collections, and publish nothing. Linking `production` to a collection
for the first time makes it live for the consumer at once, so it SHALL never happen as a side effect of
a routine re-seed, a forgotten alias variable, or `--force`.

This check applies to the cards in the run's scope, which under the default alias are
`production`-status cards only. A `candidate`-status card is skipped or refused earlier (see Candidate
Rows Are Never Linked to Production), so `--promote` never links one.

A collection absent from the registry's collection listing SHALL be treated as unpromoted without
reading its versions, because the wandb client raises when asked for the versions of a collection that
does not exist.

The check SHALL run after the credential check, and before the confirmation prompt, model resolution
and `wandb.init`, so a refused run creates no wandb run. It SHALL run under `--force`, even though
`--force` skips the idempotency read. A registry read error during the check SHALL fail the command
closed.

`--promote` SHALL be accepted only together with `--execute`, under the default alias, and with
`--only`, so every promotion names its collections. Any other use SHALL be a usage error in every mode,
raised before the dry-run return and the credential check. A seed whose in-scope collections already
all carry `production` SHALL proceed unchanged, with or without `--promote`.

#### Scenario: A first-time production link without --promote is refused

- **WHEN** `seed-registry --execute` runs under the default alias, with or without `--yes`, and an
  in-scope `production`-status collection has no `production`-aliased version (it is absent, or carries
  only `candidate`)
- **THEN** the command exits with status 1 naming every such collection and `--promote`
- **AND** no confirmation prompt is shown, no model is resolved, and `wandb.init` is not called

#### Scenario: Losing the candidate alias variable cannot publish to production

- **WHEN** the three wheat and sorghum collections are `production`-status rows that do not yet carry
  `production`, and the candidate command is run without its `SLEAP_ROOTS_MODEL_ALIAS` setting, i.e.
  `seed-registry --models-root <dir> --only <3 new ids> --execute --yes` under the default alias
- **THEN** it is refused as a first-time production link, `wandb.init` is not called and nothing is
  linked

#### Scenario: Force does not bypass the promotion check

- **WHEN** the refused invocation above is repeated with `--force`
- **THEN** it is refused in the same way

#### Scenario: Promotion with --only proceeds

- **WHEN** `seed-registry --execute --yes --only <id> --promote` runs under the default alias, for a
  `production`-status collection with no `production`-aliased version
- **THEN** the check does not refuse it, and that card proceeds to publishing under `production`
- **AND** the collections being linked for the first time are printed before publishing, even under
  `--yes`, or "nothing to promote" when there are none

#### Scenario: Re-seeding already-production collections needs no promotion

- **WHEN** every in-scope collection already holds a `production`-aliased version
- **THEN** `--execute` proceeds with or without `--promote`, skipping them as before

#### Scenario: --promote is refused where it does not apply

- **WHEN** `--promote` is given without `--execute` (a dry run or `--verify`), without `--only`, or under
  a non-default alias
- **THEN** the command fails as a usage error before any credential check or wandb call

#### Scenario: A registry read error fails closed

- **WHEN** the promotion check's registry read raises
- **THEN** the command exits non-zero with a CLI error (no traceback) and publishes nothing

### Requirement: Committed Wheat and Sorghum Rows

The committed selection matrix SHALL carry the wheat and sorghum rows decided for
talmolab/sleap-roots-pipeline#118 (talmolab/sleap-roots-training#72), with their exact models, windows,
root types and source-zip checksums. A later edit that changes any of them then fails a test, rather
than silently re-pointing a card. Matrix-wide counts are pinned by Committed Matrix Totals.

#### Scenario: Committed matrix includes the wheat and sorghum cards

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** `20250401_wheat_models/250328_095645.multi_instance.n=1658` is one `crown` card with the
  single selector (`wheat`, `cylinder`, 5, 14) and checksum
  `650fe30ba2d61e0a292c6dbeaac531a655e811e551bae8c4d9bef0b5f51ba13f`
- **AND** `20250204_sorghum_experimental/sorghum_soybean_primary_6nodes/250203_181521.multi_instance.n=1689`
  is one `primary` card with checksum
  `7c2cd05ded5b3f80163ccd171f3b4abb074ba609f4d52473799162ab763a7c07`, and
  `20250204_sorghum_experimental/sorghum_soybean_lateral_4nodes/250203_214033.multi_instance.n=590` is
  one `lateral` card with checksum
  `f694d6da5a71b17ad72a48c308916ea7d95c5cb9a5c7fcdfe619e59c90130028`, each with the single selector
  (`sorghum`, `cylinder`, 3, 14)
- **AND** the wheat origin has `snapshot` `null`, and both sorghum origins have `snapshot` `"20250204"`
- **AND** all three have status `production`, and the original 8 cards' selectors are unchanged
