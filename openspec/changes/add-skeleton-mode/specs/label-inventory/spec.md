## REMOVED Requirements

### Requirement: Skeleton Table Keying Gap
**Reason**: Its headline scenario, "Two capture modes select one row", describes a table with no `mode` column. `labeling-skeletons` adds one, so two modes can no longer select one row, and keeping the scenario name with the opposite meaning would mislead.
**Migration**: Replaced by `Skeleton Table Mode Gap` below, which carries the denominator, uncovered-species and unparseable-name scenarios unchanged and reports observed modes that have no row of their own.

## ADDED Requirements

### Requirement: Skeleton Table Mode Gap
The command SHALL report where `skeletons.yaml` cannot express the corpus, covering capture modes observed for a species and root type that have no row of their own, species with no row at all, and skeleton names the existing check cannot parse.

`skeletons.yaml` rows carry a `mode` (`labeling-skeletons`), so a row is matched on species,
mode and root type, and two capture modes can no longer select one row. What the table can
still fail to express is a mode the corpus uses and the table has no row for. Node counts
are read from the files and the mode is name-derived from the family's **whole** path, so
this report needs no scan metadata and no external service. Reading only part of the path
made the finding wrong rather than merely incomplete. A family is analysed only where
species, root type, mode and node count are all derivable, so the report SHALL state how
many families it analysed out of how many it saw, and why the rest were not: a finding
whose base is a fraction of the corpus and does not say so is misleading.

#### Scenario: An observed mode with no row is reported
- **WHEN** a 3-node plate arabidopsis lateral family is present and the table has an arabidopsis lateral row only in `cylinder`
- **THEN** the report records `(arabidopsis, plate, lateral)` as a mode with no row
- **AND** names the observed node counts and the modes the table does have for that pair

#### Scenario: A mode with its own row is not reported
- **WHEN** a 6-node cylinder arabidopsis primary family and an 8-node plate arabidopsis primary family are both present and the table has a row for each mode
- **THEN** the report records no mode gap for `(arabidopsis, primary)`

#### Scenario: The report states its own denominator
- **WHEN** some families lack a derivable mode
- **THEN** the report gives the analysed count, the total considered, and a per-reason breakdown

#### Scenario: A species with no row is reported
- **WHEN** a family's derived species has no `skeletons.yaml` row
- **THEN** the report lists that species as uncovered

#### Scenario: An auto-generated skeleton name is unparseable
- **WHEN** a file's skeleton is named in the auto-generated `Skeleton-N` form
- **THEN** the report records that the existing `skeleton.name.partition("_")` check (`tests/test_labeling_skeletons.py:419`) cannot resolve it
