# label-inventory Specification

## Purpose

Records what the label corpus actually contains, by reconciling three independent sources
— the label registry, the SLEAP share, and Bloom's scan metadata — so that the corpus is
described by evidence rather than by whichever snapshot happened to seed a table.

Division of authority, which this capability depends on and does not change: **W&B is the
system of record for labeled data and model versioning**, per `openspec/project.md`'s
Important Constraints. Bloom is the source of scan and plant metadata — species, plant
identity and age — which follows from the image-source role that same constraint assigns
it. This capability reads the first for artifacts and the second for scan facts; it is
authoritative for neither.

It emits **evidence, not cards**. A card requires fields an inventory cannot know — a
registry identifier and version are meaningless for a collection that was never registered,
and the corpus holds more unregistered collections than registered ones. Consumers build
cards from this evidence and supply the rest themselves.

Its central rule is that a fact is asserted only when two derivations agree — with one
honest qualification. For **species** the two derivations are genuinely independent: a
human typed the folder name, and Bloom records `species_name` from experiment metadata. For
**age and scan date** they are not: the download tooling wrote the directory name *from*
those same columns, so agreement is a **staleness check** — did the record change after
download, through a re-key or a correction — rather than corroboration. Both checks are
worth running; only the first is evidence of correctness.

This capability **reports**. It writes nothing to any external system and changes no
existing vocabulary or table. Every correction it implies is a separate change; that
separation is what makes it safe to run against production data.

## ADDED Requirements

### Requirement: Source Resolution Is Digest-Verified Where A Registry Artifact Exists

The capability SHALL resolve each registry collection's recorded source path onto the local
share and SHALL verify the resolved file's digest against the digest the registry records
for that file **in the artifact's manifest entry** — the base64 MD5 of the file's bytes. It
SHALL NOT compare against the artifact-level digest, which is computed over the manifest
itself and is not comparable to a file hash; comparing it would fail on every collection,
and the plausible repair under time pressure is a size comparison, which this requirement
exists to forbid. Verification SHALL read manifest metadata only and SHALL NOT download the
artifact.

A collection discovered on the share with **no registry counterpart** SHALL be inventoried
and reported as unregistered, with its facts read from the share file directly and every
field so derived marked share-only. The digest gate applies only where a registry artifact
exists to compare against. This is the majority of the corpus, not an edge case, and a
capability that excluded it would emit only the collections already known.

The registry and the share are each required for what only they can supply: without the
share there is no file to read, and without the registry no collection can be verified or
its provenance version chosen. When either is unavailable the capability SHALL exit naming
which one is absent and SHALL emit nothing.

Recorded paths use several prefixes for one tree. The mapping SHALL be explicit and
enumerated, so an unrecognized prefix is a reported failure rather than a silent miss, and
SHALL be evaluated under Windows path semantics on every platform, including the
drive-relative form, so a run on one operating system resolves a recorded path as another
would.

A collection's provenance SHALL be read from the artifact version carrying the original
recorded source path, not from a later repair derived from it: a repair re-embeds images to
restore trainability and in doing so drops the source metadata and records a temporary
working path. The value reported for whether images are embedded SHALL describe the version
a consumer receives, which in a repaired collection is a different artifact.

Two collections whose recorded paths resolve to the same file SHALL both be reported, naming
the shared path; neither SHALL silently replace the other's row.

A collection whose digest does not match, whose recorded path cannot be mapped, or whose
resolved path is not a readable file SHALL be reported and excluded. Being unreadable SHALL
be reported distinctly from mismatching, so an I/O failure is not recorded as an accusation
against a file that may be intact.

#### Scenario: A digest-matching file is read

- **WHEN** a collection's recorded source path maps to a share file whose digest equals the
  digest in the registry artifact's manifest entry
- **THEN** the file is read and the collection proceeds

#### Scenario: Verification downloads nothing

- **WHEN** a collection is verified
- **THEN** no artifact download is performed, and only manifest metadata is fetched

#### Scenario: A same-size file with different content is excluded

- **WHEN** the resolved share file has the same byte size as the manifest entry records but
  a different digest
- **THEN** the collection is reported as failing verification, so the check is not a size
  comparison

#### Scenario: A share collection absent from the registry is inventoried

- **WHEN** a discovered collection has no matching registry entry
- **THEN** it is inventoried, reported as unregistered, and its derived fields are marked
  share-only

#### Scenario: Unregistered is distinct from failing verification

- **WHEN** one collection has no registry entry and another has one whose digest differs
- **THEN** the first is reported as unregistered and the second as failing verification,
  under distinct outcomes

#### Scenario: An unmappable recorded path is reported

- **WHEN** a collection's recorded source path begins with a prefix the mapping does not
  enumerate
- **THEN** it is reported as unmappable and excluded, naming the path

#### Scenario: A recorded path resolving to a directory is refused

- **WHEN** a collection's recorded source path resolves to a directory rather than a file
- **THEN** it is reported as unresolvable and is not opened

#### Scenario: An unreadable file is distinguished from a mismatch

- **WHEN** reading the resolved share file raises an I/O error
- **THEN** the collection is reported as unreadable, naming the error, and not as a digest
  mismatch

#### Scenario: Prefix mapping is platform-independent

- **WHEN** the same recorded path is mapped on a POSIX host and on a Windows host, including
  the drive-relative form
- **THEN** both produce the same resolved share path

#### Scenario: Provenance comes from the original version, not the repair

- **WHEN** a collection has an original version and a later repair version
- **THEN** the recorded source path and species metadata are taken from the original
- **AND** the reported images-embedded value describes the repair, which is what a consumer
  receives

#### Scenario: A single-version collection reads that version

- **WHEN** a collection has exactly one version
- **THEN** provenance and the images-embedded value are both read from it

#### Scenario: Two collections resolving to one file are both reported

- **WHEN** two collections' recorded paths resolve to the same share file
- **THEN** both are reported, naming the shared path

#### Scenario: An absent registry or share is named and nothing is emitted

- **WHEN** either the registry or the share is unavailable
- **THEN** the capability exits naming the missing source and emits no artifact

### Requirement: One Collection's Failure Is Contained

The capability SHALL process collections in isolation. A failure attributable to one
collection — a digest mismatch, an unmappable or unreadable path, an internally inconsistent
count, or exceptions among its scans — SHALL affect that collection's output only, and SHALL
NOT prevent any other collection from being inventoried and emitted.

The corpus is the unit of interest and its members fail independently. A run that abandons
twenty-nine collections because one is malformed cannot inventory the corpus that motivated
it.

#### Scenario: One failing collection does not block the rest

- **WHEN** one collection fails verification and the others succeed
- **THEN** the run completes and emits output for the collections that succeeded
- **AND** the failing collection appears in the report under its own outcome

#### Scenario: A withheld aggregate does not withhold the corpus

- **WHEN** one collection's aggregate is withheld
- **THEN** the other collections are inventoried and emitted unaffected

### Requirement: Recorded Video Paths Take More Than One Shape

The capability SHALL recognise every shape a recorded video path takes in this corpus, and
SHALL state per shape which facts it can yield. There are three, and treating them as one
would silently withhold whole collections.

A **referenced** video records a path whose directory carries the scan's age, date and
scanning device and whose filename carries the scan's identifying code. An **embedded**
package records the package's own path in the same field; the original scan path is held
separately as the embedded source, which may be a list and may have been deliberately
cleared. A **generated** package records a list of curated per-view filenames carrying the
identifying code and the age but no date and no device.

A shape yielding no date SHALL NOT thereby render its scans unresolved: the comparison
SHALL use the facts a shape can supply. Two of the corpus's collections are embedded
packages and are the only ones whose skeleton rows are already independently verified —
losing them would remove the diff's sole confirmed anchor — and generated packages are the
shape every future package takes.

The capability SHALL open labels files without resolving their video backends, because a
host without the share attached cannot resolve them and does not need to.

#### Scenario: A referenced path yields code, age, date and device

- **WHEN** a referenced video path is parsed
- **THEN** the identifying code, age, date and device are available

#### Scenario: An embedded package reads the embedded source, not the package path

- **WHEN** an embedded package's video is parsed
- **THEN** the identifying code is taken from the embedded source path, not from the
  package's own filename

#### Scenario: A cleared embedded source is reported, not mis-parsed

- **WHEN** an embedded video's source has been cleared
- **THEN** its scans are reported as having no recoverable path, naming the reason

#### Scenario: A generated package resolves without a date

- **WHEN** a generated package's video is parsed
- **THEN** the identifying code and age are available and the scan resolves
- **AND** the absence of a date does not by itself make the scan unresolved

#### Scenario: Labels files open without resolving video backends

- **WHEN** a labels file is opened on a host with no access to its video backends
- **THEN** it opens and its facts are read

### Requirement: Every Scan Is Derived Twice And Reconciled

For each scan the capability SHALL derive facts independently from the recorded video path
and from Bloom's scan metadata, joined on the scan's identifying code, and SHALL classify
the result as **agreed**, **disagreed**, or **unresolved**. An unresolved row SHALL record
which of three reasons applies: no usable identifying code, no Bloom record for that code,
or nothing comparable on the labels side.

A disagreement SHALL be recorded with both values and SHALL NOT be resolved by preferring
one source. An unresolved scan SHALL NOT be an error; legacy scans may predate ingestion or
have been re-keyed.

The comparison SHALL normalise both sides before comparing, and the normalisation SHALL be
specified rather than left to the implementer: an age rendered in a directory name is the
same quantity Bloom records, but a date rendered in a directory name is ambiguous between
day-first and month-first and may carry a two-digit year. An unparseable date SHALL make a
row unresolved for that reason, never disagreed — a parse failure reported as a
disagreement would withhold a collection's aggregate on the strength of a formatting
convention.

Lookups SHALL be batched so that no request's rendered, percent-encoded URL exceeds the
gateway's length limit, and identifiers SHALL be quoted as the gateway requires. A
collection can hold more scans than one filter can carry, so an unbatched implementation
succeeds on small collections and fails only on the largest.

#### Scenario: Matching sources yield an agreed row

- **WHEN** a scan's path-derived age and Bloom's recorded age are equal, and the dates match
- **THEN** the row is classified agreed

#### Scenario: A disagreement is recorded rather than resolved

- **WHEN** a scan's path-derived age and Bloom's recorded age differ
- **THEN** the row is classified disagreed and carries both values

#### Scenario: A scan absent from Bloom is unresolved, not fatal

- **WHEN** a scan's identifying code has no record in Bloom
- **THEN** the row is classified unresolved with that reason
- **AND** the remaining scans are still processed

#### Scenario: An unusable identifying code is unresolved with a distinct reason

- **WHEN** a video path yields no usable identifying code
- **THEN** the row is unresolved recording that reason, and no lookup is attempted

#### Scenario: An unparseable date is unresolved, not disagreed

- **WHEN** a recorded date cannot be parsed unambiguously
- **THEN** the row is unresolved for that reason
- **AND** it is not classified disagreed

#### Scenario: Lookups are batched below the gateway's limit

- **WHEN** a collection holds more scans than one request's filter can carry
- **THEN** the lookups are split across requests, each within the limit, and every scan
  resolves

### Requirement: Species Is Sourced From Bloom, And A Mixed Collection Is A Defect

The species reported for a collection SHALL be taken from Bloom's records and SHALL NEVER be
inferred from the collection name, the containing folder name, or the labels filename. Those
names are what this capability exists to check. It SHALL be normalised by the same rule the
contract library applies to a species, so one spelling does not fail to join.

A collection whose scans resolve to more than one species SHALL be reported as a **defect
blocking its card**, not as a species value. A label collection is single-species by
program decision — multi-species training data is combined from separate single-species
collections at training time — and the consuming card carries one species, so "mixed" is
not a value any consumer can store.

Because species is an experiment-level property in Bloom, a mixed result means the
collection pools scans from more than one experiment. The capability SHALL emit the
experiment-to-species mapping it found, which is the evidence, rather than only the verdict.

The reported species MAY fall outside the repo's model-side species vocabulary. That is
expected output, not an error, and widening the vocabulary is not this capability's concern.

#### Scenario: Species comes from Bloom when the name disagrees

- **WHEN** a collection's name indicates one species while Bloom records another for its
  scans
- **THEN** the reported species is Bloom's, and the disagreement is recorded

#### Scenario: A mixed collection is reported as a defect with its evidence

- **WHEN** a collection's scans resolve to more than one species
- **THEN** it is reported as a defect blocking its card, and no species value is chosen
- **AND** the experiment-to-species mapping found is emitted

#### Scenario: Species spelling is normalised before comparison

- **WHEN** Bloom records a species whose spelling differs only in case or surrounding
  whitespace from the expected value
- **THEN** it normalises to the same species and does not register as mixed

#### Scenario: A species outside the model-side vocabulary is reported, not rejected

- **WHEN** Bloom records a species the repo's model-side vocabulary does not contain
- **THEN** it is reported as that species without error

### Requirement: Scans And Plants Are Counted As Distinct Quantities

The capability SHALL report scan count and plant count as separate values, derived from
distinct scan identity and distinct Bloom plant identity. The plant count SHALL NOT be
derived from the identifying code recorded in a filename, which is a human-assigned proxy.

One scan is one video; the rotational views of a scan are frames within it, not separate
scans. A plant is imaged at more than one age, and on one day by more than one device, so
scan count exceeds plant count wherever a plant was imaged repeatedly.

The reported plant count SHALL be documented as a count of **distinct Bloom plant records**,
which is not a botanical plant count under a capture mode that places several plants in one
scan. The invariant that scan count is at least plant count follows from that record
structure, not from biology, and SHALL be asserted before emission as a guard against an
inconsistent intermediate.

#### Scenario: A plant imaged at two ages is one plant and two scans

- **WHEN** one Bloom plant identity appears in two scans at different ages
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: A plant imaged twice on one day is one plant and two scans

- **WHEN** one Bloom plant identity appears in two scans on the same day from different
  devices
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: The plant count is not the count of filename codes

- **WHEN** a collection's distinct filename codes and distinct Bloom plant identities differ
  in number
- **THEN** the reported plant count is the count of Bloom plant identities

#### Scenario: An inconsistent count withholds that collection only

- **WHEN** a collection's computed scan count is lower than its computed plant count
- **THEN** it is reported, naming the collection, and no aggregate is emitted for it

### Requirement: Counts Distinguish Labels From Predictions

The capability SHALL report frame and instance counts that distinguish user-made labels from
model predictions, and SHALL report the predicted counts separately rather than merging
them.

A labeling package's starting version carries predicted instances as a labeler's starting
point, and packages deliberately ship frames with no instance at all where a root type is
absent. A single total therefore describes the labeling *request* for any collection
published before labeling finished, not the labeled corpus — and it is the labeled corpus a
consumer believes it is reading.

The capability SHALL report the count of frames carrying a user label, the count of user
instances, and the count of predicted instances, each named for what it counts.

#### Scenario: User and predicted instances are counted separately

- **WHEN** a collection carries both user labels and model predictions
- **THEN** the user instance count and the predicted instance count are reported separately

#### Scenario: Frames with no instance do not inflate the labeled count

- **WHEN** a collection carries frames with no instance
- **THEN** those frames are excluded from the count of frames carrying a user label

### Requirement: Confidence Is Per Field, And File Facts Do Not Depend On Bloom

The capability SHALL record confidence per field rather than per collection, and SHALL NOT
withhold a field whose derivation did not depend on the source that failed.

Facts read from the labels file — the skeleton's name, its node names and count, and the
frame and instance counts — have no Bloom dependency. Withholding them because one scan's
filename was malformed would suppress exactly the evidence the skeleton table is waiting on,
and would make this capability's output weaker than the check it replaces, which needs no
Bloom at all.

Fields derived by reconciliation SHALL be computed from agreed rows only. Where a collection
has disagreed or unresolved rows, those fields SHALL be withheld and the rows surfaced for
adjudication; the file-derived fields SHALL still be emitted, marked with their own
confidence.

A collection with no scans surviving reconciliation SHALL be emitted as an entry recording
that, never as a verified aggregate of zero.

#### Scenario: File facts survive a Bloom failure

- **WHEN** every scan in a collection is unresolved because Bloom was unavailable
- **THEN** the skeleton name, node count, node names and frame counts are still emitted
- **AND** the reconciliation-derived fields are withheld

#### Scenario: Reconciled fields use agreed rows only

- **WHEN** a collection has agreed rows and disagreed rows
- **THEN** the reconciliation-derived fields are computed from the agreed rows only

#### Scenario: Confidence is recorded per field

- **WHEN** a collection has a verified species and an underivable plant count
- **THEN** each field carries its own confidence rather than the collection carrying one

#### Scenario: A collection with no surviving scans is not a verified zero

- **WHEN** no scan in a collection survives reconciliation
- **THEN** the collection is emitted as an entry recording that it could not be verified

### Requirement: The Age Window Is Emitted As An Observed Range With Its Epoch

The capability SHALL emit the age window as the **observed** range across a collection's
agreed scans, labelled as observed, and SHALL record the epoch that range is measured in.

The sibling contract's age window denotes an approved selection window curated at
promotion, which may be wider than the data. An observed range emitted without that
distinction will later be read as an approved one. The capability SHALL also emit the set of
ages actually observed, because a range alone asserts a contiguity it cannot establish.

Age epochs differ across capture modes in the upstream data, and the epoch is a convention
recorded nowhere upstream. A window pooled across modes without its epoch is therefore not
interpretable, and SHALL NOT be emitted without one.

#### Scenario: The window is labelled observed and carries its epoch

- **WHEN** a collection's age window is emitted
- **THEN** it is labelled as an observed range and records the epoch it is measured in

#### Scenario: The observed age set accompanies the range

- **WHEN** a collection's scans span a range with gaps
- **THEN** the emitted evidence records the ages actually observed, not only the bounds

### Requirement: Only Read Operations Are Issued

The capability SHALL issue only read operations against the registry and against Bloom.

For Bloom the prohibition SHALL be enforced on the **data plane**: every request to the data
endpoint SHALL use the read method. Every table write and every volatile remote procedure
requires another method, so a read-only data plane cannot perform one regardless of what
authority its credentials carry. The session exchange that mints credentials is exempt; it
writes no application data and without it no read is possible. A read-only remote procedure
may itself be served by the read method, so the guarantee rests on the gateway refusing the
read method for a volatile procedure, not on procedures being writes.

The capability SHALL call only the upstream client's documented read entry points, SHALL NOT
import or reference its ingest surface, and SHALL receive its clients rather than
constructing them, so an unintended write fails a test rather than reaching production.

Loaded credentials SHALL be kept out of every representation, log line, exception message,
and emitted artifact. The artifacts are committed to a public repository, so a credential
reaching a traceback is a published credential.

#### Scenario: The data plane issues only reads

- **WHEN** the capability runs to completion against a supplied client
- **THEN** every request it issued to the data endpoint used the read method
- **AND** a data-plane request using any other method fails the run

#### Scenario: The ingest surface is never reached

- **WHEN** the modules the capability imports are inspected
- **THEN** none of them imports or references the upstream ingest surface

#### Scenario: A run performs no registry write

- **WHEN** the capability runs to completion against a supplied registry client
- **THEN** only read operations are invoked, and no artifact download is invoked

#### Scenario: Credentials do not reach output

- **WHEN** an exception carrying the loaded credentials is formatted
- **THEN** the secret values appear neither in that output nor in any emitted artifact

### Requirement: Emitted Artifacts Are Redacted Before They Are Committed

Every path recorded in an emitted artifact SHALL have its internal host segment and user
segment redacted. The artifacts are committed to a **public** repository, and the recorded
source paths contain an internal hostname and a username.

Redaction SHALL be structural rather than a list of known strings. Discovery is confined to
one user's directory, so every walked path carries one user segment — but a registry
artifact's **recorded** path is historical metadata this capability does not control and
cannot re-scope, and may name a host or user segment no enumerated substitution covers. The
rule SHALL redact the segment following a user-directory marker whatever its value, and any
host segment of a network path, with the substitutions the repository already applies as a
compatibility floor.

Fields identifying a person SHALL NOT be emitted. Fields describing plants and experiments —
genotype, accession and experiment name — are emitted by decision.

#### Scenario: An internal host and user are redacted

- **WHEN** a recorded path contains the internal host segment or the user segment
- **THEN** the emitted artifact carries the redacted form, and the un-redacted value appears
  in no emitted artifact

#### Scenario: A user segment the rule has never seen is still redacted

- **WHEN** a recorded path's user segment appears in no enumerated substitution
- **THEN** it is redacted

#### Scenario: A person-identifying field is not emitted

- **WHEN** the scan metadata contains a field identifying a person
- **THEN** that field appears in no emitted artifact

### Requirement: Collections Are Discovered Structurally

Share collections SHALL be discovered by structure rather than from a maintained list: a
folder is inventoried when it holds a labels file at its top level. Folders holding no such
file SHALL be reported as skipped, with the reason.

A maintained list would encode only what is already remembered, which defeats an inventory.
Derived training artifacts SHALL NOT be treated as collections — a split describes a
training run, not a corpus, and counting one would report a subset's frame count as the
corpus's. Where a folder holds more than one candidate labels file, the rule that selects
among them SHALL be stated and applied consistently rather than left to directory order.

The root walked SHALL be a supplied parameter. In production it is the project owner's
directory; other users' directories are out of scope and SHALL NOT be walked, and discovery
SHALL NOT ascend above the supplied root.

#### Scenario: A folder with a top-level labels file is inventoried

- **WHEN** a folder holds a labels file at its top level
- **THEN** it is inventoried as a collection

#### Scenario: A folder with no top-level labels file is skipped and reported

- **WHEN** a folder holds no labels file at its top level
- **THEN** it is not inventoried and appears in the report as skipped with a reason

#### Scenario: A split is not a collection

- **WHEN** a folder contains a labels file at its top level and derived split files beneath
- **THEN** only the top-level file is inventoried, and the reported frame count is its own

#### Scenario: Sibling candidates are selected by a stated rule

- **WHEN** a folder holds more than one candidate labels file at its top level
- **THEN** the selected file is chosen by the stated rule and the others are recorded as
  not selected

#### Scenario: Discovery runs against a supplied root and does not ascend

- **WHEN** discovery is given a root other than the production share
- **THEN** it walks that root and does not ascend above it

### Requirement: The Skeleton Table Is Diffed, Never Used As A Source Of Values

The capability SHALL emit a diff between what the corpus demonstrates and what the
repo-owned skeleton table asserts, and SHALL NOT read that table to fill in a value. Each
collection SHALL be reported as verifying a row, contradicting a row, having no row, or
exposing a keying gap.

Root type and capture mode are not available from scan metadata; where the diff needs them
to select a row they SHALL be derived from the collection's name, used **only** to select
the row to compare against, and SHALL NOT be emitted as evidence. A name-derived value is
adequate to choose what to compare and inadequate to record as provenance, and the
distinction SHALL be visible in the output.

The table's rows are keyed without capture mode while the corpus contains collections of one
species and root type whose node counts differ by mode — a missing key rather than a wrong
value, which no per-row correction fixes. The age key is not implicated: node counts do not
vary by age in the observed corpus, and the age key governs which root types exist.

The observed skeleton name SHALL be reported as the literal value the file carries. A file
carrying more than one skeleton SHALL be reported as such rather than reduced to one.

#### Scenario: A collection matching a row verifies it

- **WHEN** a collection's node count equals the value in the matching row
- **THEN** the diff reports that row as verified by evidence

#### Scenario: A contradiction is reported without writing back

- **WHEN** a collection's node count differs from the matching row
- **THEN** the diff reports a contradiction with both values, and nothing is written to the
  table

#### Scenario: A collection with no row is reported as having none

- **WHEN** a collection matches no row in the table
- **THEN** the diff reports that no row exists for it

#### Scenario: A mode-dependent node count is reported as a keying gap

- **WHEN** two collections share a species and root type, differ in capture mode, and have
  different node counts
- **THEN** the diff reports a keying gap rather than a contradiction on either row

#### Scenario: Name-derived selectors are not emitted as evidence

- **WHEN** root type or capture mode is derived from a collection's name to select a row
- **THEN** that value is used for selection and does not appear as emitted evidence

#### Scenario: A multi-skeleton file is reported, not reduced

- **WHEN** a labels file carries more than one skeleton
- **THEN** the collection is reported as carrying multiple skeletons

### Requirement: Artifacts Are Emitted Atomically And Deterministically

Artifact content SHALL be a deterministic function of the inputs alone. The capability SHALL
NOT embed a run timestamp, hostname, run identifier, or any value varying between runs over
unchanged inputs, and SHALL emit collections, rows and keys in a defined, input-derived
order, with a fixed line ending and a fixed rendering of numbers and absent values so that
output is identical across operating systems.

An artifact SHALL be rendered in full and then moved into place, so a run failing during
emission leaves the previous artifact intact. A failure the capability observes SHALL remove
its staging file; a staging file orphaned by a process killed outright SHALL be overwritten
by the next run rather than treated as state. An atomic replace requires the staging file
beside its destination, so a hard kill can leave one there — the guarantee is that the
destination is never partial.

Running twice against unchanged inputs SHALL produce identical artifacts, and adding a
collection SHALL add its entries without altering those of collections whose inputs have not
changed. There SHALL be no resume; a re-run is a full re-run.

#### Scenario: Unchanged inputs produce identical artifacts

- **WHEN** the capability is run twice with no input change
- **THEN** the emitted artifacts are byte-identical between runs

#### Scenario: Output is identical across operating systems

- **WHEN** the capability is run on different operating systems over the same inputs
- **THEN** the emitted artifacts are byte-identical

#### Scenario: No varying value is embedded

- **WHEN** an emitted artifact is inspected
- **THEN** it contains no run timestamp, hostname, or run identifier

#### Scenario: A new collection does not disturb existing entries

- **WHEN** a collection is added and the capability is re-run
- **THEN** the new entries appear, and unchanged collections' artifacts are byte-identical
  and their aggregate entries unchanged

#### Scenario: A failure during emission leaves the previous artifact intact

- **WHEN** emission raises partway through
- **THEN** the previous artifact is unchanged and the staging file is removed

### Requirement: The Emitted Evidence Schema And Its Vocabularies Are Documented And Locked

The repository SHALL document the emitted schema and **every** closed vocabulary it uses,
and a test SHALL lock each documented vocabulary against the values the emitter writes.

Four vocabularies are closed and all four are load-bearing: the per-scan reconciliation
status, the reason recorded on an unresolved row, the per-field confidence, and the
collection-level outcome. A reader who cannot distinguish an unregistered collection from an
excluded one cannot tell an unverifiable collection from a suspect one.

The vocabularies SHALL be defined as constants in a module importable without the registry
or scan-metadata client libraries, so the locking test stays cheap.

The documentation SHALL state, for each reconciliation status, whether rows carrying it
contribute to reconciliation-derived fields — so a reader comparing a per-scan row count
against a reported scan count understands why they differ.

#### Scenario: Every documented vocabulary matches the emitter

- **WHEN** each documented vocabulary is compared with the values the emitter writes
- **THEN** each is equal to its counterpart

#### Scenario: The vocabularies import without client libraries

- **WHEN** the module defining the vocabularies is imported
- **THEN** it imports without requiring the registry or scan-metadata client libraries

#### Scenario: The documentation states what each status implies

- **WHEN** the documentation is read
- **THEN** it states for each reconciliation status whether rows carrying it contribute to
  reconciliation-derived fields
