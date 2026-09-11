# label-inventory Specification

## Purpose

Records what the label corpus actually contains, by reconciling three sources — the label
registry, the SLEAP share, and Bloom's cylinder scan metadata — so that the corpus is
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
human typed the folder name, and Bloom records the species from experiment metadata. For
**age and scan date** they are not: the download tooling wrote the directory name *from*
those same columns, so agreement is a **staleness check** — did the record change after
download, through a re-key or a correction — rather than corroboration. Both checks are
worth running; only the first is evidence of correctness.

Two scope facts shape every requirement below. First, **the unit is the labels file, not
the folder**: directories on the share hold several distinct labeling efforts side by side,
including files of different species, so a rule that selected one file per folder would
discard most of the corpus. Second, **a person decides what counts as a collection and
adjudicates every conflict**: an input file, a finished collection and a scratch file cannot
be told apart by name or structure, and a conflict between two sources is a finding to
review rather than a value to pick.

Named artifacts this specification refers to, so that it stands alone once archived:

- **the skeleton table** — `src/sleap_roots_training/labeling/data/skeletons.yaml`, keyed
  `(species, root_type, age)` and advisory by its own header.
- **the contract library** — `sleap_roots_contracts`, which owns the species, capture-mode
  and root-type vocabularies and the `LabelCard` shape.
- **the scan-metadata client** — `bloomctl`, and through it Bloom's PostgREST **gateway**.
- **the redaction floor** — the substitutions in `scripts/pull_tf_reference.py`'s
  `_REDACTIONS`.
- **the documentation** — `docs/labeling-packages.md`.

This capability **reports**. It writes nothing to any external system and changes no
existing vocabulary or table. Every correction it implies is a separate change; that
separation is what makes it safe to run against production data.

## ADDED Requirements

### Requirement: The Command Emits Three Named Artifacts And One Decision Input

The capability SHALL expose an `inventory labels` command that, given a walk root, an output
directory, a decision file and a scan-metadata profile, emits three kinds of artifact into
the output directory and reads one decision file it never writes.

The kinds are: a **per-scan table** named `<collection-slug>.csv` for each promoted
collection, one row per scan, whose columns are grouped by the source each field is derived
from — so a run emits as many per-scan tables as it has promoted collections, and none on a
run that promotes nothing; one **aggregate** named `aggregate.yaml`; and one **skeleton
diff** named `skeleton-diff.md`.

The **collection slug** SHALL be derived from the promoted file's walk-root-relative path
such that two distinct promoted files cannot yield the same slug, and a slug collision SHALL
be a reported failure exiting `4`. Emission replaces an existing destination by requirement,
so a basename-derived slug would let one promoted collection silently overwrite another's
per-scan table and exit `0` — and the worked example's own file exists in three directories
at one version.

The aggregate SHALL carry one **aggregate entry** per enumerated labels file, and derived
files SHALL be reported as a count per directory rather than individually. An artifact
carrying an entry for each of eighteen thousand files could not be reviewed in a pull
request, which is the stated reason for committing it at all. There is no
fourth artifact: a file's classification, a collection's outcome, its skip reason, its
per-field confidence and its adjudication state are all recorded in its aggregate entry, and
"the report" elsewhere in this specification means the aggregate.

Withholding a **field** SHALL NOT withhold an **entry**. A collection whose
reconciliation-derived fields are withheld still emits its aggregate entry, its file-derived
fields, and the reason each withheld field is absent.

The option surface SHALL be `--walk-root` (required), `--out` (default `inventory/`),
`--decisions` (default `inventory/decisions.yaml`) and `--bloom-profile`. The registry
entity SHALL be read from `WANDB_ENTITY` rather than a flag, following the `seed-registry`
command. Every option SHALL be documented, and the documentation SHALL be locked against the
implemented surface.

Exit codes SHALL be distinct and documented: `0` on completion, `3` when a required source is
unavailable, and `4` when the run completed with one or more collection failures. Code `2` is
reserved for the CLI framework's usage errors.

#### Scenario: A run emits the three artifacts

- **WHEN** the command completes over a walk root holding two promoted collections
- **THEN** a per-scan table exists for each, one aggregate holds an entry for every
  enumerated labels file, and one skeleton diff is emitted

#### Scenario: A withheld field does not remove the entry

- **WHEN** a collection's reconciliation-derived fields are withheld
- **THEN** its aggregate entry is still present, carries its file-derived fields, and names
  each withheld field with the reason

#### Scenario: The decision file is never written

- **WHEN** the capability runs to completion
- **THEN** the decision file's bytes are unchanged

#### Scenario: A slug collision fails rather than overwrites

- **WHEN** two promoted files would yield the same collection slug
- **THEN** the run reports the collision naming both files and exits `4`

#### Scenario: Exit codes distinguish the failure kinds

- **WHEN** a required source is unavailable, and separately when the run completes with a
  failing collection
- **THEN** the first exits `3` and the second exits `4`, and both are documented

### Requirement: Every Labels File Is Enumerated And A Person Promotes It

The capability SHALL enumerate every labels file under the walk root and SHALL NOT decide by
itself which of them is a collection. Each enumerated file SHALL be classified, and the
classification that admits a file to full inventory SHALL come from the decision file.

A directory on this share commonly holds several distinct labeling efforts at once — a
finished superset, the per-day and per-labeler files that were merged into it, files of a
different species entirely, and scratch. Those tiers are not distinguishable by name or
structure, so a structural rule cannot separate them, and a rule that selected one file per
directory would drop whole species from the inventory. Enumeration is therefore structural
and complete, and promotion is a judgment recorded in a committed file.

Files SHALL be grouped into **version families** keyed on three things together: the
containing directory, the basename with the version suffix removed, and the extension. The
version suffix SHALL be the grammar `.v<digits>` immediately preceding the extension, and the
extension SHALL be `.slp` or `.pkg.slp`. Free text may precede or follow the version
component — both `…8nodes.uncropped.v008.slp` and `…labels.v003_updated_filenames.slp` occur
in this corpus, one of them in a family alongside three other shapes — and SHALL NOT be
treated as part of the version.

Each part of that key earns its place against this corpus. Keying on the basename alone
merges files across directories: `labels.vNNN.slp` occurs 57 times in 23 directories spanning
five species and both capture modes, so a basename-keyed family would name the highest
version found anywhere as the current file and refuse to read the other fifty-six. A `.slp`
and a `.pkg.slp` are different shapes — one references images, one embeds them — and are
never versions of one another; the corpus holds five same-version pairs of exactly that form,
and the embedded packages are the only collections whose skeleton rows are already
independently verified.

Within a family the highest version is the family's current file; earlier versions SHALL be
recorded as superseded, naming the file, and SHALL NOT be read or digest-verified. Two files
in one family carrying the same version SHALL be reported as a version collision and neither
SHALL be treated as the family's current file, because superseding a file suppresses it from
the inventory and no arbitrary choice may do that.

Where two or more enumerated files share a basename and a version in different directories,
each SHALL be reported as a distinct file naming the others, so a person promoting one knows
the alternatives exist. The registered wheat superset exists in three directories at one
version, so this is the ordinary case rather than an edge case.

A file carrying no version suffix SHALL be classified `unclassified`, never `scratch` by
structure alone. Classification from a filename is a structural rule, and a structural rule
may not take an irreversible read-or-not decision: the share's nine most recent plate labels
files are unversioned deliberate merges under a `combined_roots/` directory, and they are the
only trace of two experiments. `scratch` SHALL come only from the decision file.

Where a promoted file has since been superseded by a higher version, **promotion SHALL
win**: the file is classified `promoted` and read, and its aggregate entry SHALL additionally
name the higher version its promotion does not cover. A judgment recorded in a file the run
never writes stays in force until a person changes it, and naming the newer version makes a
stale promotion visible in the diff rather than silently authoritative.

Only a **promoted** file SHALL be read, digest-verified, reconciled against scan metadata, or
entered in the skeleton diff. Every other enumerated file SHALL still receive an aggregate
entry recording its classification, its path and its version family, so that nothing on the
share is silently absent from the inventory.

The decision file SHALL be a supplied input the capability reads and never writes, so that a
re-run cannot erase a judgment. A file absent from the decision file SHALL be classified
unclassified and reported as awaiting a decision, never promoted by default.

#### Scenario: An unclassified file is reported, not promoted

- **WHEN** an enumerated labels file appears in no entry of the decision file
- **THEN** it is classified unclassified, receives an aggregate entry, and is not read

#### Scenario: A promoted file is inventoried in full

- **WHEN** the decision file promotes a labels file
- **THEN** it is read, digest-verified where a registry artifact exists, and reconciled

#### Scenario: Earlier versions are superseded without being read

- **WHEN** a version family holds three versions
- **THEN** the highest is the family's current file and the other two are reported as
  superseded, naming each file, and neither is opened

#### Scenario: A file with no version suffix awaits a decision

- **WHEN** an enumerated labels file carries no version suffix
- **THEN** it is classified `unclassified` and reported as awaiting a decision, not `scratch`

#### Scenario: Families do not merge across directories

- **WHEN** two directories each hold a file of the same basename at different versions
- **THEN** each directory's highest version is its own family's current file and neither
  supersedes the other

#### Scenario: A packaged file is not a version of its plain sibling

- **WHEN** a directory holds `<name>.v003.slp` and `<name>.v003.pkg.slp`
- **THEN** they are separate families, both current, and neither is reported as superseding
  the other

#### Scenario: Free text around the version is not part of it

- **WHEN** a family holds `<name>.v003.slp`, `<name>.v003_updated_filenames.slp` and
  `<name>.v004.slp`
- **THEN** the version parsed for each is 3, 3 and 4, and the first two are reported as a
  version collision

#### Scenario: A version collision leaves no current file

- **WHEN** two files in one family carry the same version
- **THEN** the collision is reported and neither is treated as the family's current file

#### Scenario: Copies in different directories each name the others

- **WHEN** the same basename and version occurs in three directories
- **THEN** each is reported as a distinct file naming the other two

#### Scenario: A promoted file superseded since promotion is still read

- **WHEN** a promoted file has been superseded by a higher version in its directory
- **THEN** it is classified `promoted` and read, and its entry names the higher version

#### Scenario: Several promoted files in one directory are all inventoried

- **WHEN** one directory holds promoted files of three different species
- **THEN** all three are inventoried as separate collections

### Requirement: The Decision File Has A Stated Shape And Is Read, Never Written

The decision file SHALL be YAML with a documented and locked shape, and `--decisions` SHALL
accept either a file or a directory. Where a directory is supplied every `*.yaml` beneath it
SHALL be read and merged in path order, so that judgments about different collections can be
recorded in separate files. The repository squash-merges, and concurrent adjudication is the
expected workflow; a hand-resolved merge conflict in the record of why a collection was
promoted is the one place a silently dropped line does damage nothing downstream can detect.

It SHALL carry a `walk_root`, a `promotions` section and an `adjudications` section. A
promotion entry SHALL carry a `classification` drawn from the file-classification vocabulary
and a `rationale`. A verdict SHALL carry the scan key, the `field`, the `accept` value, the
pair of values observed when the verdict was made, and a `rationale`. The `rationale` and the
identity of the deciding person SHALL be recorded **as data rather than as comments**,
because this repository squash-merges and `git blame` therefore resolves every judgment to
the pull request that carried it rather than to the judgment. Neither SHALL be copied into an
emitted artifact, so determinism is unaffected.

A file SHALL be identified by its **path relative to the walk root, rendered with forward
slashes**. The alternatives fail on this share: a basename is ambiguous — 88 versioned
basenames occur in more than one directory, including the worked example's own file, which
exists three times — and an absolute path would publish the user segment that the redaction
rule exists to strip, into the same commit as artifacts that redact it, while also breaking
the one workflow a person has: reading an identifier out of the aggregate, whose paths are
redacted, and pasting it into the decision file. A walk-root-relative path carries no host or
user segment, so it needs no redaction and round-trips unchanged.

`walk_root` SHALL be compared against the supplied walk root and a mismatch SHALL exit `3`
naming both, so that a relocated share is a loud failure rather than a silent
mass-unclassification.

Every promotion and every verdict SHALL resolve — a promotion to an enumerated labels file, a
verdict to a disagreed scan of a promoted collection. An entry resolving to nothing SHALL be
reported as `decision_unmatched`, naming the entry verbatim, and the run SHALL exit `4`. A
mistyped path is the most likely first-use failure, and silently ignoring the entry would let
it read as a judgment that was made. An identifier appearing twice, in one file or across
merged files, SHALL likewise be a reported failure exiting `4` rather than a last-one-wins
merge, since duplicate-key handling is loader-defined and identical committed bytes would
otherwise produce different artifacts.

An absent decision file SHALL be treated as an empty one and reported as such, so a first run
enumerates and classifies with no bootstrap step. A decision file that exists and does not
parse SHALL exit `3` naming the parse error, never be treated as empty — an empty file
promotes nothing, so silently reading a corrupted one as empty would report the entire corpus
as awaiting a decision.

The aggregate SHALL record the digest of the decision content the run read. The committed
artifacts cannot be regenerated in continuous integration, because the share is not reachable
from a hosted runner, so the digest is what lets a reviewer tell from the diff alone whether
the artifacts were produced under the committed judgments.

#### Scenario: A directory of per-collection files is merged

- **WHEN** `--decisions` is given a directory holding one file per collection
- **THEN** every `*.yaml` beneath it is read and merged in path order

#### Scenario: An identifier in two files is a reported failure

- **WHEN** the same identifier appears in two merged files
- **THEN** the run reports both files and exits `4`, and neither entry silently wins

#### Scenario: A file is identified relative to the walk root

- **WHEN** a promotion names a file
- **THEN** the identifier is the path relative to the walk root with forward slashes, and it
  matches the identifier the aggregate reports for that file

#### Scenario: A relocated walk root is a loud failure

- **WHEN** the decision file's `walk_root` differs from the supplied walk root
- **THEN** the run exits `3` naming both, rather than classifying the corpus as unclassified

#### Scenario: A decision entry matching nothing is reported

- **WHEN** a promotion names a path no enumerated file matches
- **THEN** it is reported as `decision_unmatched`, naming the entry, and the run exits `4`

#### Scenario: An absent decision file is an empty one

- **WHEN** no decision file exists at the supplied path
- **THEN** it is treated as empty, reported as absent, and the run completes

#### Scenario: An unparseable decision file is not treated as empty

- **WHEN** the decision file exists and does not parse
- **THEN** the run exits `3` naming the parse error

#### Scenario: The run promotes nothing on a first pass

- **WHEN** the decision file promotes nothing
- **THEN** the aggregate holds an entry for every enumerated labels file, no per-scan table is
  emitted, the skeleton diff is emitted empty, and the run exits `0`

#### Scenario: The aggregate records which judgments it was built from

- **WHEN** the artifacts are emitted
- **THEN** the aggregate records the digest of the decision content the run read

### Requirement: Disagreements Are Surfaced For A Person To Adjudicate

The capability SHALL emit every disagreed scan into an adjudication queue in the aggregate,
and SHALL withhold only those fields derived from the facts in conflict until a verdict for
that scan appears in the decision file.

An unresolved scan and a disagreed scan are different events. An unresolved scan carries no
comparison — a legacy scan predating ingestion, a re-keyed plant, an unparseable path — and
SHALL never block a field; it simply does not contribute. A disagreed scan means the recorded
path and the scan metadata actively conflict, which is an anomaly a person should see before
a number resting on it is published.

Each disagreed scan SHALL record which field the conflict was in, so that the emitter
withholds the fields that field feeds and no others. A field withheld this way SHALL carry
the confidence `awaiting_adjudication` and the count of scans awaiting a verdict.

A verdict recorded in the decision file SHALL name the scan, the field and the value to
accept, and the capability SHALL then treat that scan as agreed for that field alone. The
decision file is an input to determinism: two runs over unchanged inputs **including
unchanged verdicts** produce identical artifacts.

#### Scenario: A disagreement withholds only what it touches

- **WHEN** two of a collection's scans disagree on age and none disagree on anything else
- **THEN** the age-derived fields carry `awaiting_adjudication` and the species and plant
  count are still emitted

#### Scenario: An unresolved scan blocks nothing

- **WHEN** ten of a collection's scans are unresolved and none are disagreed
- **THEN** no field is withheld on their account and they do not contribute

#### Scenario: Disagreed scans appear in the queue

- **WHEN** a collection holds disagreed scans
- **THEN** each appears in the adjudication queue naming the scan, the field, and both values

#### Scenario: An adjudicated scan stops withholding its field

- **WHEN** the decision file records a verdict for every disagreed scan of a collection
- **THEN** the previously withheld fields are emitted and carry the contributing scan count

### Requirement: Source Resolution Is Digest-Verified Where A Registry Artifact Exists

The capability SHALL resolve a promoted collection's recorded source path onto the local
share and SHALL verify the resolved file's digest against the digest the registry records
for that file **in the artifact's manifest entry** — the base64 MD5 of the file's bytes. It
SHALL NOT compare against the artifact-level digest, which is computed over the manifest
itself and is not comparable to a file hash; comparing it would fail on every collection,
and the plausible repair under time pressure is a size comparison, which this requirement
exists to forbid. Verification SHALL read manifest metadata only and SHALL NOT download the
artifact.

A manifest entry added as a reference to an external object store carries that store's ETag
rather than a file hash. Such an entry SHALL be reported as unverifiable, distinctly from
mismatching, because an ETag over a multipart upload is not an MD5 of the bytes and a
mismatch verdict would be an accusation against an intact file.

A promoted collection with **no registry counterpart** SHALL be inventoried and reported as
unregistered, with its facts read from the share file directly and every field so derived
marked `share_only`. The digest gate applies only where a registry artifact exists to
compare against. This is the majority of the corpus, not an edge case, and a capability that
excluded it would emit only the collections already known.

Both sources SHALL be required, for different reasons. Without the share there is no file to
read. The registry is required not because every collection is registered but because an
unreachable registry is indistinguishable from a collection that was never registered:
reporting an outage as `unregistered` would launder a transient failure into permanent
provenance. When either is unavailable the capability SHALL exit naming which one is absent
and SHALL emit nothing.

Recorded paths use several prefixes for one tree, and the mapping SHALL be this enumeration
rather than an implementer's choice:

| recorded prefix | resolves to |
| --- | --- |
| `D:/SLEAP/` | `<walk-root>/` |
| `//<smb-host>/hpi_dev/users/` | `<share>/users/` |
| `Z:/users/` | `<share>/users/` |
| `Z:users/` (drive-relative) | `<share>/users/` |

Each prefix SHALL be recognised in both its backslash and its forward-slash rendering,
because artifact metadata records the backslash form while the labels layer returns a
normalised forward-slash form. `<smb-host>` is the internal host segment the redaction floor
already covers. An unrecognized prefix SHALL be a reported failure rather than a silent
miss, and the mapping SHALL be evaluated under Windows path semantics on every platform so
that a run on one operating system resolves a recorded path as another would.

A collection's provenance SHALL be read from the artifact version carrying the original
recorded source path, not from a later repair derived from it: a repair re-embeds images to
restore trainability and in doing so drops the source metadata and records a temporary
working path. Where a collection has exactly one version, provenance and the images-embedded
value are both read from that version. The value reported for whether images are embedded
SHALL describe the version a consumer receives, which in a repaired collection is a
different artifact.

Two collections whose recorded paths resolve to the same file SHALL both be reported, naming
the shared path and marking the pair as sharing bytes so a consumer summing frames does not
double-count them; neither SHALL silently replace the other's row. Where the two versions'
metadata records different species for identical bytes, that SHALL be reported as a
contradiction rather than resolved.

A collection whose digest does not match, whose recorded path cannot be mapped, or whose
resolved path is not a readable file SHALL be reported and excluded. Being unreadable SHALL
be reported distinctly from mismatching, so an I/O failure is not recorded as an accusation
against a file that may be intact.

#### Scenario: A digest-matching file is read

- **WHEN** a promoted collection's recorded source path maps to a share file whose digest
  equals the digest in the registry artifact's manifest entry
- **THEN** the file is read and the collection proceeds

#### Scenario: Verification downloads nothing

- **WHEN** a collection is verified
- **THEN** no artifact download is performed, and only manifest metadata is fetched

#### Scenario: The artifact-level digest is never compared

- **WHEN** a collection is verified
- **THEN** the value compared is the manifest entry's per-file digest and the artifact-level
  digest is not read for comparison

#### Scenario: A same-size file with different content is excluded

- **WHEN** the resolved share file has the same byte size as the manifest entry records but
  a different digest
- **THEN** the collection is reported as failing verification, so the check is not a size
  comparison

#### Scenario: A reference entry's ETag is unverifiable, not mismatching

- **WHEN** a manifest entry carries an external store's ETag rather than a file hash
- **THEN** the collection is reported as unverifiable, distinctly from failing verification

#### Scenario: A share collection absent from the registry is inventoried

- **WHEN** a promoted collection has no matching registry entry
- **THEN** it is inventoried, reported as unregistered, and its derived fields are marked
  `share_only`

#### Scenario: Unregistered is distinct from failing verification

- **WHEN** one collection has no registry entry and another has one whose digest differs
- **THEN** the first is reported `unregistered` and the second `digest_mismatch`

#### Scenario: An unmappable recorded path is reported

- **WHEN** a collection's recorded source path begins with a prefix the enumeration does not
  contain
- **THEN** it is reported as unmappable and excluded, naming the path

#### Scenario: A recorded path resolving to a directory is refused

- **WHEN** a collection's recorded source path resolves to a directory rather than a file
- **THEN** it is reported `path_not_a_file` and is not opened

#### Scenario: An unreadable file is distinguished from a mismatch

- **WHEN** reading the resolved share file raises an I/O error
- **THEN** the collection is reported as unreadable, naming the error, and not as a digest
  mismatch

#### Scenario: Prefix mapping is platform-independent

- **WHEN** the same recorded path is mapped on a POSIX host and on a Windows host, in both
  renderings and including the drive-relative form
- **THEN** every case produces the same resolved share path

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
- **THEN** both are reported, naming the shared path and marking the pair as sharing bytes

#### Scenario: An absent registry or share is named and nothing is emitted

- **WHEN** either the registry or the share is unavailable
- **THEN** the capability exits `3` naming the missing source and emits no artifact

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
- **THEN** the run completes, emits output for the collections that succeeded, and exits `4`
- **AND** the failing collection appears in the aggregate under its own outcome

#### Scenario: A withheld field does not withhold the corpus

- **WHEN** one collection's fields are withheld pending adjudication
- **THEN** the other collections are inventoried and emitted unaffected

### Requirement: Recorded Video Paths Take Four Shapes, One Of Which Yields No Key

The capability SHALL recognise every shape a recorded video path takes in this corpus and
SHALL state per shape which facts it can yield. There are four, and treating them as one
would silently withhold whole collections.

A **referenced** video records a path whose directory carries the scan's age, date and
scanning device and whose filename carries the plant code. An **embedded** package records
the package's own path in the same field; the original scan path is held separately as the
embedded source, which may be a list and may have been deliberately cleared. A **generated**
package records a list of curated per-view filenames carrying the plant code and the age but
no date and no device; such a package ships a sample manifest beside its labels file, and the
scan identifier SHALL be read from that manifest rather than parsed from the filename. A
**plate** path records a plate identifier and a capture timestamp and carries **no plant
code, no age and no device**; a plate scan therefore yields no key and SHALL be reported
unresolved with the reason `no_identifying_code`, which is a property of the upstream schema
and not a defect in the file.

A shape yielding no date SHALL NOT thereby render its scans unresolved: the comparison SHALL
use the facts a shape can supply. Two of the corpus's collections are embedded packages and
are the only ones whose skeleton rows are already independently verified — losing them would
remove the diff's sole confirmed anchor — and generated packages are the shape every future
package takes.

The capability SHALL open labels files without resolving their video backends, because a
host without the share attached cannot resolve them and does not need to.

#### Scenario: A referenced path yields code, age, date and device

- **WHEN** a referenced video path is parsed
- **THEN** the plant code, age, date and device are available

#### Scenario: An embedded package reads the embedded source, not the package path

- **WHEN** an embedded package's video is parsed
- **THEN** the plant code is taken from the embedded source path, not from the package's own
  filename

#### Scenario: A cleared embedded source is unresolved with its own reason

- **WHEN** an embedded video's source has been cleared
- **THEN** its scans are unresolved with the reason `no_recoverable_path`, naming the cleared
  source

#### Scenario: A generated package takes its scan identifier from the manifest

- **WHEN** a generated package's video is parsed
- **THEN** the scan identifier is read from the sample manifest beside the labels file
- **AND** the absence of a date in the filename does not by itself make the scan unresolved

#### Scenario: A plate path yields no key and is unresolved

- **WHEN** a plate collection's video path is parsed
- **THEN** its scans are unresolved with the reason `no_identifying_code` and no lookup is
  attempted

#### Scenario: Labels files open without resolving video backends

- **WHEN** a labels file is opened on a host with no access to its video backends
- **THEN** it opens and its facts are read

### Requirement: Every Cylinder Scan Is Derived Twice And Reconciled

For each cylinder scan the capability SHALL derive facts independently from the recorded
video path and from Bloom's cylinder scan metadata, and SHALL classify the result as
`agreed`, `disagreed`, or `unresolved`. Scan metadata is read from the cylinder view only;
plate collections have no reconcilable scan metadata and are inventoried from the file alone.

The key SHALL be stated rather than assumed. The ten-character code in a recorded path is
the **plant's** code, not the scan's: one plant is scanned at several ages, and on one day by
more than one device, so a code alone selects many scan rows. A scan is therefore identified
by the plant code together with the age and the device, or — for a generated package — by the
scan identifier its manifest carries. The plant code alone SHALL NOT be used to select a
single scan row.

An unresolved row SHALL record exactly one reason from this closed set:
`no_identifying_code` (the path yields no usable plant code, including a plate path),
`no_recoverable_path` (an embedded source has been cleared), `no_bloom_record` (the key is
well formed but Bloom holds no row for it), `unparseable_date` (a recorded date cannot be
parsed unambiguously), and `nothing_comparable` (the shape supplies no fact the scan row also
carries, as in a labels file holding no video or no labeled frame).

A disagreement SHALL be recorded with both values and the field it occurred in, and SHALL NOT
be resolved by preferring one source. An unresolved scan SHALL NOT be an error; legacy scans
may predate ingestion or have been re-keyed.

The comparison SHALL normalise both sides before comparing, and the normalisation SHALL be
specified rather than left to the implementer: an age rendered in a directory name is the
same quantity Bloom records, but a date rendered in a directory name is ambiguous between
day-first and month-first and may carry a two-digit year. An unparseable date SHALL make a
row unresolved for that reason, never disagreed — a parse failure reported as a disagreement
would withhold a field on the strength of a formatting convention.

Lookups SHALL be batched so that no request's rendered, percent-encoded URL exceeds the
gateway's length limit, using the upstream client's batching helper and its measured
character budget. The quoting rule for string identifiers SHALL be specified and tested
**here**: the upstream client filters only on numeric identifiers and so provides no
precedent, and a plant code containing a character the filter grammar reserves would
otherwise corrupt the request silently.

#### Scenario: Matching sources yield an agreed row

- **WHEN** a scan's path-derived age and Bloom's recorded age are equal, and the dates match
- **THEN** the row is classified `agreed`

#### Scenario: A disagreement is recorded with its field

- **WHEN** a scan's path-derived age and Bloom's recorded age differ
- **THEN** the row is classified `disagreed`, carries both values, and names age as the field

#### Scenario: A scan absent from Bloom is unresolved, not fatal

- **WHEN** a scan's key has no record in Bloom
- **THEN** the row is classified unresolved with the reason `no_bloom_record`
- **AND** the remaining scans are still processed

#### Scenario: An unusable code is unresolved and no lookup is attempted

- **WHEN** a video path yields no usable plant code
- **THEN** the row is unresolved with the reason `no_identifying_code`, and no lookup is
  issued

#### Scenario: An unparseable date is unresolved, not disagreed

- **WHEN** a recorded date cannot be parsed unambiguously
- **THEN** the row is unresolved with the reason `unparseable_date`
- **AND** it is not classified `disagreed`

#### Scenario: A plant code alone does not select a scan

- **WHEN** one plant code has two Bloom rows at the same age from different devices
- **THEN** the device distinguishes them and neither row is chosen arbitrarily

#### Scenario: Lookups are batched below the gateway's limit

- **WHEN** a collection holds more scans than one request's filter can carry
- **THEN** the lookups are split across requests, each request's rendered URL is within the
  limit, and every scan resolves

#### Scenario: A reserved character in a code is quoted

- **WHEN** a plant code contains a character the filter grammar reserves
- **THEN** it is quoted so the request selects that code and no other

### Requirement: Species Is Sourced From Bloom, And A Mixed Collection Is A Defect

The species reported for a collection SHALL be taken from Bloom's records and SHALL NEVER be
emitted from the collection name, the containing folder name, or the labels filename. Those
names are what this capability exists to check. Comparison SHALL be on the species
identifier from Bloom's controlled species table, not on the free-text common name, and the
emitted evidence SHALL carry the identifier, the common name, the genus and the species.

Two distinct species identifiers sharing a genus and species SHALL be reported as the same
taxon carrying both identifiers, not as a mixed collection. The common name is user-writable
free text under a case-sensitive uniqueness constraint, so one taxon can acquire two names —
`medicago` and `alfalfa` both denote *Medicago sativa* — and a name-based comparison would
report a single-species collection as mixed.

Where a common name must be rendered for a consumer, it SHALL be normalised by the contract
library's species-normalisation rule, which strips surrounding whitespace and lowercases.
That rule SHALL be reached directly and not through the library's parameter-resolution entry
point, which fixes the capture mode to cylinder and raises when an age is absent — both
wrong for this capability.

A collection whose scans resolve to more than one species SHALL be reported as a **defect
blocking its card**, not as a species value, and the aggregate SHALL carry the
experiment-to-species mapping **with a scan count per species**, which is the evidence needed
to split it. The grounds are three: `LabelCard` carries one species and cannot express two;
the training backend accepts a list of labels files, so combining species inside one file is
unnecessary; and the corpus's own generalist experiments are already organised as per-species
directories. A defect verdict here concerns card eligibility, not file integrity — models
were demonstrably trained from several of these files.

Because species is an experiment-level property in Bloom, a mixed result means the collection
pools scans from more than one experiment. Mixed-species detection SHALL consider every scan
carrying a Bloom row, agreed or not, so that a thin join cannot hide a pooling.

The reported species MAY fall outside the repo's model-side species vocabulary. That is
expected output, not an error, and widening the vocabulary is not this capability's concern.

#### Scenario: Species comes from Bloom when the name disagrees

- **WHEN** a collection's name indicates one species while Bloom records another for its
  scans
- **THEN** the reported species is Bloom's, and the name-derived value is recorded separately
  as name-derived

#### Scenario: A mixed collection is a defect with its evidence

- **WHEN** a collection's scans resolve to more than one species
- **THEN** it is reported as a defect blocking its card, and no species value is chosen
- **AND** the experiment-to-species mapping is emitted with a scan count per species

#### Scenario: Mixed detection uses every scan with a Bloom row

- **WHEN** a collection's agreed scans are one species and an unresolved-heavy remainder
  carries a second
- **THEN** the collection is still reported as mixed

#### Scenario: Two identifiers for one taxon are not mixed

- **WHEN** two species identifiers share a genus and species
- **THEN** the collection reports one taxon carrying both identifiers and is not mixed

#### Scenario: A species outside the model-side vocabulary is reported, not rejected

- **WHEN** Bloom records a species the repo's model-side vocabulary does not contain
- **THEN** it is reported as that species without error

### Requirement: Scans And Plants Are Counted As Distinct Quantities

The capability SHALL report scan count and plant count as separate values, and SHALL state
which capture mode's record structure each count rests on. Scan count is the count of
distinct scans in the labels file and is file-derived, so it survives a scan-metadata
failure. Plant count is the count of distinct Bloom plant records and SHALL NOT be derived
from the code recorded in a filename, which identifies a plant but is human-assigned.

One scan is one video; the rotational views of a scan are frames within it, not separate
scans. A plant is imaged at more than one age, and on one day by more than one device, so
scan count exceeds plant count wherever a plant was imaged repeatedly.

The invariant that scan count is at least plant count SHALL be asserted **for cylinder
collections only**, and SHALL be justified on the cylinder record structure: the cylinder
scan view joins one plant per scan row, so the bound follows by counting and not from
biology. It does **not** hold for plate, where one capture carries many sections and each
section many plants, so plant count may exceed scan count legitimately. A plate collection
SHALL NOT have its aggregate withheld on that account.

The reported plant count SHALL be documented as a count of distinct Bloom plant records,
which is not a botanical plant count under a capture mode that places several plants in one
scan.

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

#### Scenario: Scan count survives a scan-metadata failure

- **WHEN** every scan in a collection is unresolved because Bloom was unavailable
- **THEN** the scan count is still emitted, marked `file_only`

#### Scenario: An inconsistent cylinder count withholds that collection's counts only

- **WHEN** a cylinder collection's computed scan count is lower than its computed plant count
- **THEN** the Bloom-derived counts are withheld and the inversion reported as
  `count_inconsistent`, while its file-derived fields are still emitted

#### Scenario: A plate collection with more plants than scans is not a defect

- **WHEN** a plate collection's plant count exceeds its scan count
- **THEN** no inconsistency is reported and no aggregate is withheld

### Requirement: Counts Distinguish Labels, Predictions And Confirmed Absences

The capability SHALL report frame and instance counts that distinguish user-made labels from
model predictions and from confirmed absences, and SHALL report each separately rather than
merging them.

A labeling package's starting version carries predicted instances as a labeler's starting
point, and packages deliberately ship frames with no instance at all where a root type is
absent — that frame is a *result*, a labeler's confirmation that the model found nothing, and
it is ground truth the corpus could not previously record. A single total therefore describes
the labeling *request* for any collection published before labeling finished, not the labeled
corpus.

Four counts SHALL be reported, each named for what it counts and for the property it is read
from: frames carrying at least one user instance, frames marked as a confirmed absence, their
sum, which is the frame set the training backend exports, and the counts of user instances
and predicted instances.

#### Scenario: User and predicted instances are counted separately

- **WHEN** a collection carries both user labels and model predictions
- **THEN** the user instance count and the predicted instance count are reported separately

#### Scenario: A confirmed absence is counted as its own quantity

- **WHEN** a collection carries frames with no instance that are marked as confirmed absences
- **THEN** they are excluded from the count of frames carrying a user instance and reported
  as confirmed absences
- **AND** their sum with that count is reported as the exported frame set

### Requirement: Confidence Is Per Field, And File Facts Do Not Depend On Bloom

The capability SHALL record confidence per field rather than per collection, and SHALL NOT
withhold a field whose derivation did not depend on the source that failed.

Facts read from the labels file — the skeleton's name, its node names and count, the scan
count, and the frame and instance counts — have no Bloom dependency. Withholding them because
one scan's filename was malformed would suppress exactly the evidence the skeleton table is
waiting on, and would make this capability's output weaker than the check it complements,
which needs no Bloom at all.

A reconciliation-derived field SHALL be computed from agreed scans only, and SHALL carry the
count of scans that contributed and the count excluded. A field SHALL be withheld in exactly
two cases: no scan agreed, or a disagreement in the field's inputs is awaiting adjudication.
An unresolved scan SHALL NOT withhold anything. Excluded scans SHALL be surfaced in the
per-scan table and, where disagreed, in the adjudication queue.

A collection with no scan agreed SHALL be emitted as an entry recording that, never as a
verified aggregate of zero.

#### Scenario: File facts survive a Bloom failure

- **WHEN** every scan in a collection is unresolved because Bloom was unavailable
- **THEN** the skeleton name, node count, node names, scan count and frame counts are still
  emitted, marked `file_only`
- **AND** the reconciliation-derived fields are withheld

#### Scenario: Reconciled fields use agreed scans only and state their coverage

- **WHEN** a collection has agreed scans and unresolved scans
- **THEN** the reconciliation-derived fields are computed from the agreed scans only and each
  carries the contributing and excluded counts

#### Scenario: Confidence is recorded per field

- **WHEN** a collection has a verified species and an underivable plant count
- **THEN** each field carries its own confidence rather than the collection carrying one

#### Scenario: A collection with no agreed scan is not a verified zero

- **WHEN** no scan in a collection is agreed
- **THEN** the collection is emitted as an entry recording that it could not be verified

### Requirement: The Age Window Is Emitted As An Observed Range With Its Provenance

The capability SHALL emit the age window as the **observed** range across a collection's
agreed scans, labelled as observed, and SHALL record both the upstream field the ages came
from and the epoch that field is measured in.

The epoch SHALL be emitted as a repo-owned constant per capture mode, carried at the
confidence `convention` and never `verified`, because no upstream record states it. For
cylinder the ages come from the scan view's age column, which Bloom's own interface labels
days after germination. For plate there is **no upstream age at all** — the plate schema
carries a capture date and a transplant date and nothing else time-like — so a plate
collection's ages are share-derived, from the collection name or a curated local age file,
marked `share_only`, and its window SHALL NOT be presented as reconciled. Days after
transplant is a third epoch and SHALL NOT be reported as either of the other two.

The contract library's `LabelCard` age window is inclusive and **contiguous**, and a
non-contiguous observed set is not expressible as one. A collection whose observed ages have
gaps SHALL be reported as `age_set_non_contiguous` so a consumer does not mint a card
asserting a range the data does not fill. The capability SHALL emit the set of ages actually
observed alongside the range, because a range alone asserts a contiguity it cannot establish.

The sibling contract's model-side age window denotes an approved selection window curated at
promotion, which may be wider than the data. An observed range emitted without that
distinction will later be read as an approved one.

#### Scenario: The window is labelled observed and carries its provenance

- **WHEN** a collection's age window is emitted
- **THEN** it is labelled as an observed range and records the upstream field and the epoch
  constant, with the epoch marked `convention`

#### Scenario: The observed age set accompanies the range

- **WHEN** a collection's scans span a range with gaps
- **THEN** the emitted evidence records the ages actually observed, not only the bounds
- **AND** the collection is reported `age_set_non_contiguous`

#### Scenario: A plate age window is share-derived, not reconciled

- **WHEN** a plate collection's age window is emitted
- **THEN** it is marked `share_only`, names its local source, and is not presented as
  reconciled

### Requirement: Only Read Operations Are Issued

The capability SHALL issue only read operations against the registry and against Bloom.

For Bloom the prohibition SHALL be enforced on the **data plane**: every HTTP request to the
data endpoint SHALL use the `GET` method. Every table write and every volatile remote
procedure requires another method, so a `GET`-only data plane cannot perform one regardless
of what authority its credentials carry. The session exchange that mints credentials is
exempt; it is a `POST`, it writes no application data, and without it no read is possible. A
read-only remote procedure may itself be served by `GET`, so the guarantee rests on the
gateway refusing `GET` for a volatile procedure, not on procedures being writes.

The capability SHALL NOT call the upstream client's ingest surface, and SHALL receive its
clients rather than constructing them, so an unintended write fails a test rather than
reaching production. The upstream client is a command-line application whose package
initialiser imports every command module, including ingest; an import-graph assertion is
therefore unavailable, because importing any read symbol also loads the ingest module. The
enforceable guarantee is a **source-level** assertion that no module of this capability names
an ingest symbol, layered on the data-plane method assertion, which catches an actual write
whatever is imported.

The symbols this capability imports from the upstream client SHALL be enumerated in one
adapter module and guarded by a test that fails loudly when one moves, because they are
internal to a pre-release command-line application and are not a published interface.

Loaded credentials SHALL be kept out of every representation, log line, exception message,
and emitted artifact. The artifacts are committed to a public repository, so a credential
reaching a traceback is a published credential.

#### Scenario: The data plane issues only GET

- **WHEN** the capability runs to completion against a supplied client
- **THEN** every request it issued to the data endpoint used `GET`
- **AND** a data-plane request using any other method fails the run

#### Scenario: The session exchange is exempt

- **WHEN** the client mints a session
- **THEN** that request may use `POST` and does not fail the run

#### Scenario: No module names an ingest symbol

- **WHEN** the source of every module of this capability is inspected
- **THEN** none of them names an ingest symbol

#### Scenario: A moved upstream symbol fails loudly

- **WHEN** an enumerated upstream symbol is absent from the installed client
- **THEN** the guard fails naming the symbol

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
host segment of a network path, with the redaction floor's substitutions kept as a
compatibility floor. The marker set SHALL include the share's user-directory marker and the
temporary-directory shape a repair version's recorded path takes.

The rule governs **emitted artifacts**, which carry hundreds of recorded paths. Prose
documentation naming the share root or host once is existing repository practice and is out
of scope; the prefix enumeration above records prefix *shapes* with the host segment given in
its redacted form for the same reason.

Fields identifying a person SHALL NOT be emitted. Fields describing plants and experiments —
genotype, accession and experiment name — are emitted by decision.

#### Scenario: An internal host and user are redacted

- **WHEN** a recorded path contains the internal host segment or the user segment
- **THEN** the emitted artifact carries the redacted form, and the un-redacted value appears
  in no emitted artifact

#### Scenario: A user segment the rule has never seen is still redacted

- **WHEN** a recorded path's user segment appears in no enumerated substitution
- **THEN** it is redacted

#### Scenario: A temporary-directory path from a repair is redacted

- **WHEN** a repair version's recorded path names a temporary directory carrying a user
  segment
- **THEN** that segment is redacted

#### Scenario: A person-identifying field is not emitted

- **WHEN** the scan metadata contains a field identifying a person
- **THEN** that field appears in no emitted artifact

#### Scenario: Approved plant and experiment fields are emitted

- **WHEN** the scan metadata carries genotype, accession and experiment name
- **THEN** each appears in the emitted artifact

### Requirement: The Walk Is Structural And Bounded

Labels files SHALL be discovered by walking the supplied root rather than from a maintained
list, and every directory beneath that root SHALL be walked. A maintained list would encode
only what is already remembered, which defeats an inventory.

Derived training and inference artifacts SHALL NOT be enumerated as labels files, and the
exclusion SHALL be stated by **shape rather than by containing directory**: a file whose name
marks it as a split, a ground-truth or prediction export, or an inference output is derived
wherever it sits. A split describes a training run, not a corpus, and counting one would
report a subset's frame count as the corpus's.

The directory-shaped reading is not sufficient against this share. The walk root holds
**18,099** labels files, of which **13,164** are inference outputs named `*.predictions.slp`,
and thousands of those sit outside any `train_test_split`, `models` or `predictions`
directory. Excluding by shape leaves roughly 1,450 files, of which about **470** carry a
version suffix and are the real promotion candidates — a task a person can work through,
which the unfiltered enumeration is not.

A directory holding no labels file SHALL be reported as skipped, with the reason.

The root walked SHALL be a supplied parameter. In production it is the project owner's
directory; other users' directories are out of scope and SHALL NOT be walked, and discovery
SHALL NOT ascend above the supplied root.

A labels file whose skeleton or content is unrelated to root phenotyping — a different
imaging subject entirely — SHALL be reportable as out of scope through the decision file
rather than admitted silently, because the structural filter cannot exclude it.

#### Scenario: Labels files are found at any depth

- **WHEN** a directory beneath the root holds labels files while the root itself holds none
- **THEN** those files are enumerated

#### Scenario: A directory with no labels file is skipped and reported

- **WHEN** a directory holds no labels file
- **THEN** nothing is enumerated from it and it appears in the aggregate as skipped with a
  reason

#### Scenario: A split is not a labels file

- **WHEN** a directory contains a promoted labels file and derived split files beneath it
- **THEN** only the labels file is enumerated, and the reported frame count is its own

#### Scenario: An inference output is derived wherever it sits

- **WHEN** a file named `*.predictions.slp` sits in a directory named none of
  `train_test_split`, `models` or `predictions`
- **THEN** it is excluded as derived, on its name rather than on its location

#### Scenario: Derived files are counted, not enumerated individually

- **WHEN** a directory holds four thousand derived files
- **THEN** the aggregate records a count for that directory and no entry per file

#### Scenario: Discovery runs against a supplied root and does not ascend

- **WHEN** discovery is given a root other than the production share
- **THEN** it walks that root and does not ascend above it

#### Scenario: An out-of-scope subject is excluded by decision, not by guess

- **WHEN** the decision file marks an enumerated labels file as out of scope
- **THEN** it is reported as such and not inventoried

### Requirement: The Skeleton Table Is Diffed, Never Used As A Source Of Values

The capability SHALL emit a diff between what the corpus demonstrates and what the skeleton
table asserts, and SHALL NOT read that table to fill in a value. Each promoted collection
SHALL be reported as verifying a row, contradicting a row, having no row, exposing a keying
gap, or naming a root type the contract vocabulary does not contain.

Selecting a row needs the table's three keys, and none of them is available from scan
metadata. Species, root type, capture mode and age SHALL therefore be derived from the
collection's name and the file's observed ages, used **only** to select the row to compare
against, and SHALL NOT be emitted as evidence. A name-derived value is adequate to choose
what to compare and inadequate to record as provenance, and the distinction SHALL be visible
in the output. Because selection needs no Bloom, the diff SHALL be emitted even when scan
metadata is unavailable.

The name-to-root-type mapping SHALL be stated: `seminal`, `sr` and `seminal_root` select the
`crown` row, because the team's seminal roots are the contract's crown root type and the
contract vocabulary has no `seminal` member. A name yielding a root type outside the contract
vocabulary — `tertiary` and `adventitious` occur in the corpus — SHALL be reported as
out-of-vocabulary rather than as a missing row, because the two need different fixes.

The table's rows are keyed without capture mode while the corpus contains collections of one
species and root type whose node counts differ by mode — a missing key rather than a wrong
value, which no per-row correction fixes. Whether node counts also vary by age is a
hypothesis this diff tests rather than an established fact, and an age-dependent node count
SHALL likewise be reportable as a keying gap.

The observed skeleton name SHALL be reported as the literal value the file carries, with no
normalisation. A file carrying more than one skeleton SHALL be reported as such rather than
reduced to one, and a file carrying none SHALL be reported distinctly, because both raise
identically in the labels layer and conflating them would hide an empty file.

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

#### Scenario: An age-dependent node count is reported as a keying gap

- **WHEN** two collections share species, root type and mode, differ in age, and have
  different node counts
- **THEN** the diff reports a keying gap on the age key

#### Scenario: A seminal-named collection selects the crown row

- **WHEN** a collection's name carries `seminal` or `sr`
- **THEN** the crown row is selected for comparison

#### Scenario: An out-of-vocabulary root type is reported as such

- **WHEN** a collection's name yields a root type the contract vocabulary does not contain
- **THEN** it is reported as out-of-vocabulary rather than as a missing row

#### Scenario: Name-derived selectors are not emitted as evidence

- **WHEN** species, root type, capture mode or age is derived from a collection's name to
  select a row
- **THEN** that value is used for selection and does not appear as emitted evidence

#### Scenario: The diff is emitted without scan metadata

- **WHEN** Bloom is unavailable
- **THEN** the diff is still emitted, using name-derived selectors and file-derived node
  counts

#### Scenario: A multi-skeleton file is reported, not reduced

- **WHEN** a labels file carries more than one skeleton
- **THEN** the collection is reported as carrying multiple skeletons

#### Scenario: A file with no skeleton is reported distinctly

- **WHEN** a labels file carries no skeleton
- **THEN** the collection is reported as carrying none, distinctly from carrying several

### Requirement: Artifacts Are Emitted Atomically And Deterministically

Artifact content SHALL be a deterministic function of the inputs alone, the decision file
among them. The capability SHALL NOT embed a run timestamp, hostname, run identifier, or any
value varying between runs over unchanged inputs.

Rendering SHALL be pinned rather than left to the host. Collections SHALL be emitted ordered
by collection slug, scan rows by plant code then age then device then source path, and
mapping keys in the documented field order. Every artifact SHALL use `LF` line endings, a
fixed rendering of numbers and absent values, and **every emitted path rendered with forward
slashes whatever the host** — the artifacts are largely paths, and the platform's native
rendering would otherwise differ between operating systems. Because the artifacts are
committed, the repository SHALL also pin their line endings so that a checkout cannot
reintroduce the difference.

An artifact SHALL be rendered in full and then moved into place with an operation that
replaces an existing destination, so a run failing during emission leaves the previous
artifact intact. Replacement over an existing destination is the normal case, not the
exception, because the artifacts are committed and re-emitted. A failure the capability
observes SHALL remove its staging file; a staging file orphaned by a process killed outright
SHALL be overwritten by the next run rather than treated as state.

Running twice against unchanged inputs SHALL produce identical artifacts, and adding a
collection SHALL add its entries without altering those of collections whose inputs have not
changed. There SHALL be no resume; a re-run is a full re-run, which is why no judgment may
live in a file the run writes.

The output directory's contents SHALL be reconciled to the promoted set: a per-scan table
present from a previous emission whose collection is no longer promoted SHALL be removed, and
the decision content SHALL be exempt from that reconciliation because it is an input. Without
this a de-promoted collection leaves a stale table behind, and "regenerate and diff" — the
whole reason the output path is pinned — shows a clean diff over data the run no longer
produces.

#### Scenario: Unchanged inputs produce identical artifacts

- **WHEN** the capability is run twice with no input change
- **THEN** the emitted artifacts are byte-identical between runs

#### Scenario: Output is identical across operating systems

- **WHEN** the capability is run on different operating systems over the same inputs
- **THEN** the emitted artifacts are byte-identical, and every emitted path uses forward
  slashes

#### Scenario: No varying value is embedded

- **WHEN** an emitted artifact is inspected
- **THEN** it contains no run timestamp, hostname, or run identifier

#### Scenario: A new collection does not disturb existing entries

- **WHEN** a collection is promoted and the capability is re-run
- **THEN** the new entries appear, and unchanged collections' artifacts are byte-identical
  and their aggregate entries unchanged

#### Scenario: Emission replaces an existing artifact

- **WHEN** an artifact is emitted over a non-empty destination
- **THEN** the destination is replaced and the run succeeds

#### Scenario: A failure during emission leaves the previous artifact intact

- **WHEN** emission raises partway through
- **THEN** the previous artifact is unchanged and the staging file is removed

#### Scenario: A de-promoted collection's table is removed

- **WHEN** a collection promoted in a previous run is no longer promoted
- **THEN** its per-scan table is removed from the output directory and the decision content
  is left untouched

### Requirement: The Emitted Schema And Its Vocabularies Are Documented And Locked

The documentation SHALL carry the emitted schema of all three artifacts and **every** closed
vocabulary this capability uses, and a test SHALL lock each documented vocabulary against the
values the emitter writes, by set equality in both directions.

Five vocabularies are closed and all five are load-bearing. A reader who cannot distinguish
an unregistered collection from an excluded one cannot tell an unverifiable collection from a
suspect one:

- **per-scan reconciliation status** — `agreed`, `disagreed`, `unresolved`.
- **unresolved reason** — `no_identifying_code`, `no_recoverable_path`, `no_bloom_record`,
  `unparseable_date`, `nothing_comparable`.
- **per-field confidence** — `verified`, `share_only`, `file_only`, `convention`,
  `awaiting_adjudication`, `withheld`.
- **file classification** — `promoted`, `superseded_version`, `unclassified`, `scratch`,
  `out_of_scope`.
- **collection outcome**, which is two fields because the values are not mutually exclusive:
  an exclusive **resolution** outcome — `inventoried`, `unregistered`, `digest_mismatch`,
  `unverifiable_reference`, `path_unmappable`, `path_not_a_file`, `unreadable`,
  `not_promoted`, `skipped_no_labels_file`, `decision_unmatched` — and a non-exclusive
  **defect** set —
  `mixed_species`, `count_inconsistent`, `multiple_skeletons`, `no_skeleton`,
  `no_agreed_scan`, `duplicate_resolved_path`, `age_set_non_contiguous`,
  `root_type_out_of_vocabulary`.

No requirement SHALL introduce an outcome, reason, confidence or classification value outside
these sets.

The vocabularies SHALL be defined as constants in a module importable without the registry or
scan-metadata client libraries, so the locking test stays cheap and a consumer can read the
vocabulary without installing either.

The documentation SHALL state, for each reconciliation status, whether scans carrying it
contribute to reconciliation-derived fields — so a reader comparing a per-scan row count
against a reported scan count understands why they differ — and a test SHALL lock that
statement against the emitter's behaviour.

The documentation SHALL state that `inventory/` is the pinned output path, because
regenerating and diffing only works if everyone regenerates to the same place.

#### Scenario: Every documented vocabulary matches the emitter

- **WHEN** each of the five documented vocabularies is compared with the values the emitter
  writes
- **THEN** each is equal to its counterpart in both directions

#### Scenario: The vocabularies import without client libraries

- **WHEN** the module defining the vocabularies is imported with the registry and
  scan-metadata client libraries absent
- **THEN** it imports successfully

#### Scenario: The documentation states what each status implies

- **WHEN** the documentation is read
- **THEN** it states for each reconciliation status whether scans carrying it contribute to
  reconciliation-derived fields
- **AND** a test asserts that statement against the emitter

#### Scenario: The pinned output path is documented

- **WHEN** the documentation is read
- **THEN** it names `inventory/` as the pinned output path
