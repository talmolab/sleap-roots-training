import hashlib
import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import TF_RUN_IDS  # committed real TF-reference run ids (shared)
from sleap_roots_training.registry import lineage


def _fake_git(rev="deadbeef\n", status="\n"):
    def run(args, **kwargs):
        kind = "rev-parse" if "rev-parse" in args else "status"
        return SimpleNamespace(stdout=rev if kind == "rev-parse" else status)

    return run


def test_git_sha_env_override(monkeypatch):
    monkeypatch.setenv("SLEAP_ROOTS_TRAINING_GIT_SHA", "override-sha")
    assert lineage._resolve_git_sha() == "override-sha"


def test_git_sha_clean(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: Path("/repo"))
    monkeypatch.setattr(lineage.subprocess, "run", _fake_git())
    assert lineage._resolve_git_sha() == "deadbeef"


def test_git_sha_dirty_suffix(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: Path("/repo"))
    monkeypatch.setattr(lineage.subprocess, "run", _fake_git(status="M file\n"))
    assert lineage._resolve_git_sha() == "deadbeef+dirty"


def test_git_sha_no_repo_falls_back_never_raises(monkeypatch):
    monkeypatch.delenv("SLEAP_ROOTS_TRAINING_GIT_SHA", raising=False)
    monkeypatch.setattr(lineage, "_git_root", lambda: None)
    sha = lineage._resolve_git_sha()  # must not raise
    assert sha == "unknown" or sha.startswith("v")


def test_build_lineage_keys_and_values(monkeypatch):
    monkeypatch.setenv("SLEAP_ROOTS_TRAINING_GIT_SHA", "abc123+dirty")
    matrix_hash = hashlib.sha256(b"models: []\n").hexdigest()
    lin = lineage.build_lineage(matrix_hash)
    assert set(lin) == {
        "git_sha",
        "git_dirty",
        "matrix_content_sha256",
        "selection_matrix_source",
        "selection_matrix_date",
        "models_snapshot",
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
    lin = lineage.build_lineage(hashlib.sha256(b"models: []\n").hexdigest())
    assert set(lin).isdisjoint(_flatten_keys(config))
    merged = {**config, **lin}
    assert json.loads(json.dumps(merged)) == merged
