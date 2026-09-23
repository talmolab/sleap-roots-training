"""Walk a share root, exclude derived files, and group what remains into families.

Exclusion is by **filename shape as well as directory**, and the filename rule is the
operative one. Measured over one share root, ``*.predictions.slp`` inference output
accounts for 13,164 of 18,099 ``.slp`` files, and thousands of derived files sit outside
every ``models/``, ``predictions/`` and ``train_test_split*/`` directory — a
directory-only rule admits them all.

Families are keyed on ``(directory, stem, suffix)``. Keying on the basename alone is
wrong: ``labels.vNNN.slp`` occurs 57 times across 23 directories spanning five species
and both capture modes, and 88 versioned basenames collide across directories, so one
rice file would supersede 56 unrelated ones.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

#: Exclusion rule: the filename says the file is inference output.
DERIVED_FILENAME = "derived-filename"

#: Exclusion rule: the file sits under a directory that only holds derived data.
DERIVED_DIR = "derived-directory"

#: Suffix that marks inference output, wherever the file happens to live.
_PREDICTIONS_SUFFIX = ".predictions.slp"

#: Directory names whose contents are derived. ``train_test_split`` is a prefix match —
#: real directories carry a ratio, e.g. ``train_test_split_0.8``.
_DERIVED_DIRS = ("models", "predictions")
_DERIVED_DIR_PREFIXES = ("train_test_split",)

#: A version token: ``v001``, optionally carrying trailing text as in ``v001_ana``.
_VERSION = re.compile(r"^v(\d+)(?P<trailing>_.*)?$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedName:
    """A labels filename split into the parts the family key is built from.

    Attributes:
        stem: The basename with only its version token removed, all other text kept.
            Retaining the trailing text is what keeps two labelers' files apart rather
            than letting one supersede the other.
        version: The version number, or ``None`` for an unversioned file. Unversioned
            does not mean scratch: the newest labeling on the measured share is
            unversioned.
        suffix: The full suffix chain, which keeps ``.slp`` distinct from ``.pkg.slp``.
    """

    stem: str
    version: Optional[int]
    suffix: str


@dataclass(frozen=True)
class Candidate:
    """A labels file that survived exclusion.

    Attributes:
        path: Absolute path to the file.
        parsed: Its parsed name.
    """

    path: Path
    parsed: ParsedName

    @property
    def version(self) -> Optional[int]:
        """The candidate's version, or ``None`` if unversioned."""
        return self.parsed.version


@dataclass
class ScanResult:
    """What one walk found, including what it could not read.

    Attributes:
        root: The root that was walked.
        candidates: Files that survived exclusion.
        exclusions: Excluded file to the rule that removed it.
        files_seen: Every ``.slp`` encountered, excluded or not.
        unreadable_paths: Directories the walk could not list.
    """

    root: Path
    candidates: list[Candidate] = field(default_factory=list)
    exclusions: dict[Path, str] = field(default_factory=dict)
    files_seen: int = 0
    unreadable_paths: list[Path] = field(default_factory=list)

    @property
    def unreadable_directories(self) -> int:
        """How many directories could not be listed."""
        return len(self.unreadable_paths)

    @property
    def counts_by_rule(self) -> dict[str, int]:
        """How many files each exclusion rule removed."""
        counts = {DERIVED_FILENAME: 0, DERIVED_DIR: 0}
        for rule in self.exclusions.values():
            counts[rule] = counts.get(rule, 0) + 1
        return counts


@dataclass
class Family:
    """One labeling effort's versions, in one directory.

    Attributes:
        directory: The containing directory.
        stem: The version-stripped basename.
        suffix: The full suffix chain.
        members: Every version found, ordered oldest to newest.
        twins: Keys of families that are the same effort in another representation — a
            ``.slp`` and a ``.pkg.slp`` at the same version reference and embed the same
            images. Cross-referenced, never merged.
    """

    directory: Path
    stem: str
    suffix: str
    members: list[Candidate] = field(default_factory=list)
    twins: set[tuple[Path, str, str]] = field(default_factory=set)

    @property
    def key(self) -> tuple[Path, str, str]:
        """The grouping key: directory, stem, suffix."""
        return (self.directory, self.stem, self.suffix)

    @property
    def latest(self) -> Candidate:
        """The highest-versioned member; an unversioned member sorts lowest."""
        return max(self.members, key=lambda c: (c.version is not None, c.version or 0))


def parse_version(path: Path) -> ParsedName:
    """Split a labels filename into stem, version and suffix chain.

    Four suffix shapes occur on the share: ``.vNNN.slp``, ``.vNNN.pkg.slp``,
    ``.vNNN_<text>.slp`` and ``.<text>.vNNN.slp``.

    Args:
        path: The file, or just its name.

    Returns:
        The parsed name. An unversioned filename yields ``version=None`` and keeps its
        whole basename as the stem.
    """
    parts = path.name.split(".")
    suffix_parts = [parts.pop()]
    if parts and parts[-1].lower() == "pkg":
        suffix_parts.insert(0, parts.pop())
    suffix = "." + ".".join(suffix_parts)

    for index in range(len(parts) - 1, -1, -1):
        match = _VERSION.match(parts[index])
        if match is None:
            continue
        trailing = match.group("trailing") or ""
        stem = ".".join(parts[:index]) + trailing
        return ParsedName(stem=stem, version=int(match.group(1)), suffix=suffix)

    return ParsedName(stem=".".join(parts), version=None, suffix=suffix)


def _exclusion_rule(path: Path, root: Path) -> Optional[str]:
    """Return the rule excluding ``path``, or ``None`` if it is a candidate."""
    if path.name.lower().endswith(_PREDICTIONS_SUFFIX):
        return DERIVED_FILENAME
    for part in path.relative_to(root).parts[:-1]:
        lowered = part.lower()
        if lowered in _DERIVED_DIRS or lowered.startswith(_DERIVED_DIR_PREFIXES):
            return DERIVED_DIR
    return None


def walk(root: Path) -> ScanResult:
    """Enumerate ``.slp`` files beneath ``root``, excluding derived ones.

    Symlinks are not followed, so the walk cannot loop or wander off the share. A
    directory that cannot be listed is counted and named rather than skipped silently:
    ``os.walk`` discards those errors by default, and for a tool whose purpose is to
    establish what exists, a silent undercount would falsify its own coverage evidence.

    Args:
        root: Directory to walk.

    Returns:
        The scan result, including exclusions and unreadable directories.
    """
    root = Path(root)
    result = ScanResult(root=root)

    def _record_error(error: OSError) -> None:
        result.unreadable_paths.append(Path(error.filename))

    for directory, _subdirs, filenames in os.walk(
        root, onerror=_record_error, followlinks=False
    ):
        for filename in sorted(filenames):
            if not filename.lower().endswith(".slp"):
                continue
            path = Path(directory) / filename
            result.files_seen += 1
            rule = _exclusion_rule(path, root)
            if rule is not None:
                result.exclusions[path] = rule
            else:
                result.candidates.append(
                    Candidate(path=path, parsed=parse_version(path))
                )

    return result


def group(candidates: Iterable[Candidate]) -> list[Family]:
    """Group candidates into version families and cross-reference packaged twins.

    Args:
        candidates: Candidates from :func:`walk`.

    Returns:
        Families, ordered by directory then stem then suffix.
    """
    families: dict[tuple[Path, str, str], Family] = {}
    for candidate in candidates:
        key = (candidate.path.parent, candidate.parsed.stem, candidate.parsed.suffix)
        family = families.get(key)
        if family is None:
            family = Family(directory=key[0], stem=key[1], suffix=key[2])
            families[key] = family
        family.members.append(candidate)

    for family in families.values():
        family.members.sort(key=lambda c: (c.version is not None, c.version or 0))
        for other in families.values():
            if other.key == family.key:
                continue
            if other.directory == family.directory and other.stem == family.stem:
                family.twins.add(other.key)

    return sorted(families.values(), key=lambda f: (f.directory, f.stem, f.suffix))
