## ADDED Requirements

### Requirement: Skeleton Table Mode Key
The skeleton table SHALL key every row on `(species, mode, root_type, age)`, with `mode` a required value from `chooser.MODE_VOCAB`, and SHALL reject a table that violates this with the offending row number.

`mode` is required rather than defaulted: a default is picking, and a missing mode is a
table error. Duplicate detection and the rule that an age-agnostic row may not shadow an
age-split one both apply per `(species, mode, root_type)`.

#### Scenario: A row without a mode is rejected
- **WHEN** row 1 of a table omits `mode`
- **THEN** loading raises `ValueError` naming row 1 and the missing key `mode`

#### Scenario: A mode outside the vocabulary is rejected
- **WHEN** a table row carries `mode: plates`
- **THEN** loading raises `ValueError` naming the row number and every mode in `MODE_VOCAB`

#### Scenario: One key in two modes is not a duplicate
- **WHEN** a table has `soybean/primary` with `age: null` once in `cylinder` and once in `plate`
- **THEN** the table loads with both rows

#### Scenario: One pair may be age-agnostic in one mode and age-split in another
- **WHEN** a table has an `arabidopsis/primary` row in `cylinder` with `age: null` and rows in `plate` split by age
- **THEN** the table loads with all of them

#### Scenario: A duplicate within one mode is rejected
- **WHEN** two rows share species, mode, root type and age
- **THEN** loading raises `ValueError` naming the second row and the mode

#### Scenario: Shadowing is still rejected within one mode
- **WHEN** a table has `rice/crown` in `cylinder` both with `age: null` and split by age
- **THEN** loading raises `ValueError` naming the mode

### Requirement: Mode-Aware Skeleton Lookup
`lookup_skeleton` SHALL accept an optional `mode` and, when it is omitted and rows of more than one mode match the species and root type, SHALL raise `ValueError` naming those modes rather than picking one, whatever `age` is passed.

When only one mode matches, an omitted `mode` behaves as before. A given `mode` with no row
for an otherwise covered pair fails, naming the modes that do exist. A pair with no row in
any mode fails as it did before. Age handling is unchanged and applies within the chosen
mode. The warning for an unverified row names the species, mode and root type.

#### Scenario: An omitted mode with two matching modes raises
- **WHEN** `lookup_skeleton("arabidopsis", "primary")` is called against a table with cylinder and plate rows for that pair, with no age and again with `age=3`
- **THEN** each call raises `ValueError` naming `cylinder` and `plate`

#### Scenario: An omitted mode with one matching mode is unchanged
- **WHEN** `lookup_skeleton("soybean", "primary")` is called and only cylinder rows exist for that pair
- **THEN** it returns the cylinder row

#### Scenario: A given mode selects its own row
- **WHEN** `lookup_skeleton("arabidopsis", "primary", age=3, mode="plate")` is called on the committed table
- **THEN** it returns the 8-node row
- **AND** `mode="cylinder"` returns the 6-node row

#### Scenario: A given mode with no row raises
- **WHEN** `lookup_skeleton("soybean", "primary", mode="multiplant cylinder")` is called and soybean has only cylinder rows
- **THEN** it raises `ValueError` naming `cylinder` as the mode that exists

#### Scenario: A given mode for an uncovered pair fails as before
- **WHEN** `lookup_skeleton("pennycress", "primary", mode="plate")` is called and pennycress has no row
- **THEN** it raises the existing no-row `ValueError` listing the pairs the table covers

#### Scenario: An age-split mode requires an age
- **WHEN** `lookup_skeleton("arabidopsis", "primary", mode="plate")` is called on the committed table without an age
- **THEN** it raises `ValueError` saying an age is required and listing 2-7 DAG only

#### Scenario: The plate window has exact bounds
- **WHEN** the committed table is looked up with `mode="plate"` at ages 1, 2, 7 and 8
- **THEN** ages 2 and 7 return the 8-node row
- **AND** ages 1 and 8 raise `ValueError` listing 2-7 DAG

#### Scenario: The unverified warning names the mode
- **WHEN** an unverified row is returned
- **THEN** the logged warning names its species, mode and root type

### Requirement: Committed Skeleton Rows Carry Their Mode
The committed `skeletons.yaml` SHALL mark every transcribed row `mode: cylinder` and SHALL carry an unverified `arabidopsis/plate/primary` row at 8 nodes for ages 2-7 whose node count agrees with the committed label inventory.

The transcribed rows' only in-repo source, `/build-labeling-package`, builds from cylinder
experiments. The plate row's node count SHALL be the strict plurality among labelled
arabidopsis plate primary families in `inventory/label-inventory.csv`. The test reads the
committed file, resolved from the test's own path, and fails if the file is absent, so a
later scan that moves the evidence fails the test instead of silently diverging.

#### Scenario: Every transcribed row is cylinder
- **WHEN** the committed table is loaded
- **THEN** every row other than the arabidopsis plate primary row has `mode` `cylinder`

#### Scenario: The plate row is unverified
- **WHEN** the committed table is loaded
- **THEN** the arabidopsis plate primary row has `verified: false`

#### Scenario: The plate row agrees with the committed scan
- **WHEN** labelled arabidopsis plate primary families in `inventory/label-inventory.csv` are counted by node count
- **THEN** the plate row's `node_count` has strictly more families than any other count

### Requirement: Labeling Packages Use Their Own Mode
The labeling package builder SHALL look up each root type's skeleton with the package's own `mode`, as recorded in its package metadata, and SHALL fail before writing anything when that mode has no row.

The mode is already a required, vocabulary-checked CLI option recorded in
`package_metadata.yaml`, so this adds no input.

#### Scenario: A plate package gets the plate skeleton
- **WHEN** an arabidopsis primary package with `mode: plate` spanning ages 3-5 is built
- **THEN** its `.slp` skeleton and its `package_metadata.yaml` skeletons record 8 nodes

#### Scenario: A cylinder package gets the cylinder skeleton
- **WHEN** the same selection with `mode: cylinder` resolves its skeleton
- **THEN** the skeleton has 6 nodes

#### Scenario: A mode with no row fails the build before writing
- **WHEN** a soybean primary package with `mode: multiplant cylinder` is built
- **THEN** the build raises `ValueError` naming `cylinder` as the mode that exists
- **AND** neither the output directory nor any partial directory exists afterwards
