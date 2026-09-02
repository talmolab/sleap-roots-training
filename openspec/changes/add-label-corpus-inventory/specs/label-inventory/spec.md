# label-inventory Specification

## Purpose

Records what the label corpus actually contains, by reconciling three independent sources
— the label registry, the SLEAP share, and Bloom's scan metadata — so that the corpus is
described by evidence rather than by whichever snapshot happened to seed a table.

Division of authority, which this capability depends on and does not change: **W&B is the
system of record for labeled data and model versioning**, per `openspec/project.md`'s
Important Constraints. **Bloom is the system of record for scan and plant metadata** —
species, plant identity, and age — which is the image-source role that same constraint
assigns it. This capability reads the first for artifacts and the second for scan facts;
it is authoritative for neither.

Its central rule is that a fact is only asserted when two independent derivations agree. A
filename says a folder is called `SLEAP_wheat`; Bloom records a scan's `species_name`. The
first is a guess and the second is authoritative for that field, so the capability computes
both and treats disagreement as a question for a person rather than a value to pick.

This capability **reports**. It writes nothing to any external system and changes no
existing vocabulary or table. Every correction it implies is a separate change; that
separation is what makes it safe to run against production data.

## ADDED Requirements

### Requirement: Digest-Verified Source Resolution

The capability SHALL resolve each registry collection's recorded source path onto the
local share, and SHALL verify the resolved file's digest against the digest the registry
records for that file **in the artifact's manifest entry** — the base64 MD5 of the file's
bytes. It SHALL NOT compare against the artifact-level digest, which is a hex MD5 computed
over the manifest itself and is not comparable to a file hash; comparing it would fail on
every collection, and the plausible repair under time pressure is a size comparison, which
this requirement exists to forbid.

Verification SHALL read manifest metadata only and SHALL NOT download the artifact. The
largest collections are hundreds of megabytes, and the manifest already carries both the
digest and the size.

Recorded paths use several prefixes for one tree (a mapped drive letter, a UNC share path,
and the share's own drive letter). The mapping SHALL be explicit and enumerated, so an
unrecognized prefix is a reported failure rather than a silent miss. It SHALL be evaluated
under Windows path semantics on every platform, including the drive-relative form
(`D:name`), so a run on one operating system resolves a recorded path the same way as a
run on another.

A collection whose digest does not match, whose recorded path cannot be mapped, or whose
resolved path is not a readable file SHALL be reported and excluded — never read on the
strength of a matching filename or byte count. Being unreadable SHALL be reported
distinctly from mismatching, so an I/O failure is not recorded as an accusation against a
file that may be intact.

Collections SHALL be processed in isolation: one collection failing verification SHALL NOT
prevent the others from being inventoried.

#### Scenario: A digest-matching file is read

- **WHEN** a collection's recorded source path maps to a share file whose digest equals the
  digest in the registry artifact's manifest entry
- **THEN** the file is read and the collection proceeds

#### Scenario: Verification downloads nothing

- **WHEN** a collection is verified
- **THEN** no artifact download is performed, and only manifest metadata is fetched

#### Scenario: A digest mismatch excludes the collection

- **WHEN** the resolved share file's digest differs from the manifest entry's digest
- **THEN** the collection is reported as failing verification and no value is read from it

#### Scenario: A same-size file with different content is still excluded

- **WHEN** the resolved share file has the same byte size as the manifest entry records but
  a different digest
- **THEN** the collection is reported as failing verification, so the check is not a size
  comparison

#### Scenario: An unmappable recorded path is reported

- **WHEN** a collection's recorded source path begins with a prefix the mapping does not
  enumerate
- **THEN** it is reported as unmappable and excluded, naming the path

#### Scenario: A recorded path resolving to a directory is refused

- **WHEN** a collection's recorded source path resolves to a directory rather than a file
- **THEN** it is reported as unresolvable and is not opened

#### Scenario: An unreadable file is distinguished from a mismatch

- **WHEN** reading the resolved share file raises an I/O error
- **THEN** the collection is reported as unreadable, naming the error
- **AND** it is not reported as a digest mismatch

#### Scenario: Prefix mapping is platform-independent

- **WHEN** the same recorded path is mapped on a POSIX host and on a Windows host,
  including the drive-relative `D:name` form
- **THEN** both produce the same resolved share path

#### Scenario: One failing collection does not block the rest

- **WHEN** one collection fails verification and the others succeed
- **THEN** the run completes and emits artifacts for the collections that succeeded
- **AND** the failing collection appears in the report as excluded

### Requirement: A Collection Without A Registry Counterpart Is Inventoried As Unregistered

A collection discovered on the share with no registry counterpart SHALL be inventoried and
reported as **unregistered**. Its facts SHALL be read from the share file directly, and
every field so derived SHALL be marked as share-only. The digest gate applies only where a
registry artifact exists to compare against.

This is the larger part of the corpus, not an edge case: the registry holds 8 collections
against an expected 25–30, so most discovered collections have nothing to verify against.
A capability that excluded them for failing a gate they cannot enter would emit only the
collections already known, which is the state this capability exists to change.

Unregistered SHALL be reported distinctly from unverified-because-mismatched. The first
means no registry entry exists; the second means one exists and disagrees.

#### Scenario: A share collection absent from the registry is inventoried

- **WHEN** a discovered collection has no matching registry entry
- **THEN** it is inventoried, reported as unregistered, and its derived fields are marked
  share-only

#### Scenario: Unregistered is distinct from mismatched

- **WHEN** one collection has no registry entry and another has one whose digest differs
- **THEN** the first is reported as unregistered and the second as failing verification,
  under distinct statuses

### Requirement: Every Scan Is Derived Twice And Reconciled

For each scan in a collection the capability SHALL derive its facts independently from two
sources — the labels file's recorded video path, and Bloom's scan metadata joined on the
scan's QR code — and SHALL classify the result as one of exactly three states:

- **agreed** — both sources produced values and they match
- **disagreed** — both produced values and they differ
- **unresolved** — no Bloom record could be obtained for the scan, either because the video
  path yields no usable QR code or because Bloom holds no record of that code. The reason
  SHALL be recorded per row, so a malformed path is distinguishable from a scan Bloom has
  never seen.

The compared facts SHALL be the scan's age and its scan date. Species SHALL NOT be compared
per scan; it is a collection-level property with its own requirement.

A disagreement SHALL be recorded with both values. It SHALL NOT be resolved by preferring
one source, because the point of deriving twice is to surface the conflict.

An unresolved scan SHALL NOT be an error. Legacy scans may predate Bloom ingestion or have
been re-keyed, and a run that aborts on the first one cannot inventory the corpus that
motivated it.

Bloom lookups SHALL be batched so that no request's rendered filter exceeds the gateway's
URL length limit. A single collection can hold more scans than one filter can carry, so an
unbatched implementation succeeds on small collections and fails only on the largest — the
failure mode that survives testing.

A failure that indicates an expired session SHALL be retried once after re-authenticating,
rather than reported as a missing scan. Hashing a large corpus takes long enough to outlive
a session token, and a token expiry that presented as `unresolved` would silently
misreport the corpus as unverifiable.

#### Scenario: Matching sources yield an agreed row

- **WHEN** a scan's filename-derived age and Bloom's recorded plant age are equal, and the
  dates match
- **THEN** the row is classified agreed

#### Scenario: A disagreement is recorded rather than resolved

- **WHEN** a scan's filename-derived age and Bloom's recorded plant age differ
- **THEN** the row is classified disagreed and carries both values
- **AND** no single value is chosen for it

#### Scenario: A scan absent from Bloom is unresolved, not fatal

- **WHEN** a scan's QR code has no record in Bloom
- **THEN** the row is classified unresolved, recording that Bloom held no record
- **AND** the remaining scans in that collection are still processed

#### Scenario: An unusable QR code is unresolved with a distinct reason

- **WHEN** a video path yields no usable QR code
- **THEN** the row is classified unresolved, recording that the path was malformed
- **AND** no lookup is attempted for it

#### Scenario: Lookups are batched below the gateway's URL limit

- **WHEN** a collection holds more scans than one request's filter can carry
- **THEN** the lookups are split across requests, each within the limit
- **AND** every scan in the collection is resolved

#### Scenario: An expired session is retried once

- **WHEN** a lookup fails in a way that indicates an expired session
- **THEN** the capability re-authenticates and retries that lookup once
- **AND** a scan that resolves on the retry is not classified unresolved

### Requirement: Species Is Sourced From Bloom, Never From A Name

The species reported for a collection SHALL be taken from Bloom's per-scan records and
SHALL NEVER be inferred from the collection name, the containing folder name, or the labels
filename. Those names are what this capability exists to check.

A collection whose scans record more than one species SHALL be reported as mixed rather
than reduced to one value. Detecting that is a primary purpose of the capability, and
picking a majority would hide it.

Where the name and Bloom disagree, the disagreement SHALL be recorded alongside the
Bloom-sourced value.

The reported species MAY fall outside the repo's model-side species vocabulary — wheat,
sorghum, medicago and alfalfa all have published label data with no vocabulary entry. That
is expected output, not an error, and widening the vocabulary is not this capability's
concern.

#### Scenario: Species comes from Bloom when the name disagrees

- **WHEN** a collection's name and containing folder both indicate one species while Bloom
  records a different species for its scans
- **THEN** the reported species is Bloom's, and the disagreement is recorded

#### Scenario: A collection with two species is reported as mixed

- **WHEN** a collection's scans record more than one species in Bloom
- **THEN** the collection is reported as mixed, naming each species found
- **AND** no single species is chosen for it

#### Scenario: A species outside the model-side vocabulary is reported, not rejected

- **WHEN** Bloom records a species that the repo's model-side vocabulary does not contain
- **THEN** it is reported as that species without error

### Requirement: Aggregates Derive Only From Agreed Rows, Behind A Per-Collection Gate

A collection's aggregate values SHALL be computed only from rows classified agreed.
Disagreed and unresolved rows SHALL be carried into the per-scan output and counted in a
tally, and SHALL NOT contribute to any aggregate.

When a collection has any disagreed or unresolved row, the capability SHALL withhold that
collection's aggregate and SHALL surface those rows for adjudication. Withholding SHALL be
scoped to the collection: other collections SHALL still be inventoried and emitted. A
global halt would mean that one poorly-covered collection suppresses the whole corpus,
which is the outcome the per-collection isolation rule exists to prevent.

A collection with no exceptions SHALL emit its aggregate without a gate.

A collection with no scans surviving reconciliation SHALL be emitted as an entry recording
that, and SHALL NOT be emitted as a verified aggregate of zero. An all-zero aggregate
labelled verified is exactly the number that looks authoritative and is not.

#### Scenario: Non-agreed rows are excluded from aggregates

- **WHEN** a collection has agreed rows and disagreed rows
- **THEN** its aggregate counts are computed from the agreed rows only
- **AND** the disagreed rows appear in the per-scan output and in the tally

#### Scenario: Exceptions gate one collection, not the run

- **WHEN** a collection has at least one disagreed or unresolved row and other collections
  have none
- **THEN** that collection's aggregate is withheld and its exception rows are reported
- **AND** the other collections are inventoried and emitted unaffected

#### Scenario: A clean collection needs no gate

- **WHEN** every row in a collection is agreed
- **THEN** its aggregate is emitted without withholding

#### Scenario: A collection with no surviving scans is not a verified zero

- **WHEN** no scan in a collection survives reconciliation
- **THEN** the collection is emitted as an entry recording that it could not be verified
- **AND** it is not emitted as an aggregate of zero marked verified

### Requirement: Scans And Plants Are Counted As Distinct Quantities

The capability SHALL report the number of scans and the number of plants as separate
values, derived from distinct scan identity and distinct Bloom plant identity respectively.
They SHALL NOT be derived from a single count, and the plant count SHALL NOT be derived
from the filename-recorded code, which is a human-assigned proxy rather than plant identity.

A plant is imaged at more than one age, and on one day by more than one scanner. In one
observed collection, 170 videos carry 125 distinct filename codes — so deriving plant count
from video count overcounts, and the proxy itself is only an estimate of what Bloom's
`plant_id` states.

Because a plant is never imaged fewer than once, the scan count SHALL be greater than or
equal to the plant count. The capability SHALL assert this before emitting and SHALL fail
loudly if it is violated, as a guard against an internally inconsistent intermediate rather
than as an expected outcome of well-formed data.

#### Scenario: A plant imaged at two ages is one plant and two scans

- **WHEN** one Bloom plant identity appears in two scans at different ages
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: A plant imaged twice on one day is one plant and two scans

- **WHEN** one Bloom plant identity appears in two scans on the same day from different
  scanners
- **THEN** it contributes 1 to the plant count and 2 to the scan count

#### Scenario: The plant count is not the count of filename codes

- **WHEN** a collection's distinct filename codes and its distinct Bloom plant identities
  differ in number
- **THEN** the reported plant count is the count of Bloom plant identities

#### Scenario: An inconsistent count fails loudly

- **WHEN** a collection's computed scan count is lower than its computed plant count
- **THEN** the capability fails, naming the collection, and emits no aggregate for it

### Requirement: Provenance Is Read From The Originally Uploaded Version

A collection's provenance SHALL be read from the artifact version that carries the original
recorded source path, not from a later repair derived from it. A repair version re-embeds
images to restore trainability and in doing so drops the source metadata and records a
temporary working path; reading it yields a path that resolves nowhere and no species
information.

The value the capability reports for whether images are embedded SHALL describe the version
a consumer receives, not the version provenance was read from, because those are different
artifacts in a repaired collection.

#### Scenario: Provenance comes from the original version, not the repair

- **WHEN** a collection has an original version and a later repair version
- **THEN** the recorded source path and species metadata are taken from the original
- **AND** the reported images-embedded value describes the repair, which is what a consumer
  receives

#### Scenario: A single-version collection reads that version

- **WHEN** a collection has exactly one version
- **THEN** provenance and the images-embedded value are both read from it

### Requirement: Only Read Operations Are Issued

The capability SHALL issue only read operations against the registry and against Bloom.

For Bloom the prohibition SHALL be enforced by HTTP method: the client SHALL issue **only
`GET`** requests. Every write path — a table insert, an update, a delete, and every remote
procedure call, including the ingest procedure — requires a method other than `GET`, so a
`GET`-only client cannot perform one regardless of what authority its credentials carry.
This is enforceable and assertable, where "performs no write" is neither.

The credentials available in practice belong to a person and carry write authority. The
prohibition is therefore on the **effect**, not on a named function, and the capability
SHALL be built so that its external clients are supplied to it rather than constructed
inside it — making an unintended write visible in a test rather than only in production.

Loaded credentials SHALL be kept out of every representation, log line, exception message,
and emitted artifact. The emitted artifacts are committed to a public repository, so a
credential reaching a traceback is a published credential.

#### Scenario: The Bloom client issues only GET

- **WHEN** the capability runs to completion against a supplied Bloom client
- **THEN** every request it issued used the `GET` method
- **AND** a client that would issue any other method fails the run

#### Scenario: A run performs no registry write

- **WHEN** the capability runs to completion against a supplied registry client
- **THEN** only read operations are invoked on that client
- **AND** no artifact download is invoked

#### Scenario: Credentials do not reach output

- **WHEN** an exception carrying the loaded credentials is formatted
- **THEN** neither the secret values nor their containing object's contents appear in the
  output
- **AND** no emitted artifact contains them

### Requirement: Emitted Artifacts Are Redacted Before They Are Committed

Every path recorded in an emitted artifact SHALL have its internal host segment and user
segment redacted, using the same substitutions the repository already applies when
committing captured payloads. The artifacts are committed to a **public** repository, and
the recorded source paths contain an internal SMB hostname and a username.

Redaction SHALL be applied on every run, so a re-run remains identical, and SHALL preserve
the distinction between the recorded prefixes so a reader can still tell which of them a
path came from.

Fields that identify a person SHALL NOT be emitted at all.

#### Scenario: An internal host and user are redacted

- **WHEN** a recorded path contains the internal host segment or the user segment
- **THEN** the emitted artifact carries the redacted form
- **AND** the un-redacted value appears in no emitted artifact

#### Scenario: Redaction preserves prefix distinguishability

- **WHEN** two collections record their source under different prefixes
- **THEN** their redacted paths remain distinguishable by prefix

#### Scenario: Person-identifying fields are not emitted

- **WHEN** a Bloom record carries a field identifying a person
- **THEN** that field appears in no emitted artifact

### Requirement: Collections Are Discovered Structurally

Share collections SHALL be discovered by structure rather than from a maintained list: a
folder is inventoried when it holds a labels file at its top level. Folders holding no such
file SHALL be reported as skipped, with the reason.

A maintained list would encode only what is already remembered, which defeats the purpose
of an inventory. Derived training artifacts SHALL NOT be treated as collections — a
train/test split describes a training run, not a corpus, and counting one as a collection
would report a subset's frame count as the corpus's.

The root the capability walks SHALL be a supplied parameter rather than a fixed location, so
discovery can be exercised without the production share.

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

#### Scenario: Two collections resolving to one file are both reported

- **WHEN** two collections' recorded paths resolve to the same share file
- **THEN** both are reported, naming the shared path

#### Scenario: Discovery runs against a supplied root

- **WHEN** discovery is given a root other than the production share
- **THEN** it walks that root

### Requirement: The Skeleton Table Is Diffed, Never Used As A Source Of Values

The capability SHALL emit a diff between what the corpus demonstrates and what the
repo-owned skeleton table asserts, and SHALL NOT read that table to fill in a value. Each
collection SHALL be reported as **verifying** a row, **contradicting** a row, or having **no
row**.

The capability SHALL also report where the table's keying cannot express the corpus. Rows
are keyed on species, root type and age with no capture mode, while the corpus contains two
collections of the same species and root type with different node counts under different
modes — a missing key rather than a wrong value, which no per-row correction would fix.

The observed skeleton name SHALL be reported as the literal value the file carries, with no
substitution of a canonical name, because the literal is the evidence.

Nothing SHALL be written back to the table. Correcting it is a separate change.

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

#### Scenario: The literal skeleton name is reported

- **WHEN** a labels file carries an auto-generated skeleton name
- **THEN** that literal value is reported, with no canonical name substituted

### Requirement: A Missing Source Is Named, Not Worked Around

The capability SHALL treat the registry and the share as **jointly required** — neither
alone can satisfy digest verification. When either is unavailable it SHALL exit naming
which one is absent, and SHALL emit nothing.

Bloom absence SHALL be degradable: every row SHALL be classified unresolved, the per-scan
output SHALL be emitted, and no aggregate SHALL be. The run then reports that the corpus
could not be verified, which is the honest result of running without the system of record
for scan metadata.

#### Scenario: An absent registry is named and nothing is emitted

- **WHEN** the registry is unavailable
- **THEN** the capability exits naming the registry as the missing source
- **AND** no artifact is emitted

#### Scenario: An absent share is named and nothing is emitted

- **WHEN** the share is unavailable
- **THEN** the capability exits naming the share as the missing source
- **AND** no artifact is emitted

#### Scenario: An absent Bloom degrades to unresolved

- **WHEN** Bloom is unavailable
- **THEN** every row is classified unresolved and the per-scan output is emitted
- **AND** no aggregate is emitted

### Requirement: Every Emitted Artifact Is Written Atomically

An artifact SHALL be rendered in full and then moved into place, so an interrupted run
leaves the previous artifact intact rather than a truncated one, and leaves no partial file
beside it.

There SHALL be no resume. A re-run is a full re-run, which the determinism requirement makes
cheap to verify and which avoids inheriting partial state from a run that died halfway.

#### Scenario: An interrupted emission leaves the previous artifact intact

- **WHEN** a run is interrupted during emission
- **THEN** the previously emitted artifact is unchanged
- **AND** no partial file remains beside it

### Requirement: Output Is Deterministic And Re-Running Is Idempotent

Artifact content SHALL be a deterministic function of the inputs alone. The capability
SHALL NOT embed a run timestamp, hostname, run identifier, or any other value that varies
between runs over unchanged inputs, and SHALL emit collections, rows, and mapping keys in a
defined, input-derived order.

Running the capability twice against unchanged inputs SHALL produce identical artifacts.
Adding a collection SHALL add its entries without altering the entries of collections whose
inputs have not changed.

The corpus grows, so a one-time script would be stale on the day a further collection is
published. Determinism is what lets the artifacts be regenerated and diffed rather than
audited by hand.

#### Scenario: Unchanged inputs produce identical artifacts

- **WHEN** the capability is run twice with no input change
- **THEN** the emitted artifacts are byte-identical between runs

#### Scenario: No varying value is embedded

- **WHEN** an emitted artifact is inspected
- **THEN** it contains no run timestamp, hostname, or run identifier

#### Scenario: A new collection does not disturb existing entries

- **WHEN** a collection is added and the capability is re-run
- **THEN** the new collection's entries appear
- **AND** the per-collection artifacts of unchanged collections are byte-identical, and
  their entries in the aggregate artifact are unchanged

### Requirement: The Artifact Schemas And Their Vocabularies Are Documented And Locked

The repository SHALL document the emitted artifacts' schemas and the closed vocabularies
they use — the per-scan reconciliation status and the per-field confidence — and a test
SHALL lock the documented vocabularies against the values the emitter actually writes.

A committed artifact outlives the conversation that produced it. A reader encountering
`unresolved` must be able to learn that it means no Bloom record was obtained, not that the
scan is absent from the corpus, and that such rows are excluded from every aggregate — so a
per-scan row count and a reported scan count are expected to differ.

#### Scenario: The documented vocabularies match the emitter

- **WHEN** the documented status and confidence vocabularies are compared with the values
  the emitter writes
- **THEN** they are equal

#### Scenario: The documentation states what each status implies

- **WHEN** the documentation is read
- **THEN** it states for each status whether rows carrying it contribute to aggregates
