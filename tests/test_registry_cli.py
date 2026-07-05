from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from sleap_roots_training import cli
from sleap_roots_training.registry import publish

TINY_MATRIX = """\
models:
  - species: soybean
    mode: cylinder
    age: "2, 3"
    primary_model_id: soy/p
    lateral_model_id: soy/l
    crown_model_id: null
checksums:
  soy/p: {sha}
  soy/l: {sha}
""".format(sha="0" * 64)


@pytest.fixture
def tiny_matrix(tmp_path):
    path = tmp_path / "matrix.yaml"
    path.write_text(TINY_MATRIX)
    return path


@pytest.fixture
def stub_models_root(tmp_path):
    """A models-root with the two tiny models as already-unzipped dirs."""
    root = tmp_path / "models"
    for model_id in ("soy/p", "soy/l"):
        model_dir = root / model_id
        model_dir.mkdir(parents=True)
        (model_dir / "best_model.h5").write_bytes(b"w")
        (model_dir / "training_config.json").write_bytes(b"{}")
    return root


def _invoke(args, **kw):
    return CliRunner().invoke(cli.main, ["seed-registry", *args], **kw)


def _no_wandb(monkeypatch):
    """Make any wandb.init / publish_card call fail the test loudly."""
    import wandb

    def boom(*a, **k):  # pragma: no cover - only hit on a bug
        raise AssertionError("unexpected wandb call")

    monkeypatch.setattr(wandb, "init", boom)
    monkeypatch.setattr(publish, "publish_card", boom)


def test_dry_run_default_resolves_without_network(
    monkeypatch, tiny_matrix, stub_models_root
):
    _no_wandb(monkeypatch)
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code == 0, result.output
    assert "soybean-cylinder-primary-age2-3" in result.output
    assert "soybean-cylinder-lateral-age2-3" in result.output


def test_dry_run_reports_missing_model(monkeypatch, tiny_matrix, tmp_path):
    _no_wandb(monkeypatch)
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--models-root", str(empty_root)]
    )
    assert result.exit_code == 0
    assert "MISSING" in result.output.upper()


def test_execute_without_api_key_fails_before_prompt(
    monkeypatch, tiny_matrix, stub_models_root
):
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    _no_wandb(monkeypatch)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
        ]
    )
    assert result.exit_code != 0
    assert "WANDB_API_KEY" in result.output


def test_execute_declined_publishes_nothing(monkeypatch, tiny_matrix, stub_models_root):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    _no_wandb(monkeypatch)  # confirm declined -> no wandb.init
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
        ],
        input="n\n",
    )
    assert result.exit_code != 0  # aborted


def test_execute_yes_seeds_and_reports(monkeypatch, tiny_matrix, stub_models_root):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    import wandb

    init_calls = {}

    def fake_init(job_type=None, config=None, **kw):
        init_calls["config"] = config
        return SimpleNamespace(finish=lambda: None)

    seed_calls = {}

    def fake_seed(cards_, root, checksums, cfg, run, *, force, only):
        seed_calls["force"] = force
        seed_calls["only"] = only
        return {"published": ["soybean-cylinder-primary-age2-3"], "skipped": []}

    monkeypatch.setattr(wandb, "init", fake_init)
    monkeypatch.setattr(publish, "seed_registry", fake_seed)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
            "--yes",
            "--only",
            "soybean-cylinder-primary-age2-3",
        ]
    )
    assert result.exit_code == 0, result.output
    assert init_calls["config"]["git_sha"]  # lineage recorded
    assert seed_calls["only"] == {"soybean-cylinder-primary-age2-3"}
    assert "published" in result.output


def test_verify_needs_no_models_root(monkeypatch, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        publish,
        "verify_registry",
        lambda cfg, expected, api=None: {
            "present": ["soybean-cylinder-primary-age2-3"],
            "missing": ["soybean-cylinder-lateral-age2-3"],
        },
    )
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code != 0  # a missing collection -> non-zero
    assert "missing" in result.output.lower()


def test_missing_models_root_errors_for_execute(monkeypatch, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--execute"])
    assert result.exit_code != 0
    assert "models-root" in result.output.lower()
