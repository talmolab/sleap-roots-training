## ADDED Requirements

### Requirement: Labeling Package Layout

The repo SHALL define a **labeling package** as a directory containing the labeled `.slp` file, a
`sample_manifest.csv` with one row per labeled frame, and the package metadata describing the
selection (species, capture mode, root type, age window, skeleton). The package directory SHALL be
the complete handoff to publication: everything a consumer needs to build and validate a label
provenance card SHALL be present inside it, with no dependency on the machine that produced it.

#### Scenario: A built package contains the full layout

- **WHEN** a labeling package is built successfully
- **THEN** the output directory contains the `.slp` file, `sample_manifest.csv`, and the package
  metadata, and no required piece is left in a temporary or user-specific location

#### Scenario: An incomplete package is rejected by validation

- **WHEN** a package directory is validated with `sample_manifest.csv` absent
- **THEN** validation fails with an error naming the missing file, before any network call

### Requirement: Sample Manifest Row-Level Provenance

`sample_manifest.csv` SHALL carry one row per labeled frame, recording at least `scan_id`,
`plant_qr_code`, `plant_age_days`, `accession_id`, `accession_name`, `wave_number`, `view_index`,
`frame_index`, `source_scan_path`, `source_image`, and `output_filename`. This provenance SHALL
travel inside the package, so that the exact scans, plants, and accessions behind a label set are
recoverable from the artifact alone without access to the original source filesystem.

#### Scenario: Every labeled frame has a manifest row

- **WHEN** a package is built from a selection of N frames
- **THEN** `sample_manifest.csv` has exactly N data rows, one per labeled frame

#### Scenario: A manifest missing a required column is rejected

- **WHEN** a package directory is validated whose `sample_manifest.csv` lacks a required column
- **THEN** validation fails with an error naming the missing column

#### Scenario: Frame count and manifest agree

- **WHEN** a package is validated whose declared frame count disagrees with the manifest row count
- **THEN** validation fails with an error reporting both numbers

### Requirement: Curated Images Correspond One-To-One With Manifest Rows

Every row of `sample_manifest.csv` SHALL correspond to exactly one curated image, and every curated
image SHALL correspond to exactly one manifest row. `output_filename` SHALL be unique across the
manifest, and the step that populates the curated image directory SHALL fail rather than skip a
source it cannot resolve. Neither a dropped image nor a duplicate name SHALL be reported as a
successful build.

This is what stops two independent silent corruptions. A source path that resolves nowhere currently
produces a warning and a zero exit at two separate stages, yielding an empty package that reports
success. A duplicate `output_filename` currently overwrites, so two scans are drawn from one image
while every count still reads correct.

#### Scenario: An unresolvable source image fails the step

- **WHEN** the curated image directory is populated and any row's `source_image` cannot be resolved
  to an existing file
- **THEN** the step fails with an error naming the row and the path it resolved to, and does not
  report success with a partially populated directory

#### Scenario: A duplicate curated filename is rejected

- **WHEN** a selection or a manifest would assign the same `output_filename` to two different frames
- **THEN** it fails with an error naming the colliding rows, rather than overwriting one with the
  other

#### Scenario: Validation catches a manifest/image mismatch

- **WHEN** a package directory is validated whose curated image count disagrees with its manifest
  row count
- **THEN** validation fails with an error reporting both numbers, rather than the discrepancy
  surfacing only as prose in the README

### Requirement: Deliberate Image Embedding

The package builder SHALL write the `.slp` with images embedded, as an explicit and tested step. A
package whose `.slp` is not self-contained SHALL be invalid. The builder SHALL NOT produce an
external-reference `.slp` for publication, because such a file breaks when its source paths become
unreachable and the standard repair — re-saving the embedded subset — permanently caps the label set
at the frames embedded at repair time.

#### Scenario: The built .slp is self-contained

- **WHEN** a labeling package is built
- **THEN** its `.slp` carries embedded images and can be opened on a machine that has never had
  access to the source scan paths

#### Scenario: A non-embedded package is rejected

- **WHEN** a package directory is validated whose `.slp` references external images
- **THEN** validation fails with an error stating that the package is not self-contained, rather than
  passing it on to be published and repaired later

### Requirement: Deterministic Sample Selection

Sample selection SHALL be deterministic: the same inputs and the same selection parameters SHALL
yield the same frames, and the selected frames SHALL be recoverable from `sample_manifest.csv` alone.

A selected frame SHALL be identified by `output_filename` independently of the parameters that
selected it: the same view of the same plant at the same age SHALL receive the same
`output_filename` at every `views_per_plant`, and a view not previously selected SHALL receive a
name no earlier selection used. This — not a superset of frames — is what makes a re-derived
package safe to merge with labels returned against a narrower one, since `output_filename` is the
only key a labeler's corrections carry.

Widening `plants_per_group` SHALL yield a superset of the narrower selection's plants. Widening
`views_per_plant` re-spaces the views evenly over the rotation and is NOT required to yield a
superset; see design.md "F3 revisited" for why nesting the view dimension was given up.

#### Scenario: Re-running selection reproduces the same frames

- **WHEN** selection runs twice over the same inputs with the same parameters
- **THEN** both runs select the same frames in the same order

#### Scenario: A curated filename names the same image at every width

- **WHEN** selection re-runs over the same inputs with a different `views_per_plant`
- **THEN** every `output_filename` present in both runs refers to the same view of the same plant,
  and every newly selected view receives a name the narrower run did not use

#### Scenario: A widened plant count is a superset

- **WHEN** selection re-runs over the same inputs with a larger `plants_per_group`
- **THEN** the resulting selection contains every plant the narrower run selected

#### Scenario: Selected views cover the whole rotation

- **WHEN** selection runs with any `views_per_plant` between 1 and `total_views`
- **THEN** the selected views are spread around the full rotation, with no arc left unsampled
  wider than the spacing between adjacent selected views

### Requirement: Build Fails Before Producing A Partial Package

The builder SHALL fail fast — before writing any package output — on an unreadable or missing source
scan, on selection parameters that cannot be satisfied, and on package metadata missing a required
field. A failed build SHALL NOT leave a partially written package directory that a later step could
mistake for a complete one.

#### Scenario: An unreadable source scan fails the build

- **WHEN** a build runs against a source scan path that does not exist or cannot be read
- **THEN** the build fails with an error naming the path, and no package directory is written

#### Scenario: Missing required package metadata fails the build

- **WHEN** a build runs without a required metadata field (for example the capture mode or the
  skeleton name)
- **THEN** the build fails with an error naming the field, and no package directory is written

### Requirement: Labeling Package CLI

The package generator SHALL be reachable from the repo's `click` CLI, mirroring how the registry
commands are exposed, so that building a labeling package is a public, scriptable operation rather
than a personal-machine workflow.

#### Scenario: The CLI builds a package

- **WHEN** the labeling-package build command runs with valid inputs
- **THEN** it writes a complete, validated package directory and reports its path

#### Scenario: The CLI surfaces a validation failure

- **WHEN** the build command runs with inputs that fail validation
- **THEN** it exits non-zero with the validation error, and does not write a package

### Requirement: Continued Labeling Is Re-derive And Republish

The documented path for adding labeled frames to an already-published package SHALL be to re-fetch
the source scan, re-run selection with a wider frame set, and publish a new version — not to edit or
de-embed the published artifact. The documentation SHALL state why: de-embedding restores original
video only when it is still reachable, so a package that has already lost its source paths is capped
at its embedded frames permanently.

#### Scenario: The workflow documentation states the re-derive path

- **WHEN** a contributor consults the labeling-package documentation for how to add more labeled
  frames to an existing package
- **THEN** it directs them to re-fetch, re-select, and publish a new version, and explains why
  editing the published artifact in place is not a supported path
