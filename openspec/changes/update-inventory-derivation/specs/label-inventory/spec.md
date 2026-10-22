## ADDED Requirements

### Requirement: Filename-First Species Derivation
The command SHALL derive a family's species from its filename before its folder, and SHALL derive no species, flagging the family `multi-species`, where the part that decides names more than one.

People put other crops' data in a crop's folder to train one model, so the filename is the
more specific name (eberrigan, 2026-09-24). The stem is read against a closed vocabulary:
`KNOWN_SPECIES` after `_SPECIES_ALIASES`, with a token `only<species>` read as that species
and a bare `only` naming nothing. A stem naming the same species twice, or by alias and name,
names one. Where the stem names none, the folder decides: the known species in the first
`SLEAP_<x>` directory, or its open `<x>` where it names none; where no directory is
`SLEAP_<x>`, the known species of the first directory that names one. Only that deciding
directory is consulted, and only directories below the scan root are read: the ones above
it are the operator's, not the corpus's, and must supply no species, mode or flag. A multi-species label file is never registered as it is — it is split
per species or matched to per-species files — so a part naming several species yields no
species, never the first it names. A single filename species is kept, and flagged
`folder-species-differs`, where the deciding directory names at least one known species and
none of them is the filename's.

#### Scenario: The filename's species beats the folder's
- **WHEN** a family is `SLEAP_arabidopsis_plates/labels/primary_8nodes/labels_wheat_2-3DAG.v002.slp`
- **THEN** its species is `wheat`, decided by the filename, with named species `wheat` and folder species `arabidopsis`
- **AND** it is flagged `folder-species-differs`

#### Scenario: An alias in the filename is read and compared
- **WHEN** a family is `SLEAP_sorghum/lateral_4nodes/labels_soy_lateral_4nodes.v001.slp`
- **THEN** its species is `soybean`
- **AND** it is flagged `folder-species-differs`

#### Scenario: A species glued to ONLY is read, and a bare ONLY is not
- **WHEN** one family's stem is `labels_ONLYpennycress_primary_6nodes.v000` and another's is `labels_7DAP_laterals_ONLY.v007`, both under directories naming no species
- **THEN** the first's species is `pennycress`
- **AND** the second's species is empty and it carries no flag

#### Scenario: A filename naming several species derives none
- **WHEN** a family is `SLEAP_medicago/primary_root/labels_canola_pennycress_arabidopsis.v015.slp`
- **THEN** its species is empty and its named species are `arabidopsis`, `canola`, `pennycress`, decided by the filename
- **AND** it is flagged `multi-species` and not `folder-species-differs`

#### Scenario: A folder naming several species derives none
- **WHEN** a family's stem names no species and its first `SLEAP_<x>` directory is `SLEAP_Canola_Pennycress`
- **THEN** its species is empty and its named species are `canola`, `pennycress`, decided by the folder
- **AND** it is flagged `multi-species`

#### Scenario: A filename naming no species falls back to the folder
- **WHEN** a family is `SLEAP_Soy/lateral/labels.v001.slp`
- **THEN** its species is `soybean`, decided by the folder, with named species `soybean` and no flag

#### Scenario: An open folder word is kept and contradicts nothing
- **WHEN** one family is `SLEAP_packages_10-24-23/labels.v001.slp` and another is `SLEAP_packages_10-24-23/labels_rice_3do.v001.slp`
- **THEN** the first's species is `packages`, decided by the folder
- **AND** the second's species is `rice` and it is not flagged `folder-species-differs`

#### Scenario: A folder naming the filename's species among several contradicts nothing
- **WHEN** a family is `experiments/x_sorghum_soybean_canola_pennycress_rice_arabidopsis_on_y/labels_rice_3do.v001.slp`
- **THEN** its species is `rice` and it is not flagged `folder-species-differs`

#### Scenario: Names above the scan root derive nothing
- **WHEN** the scan root is `…/SLEAP_janedoe/plates_x/share` and it holds `cyl_x/labels.v001.slp` and `exp/labels_wheat.v001.slp`
- **THEN** the first family's species is empty and its mode is `cylinder`, with no flag
- **AND** the second's species is `wheat` and its mode is empty, with no flag
- **AND** `janedoe` appears in neither artifact

#### Scenario: A filename species outside a multi-species folder is flagged
- **WHEN** a family is `SLEAP_Canola_Pennycress/primary_root/labels_wheat_5DAG.v001.slp`
- **THEN** its species is `wheat` and it is flagged `folder-species-differs`

### Requirement: Capture Mode Derivation
The command SHALL derive a family's capture mode from its whole path below the scan root, SHALL read an exact `multiplant` token as `multiplant cylinder`, and SHALL derive no mode, flagging the family `ambiguous-mode`, where the path names more than one distinct mode.

`multiplant cylinder` is the `MODE_VOCAB` spelling. Multiplant cylinders are arabidopsis only,
all from one labeler who also labelled single-plant cylinders, so a labeler's name is not
evidence of multiplant; only the literal token is. An exact `multiplant` token anywhere in the
path derives `multiplant cylinder`, and a `cyl` or `cylinder` token elsewhere in the path is
read as part of it. No other spelling matches: `multi`, `multiple` and `multiclass` all occur
on the share meaning something else, and `multi-plant` tokenizes to `multi` and `plant`. A
mode named twice is one mode. Mode stays underivable for most labelled families; no heuristic
is added for them.

#### Scenario: A multiplant token derives multiplant cylinder
- **WHEN** one family sits under `multiplant_cylinder/` and another under `multiplant/`
- **THEN** each family's mode is `multiplant cylinder`
- **AND** neither is flagged `ambiguous-mode`

#### Scenario: A cylinder word apart from multiplant is part of it
- **WHEN** a family sits under `SLEAP_arabidopsis/cyl_primary/multiplant/`
- **THEN** its mode is `multiplant cylinder` and it is not flagged `ambiguous-mode`

#### Scenario: Look-alike spellings are not multiplant
- **WHEN** families sit under `SLEAP_Soy/primary_multi-day/`, `SLEAP_medicago_plates/multiclass_bottomup/` and `SLEAP_multiple_species/cyl/`
- **THEN** their modes are empty, `plate` and `cylinder` respectively

#### Scenario: A path naming two modes derives none
- **WHEN** one family sits under `plates/cyl_primary/` and another under `multiplant/plate/`
- **THEN** each family's mode is empty, its named modes are listed sorted, and it is flagged `ambiguous-mode`

#### Scenario: A mode named twice is one mode
- **WHEN** a family sits under `SLEAP_arabidopsis_plates/plate_primary/`
- **THEN** its mode is `plate` and it is not flagged `ambiguous-mode`

### Requirement: Derivation Findings Are Reported
The command SHALL record each family's named species and derivation flags in the table, and SHALL list in the report every family naming more than one species, every directory where folder and filename disagree on species, and every path naming more than one capture mode, deciding nothing about any of them.

The table gains `species_named`, a JSON list of the species the deciding part named, and
`flags`, the family's flags sorted and space-joined like `members_disagree`, both placed right
after `species_source` so the other columns keep their order. The report gains a "Name
derivation" section, after "Coverage", that states the precedence in one sentence and holds
three subsections, each omitted when it has nothing to list. Entries are ordered by emitted
path and every list within an entry is sorted, so successive runs diff. A multi-species line
names the family, its named species and whether the filename or the folder named them; the
subsection says each must be split per species or matched to per-species files before it is
registered. A folder disagreement is one line per family directory, giving the count and each
`folder → filename` pair with its count; the subsection says the filename's species was used.
The tool lists these and decides nothing about them.

#### Scenario: The table records named species and flags
- **WHEN** a multi-species family is emitted
- **THEN** its row has an empty `species`, a `species_named` JSON list of every species named, sorted, and `multi-species` in `flags`
- **AND** the header places `species_named` and `flags` immediately after `species_source`, with the other columns in their prior order

#### Scenario: Flags are emitted in sorted order
- **WHEN** a family is flagged both `folder-species-differs` and `ambiguous-mode`
- **THEN** its `flags` cell is `ambiguous-mode folder-species-differs`

#### Scenario: The report states the precedence
- **WHEN** the report is emitted
- **THEN** its "Name derivation" section states that species is read from the filename before the folder, and that a part naming several species yields none

#### Scenario: A multi-species family is listed, not resolved
- **WHEN** the report is emitted with one family named multi-species by its filename and one by its folder
- **THEN** the "Families naming more than one species" subsection has one line for each, giving its path, its sorted named species and `filename` or `folder`
- **AND** it states that each must be split per species or matched to per-species files before it is registered

#### Scenario: Folder disagreements are grouped by directory
- **WHEN** two families in one directory and one in another are flagged `folder-species-differs`
- **THEN** the "Folder and filename disagree on species" subsection has exactly two lines, one per directory, each giving its count and its `folder → filename` pairs
- **AND** it states that the filename's species was used

#### Scenario: An ambiguous mode is listed
- **WHEN** the report is emitted with a family flagged `ambiguous-mode`
- **THEN** the "Paths naming more than one capture mode" subsection names the family and its sorted named modes

#### Scenario: Empty findings emit no subsection
- **WHEN** no family is multi-species, disagrees with its folder, or names two modes
- **THEN** none of the three subsections appears
- **AND** the "Name derivation" section says `None.` and that these are names, not evidence

#### Scenario: The new sections carry no path above the root
- **WHEN** any of the three subsections is emitted
- **THEN** every path in it begins with the fixed root token
- **AND** no segment of the root's own absolute path appears in either artifact

## MODIFIED Requirements

### Requirement: Deterministic Artifacts
The command SHALL emit one per-family table and one report in a deterministic order, written under `inventory/` so successive runs diff.

Rows are ordered by emitted path, which is unique per candidate and therefore a total
order. A value a spreadsheet would evaluate as a formula SHALL be neutralized: these
artifacts are committed and opened in Excel, and the values come from files written
elsewhere. A scan that could not list part of the tree SHALL NOT overwrite the artifacts,
because writing what it found makes the diff read as the corpus having disappeared. That
holds whenever any directory could not be listed, not only when nothing was found: the command
writes nothing, names each unreadable directory once, relative to the root — the first 20,
then how many more, since a dropped share connection fails every directory still to be
walked — and exits non-zero. The artifacts SHALL carry no run-varying metadata — no wall-clock timestamp, no
duration, no hostname — or successive runs could not diff. Byte identity across operating
systems is out of scope.

#### Scenario: Two runs over an unchanged tree agree
- **WHEN** the command runs twice over one unchanged tree
- **THEN** both runs emit byte-identical artifacts

#### Scenario: Rows are ordered by emitted path
- **WHEN** the table is emitted
- **THEN** its rows are sorted by emitted path

#### Scenario: A partial scan refuses to write
- **WHEN** the root can be opened but part of the tree cannot be listed and no candidate is found
- **THEN** the command writes nothing and reports the directories it could not read

#### Scenario: A partially readable root writes nothing
- **WHEN** candidates are found but one directory beneath the root cannot be listed
- **THEN** the command writes neither artifact, leaving any existing ones unchanged
- **AND** it names that directory relative to the root and exits non-zero

#### Scenario: A refused scan names each directory once, and caps the list
- **WHEN** 25 distinct directories, one of them reported twice, cannot be listed
- **THEN** the message counts 25, names `<ROOT>/d00` once, lists the first 20 sorted and says `and 5 more`
- **AND** the root itself is named `<ROOT>` and a directory the walk could not name is `<unknown>`

#### Scenario: Exit status reflects usability, not findings
- **WHEN** the scan completes having recorded mismatches, unregistered families and unresolvable groups
- **THEN** the command exits zero
- **AND** it exits non-zero only where the supplied root is missing or unreadable, or part of the tree could not be listed

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
out of how many it saw, and why the rest were not. Each underivable field counts once under
its own reason, so one family can count under several. A species left empty because the name
gives several counts as `multi-species`, and a mode left empty because the path names several
counts as `ambiguous-mode`, not as `no-species` or `no-mode`: a name that says too much is a
different finding from a name that says nothing. A multi-species family's named species still
count toward the uncovered list: a pooled file is labels of each crop it names. A
`multiplant cylinder` family is matched in that mode, so while the table has no multiplant
rows it is a mode gap against the cylinder row rather than a cylinder match.

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

#### Scenario: A name that says too much is skipped by its own reason
- **WHEN** one family's filename names two species and another's path names two modes, each otherwise deriving species or mode, root type and a node count
- **THEN** the per-reason breakdown is exactly one `multi-species` and one `ambiguous-mode`

#### Scenario: A multiplant family is a mode gap, not a cylinder match
- **WHEN** a 6-node `multiplant_cylinder/` arabidopsis primary family is present and the table has an arabidopsis primary row only in `cylinder`, at 6 nodes
- **THEN** the report records `(arabidopsis, multiplant cylinder, primary)` as a mode with no row, naming `cylinder` as the mode the table has
- **AND** records no node-count disagreement for `(arabidopsis, cylinder, primary)`

#### Scenario: A multi-species family's species still count as uncovered
- **WHEN** the only families naming pennycress are `labels_canola_pennycress.v001.slp` and a family under `SLEAP_Canola_Pennycress/` whose stem names no species, and pennycress has no row
- **THEN** pennycress is listed as uncovered
- **AND** both families are still skipped as `multi-species`
