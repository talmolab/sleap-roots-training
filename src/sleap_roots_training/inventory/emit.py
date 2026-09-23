"""Build the inventory and write it out, deterministically.

One table and one report, ordered by emitted path, with no run-varying metadata in
either — no wall clock, no duration, no hostname — because the artifacts are committed
so that successive runs diff. Byte identity *across* operating systems is out of scope;
stability within a run is not.

The report says what the tool could not determine and stops there. Where a directory
holds several families it lists them and asserts no collection membership: a directory
is not a collection, and on the measured share one of them holds 28 labels files
spanning a superset, a second species' collection, a generalist, per-labeler inputs and
practice files. Deciding which of those is a collection is a person's job, and this
module deliberately offers nowhere to record that decision.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

from sleap_roots_training.inventory import discover, gap, read, redact
from sleap_roots_training.labeling.skeletons import SkeletonRow

#: The per-family table.
TABLE_FILENAME = "label-inventory.csv"

#: The prose report.
REPORT_FILENAME = "label-inventory.md"

#: How many family names to print per crowded directory. One measured directory holds
#: 30, and the untruncated line is unreadable — the count is the finding, the full
#: list is in the table.
_STEMS_SHOWN = 8

#: Registry status for a family whose digest was not looked up at all.
NOT_CHECKED = "not-checked"

#: Column order of the table. Fixed, so a diff shows content changes and not reordering.
COLUMNS = (
    "path",
    "version",
    "species",
    "species_source",
    "mode",
    "root_type",
    "node_count",
    "frames",
    "user_instances",
    "predicted_instances",
    "skeleton_state",
    "skeleton_names",
    "video_filenames",
    "registry_status",
    "error",
)


class UnusableRoot(Exception):
    """The supplied discovery root does not exist or cannot be read."""


@dataclass(frozen=True)
class AmbiguousDirectory:
    """A directory holding more than one family, which the tool will not resolve.

    Attributes:
        path: The directory, emitted relative to the root.
        family_count: How many families it holds.
        stems: Their version-stripped basenames, sorted.
    """

    path: str
    family_count: int
    stems: tuple[str, ...]


@dataclass
class Inventory:
    """Everything one scan found, ready to write.

    Attributes:
        root: The root that was scanned.
        scan: The raw walk result, including exclusions and unreadable directories.
        rows: One row per family, ordered by emitted path.
        gap: The skeleton-table keying gap.
        ambiguous_directories: Directories holding several families.
    """

    root: Path
    scan: discover.ScanResult
    rows: list[dict] = field(default_factory=list)
    gap: gap.GapReport = field(default_factory=gap.GapReport)
    ambiguous_directories: list[AmbiguousDirectory] = field(default_factory=list)


def build(
    root: Path,
    *,
    table: Optional[Sequence[SkeletonRow]] = None,
    statuses: Optional[dict[Path, str]] = None,
    verifier: Optional[Callable[[Sequence[Path]], dict[Path, str]]] = None,
) -> Inventory:
    """Scan ``root`` and assemble the inventory.

    Args:
        root: Directory to scan.
        table: Skeleton table to check against; defaults to the packaged one.
        statuses: Registry status per candidate path. Absent entries are recorded as
            :data:`NOT_CHECKED` rather than as unregistered — not looking is not the
            same finding as looking and finding nothing.
        verifier: Called once with every candidate path, returning their statuses.
            Takes precedence over ``statuses``. Passing it here rather than walking
            twice keeps one pass over a share holding 18,099 `.slp` files.

    Returns:
        The assembled inventory.

    Raises:
        UnusableRoot: If ``root`` is not a readable directory. Nothing is written.
    """
    root = Path(root)
    if not root.is_dir():
        raise UnusableRoot(f"not a readable directory: {root}")

    statuses = dict(statuses or {})
    scan = discover.walk(root)
    families = discover.group(scan.candidates)
    if verifier is not None:
        statuses = verifier([family.latest.path for family in families])

    observations: list[gap.Observed] = []
    rows: list[dict] = []
    for family in families:
        candidate = family.latest
        facts = read.read_facts(candidate.path)
        observations.append(gap.Observed(family=family, facts=facts))
        derived = gap.derive(family)
        emitted = redact.emit_path(candidate.path, root)
        rows.append(
            {
                "path": emitted.text,
                "version": "" if candidate.version is None else candidate.version,
                "species": derived.species or "",
                "species_source": derived.source,
                "mode": derived.mode or "",
                "root_type": derived.root_type or "",
                "node_count": "" if facts.node_count is None else facts.node_count,
                "frames": "" if facts.frame_count is None else facts.frame_count,
                "user_instances": (
                    "" if facts.user_instances is None else facts.user_instances
                ),
                "predicted_instances": (
                    ""
                    if facts.predicted_instances is None
                    else facts.predicted_instances
                ),
                "skeleton_state": facts.skeleton_state,
                "skeleton_names": " ".join(facts.skeleton_names),
                "video_filenames": " ".join(
                    sorted({redact.emit_video_path(v) for v in facts.video_filenames})
                ),
                "registry_status": statuses.get(candidate.path, NOT_CHECKED),
                "error": facts.error or "",
            }
        )

    rows.sort(key=lambda row: row["path"])

    by_directory: dict[Path, list[discover.Family]] = {}
    for family in families:
        by_directory.setdefault(family.directory, []).append(family)
    ambiguous = [
        AmbiguousDirectory(
            path=redact.emit_path(directory, root).text,
            family_count=len(group),
            stems=tuple(sorted(f.stem for f in group)),
        )
        for directory, group in by_directory.items()
        if len(group) > 1
    ]
    ambiguous.sort(key=lambda entry: entry.path)

    return Inventory(
        root=root,
        scan=scan,
        rows=rows,
        gap=gap.build_report(observations, table=table),
        ambiguous_directories=ambiguous,
    )


def exit_code(inventory: Inventory) -> int:
    """Return the process exit status for a completed scan.

    Always zero. Mismatches, unregistered families and unresolvable groups are findings
    for a person to read, not failures of the tool. Only an unusable root is an error,
    and that raises :class:`UnusableRoot` before anything is written.

    Args:
        inventory: The completed scan.

    Returns:
        ``0``.
    """
    del inventory
    return 0


def _render_report(inventory: Inventory) -> str:
    """Render the prose report. Contains nothing that varies between runs."""
    scan = inventory.scan
    lines: list[str] = [
        "# Label inventory",
        "",
        "What labels files exist beneath the scanned root, and what is in them. Every",
        "path is emitted relative to the root, which appears as "
        f"`{redact.ROOT_TOKEN}`.",
        "",
        "## Coverage",
        "",
        f"- `.slp` files seen: {scan.files_seen}",
        f"- candidates: {len(scan.candidates)}",
        f"- excluded, derived filename: {scan.counts_by_rule[discover.DERIVED_FILENAME]}",
        f"- excluded, derived directory: {scan.counts_by_rule[discover.DERIVED_DIR]}",
        f"- directories that could not be read: {scan.unreadable_directories}",
        f"- families: {len(inventory.rows)}",
        "",
        "## Skeleton table",
        "",
    ]

    if inventory.gap.mode_collisions:
        lines += ["### Rows selected by more than one capture mode", ""]
        for collision in inventory.gap.mode_collisions:
            modes = ", ".join(collision.modes)
            counts = ", ".join(str(c) for c in collision.node_counts)
            lines.append(
                f"- `({collision.species}, {collision.root_type}, "
                f"age: {collision.row_age})` is selected by {modes}, whose files carry "
                f"{counts} nodes. One row cannot describe both."
            )
        lines.append("")

    if inventory.gap.uncovered_species:
        uncovered = sorted(inventory.gap.uncovered_species)
        crops = [n for n in uncovered if n in gap.KNOWN_SPECIES]
        other = [n for n in uncovered if n not in gap.KNOWN_SPECIES]
        lines += ["### Species with no row", ""]
        if crops:
            lines += [f"- {name}" for name in crops]
            lines.append("")
        if other:
            lines += [
                "Derivation is open by design, so a crop nobody has heard of is not",
                "hidden — which means directory names that are not crops also land here.",
                "These are **not** species; they are tokens read off a path:",
                "",
                "- " + ", ".join(other),
                "",
            ]

    if inventory.gap.unparseable_skeletons:
        lines += ["### Skeleton names the existing check cannot resolve", ""]
        for entry in inventory.gap.unparseable_skeletons:
            names = ", ".join(entry.skeleton_names)
            lines.append(f"- {Path(entry.path).name}: {names}")
        lines.append("")

    lines += ["## Directories holding more than one family", ""]
    if inventory.ambiguous_directories:
        lines += [
            "A directory is not a collection. This tool lists what it found and",
            "**makes no determination** about which files form a collection, which",
            "supersedes which, or which should be registered. A person reads this.",
            "",
        ]
        for entry in inventory.ambiguous_directories:
            shown = ", ".join(entry.stems[:_STEMS_SHOWN])
            if entry.family_count > _STEMS_SHOWN:
                shown += f", and {entry.family_count - _STEMS_SHOWN} more"
            lines.append(
                f"- `{entry.path}` holds {entry.family_count} families: {shown}"
            )
    else:
        lines.append(
            "None. The tool still **makes no determination** about collections."
        )
    lines.append("")

    lines += [
        "## How to read this",
        "",
        "`species`, `mode` and `root_type` are **name-derived**: read off the path, not",
        "out of the file. They are *not evidence* of what a file contains. Node counts,",
        "frame counts and instance counts are read from the files themselves and are.",
        "",
        "Referenced video paths are emitted as filenames alone, and any candidate that",
        "could not be expressed relative to the root is reported by filename only.",
        "",
    ]
    return "\n".join(lines)


def write(inventory: Inventory, out_dir: Path) -> tuple[Path, Path]:
    """Write the table and the report into ``out_dir``.

    Args:
        inventory: The completed scan.
        out_dir: Where to write; created if absent. Nothing else is written there.

    Returns:
        The table path and the report path.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    table_path = out_dir / TABLE_FILENAME
    with table_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(inventory.rows)

    report_path = out_dir / REPORT_FILENAME
    report_path.write_text(_render_report(inventory), encoding="utf-8", newline="\n")
    return table_path, report_path
