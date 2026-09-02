# label-inventory Specification

## Purpose

Records what the label corpus actually contains, by reconciling three independent sources
— the model/label registry, the SLEAP share, and Bloom's scan metadata — so that the
corpus is described by evidence rather than by whichever snapshot happened to seed a
table.

This capability **reports**. It writes nothing to any external system and changes no
existing vocabulary or table. Every correction it implies is a separate change; that
separation is what makes it safe to run against production data.

Its central rule is that a fact is only asserted when two independent derivations agree.
A filename says a folder is called `SLEAP_wheat`; Bloom says a scan's `species_name` is
`wheat`. The first is a guess and the second is the system of record, so the capability
computes both and treats disagreement as a question for a human rather than a value to
pick.

## ADDED Requirements

### Requirement: Digest-Verified Source Resolution

The capability SHALL resolve each registry collection's recorded source path onto the
local share, and SHALL verify the resolved file's digest against the registry artifact
before any value is read from it. A collection whose digest does not match, or whose
recorded path cannot be mapped, SHALL be reported and excluded — never read on the
strength of a matching filename or byte count.

Recorded paths use several prefixes for one tree (a mapped drive letter, a UNC share path,
and the share's own drive letter). The mapping SHALL be explicit and enumerated, so an
unrecognized prefix is a reported failure rather than a silent miss.

Collections SHALL be processed in isolation: one collection failing verification SHALL NOT
prevent the others from being inventoried.

#### Scenario: A digest-matching file is read

- **WHEN** a collection's recorded source path maps to a share file whose digest equals the
  registry artifact's digest
- **THEN** the file is read and the collection proceeds

#### Scenario: A digest mismatch excludes the collection

- **WHEN** the resolved share file's digest differs from the registry artifact's digest
- **THEN** the collection is reported as failing verification and no value is read from it
- **AND** a same-size file with a different digest is still excluded, so the check is not
  a size comparison

#### Scenario: An unmappable recorded path is reported

- **WHEN** a collection's recorded source path begins with a prefix the mapping does not
  enumerate
- **THEN** it is reported as unmappable and excluded, naming the path

#### Scenario: One failing collection does not block the rest

- **WHEN** one collection fails verification and the others succeed
- **THEN** the run completes and emits artifacts for the collections that succeeded
- **AND** the failing collection appears in the report as excluded

### Requirement: Provenance Is Read From The Originally Uploaded Version

A collection's provenance SHALL be read from the artifact version that carries the
original recorded source path, not from a later repair derived from it. A repair version
re-embeds images to restore trainability and in doing so drops the source metadata and
records a temporary working path; reading it yields a path that resolves nowhere and no
species information.

The value the capability reports for whether images are embedded SHALL describe the
version a consumer receives, not the version provenance was read from, because those are
different artifacts in a repaired collection.

#### Scenario: Provenance comes from the original version, not the repair

- **WHEN** a collection has an original version and a later repair version
- **THEN** the recorded source path and species metadata are taken from the original
- **AND** the reported images-embedded value describes the repair, which is what a consumer
  receives

#### Scenario: A single-version collection reads that version

- **WHEN** a collection has exactly one version
- **THEN** provenance and the images-embedded value are both read from it

### Requirement: Every Scan Is Derived Twice And Reconciled

For each scan in a collection the capability SHALL derive its facts independently from two
sources — the labels file's recorded video path, and Bloom's scan metadata joined on the
scan's QR code — and SHALL classify the result as one of exactly three states:

- **agreed** — both sources produced values and they match
- **disagreed** — both produced values and they differ
- **unresolved** — Bloom has no record of that QR code

A disagreement SHALL be recorded with both values. It SHALL NOT be resolved by preferring
one source, because the point of deriving twice is to surface the conflict.

An unresolved scan SHALL NOT be an error. Legacy scans may predate Bloom ingestion or have
been re-keyed, and a run that aborts on the first one cannot inventory the corpus that
motivated it.

Species SHALL be taken from Bloom's per-scan record and SHALL NEVER be inferred from the
collection name or the containing folder name. Those names are what the capability exists
to check.

#### Scenario: Matching sources yield an agreed row

- **WHEN** a scan's filename-derived age and Bloom's recorded plant age are equal
- **THEN** the row is classified agreed

#### Scenario: A disagreement is recorded rather than resolved

- **WHEN** a scan's filename-derived age and Bloom's recorded plant age differ
- **THEN** the row is classified disagreed and carries both values
- **AND** no single value is chosen for it

#### Scenario: A scan absent from Bloom is unresolved, not fatal

- **WHEN** a scan's QR code has no record in Bloom
- **THEN** the row is classified unresolved
- **AND** the remaining scans in that collection are still processed

#### Scenario: Species never comes from a name

- **WHEN** a collection's name and containing folder both indicate one species while
  Bloom records a different species for its scans
- **THEN** the reported species is Bloom's, and the conflict is recorded as a disagreement

### Requirement: Aggregates Derive Only From Agreed Rows, Behind A Human Gate

A collection's aggregate values SHALL be computed only from rows classified agreed.
Disagreed and unresolved rows SHALL be carried into the per-scan output and counted in a
tally, and SHALL NOT contribute to any aggregate.

When a collection has any disagreed or unresolved row, the capability SHALL stop before
emitting that collection's final aggregate and SHALL surface those rows for adjudication.
A collection with no exceptions SHALL complete without a gate.

Reporting a total computed from a mix of verified and unverified rows would produce a
number that looks authoritative and is not. A collection reporting "170 scans, 12
unresolved" forces a decision; one reporting "170 scans" with a footnote does not.

#### Scenario: Non-agreed rows are excluded from aggregates

- **WHEN** a collection has agreed rows and disagreed rows
- **THEN** its aggregate counts are computed from the agreed rows only
- **AND** the disagreed rows appear in the per-scan output and in the tally

#### Scenario: Exceptions gate the final aggregate

- **WHEN** a collection has at least one disagreed or unresolved row
- **THEN** the run stops before emitting that collection's final aggregate and reports
  those rows

#### Scenario: A clean collection needs no gate

- **WHEN** every row in a collection is agreed
- **THEN** its aggregate is emitted without stopping

### Requirement: Scans And Plants Are Counted As Distinct Quantities

The capability SHALL report the number of scans and the number of plants as separate
values, derived from distinct scan identity and distinct plant identity respectively. They
SHALL NOT be derived from a single count.

A plant is imaged at more than one age, and on one day by more than one scanner. Deriving
plant count from video count therefore overcounts — measurably, by 36% in the wheat
collection (170 videos, 125 distinct plants). Because a plant is never imaged fewer than
once, the scan count SHALL be greater than or equal to the plant count for every
collection, and a result violating that SHALL be reported as a defect rather than emitted.

#### Scenario: A plant imaged at two ages is one plant and two scans

- **WHEN** one plant identity appears in two scans at different ages
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: A plant imaged twice on one day is one plant and two scans

- **WHEN** one plant identity appears in two scans on the same day from different scanners
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: Scan count is never below plant count

- **WHEN** a collection's computed scan count is lower than its computed plant count
- **THEN** the collection is reported as a defect and its aggregate is not emitted

### Requirement: No External System Is Written

The capability SHALL perform no write, publish, upload, ingest, alias, or delete against
the registry or Bloom. It SHALL use only read operations.

The prohibition is on the **effect**, not on a named function: the credentials it runs
with can write, and Bloom's own CLI exposes an ingest path, so nothing in the environment
prevents a later edit from mutating production data. The capability SHALL therefore be
built so that its external clients are supplied to it rather than constructed inside it,
making an unintended write visible in a test rather than only in production.

#### Scenario: A run performs no registry write

- **WHEN** the capability runs to completion against a supplied registry client
- **THEN** no publish, link, alias, or delete operation is invoked on that client

#### Scenario: A run performs no Bloom write

- **WHEN** the capability runs to completion against a supplied Bloom client
- **THEN** only read operations are invoked on that client

### Requirement: Collections Are Discovered Structurally

Share collections SHALL be discovered by structure rather than from a maintained list: a
folder is inventoried when it holds a labels file at its top level. Folders holding no
such file SHALL be reported as skipped, with the reason.

A maintained list would encode only what is already remembered, which defeats the purpose
of an inventory. Derived training artifacts SHALL NOT be treated as collections — a
train/test split describes a training run, not a corpus, and counting one as a collection
would report a subset's frame count as the corpus's.

#### Scenario: A folder with a top-level labels file is inventoried

- **WHEN** a folder holds a labels file at its top level
- **THEN** it is inventoried as a collection

#### Scenario: A folder with no top-level labels file is skipped and reported

- **WHEN** a folder holds no labels file at its top level
- **THEN** it is not inventoried, and appears in the report as skipped with a reason

#### Scenario: A train/test split is not a collection

- **WHEN** a folder contains a labels file at its top level and derived split files beneath
  it
- **THEN** only the top-level file is inventoried
- **AND** the reported frame count is the top-level file's, not a split's

### Requirement: The Skeleton Table Is Diffed, Never Consulted

The capability SHALL emit a diff between what the corpus demonstrates and what
`skeletons.yaml` asserts, and SHALL NOT read that table to fill in a value. Each
collection SHALL be reported as **verifying** a row, **contradicting** a row, or having
**no row**.

The capability SHALL also report where the table's keying cannot express the corpus. Rows
are keyed on species, root type and age with no capture mode, while the corpus contains
two collections of the same species and root type with different node counts under
different modes — a missing key rather than a wrong value, which no per-row correction
would fix.

The observed skeleton name SHALL be reported as the literal value the file carries, with
no substitution of a canonical name, because the literal is the evidence.

#### Scenario: A collection matching a row verifies it

- **WHEN** a collection's node count equals the value in the matching table row
- **THEN** the diff reports that row as verified by evidence

#### Scenario: A collection contradicting a row is reported as a contradiction

- **WHEN** a collection's node count differs from the value in the matching table row
- **THEN** the diff reports a contradiction with both values
- **AND** no value is written back to the table

#### Scenario: A collection with no row is reported as missing

- **WHEN** a collection's species and root type match no row in the table
- **THEN** the diff reports the row as missing

#### Scenario: A mode-dependent node count is reported as a keying gap

- **WHEN** two collections share a species and root type, differ in capture mode, and have
  different node counts
- **THEN** the diff reports a keying gap rather than a contradiction on either row

### Requirement: Re-Running Is Idempotent

Running the capability twice against unchanged inputs SHALL produce identical artifacts.
Adding a collection SHALL add its entries without altering the entries of collections
whose inputs have not changed.

The corpus grows, so a one-time script would be stale on the day a further collection is
published. Idempotence is what lets the artifacts be regenerated and diffed rather than
audited by hand.

#### Scenario: Unchanged inputs produce identical artifacts

- **WHEN** the capability is run twice with no input change
- **THEN** the emitted artifacts are byte-identical between runs

#### Scenario: A new collection does not disturb existing entries

- **WHEN** a collection is added and the capability is re-run
- **THEN** the new collection's entries appear
- **AND** the entries for unchanged collections are byte-identical to the previous run
