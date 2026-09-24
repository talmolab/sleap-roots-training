## ADDED Requirements

### Requirement: Skeleton Table Mode Key
The skeleton table SHALL key every row on `(species, mode, root_type, age)`, with `mode` a required value from `chooser.MODE_VOCAB`, and SHALL reject a table that violates this with the offending row number.

`mode` is required rather than defaulted: a default is picking, and a missing mode is a
table error. Duplicate detection and the rule that an age-agnostic row may not shadow an
age-split one both apply per `(species, mode, root_type)`, so one species and root type may
be age-agnostic in one mode and age-split in another.

#### Scenario: A row without a mode is rejected
- **WHEN** a table row omits `mode`
- **THEN** loading raises `ValueError` naming that row's number and the missing key

#### Scenario: A mode outside the vocabulary is rejected
- **WHEN** a table row carries `mode: plates`
- **THEN** loading raises `ValueError` naming the row number and the accepted modes

#### Scenario: One pair in two modes loads
- **WHEN** a table has an `arabidopsis/primary` row in `cylinder` with `age: null` and one in `plate` split by age
- **THEN** the table loads with both rows

#### Scenario: A duplicate within one mode is rejected
- **WHEN** two rows share species, mode, root type and age
- **THEN** loading raises `ValueError` naming the second row

### Requirement: Mode-Aware Skeleton Lookup
`lookup_skeleton` SHALL accept an optional `mode` and, when it is omitted and rows of more than one mode match the species and root type, SHALL raise `ValueError` naming those modes rather than picking one.

When only one mode matches, an omitted `mode` behaves as before. A given `mode` with no row
fails, naming the modes that do exist. Age handling is unchanged and applies within the
chosen mode.

#### Scenario: An omitted mode with two matching modes raises
- **WHEN** `lookup_skeleton("arabidopsis", "primary")` is called against a table with cylinder and plate rows for that pair
- **THEN** it raises `ValueError` naming `cylinder` and `plate`

#### Scenario: An omitted mode with one matching mode is unchanged
- **WHEN** `lookup_skeleton("soybean", "primary")` is called and only cylinder rows exist for that pair
- **THEN** it returns the cylinder row

#### Scenario: A given mode selects its own row
- **WHEN** `lookup_skeleton("arabidopsis", "primary", age=3, mode="plate")` is called on the committed table
- **THEN** it returns the 8-node row
- **AND** `mode="cylinder"` returns the 6-node row

#### Scenario: A given mode with no row raises
- **WHEN** `lookup_skeleton("soybean", "primary", mode="plate")` is called and soybean has only cylinder rows
- **THEN** it raises `ValueError` naming `cylinder` as the mode that exists

#### Scenario: An age outside the plate window raises
- **WHEN** `lookup_skeleton("arabidopsis", "primary", age=8, mode="plate")` is called
- **THEN** it raises `ValueError` listing the covered window 2-7 DAG

### Requirement: Committed Skeleton Rows Carry Their Mode
The committed `skeletons.yaml` SHALL mark every onboarding-doc row `mode: cylinder` and SHALL carry an `arabidopsis/plate/primary` row at 8 nodes for ages 2-7, marked verified, whose node count agrees with the committed label inventory.

The onboarding doc the existing rows were transcribed from covers cylinder only. The plate
row's evidence is `inventory/label-inventory.csv`, where 8 is the most common node count
among arabidopsis plate primary families. The test reads the committed CSV rather than
re-scanning, so a later scan that moves the evidence fails the test instead of silently
diverging from the table.

#### Scenario: Every transcribed row is cylinder
- **WHEN** the committed table is loaded
- **THEN** every row other than the arabidopsis plate primary row has `mode` `cylinder`

#### Scenario: The plate row agrees with the committed scan
- **WHEN** the arabidopsis plate primary families in `inventory/label-inventory.csv` are counted by node count
- **THEN** the most common count equals the plate row's `node_count`

### Requirement: Labeling Packages Use Their Own Mode
The labeling package builder SHALL look up each root type's skeleton with the package's own `mode`, as recorded in its package metadata.

The mode is already a required, vocabulary-checked CLI option recorded in
`package_metadata.yaml`, so this adds no input. Without it, an arabidopsis primary package
fails to build instead of silently taking one mode's skeleton.

#### Scenario: A plate package gets the plate skeleton
- **WHEN** an arabidopsis primary package with `mode: plate` spanning ages 3-5 resolves its skeleton
- **THEN** the skeleton has 8 nodes

#### Scenario: A cylinder package gets the cylinder skeleton
- **WHEN** the same package with `mode: cylinder` resolves its skeleton
- **THEN** the skeleton has 6 nodes
