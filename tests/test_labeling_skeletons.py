"""Tests for the committed per-crop labeling skeleton table (design.md Decision 7).

The table is transcribed from an advisory source that says of itself "Query the Bloom
database or check existing test data ... to confirm node counts", so these tests do two
jobs: pin that a gap fails loudly rather than defaulting, and cross-check the one part of
the table that has an independent source in this repo — the rice age split, which
``registry/data/model_selection.yaml`` already encodes.

The verification against the eight published collections lives at the bottom, marked
``integration``: it is what converts the rest of the table from hypothesis to record, and
it downloads multi-gigabyte artifacts, so it is not part of the default run.
"""

from __future__ import annotations

import os

import pytest

from sleap_roots_training.labeling.skeletons import (
    load_skeleton_table,
    lookup_skeleton,
    skeleton_table_sha256,
)
from sleap_roots_training.registry.chooser import (
    load_selection_matrix,
    parse_age_window,
)


def write_table(tmp_path, body: str):
    """Write a skeleton-table YAML and return its path."""
    path = tmp_path / "skeletons.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# The committed table
# --------------------------------------------------------------------------------------


def test_the_committed_table_loads_and_is_hashable():
    """The SHA is what pins which table a package was built against, as for the matrix."""
    rows = load_skeleton_table()

    assert rows
    assert len(skeleton_table_sha256()) == 64


@pytest.mark.parametrize(
    "species, root_type, node_count",
    [
        ("soybean", "primary", 6),
        ("soybean", "lateral", 4),
        ("canola", "primary", 6),
        ("canola", "lateral", 3),
        ("arabidopsis", "primary", 6),
        ("arabidopsis", "lateral", 4),
    ],
)
def test_the_doc_table_is_transcribed_faithfully(species, root_type, node_count):
    """Row-for-row against ``build-labeling-package.md:45-51``.

    Canola's lateral 3 is deliberately included as-is: it is the table's one asymmetry —
    soybean and arabidopsis laterals are both 4 — and transcribing it accurately is what
    lets the verification test find out whether it is real.
    """
    assert lookup_skeleton(species, root_type).node_count == node_count


def test_soybean_matches_the_real_published_artifacts():
    """Verified 2026-08-04 against the WEEP v000 projects and their repaired packages.

    Those files carry ``soybean_primary`` r1-r6 and ``soybean_lateral`` r1-r4, so these
    two rows are record rather than hypothesis. The artifacts are not committed (hundreds
    of MB), so this test pins the *finding*; the integration test below is what re-derives
    it from the registry.
    """
    assert lookup_skeleton("soybean", "primary").node_count == 6
    assert lookup_skeleton("soybean", "lateral").node_count == 4


def test_node_names_and_edges_follow_the_fixed_convention():
    """``r1`` is the base, the last node is the tip, and the edges are a simple chain."""
    skeleton = lookup_skeleton("soybean", "primary").to_skeleton()

    assert [node.name for node in skeleton.nodes] == [
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
    ]
    assert skeleton.name == "soybean_primary"
    assert len(skeleton.edges) == 5


def test_the_skeleton_name_matches_what_the_vault_script_wrote():
    """A new package's skeleton has to be recognizable as the same one the corpus uses."""
    assert lookup_skeleton("soybean", "lateral").to_skeleton().name == "soybean_lateral"


# --------------------------------------------------------------------------------------
# Task 6.3 — a gap fails loudly
# --------------------------------------------------------------------------------------


def test_pennycress_has_no_row_and_fails_rather_than_defaulting():
    """The table ships incomplete on purpose; the source omits pennycress.

    Pennycress is in ``SPECIES_VOCAB`` and has two ``model_selection.yaml`` rows, so a
    caller can reach this. Defaulting to canola's counts — which share a primary model —
    would produce a labeling package that looks fine and cannot be combined with anything.
    """
    with pytest.raises(ValueError) as excinfo:
        lookup_skeleton("pennycress", "primary")

    assert "pennycress" in str(excinfo.value)
    # The error lists what the table does cover, so the reader can see the gap is real.
    assert "soybean" in str(excinfo.value)


def test_a_root_type_the_species_does_not_have_fails():
    """Soybean has no crown row, and inventing one would invent a skeleton."""
    with pytest.raises(ValueError, match="crown"):
        lookup_skeleton("soybean", "crown")


def test_rice_lateral_has_no_row():
    """``model_selection.yaml`` has no rice lateral model either — the two agree."""
    with pytest.raises(ValueError, match="lateral"):
        lookup_skeleton("rice", "lateral", age=3)


# --------------------------------------------------------------------------------------
# Task 6.4 — the rice age split cross-checked against model_selection.yaml
# --------------------------------------------------------------------------------------


def rice_matrix_rows():
    """Return ``{age_window: {root_type, ...}}`` from the committed selection matrix."""
    windows = {}
    for row in load_selection_matrix().rows:
        if row.species != "rice":
            continue
        present = {
            root_type
            for root_type, model_id in (
                ("primary", row.primary_model_id),
                ("lateral", row.lateral_model_id),
                ("crown", row.crown_model_id),
            )
            if model_id
        }
        windows[parse_age_window(row.age)] = present
    return windows


def test_the_rice_age_split_agrees_between_the_two_tables():
    """Young 2-5 DAG is primary + crown; old 6-10 DAG is crown only.

    These tables are transcribed from different sources — the skeleton table from the
    command doc, the matrix from ``models-downloader``'s chooser xlsx — so agreement is
    evidence rather than tautology. Disagreement would mean a package labeled for a root
    type no model predicts, or predictions with no skeleton to correct them against.
    """
    matrix = rice_matrix_rows()
    assert matrix == {(2, 5): {"primary", "crown"}, (6, 10): {"crown"}}

    table = {}
    for row in load_skeleton_table():
        if row.species == "rice":
            table.setdefault(row.age_window, set()).add(row.root_type)
    assert table == matrix


@pytest.mark.parametrize(
    "age, expected",
    [
        (2, {"primary", "crown"}),
        (5, {"primary", "crown"}),
        (6, {"crown"}),
        (10, {"crown"}),
    ],
)
def test_rice_lookup_respects_the_age_window(age, expected):
    resolved = set()
    for root_type in ("primary", "crown"):
        try:
            lookup_skeleton("rice", root_type, age=age)
        except ValueError:
            continue
        resolved.add(root_type)
    assert resolved == expected


def test_an_age_split_species_requires_an_age():
    """Silently picking the first window would label old rice against a young skeleton."""
    with pytest.raises(ValueError, match="an age is required"):
        lookup_skeleton("rice", "crown")


def test_an_age_outside_every_window_fails_with_the_windows_listed():
    with pytest.raises(ValueError, match="14"):
        lookup_skeleton("rice", "crown", age=14)


def test_an_age_agnostic_row_ignores_the_age():
    """Only rice splits, so passing an age elsewhere must not narrow anything."""
    assert lookup_skeleton("soybean", "primary", age=99).node_count == 6


# --------------------------------------------------------------------------------------
# Loader validation — row-numbered, mirroring the selection matrix's loader
# --------------------------------------------------------------------------------------


def test_an_empty_table_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="no `skeletons:` rows"):
        load_skeleton_table(write_table(tmp_path, "skeletons: []\n"))


def test_a_missing_key_is_reported_with_its_row_number(tmp_path):
    body = "skeletons:\n  - species: soybean\n    root_type: primary\n"
    with pytest.raises(ValueError, match="row 0: missing required key 'node_count'"):
        load_skeleton_table(write_table(tmp_path, body))


def test_an_unknown_species_is_reported_with_its_row_number(tmp_path):
    body = "skeletons:\n  - species: wheat\n    root_type: primary\n    node_count: 6\n"
    with pytest.raises(ValueError, match="row 0: unknown species 'wheat'"):
        load_skeleton_table(write_table(tmp_path, body))


def test_an_unknown_root_type_is_reported_with_its_row_number(tmp_path):
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    node_count: 6\n"
        "  - species: soybean\n    root_type: taproot\n    node_count: 6\n"
    )
    with pytest.raises(ValueError, match="row 1: unknown root_type 'taproot'"):
        load_skeleton_table(write_table(tmp_path, body))


@pytest.mark.parametrize("node_count", ["six", 1, 0, -3])
def test_a_node_count_that_cannot_describe_a_root_is_rejected(tmp_path, node_count):
    """Fewer than two nodes leaves no edge to label along."""
    body = (
        f"skeletons:\n  - species: soybean\n    root_type: primary\n"
        f"    node_count: {node_count}\n"
    )
    with pytest.raises(ValueError, match="node_count"):
        load_skeleton_table(write_table(tmp_path, body))


def test_a_gapped_age_window_is_rejected(tmp_path):
    """Same rule the selection matrix applies, so the two files cannot drift on it."""
    body = (
        "skeletons:\n  - species: rice\n    root_type: crown\n"
        '    age: "2, 3, 5"\n    node_count: 6\n'
    )
    with pytest.raises(ValueError, match="not contiguous"):
        load_skeleton_table(write_table(tmp_path, body))


def test_a_duplicate_entry_is_rejected(tmp_path):
    """A silent first-match win is how a table grows two answers to one question."""
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    node_count: 6\n"
        "  - species: soybean\n    root_type: primary\n    node_count: 8\n"
    )
    with pytest.raises(ValueError, match="row 1: duplicate entry"):
        load_skeleton_table(write_table(tmp_path, body))


# --------------------------------------------------------------------------------------
# Task 6.5 — verification against the published collections
# --------------------------------------------------------------------------------------


#: Opt-in for the registry verification below. It is marked ``integration`` (so CI's
#: ``-m "not integration"`` deselects it) *and* gated on this variable, because unlike the
#: other integration tests it downloads 170 MB - 1.2 GB per collection, eight times. A
#: local run should not do that by accident.
_REGISTRY_CHECK_ENV = "SLEAP_ROOTS_LABEL_SKELETON_CHECK"


@pytest.mark.integration
def test_the_table_agrees_with_the_published_label_collections(tmp_path):
    """Read every collection in ``wandb-registry-sleap-roots-labels`` and diff node counts.

    This is what converts the table from hypothesis to record (design.md Decision 7), and
    it is the same check ``#10``'s ``LabelCard.node_count`` will run against the contract's
    skeleton-coherence rule. Run it deliberately::

        SLEAP_ROOTS_LABEL_SKELETON_CHECK=1 uv run pytest -m integration \\
            tests/test_labeling_skeletons.py

    A disagreement is a finding either way — the table may be wrong, or a published
    collection may have been labeled against a skeleton nobody recorded — so it reports
    every mismatch rather than stopping at the first, and names the collection.
    """
    if not os.environ.get(_REGISTRY_CHECK_ENV):
        pytest.skip(
            f"set {_REGISTRY_CHECK_ENV}=1 to download and check the collections"
        )
    wandb = pytest.importorskip("wandb")
    import pathlib

    import sleap_io as sio

    from sleap_roots_training.registry.config import resolve_registry_config

    # Same entity/org resolution the model registry uses, pointed at the labels registry.
    cfg = resolve_registry_config()
    project = f"{cfg.entity}-org/wandb-registry-sleap-roots-labels"
    api = wandb.Api()

    mismatches: list[str] = []
    checked = 0
    for collection in api.artifact_collections(project, "model"):
        artifact = api.artifact(f"{project}/{collection.name}:latest")
        directory = artifact.download(root=str(tmp_path / collection.name))
        for slp in sorted(pathlib.Path(directory).rglob("*.slp")):
            labels = sio.load_slp(str(slp), open_videos=False)
            for skeleton in labels.skeletons:
                species, _, root_type = skeleton.name.partition("_")
                try:
                    row = lookup_skeleton(species, root_type)
                except ValueError as error:
                    mismatches.append(f"{collection.name}: {skeleton.name}: {error}")
                    continue
                checked += 1
                names = tuple(node.name for node in skeleton.nodes)
                if names != row.node_names:
                    mismatches.append(
                        f"{collection.name}: {skeleton.name} has {len(names)} nodes "
                        f"{list(names)}, table says {row.node_count} "
                        f"{list(row.node_names)}"
                    )

    assert checked, "no skeletons were read; the registry query found nothing"
    assert not mismatches, "\n".join(mismatches)
