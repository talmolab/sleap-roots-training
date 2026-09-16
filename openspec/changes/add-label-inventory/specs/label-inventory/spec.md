## ADDED Requirements

### Requirement: Candidate Enumeration
The command SHALL walk a supplied root directory, enumerate every `.slp` file beneath it, and exclude derived files by filename shape as well as by derived-directory location.

The filename rule is the operative one. Measured over one share root, `*.predictions.slp`
inference output accounts for 13,164 of 18,099 `.slp` files, and thousands of derived files
sit outside every `models/`, `predictions/` and `train_test_split*/` directory — so a
directory-only rule admits them. An unversioned filename SHALL NOT be treated as derived:
the newest labeling on the measured share is unversioned. The walk SHALL NOT follow symlinks,
and an unreadable directory SHALL be counted and reported — a silent undercount would
falsify the tool's own evidence of its coverage.

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

#### Scenario: Files seen, files excluded and unreadable directories all reconcile
- **WHEN** the walk completes
- **THEN** the report states how many files were seen, how many each exclusion rule removed, and how many directories could not be read
- **AND** the per-rule counts and the candidate count sum to the files seen

### Requirement: Version Family Grouping
The command SHALL group candidates into version families keyed on the containing directory, the basename with only its `.vNNN` token removed and all other text retained, and the full suffix chain.

Four suffix shapes occur: `.vNNN.slp`, `.vNNN.pkg.slp`, `.vNNN_<text>.slp` and
`.<text>.vNNN.slp`. Keying on the basename alone is wrong — `labels.vNNN.slp` occurs 57
times across 23 directories spanning five species and both capture modes, and 88 versioned
basenames collide across directories. Retaining the non-version text keeps two labelers'
files apart rather than letting one supersede the other, and the full suffix chain keeps
`.slp` distinct from `.pkg.slp`.

#### Scenario: Identical basenames in different directories stay separate
- **WHEN** two directories each hold a file named `labels.v001.slp`
- **THEN** they form two families
- **AND** neither version supersedes the other

#### Scenario: Trailing text after the version keeps families apart
- **WHEN** one directory holds `labels.v001_ana.slp` and `labels.v001_ben.slp`
- **THEN** they form two families
- **AND** neither is presented as the canonical one

#### Scenario: A packaged twin is cross-referenced, not merged
- **WHEN** one directory holds `labels.v003.slp` and `labels.v003.pkg.slp`
- **THEN** the suffix chain keeps them in separate families
- **AND** the report cross-references them as one labeling effort in two representations

### Requirement: Per-File Labeling Facts
The command SHALL read each candidate and record its skeleton names, node names, node count, frame count, separate counts of user-labeled and predicted instances, and the filenames of the videos it references.

`sleap_io` 0.7.1 spells the counts `Labels.n_user_instances` and `Labels.n_pred_instances`,
not `user_instances`/`predicted_instances`. `Labels.skeleton` raises on zero skeletons as
well as on more than one — both `ValueError`, so the two cases separate on
`len(Labels.skeletons)`, not on exception type. No confirmed-absence count is required:
`is_negative` is set nowhere in this corpus and `labeling/build_package.py` does not set it
for deliberately-empty frames, so any such count would be unreadable rather than zero.

#### Scenario: Facts are recorded per file
- **WHEN** a candidate is read
- **THEN** its skeleton names, node names, node count, frame count, user-instance count, predicted-instance count and referenced video filenames are recorded

#### Scenario: Zero and multiple skeletons are distinguished
- **WHEN** a file carries no skeleton, or more than one
- **THEN** the two cases are reported distinctly rather than as one failure

#### Scenario: An unreadable file does not abort the scan
- **WHEN** one candidate cannot be read
- **THEN** the failure is recorded against that family
- **AND** the remaining candidates are still read

### Requirement: Registry Digest Verification
The command SHALL compare each candidate against the digest on the `ArtifactManifestEntry` whose path basename equals the candidate's filename within a `wandb-registry-sleap-roots-labels` artifact, and SHALL report a candidate with no such entry as unregistered rather than as a failure.

Where more than one entry matches, every match is reported and none is crowned.
`ArtifactManifestEntry.digest` is a base64 MD5 over the whole file for uploads and for
`file://` references logged with checksumming on. `Artifact.digest` is computed over the
manifest and SHALL NOT be used. A reference entry's digest is not always a content hash —
`add_reference` against S3, GCS, Azure or HTTP carries that store's ETag or the URI itself,
and a `file://` reference logged with `checksum=False` carries an MD5 of the *path* — so the
discriminator is the reference scheme, not the mere presence of a digest.

#### Scenario: A digest match is reported as verified
- **WHEN** a candidate's base64 MD5 equals its manifest entry's digest
- **THEN** the family is reported as digest-verified against that artifact and version

#### Scenario: A digest mismatch is reported as a mismatch
- **WHEN** the two digests differ and the entry's digest is a content hash
- **THEN** the family is reported as mismatching, naming both digests

#### Scenario: An unregistered file is not a failure
- **WHEN** no registry artifact holds an entry matching a candidate
- **THEN** the family is reported as unregistered
- **AND** the scan's exit status is unaffected

#### Scenario: A reference digest that is not a content hash is unverifiable
- **WHEN** a matching entry carries a reference whose scheme is not `file`, or a `file://` reference logged without checksumming
- **THEN** the family is reported as unverifiable
- **AND** it is not reported as mismatching

### Requirement: Skeleton Table Keying Gap
The command SHALL report where `skeletons.yaml` cannot express the corpus, covering rows that two capture modes both select, species with no row at all, and skeleton names the existing check cannot parse.

`lookup_skeleton` (`src/sleap_roots_training/labeling/skeletons.py:327`) takes `species`,
`root_type` and `age`, and no `mode`. Node counts are read from the files and the mode is
name-derived from the family's directory path, so this report needs no scan metadata and no
external service.

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

### Requirement: Path Redaction
The command SHALL emit every candidate path relative to the supplied discovery root with the root rendered as one fixed token, and SHALL emit a referenced video path as its filename alone.

This is a whitelist, and smaller than the blacklist it replaces. Person-identifying segments
lie *above* the discovery root, or inside video paths recorded on other machines — two of
which carry colleagues' names, one with no `users/` marker at all. A marker-plus-first-segment
blacklist cannot be shown complete: it misses the backslash form Windows SLEAP records,
relative and `..`-rooted paths, and a person-named UNC share. Video filenames SHALL be split
on both separators, since recorded strings are Windows-shaped whatever host runs the scan.
`genotype`, `accession_id` and `experiment_name` are not paths and are emitted unchanged.

#### Scenario: A candidate path is emitted relative to the root
- **WHEN** a candidate is found beneath the supplied discovery root
- **THEN** its emitted path begins with the fixed root token
- **AND** no segment of the root's own absolute path appears in any emitted artifact

#### Scenario: A referenced video path is emitted as a filename
- **WHEN** a labels file references a video by an absolute path, in either separator form
- **THEN** only the filename is emitted
- **AND** no directory segment of that path appears in any emitted artifact

#### Scenario: A candidate outside the root is reported by filename
- **WHEN** a candidate path cannot be expressed relative to the supplied root
- **THEN** it is reported by filename alone
- **AND** the report records that it lay outside the root

### Requirement: Deterministic Artifacts
The command SHALL emit one per-family table and one report in a deterministic order, written under `inventory/` so successive runs diff.

Rows are ordered by emitted path, which is unique per candidate and therefore a total
order. The artifacts SHALL carry no run-varying metadata — no wall-clock timestamp, no
duration, no hostname — or successive runs could not diff. Byte identity across operating
systems is out of scope.

#### Scenario: Two runs over an unchanged tree agree
- **WHEN** the command runs twice over one unchanged tree
- **THEN** both runs emit byte-identical artifacts

#### Scenario: Rows are ordered by emitted path
- **WHEN** the table is emitted
- **THEN** its rows are sorted by emitted path

#### Scenario: Exit status reflects usability, not findings
- **WHEN** the scan completes having recorded mismatches, unregistered families and unresolvable groups
- **THEN** the command exits zero
- **AND** it exits non-zero only where the supplied root is missing or unreadable

### Requirement: No Decision Capture
The command SHALL report what it cannot determine and make no determination, and SHALL NOT read or write any file recording a human determination.

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

#### Scenario: Only labels files, the skeleton table and manifests are read
- **WHEN** the command runs
- **THEN** the only files it writes are the table and the report under `inventory/`
- **AND** the only files it reads are labels files, `skeletons.yaml` and registry manifests

#### Scenario: A name-derived species is labelled as name-derived
- **WHEN** a family's species is inferred from its path or filename
- **THEN** the report labels the value name-derived
- **AND** states that it is not evidence
