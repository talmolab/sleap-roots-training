# labeling-package — experiment identity verification

## ADDED Requirements

### Requirement: Verified Bloom Experiment Identity

The build SHALL accept an optional Bloom-derived export carrying `experiment_id` and `scan_id`
columns, and when one is supplied SHALL verify that every scan named by `sample_manifest.csv`
belongs to the declared Bloom experiment. A disagreement SHALL fail the build before any package
output is written.

The export is identified by its **columns**, not by its filename or its position in the experiment
folder, so any Bloom-derived table carrying both columns satisfies the requirement.

`bloom_experiment_id` is otherwise a free value typed by the operator at build time and recorded
into the package unchanged; it is the package's trace back to source data, and an unverifiable trace
that reads as authoritative is worse than an absent one.

#### Scenario: Every manifest scan belongs to the declared experiment

- **WHEN** a build runs with an export whose rows all carry the declared `bloom_experiment_id` for
  the manifest's `scan_id`s
- **THEN** the build proceeds, and the package records that its experiment identity was verified

#### Scenario: A scan belongs to a different experiment

- **WHEN** a build runs with an export in which any manifest `scan_id` carries an `experiment_id`
  other than the declared one
- **THEN** the build fails with an error naming the offending scan, the declared experiment, and the
  experiment the export gives it, and no package directory is written

#### Scenario: A manifest scan is absent from the export

- **WHEN** a build runs with an export that does not describe every `scan_id` in the manifest
- **THEN** the build fails with an error naming the absent scans, since an export that does not
  cover the manifest cannot verify it

#### Scenario: An export missing a required column is rejected by name

- **WHEN** a build runs with an export lacking `experiment_id` or `scan_id`
- **THEN** the build fails with an error naming the missing column, rather than failing later on an
  unrelated symptom

### Requirement: Unverified Identity Is Recorded, Not Rejected

A build without the optional export SHALL succeed and SHALL record in the package metadata that the
Bloom experiment identity was not verified. Consumers SHALL be able to distinguish a package whose
identity was checked against source data from one whose identity was typed by an operator.

Requiring the export would make the pipeline's traits stage a hard prerequisite of the labeling
stage, which it is not, and would invalidate every package built before this capability existed.

#### Scenario: A build without the export still produces a valid package

- **WHEN** a build runs with no export supplied
- **THEN** the build proceeds, the package validates, and its metadata records the experiment
  identity as unverified

#### Scenario: A package predating this capability still reads

- **WHEN** a package written before this capability existed is read
- **THEN** it reads successfully, with the verification status absent rather than an error

### Requirement: Human-Readable Experiment Identity

When the supplied export carries an `experiment_name`, the package metadata SHALL record it
alongside the numeric `bloom_experiment_id`, so the package states its origin in a form a person can
check without a Bloom lookup.

Bloom mints scans, plants, and waves from one shared integer sequence — the same integer denotes
different entity types depending on the column it appears in — so a bare id is not self-describing
even to a reader who knows Bloom.

#### Scenario: The experiment name is carried into the package

- **WHEN** a build runs with an export supplying `experiment_name`
- **THEN** the package metadata records that name alongside the numeric experiment id

#### Scenario: An export without a name still verifies the id

- **WHEN** a build runs with an export carrying `experiment_id` and `scan_id` but no
  `experiment_name`
- **THEN** the identity is still verified and the name is recorded as absent
