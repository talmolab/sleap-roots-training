## REMOVED Requirements

### Requirement: Skeleton Table Keying Gap
**Reason**: Its headline scenario, "Two capture modes select one row", describes a table with no `mode` column. `labeling-skeletons` adds one, so two modes can no longer select one row, and keeping that scenario name with the opposite meaning would mislead.
**Migration**: Replaced by `Skeleton Table Mode Gap`, which carries the denominator, uncovered-species and unparseable-name scenarios unchanged, and reports observed modes with no row of their own and node counts that disagree with the matched row.

## ADDED Requirements

### Requirement: Skeleton Table Mode Gap
The command SHALL report where `skeletons.yaml` cannot express the corpus, covering observed modes with no row of their own, observed node counts that disagree with the matched rows, species with no row at all, and skeleton names the existing check cannot parse.

Rows carry a `mode` (`labeling-skeletons`), so a family is matched on species, mode and root
type. A mode gap is reported only where the table has at least one row for the species and
root type in some other mode; a species with no row is reported as uncovered instead, and a
covered species whose root type has no row in any mode is reported as neither. A node-count
disagreement lists, per matched `(species, mode, root_type)`, the row node counts and each
observed count outside them with its files. The report prints both and decides nothing.
Age is not considered: it is not derivable from the path. Node counts are read from the files
and the mode is name-derived from the family's **whole** path, so this report needs no scan
metadata and no external service. A family is analysed only where species, root type, mode
and node count are all derivable, so the report SHALL state how many families it analysed
out of how many it saw, and why the rest were not.

#### Scenario: An observed mode with no row is reported
- **WHEN** a 3-node plate arabidopsis lateral family is present and the table has an arabidopsis lateral row only in `cylinder`
- **THEN** the report records `(arabidopsis, plate, lateral)` as a mode with no row
- **AND** names the observed node counts and `cylinder` as the mode the table has

#### Scenario: A mode with its own row is not a gap
- **WHEN** a 6-node cylinder and an 8-node plate arabidopsis primary family are present and the table has an arabidopsis primary row in each mode at those counts
- **THEN** the report records no mode gap and no node-count disagreement

#### Scenario: An uncovered species is not a mode gap
- **WHEN** a plate medicago lateral family is present and medicago has no row
- **THEN** medicago is listed as uncovered and no mode gap is recorded

#### Scenario: A disagreeing node count is reported
- **WHEN** 8-node and 7-node plate arabidopsis primary families are present and the plate row has 8 nodes
- **THEN** the report records `(arabidopsis, plate, primary)` with row count 8, observed count 7, and the 7-node files

#### Scenario: The findings are rendered
- **WHEN** the report is emitted with a mode gap and a node-count disagreement
- **THEN** it contains a "Capture modes with no row" section and a "Node counts that disagree with their row" section naming each finding

#### Scenario: The report states its own denominator
- **WHEN** some families lack a derivable mode
- **THEN** the report gives the analysed count, the total considered, and a per-reason breakdown

#### Scenario: A species with no row is reported
- **WHEN** a family's derived species has no `skeletons.yaml` row
- **THEN** the report lists that species as uncovered

#### Scenario: An auto-generated skeleton name is unparseable
- **WHEN** a file's skeleton is named in the auto-generated `Skeleton-N` form
- **THEN** the report records that the existing `skeleton.name.partition("_")` check in `test_the_table_agrees_with_the_published_label_collections` cannot resolve it
