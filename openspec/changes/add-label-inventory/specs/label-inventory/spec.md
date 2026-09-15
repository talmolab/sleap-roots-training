## ADDED Requirements

### Requirement: Candidate Enumeration
The command SHALL walk a supplied root directory, enumerate every `.slp` file beneath it, and exclude derived files by filename shape as well as by derived-directory location.

The filename rule is the operative one. Measured over one share root, `*.predictions.slp`
inference output accounts for 13,164 of 18,099 `.slp` files, and thousands of derived files
sit outside every `models/`, `predictions/` and `train_test_split*/` directory — so a
directory-only rule admits them. An unversioned filename SHALL NOT be treated as derived:
the newest labeling on the measured share is unversioned.

#### Scenario: A prediction file outside every derived directory is excluded
- **WHEN** enumeration reaches a `*.predictions.slp` file whose path has no `models/`, `predictions/` or `train_test_split*/` segment
- **THEN** the file is excluded
- **AND** the report attributes the exclusion to its filename shape

#### Scenario: A file under a derived directory is excluded
- **WHEN** enumeration reaches a `.slp` file beneath `models/`, `predictions/` or `train_test_split*/`
- **THEN** the file is excluded

#### Scenario: An unversioned labels file is a candidate
- **WHEN** enumeration reaches a labels file carrying neither a `.vNNN` suffix nor a derived shape
- **THEN** the file is enumerated as a candidate

#### Scenario: Exclusion counts are reported
- **WHEN** the walk completes
- **THEN** the report states how many files were seen and how many each exclusion rule removed

### Requirement: Version Family Grouping
The command SHALL group candidates into version families keyed on the containing directory, the basename with its version suffix removed, and the extension.

Four suffix shapes occur: `.vNNN.slp`, `.vNNN.pkg.slp`, `.vNNN_<text>.slp` and
`.<text>.vNNN.slp`. Keying on the basename alone is wrong — `labels.vNNN.slp` occurs 57
times across 23 directories spanning five species and both capture modes, and 88 versioned
basenames collide across directories, so basename keying would let one file supersede
unrelated ones.

#### Scenario: Identical basenames in different directories stay separate
- **WHEN** two directories each hold a file named `labels.v001.slp`
- **THEN** they form two families
- **AND** neither version supersedes the other

#### Scenario: A packaged twin is cross-referenced, not merged
- **WHEN** one directory holds `labels.v003.slp` and `labels.v003.pkg.slp`
- **THEN** the extension keeps them in separate families
- **AND** the report cross-references them as one labeling effort in two representations

#### Scenario: One basename in three directories yields three families
- **WHEN** the same versioned basename is found in three directories at the same version and byte size
- **THEN** three families are reported
- **AND** none is presented as the canonical one

### Requirement: Per-File Labeling Facts
The command SHALL read each candidate and record its skeleton names, node names, node count, frame count, and separate counts of user-labeled and predicted instances.

`sleap_io` 0.7.1 exposes no `Labels`-level `user_instances` or `predicted_instances`, so
both counts are summed over `LabeledFrame`. `Labels.skeleton` raises on zero skeletons as
well as on more than one, with different messages. `is_negative` is set nowhere in the
corpus, and `labeling/build_package.py` does not set it when it writes deliberately-empty
frames.

#### Scenario: Facts are recorded per file
- **WHEN** a candidate is read
- **THEN** its skeleton names, node names, node count, frame count, user-instance count and predicted-instance count are recorded

#### Scenario: Zero and multiple skeletons are distinguished
- **WHEN** a file carries no skeleton, or more than one
- **THEN** the two cases are reported distinctly rather than as one failure

#### Scenario: Confirmed absences are unreadable, not zero
- **WHEN** the report covers confirmed absences
- **THEN** the count is recorded as unreadable
- **AND** it is not recorded as zero

#### Scenario: An unreadable file does not abort the scan
- **WHEN** one candidate cannot be read
- **THEN** the failure is recorded against that family
- **AND** the remaining candidates are still read

### Requirement: Registry Digest Verification
The command SHALL compare each candidate against the per-file digest on the matching `ArtifactManifestEntry`, and SHALL report a candidate with no registry artifact as unregistered rather than as a failure.

`ArtifactManifestEntry.digest` is a base64 MD5 over the whole file for uploads and
`file://` references, at any size. `Artifact.digest` is computed over the manifest and
SHALL NOT be used. `Artifact.manifest` fetches metadata over GraphQL without downloading.
Unregistered files outnumber registered ones.

#### Scenario: A digest match is reported as verified
- **WHEN** a candidate's base64 MD5 equals its manifest entry's digest
- **THEN** the family is reported as digest-verified against that artifact and version

#### Scenario: A digest mismatch is reported as a mismatch
- **WHEN** the two digests differ
- **THEN** the family is reported as mismatching, naming both digests

#### Scenario: An unregistered file is not a failure
- **WHEN** no registry artifact references a candidate
- **THEN** the family is reported as unregistered
- **AND** the scan's exit status is unaffected

#### Scenario: A reference-store entry is unverifiable
- **WHEN** a manifest entry was added by `add_reference` against S3, GCS, Azure or HTTP and carries that store's ETag
- **THEN** the family is reported as unverifiable
- **AND** it is not reported as mismatching

### Requirement: Skeleton Table Keying Gap
The command SHALL report where `skeletons.yaml` cannot express the corpus, covering rows that two capture modes both select, species with no row at all, and skeleton names the existing check cannot parse.

`lookup_skeleton` (`src/sleap_roots_training/labeling/skeletons.py:327`) takes `species`,
`root_type` and `age`, and no `mode`. Node counts are read from the files and the mode is
derived from the collection name, so this report needs no scan metadata and no external
service.

#### Scenario: Two capture modes select one row
- **WHEN** a 6-node cylinder arabidopsis primary family and an 8-node plate arabidopsis primary family are both present
- **THEN** the report records that both select the single `(arabidopsis, primary, age: null)` row
- **AND** names the differing node counts as the evidence

#### Scenario: A species with no row is reported
- **WHEN** a family's derived species has no `skeletons.yaml` row
- **THEN** the report lists that species as uncovered

#### Scenario: An auto-generated skeleton name is unparseable
- **WHEN** a file's skeleton is named in the auto-generated `Skeleton-N` form
- **THEN** the report records that the existing `skeleton.name.partition("_")` check (`tests/test_labeling_skeletons.py:419`) cannot resolve it

#### Scenario: The gap report needs no external service
- **WHEN** the gap report is produced
- **THEN** every value in it is derived from the labels files, their paths, and `skeletons.yaml`

### Requirement: Path Redaction
The command SHALL redact person-identifying segments from every emitted path, using a case-insensitive marker set and a first-segment rule for drive-rooted and UNC paths.

Two recorded video paths defeat a marker-only rule: one carries a `Users/` marker that is
not the share's, and one carries no marker at all — the name is the first segment after the
drive letter. Both are colleagues' names and both appear in every emitted row for their
family. `scripts/pull_tf_reference.py`'s `_REDACTIONS` is the existing floor. `genotype`,
`accession_id` and `experiment_name` are not person-identifying and are not redacted.

#### Scenario: A marked user segment is redacted case-insensitively
- **WHEN** an emitted path contains a `users/`, `Users/` or `home/` segment in any casing
- **THEN** the following segment is replaced with a placeholder

#### Scenario: A drive-rooted first segment is redacted
- **WHEN** an emitted path is drive-rooted and its first segment after the drive is not a marker
- **THEN** that first segment is replaced with a placeholder

#### Scenario: A UNC first segment is redacted
- **WHEN** an emitted path is UNC-rooted
- **THEN** its first segment is replaced with a placeholder

#### Scenario: The two known real paths are covered
- **WHEN** the two recorded video paths described above are emitted
- **THEN** neither emitted path retains the colleague's name

### Requirement: Deterministic Artifacts
The command SHALL emit one per-family table and one report in a deterministic order, written under `inventory/` so successive runs diff.

The guarantee is a stable sort within a run, ordered by redacted path. Byte identity across
operating systems is out of scope.

#### Scenario: Two runs over an unchanged tree agree
- **WHEN** the command runs twice over one unchanged tree
- **THEN** both runs emit identical artifacts

#### Scenario: Rows are ordered by redacted path
- **WHEN** the table is emitted
- **THEN** its rows are sorted by redacted path

#### Scenario: Artifacts are written under inventory/
- **WHEN** the command completes
- **THEN** the table and the report are written under `inventory/`

### Requirement: No Decision Capture
The command SHALL print what it cannot determine and stop, and SHALL NOT read or write any file recording a human determination.

A directory is not a collection: one measured directory holds 28 labels files spanning a
sorghum superset, a soybean collection, a generalist, per-labeler inputs and practice
files. Where the tool cannot resolve candidates into collections it lists them and makes no
determination. It has no promotion, decision, adjudication or verdict concept, and no
per-run human-override state. eberrigan, 2026-09-15: *"i don't mind being a human in the
loop for this to avoid unnecessary complications."*

#### Scenario: An unresolvable group is listed, not resolved
- **WHEN** one directory holds families the tool cannot resolve into collections
- **THEN** the report lists them as candidates
- **AND** asserts no collection membership for them

#### Scenario: No record of a human determination is consulted
- **WHEN** the command runs
- **THEN** it reads no file recording a human determination
- **AND** writes none

#### Scenario: A name-derived species is labelled as name-derived
- **WHEN** a family's species is inferred from its path or filename
- **THEN** the report labels the value name-derived
- **AND** states that it is not evidence
