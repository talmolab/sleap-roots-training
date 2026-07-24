## ADDED Requirements

### Requirement: Label Package Publishing

The package SHALL provide a `publish-labels` path that takes a **labeling-package directory**,
builds a `LabelCard` from the package's metadata, validates it, and publishes the package as an
artifact linked into the labels registry — mirroring the production model publishing path.

The card SHALL be attached as the artifact's metadata, so that a label set's species, mode, root
type, age window, skeleton, content counts, and source experiment are **queryable key→value fields**
rather than boolean-key tags or free-text description prose.

The published artifact SHALL NOT record a `data_path` locator.

#### Scenario: A labeling package publishes with a populated card

- **WHEN** `publish-labels` is run against a well-formed labeling-package directory
- **THEN** the package is published as an artifact in the labels registry
- **AND** the artifact's metadata carries the full `LabelCard` field set as key→value pairs
- **AND** the artifact is linked under the configured alias

#### Scenario: Card fields are queryable, not boolean-key tags

- **WHEN** a published label artifact's metadata is read back
- **THEN** `species`, `root_type`, and `node_count` are retrievable as values
- **AND** the metadata does not encode them as keys whose value is `true`

#### Scenario: No unusable locator is recorded

- **WHEN** a published label artifact's metadata is read back
- **THEN** it contains no `data_path` field pointing at a temp directory or a drive letter

### Requirement: Sample Manifest Travels With The Labels

The `publish-labels` path SHALL attach the labeling package's `sample_manifest.csv` **inside** the
published artifact, so that row-level provenance — the exact scans, plants, accessions, and source
image paths behind each labeled frame — is recoverable from the artifact alone, without a working
network mount.

#### Scenario: The manifest is attached and round-trips

- **WHEN** a published label artifact is downloaded
- **THEN** `sample_manifest.csv` is present inside it
- **AND** its rows carry the per-frame provenance columns (including `scan_id`, `plant_qr_code`,
  `accession_name`, and `source_image`) unchanged from the source package

#### Scenario: A package without a manifest is rejected

- **WHEN** `publish-labels` is run against a directory containing no `sample_manifest.csv`
- **THEN** it exits with a clear error naming the missing manifest
- **AND** no artifact is published

### Requirement: Fail Fast Before Any Network Call

The `publish-labels` path SHALL validate the card and the package in a pure, pre-network stage —
mirroring how model selection resolution runs before `wandb.init` — so that a malformed package fails
before any upload begins.

#### Scenario: A missing required field fails before upload

- **WHEN** `publish-labels` is run against a package whose metadata omits a required `LabelCard`
  field
- **THEN** it exits with a clear error naming the missing field
- **AND** no artifact is uploaded and no network call is made

#### Scenario: An invalid mode fails before upload

- **WHEN** `publish-labels` is run against a package declaring `mode` as the `cyl` shorthand
- **THEN** it exits with a clear error naming the unknown mode and the accepted vocabulary
- **AND** no artifact is uploaded

#### Scenario: Validation is importable without wandb

- **WHEN** the pure validation stage is exercised without `wandb` available
- **THEN** it runs to completion, because the network layer is imported lazily

### Requirement: Declared Frame Count Matches The Manifest

The `publish-labels` path SHALL verify that the card's `n_frames` equals the number of rows in the
package's `sample_manifest.csv`, and SHALL refuse to publish on a mismatch. This check lives here
rather than in the contract because it compares a card field against a file's contents, and the
contract library performs no filesystem I/O.

#### Scenario: A matching frame count publishes

- **WHEN** a package declares `n_frames` of `482` and its `sample_manifest.csv` holds 482 data rows
- **THEN** validation passes and publishing proceeds

#### Scenario: A mismatched frame count is rejected before upload

- **WHEN** a package declares `n_frames` of `482` and its `sample_manifest.csv` holds 300 data rows
- **THEN** it exits with a clear error naming both the declared count and the actual row count
- **AND** no artifact is uploaded

### Requirement: Published Label Artifact Verification

The package SHALL provide a read-back verification path for label artifacts, mirroring the existing
registry verification command, that confirms a published artifact carries its alias, a card that
validates against the contract, and an attached manifest.

#### Scenario: Verification confirms a published label artifact

- **WHEN** the verification path is run against a published label collection
- **THEN** it reports the artifact's alias, confirms its metadata validates as a `LabelCard`, and
  confirms `sample_manifest.csv` is present

#### Scenario: Verification reports a card that no longer validates

- **WHEN** the verification path is run against a collection whose metadata does not satisfy the
  contract (for example a legacy collection carrying only boolean-key tags)
- **THEN** it reports that collection as failing validation rather than raising
