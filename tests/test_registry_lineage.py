import hashlib
import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import TF_RUN_IDS  # committed real TF-reference run ids (shared)
from sleap_roots_training.registry import cards, chooser, lineage

CPA_PRIMARY = "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
CANOLA_LATERAL = "canola/lateral/240611_083419.multi_instance.n=631"


def _committed():
    matrix = chooser.load_selection_matrix()
    return matrix, cards.expand_rows_to_cards(matrix.rows)


def _lineage_for(*model_ids):
    matrix, all_cards = _committed()
    scope = (
        [c for c in all_cards if c.source_model_id in model_ids]
        if model_ids
        else all_cards
    )
    return lineage.build_lineage("0" * 64, scope, matrix)


def _fake_git(rev="deadbeef\n", status="\n"):
    def run(args, **kwargs):
        kind = "rev-parse" if "rev-parse" in args else "status"
        return SimpleNamespace(stdout=rev if kind == "rev-parse" else status)

    return run


def test_git_sha_env_override(monkeypatch):
    monkeypatch.setenv("SLEAP_ROOTS_TRAINING_GIT_SHA", "override-sha")
    assert lineage.resolve_git_sha() == "override-sha"


def test_git_sha_clean(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: Path("/repo"))
    monkeypatch.setattr(lineage.subprocess, "run", _fake_git())
    assert lineage.resolve_git_sha() == "deadbeef"


def test_git_sha_dirty_suffix(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: Path("/repo"))
    monkeypatch.setattr(lineage.subprocess, "run", _fake_git(status="M file\n"))
    assert lineage.resolve_git_sha() == "deadbeef+dirty"


def test_git_sha_no_repo_falls_back_never_raises(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: None)
    sha = lineage.resolve_git_sha()  # must not raise
    assert sha == "unknown" or sha.startswith("v")


def test_build_lineage_keys_and_values(monkeypatch):
    monkeypatch.setenv("SLEAP_ROOTS_TRAINING_GIT_SHA", "abc123+dirty")
    matrix_hash = hashlib.sha256(b"models: []\n").hexdigest()
    matrix, all_cards = _committed()
    lin = lineage.build_lineage(matrix_hash, all_cards, matrix)
    assert set(lin) == {
        "git_sha",
        "git_dirty",
        "matrix_content_sha256",
        "row_sources",
        "model_origins",
        "sleap_roots_training_version",
        "wandb_version",
        "sleap_roots_contracts_version",
    }
    assert lin["git_sha"] == "abc123+dirty"
    assert lin["git_dirty"] is True
    assert lin["matrix_content_sha256"] == matrix_hash
    assert lin["wandb_version"] == importlib.metadata.version("wandb")
    assert lin["sleap_roots_contracts_version"] == importlib.metadata.version(
        "sleap-roots-contracts"
    )


def test_chooser_matrix_sha256_matches_file(tmp_path):
    from sleap_roots_training.registry import chooser

    matrix = tmp_path / "m.yaml"
    matrix.write_bytes(b"models: []\n")
    assert chooser.matrix_sha256(matrix) == hashlib.sha256(b"models: []\n").hexdigest()
    # Packaged default is a 64-hex digest.
    assert len(chooser.matrix_sha256()) == 64


def _flatten_keys(obj, prefix=""):
    """Return the full nested keyset of a config (both bare and dotted keys)."""
    keys = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            dotted = f"{prefix}.{key}" if prefix else key
            keys.add(key)
            keys.add(dotted)
            keys |= _flatten_keys(value, dotted)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item, prefix)
    return keys


@pytest.mark.parametrize("run_id", TF_RUN_IDS)
def test_lineage_coexists_with_real_run_config(run_id, tf_config, monkeypatch):
    # Exercise lineage against a committed real W&B run config (not a hand-rolled dict):
    # the lineage keys must be disjoint from the config's full nested keyset, and the
    # combined mapping must round-trip through JSON unchanged.
    monkeypatch.setenv("SLEAP_ROOTS_TRAINING_GIT_SHA", "abc123")
    config = tf_config(run_id)
    matrix, all_cards = _committed()
    lin = lineage.build_lineage(
        hashlib.sha256(b"models: []\n").hexdigest(), all_cards, matrix
    )
    assert set(lin).isdisjoint(_flatten_keys(config))
    merged = {**config, **lin}
    assert json.loads(json.dumps(merged)) == merged


# --- per-row and per-model provenance (add-wheat-sorghum-production-cards) ---


def test_lineage_no_longer_claims_one_source_for_the_whole_matrix():
    # Rows and models come from more than one place, so a single source/date/snapshot
    # for the run would be false for some of its cards.
    lin = _lineage_for()
    for key in ("selection_matrix_source", "selection_matrix_date", "models_snapshot"):
        assert key not in lin
    for name in ("SELECTION_MATRIX_SOURCE", "SELECTION_MATRIX_DATE", "MODELS_SNAPSHOT"):
        assert not hasattr(lineage, name)


def test_a_generalist_card_records_every_row_that_names_it_and_one_origin():
    lin = _lineage_for(CPA_PRIMARY)
    assert [(r["species"], r["mode"]) for r in lin["row_sources"]] == [
        ("canola", "cylinder"),
        ("pennycress", "cylinder"),
        ("arabidopsis", "multiplant cylinder"),
        ("arabidopsis", "cylinder"),
    ]
    assert [o["model_id"] for o in lin["model_origins"]] == [CPA_PRIMARY]


def test_rows_are_scoped_to_the_card_they_back_not_its_species():
    lin = _lineage_for(CANOLA_LATERAL)
    assert [(r["species"], r["mode"]) for r in lin["row_sources"]] == [
        ("canola", "cylinder"),
        ("pennycress", "cylinder"),
    ]


def test_full_scope_records_every_row_and_every_origin():
    matrix, _ = _committed()
    lin = _lineage_for()
    assert len(lin["row_sources"]) == len(matrix.rows)
    assert {o["model_id"] for o in lin["model_origins"]} == set(matrix.origins)


def test_records_carry_the_raw_age_and_source_and_origins_are_sorted():
    matrix, _ = _committed()
    lin = _lineage_for()
    first = matrix.rows[0]
    assert lin["row_sources"][0] == {
        "species": first.species,
        "mode": first.mode,
        "age": first.age,  # the raw comma-list, not the parsed window
        "source": first.source,
    }
    ids = [o["model_id"] for o in lin["model_origins"]]
    assert ids == sorted(ids)
    origin = matrix.origins[ids[0]]
    assert lin["model_origins"][0] == {
        "model_id": ids[0],
        "snapshot": origin.snapshot,
        "location": origin.location,
        "pinned_by": origin.pinned_by,
    }


def test_lineage_round_trips_through_json():
    lin = _lineage_for()
    assert json.loads(json.dumps(lin)) == lin
