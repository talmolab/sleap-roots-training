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
    # The stub models-root uses unzipped dirs -> honestly flagged as unpinned.
    assert "UNPINNED" in result.output


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
    import wandb

    # Spy (record) rather than raise, so we can POSITIVELY assert nothing ran —
    # asserting only a non-zero exit would also pass if a regression called wandb
    # and then blew up (CliRunner swallows the exception into the exit code).
    calls = []
    monkeypatch.setattr(wandb, "init", lambda *a, **k: calls.append("init"))
    monkeypatch.setattr(
        publish, "resolve_all", lambda *a, **k: calls.append("resolve_all") or []
    )
    monkeypatch.setattr(
        publish, "publish_card", lambda *a, **k: calls.append("publish")
    )
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
    assert calls == []  # nothing resolved, no run created, nothing published


def test_execute_yes_seeds_and_reports(monkeypatch, tiny_matrix, stub_models_root):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    import wandb

    from sleap_roots_training.registry import cards

    init_calls = {}

    def fake_init(job_type=None, config=None, **kw):
        init_calls["config"] = config
        return SimpleNamespace(finish=lambda: None)

    resolve_calls = {}

    def fake_resolve_all(card_list, root, checksums):
        resolve_calls["collections"] = [cards.collection_id(c) for c in card_list]
        return [(c, root) for c in card_list]

    seed_calls = {}

    def fake_seed(resolved, cfg, run, *, api=None, force=False):
        seed_calls["n"] = len(resolved)
        seed_calls["force"] = force
        return {"published": ["soybean-cylinder-primary-age2-3"], "skipped": []}

    monkeypatch.setattr(wandb, "init", fake_init)
    monkeypatch.setattr(publish, "resolve_all", fake_resolve_all)
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
    # --only scoped BOTH resolution and publishing to the one canary card.
    assert resolve_calls["collections"] == ["soybean-cylinder-primary-age2-3"]
    assert seed_calls["n"] == 1
    assert "published" in result.output


def test_only_unknown_fails_fast(monkeypatch, tiny_matrix, stub_models_root):
    _no_wandb(monkeypatch)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--only",
            "does-not-exist",
        ]
    )
    assert result.exit_code != 0
    assert "unknown" in result.output.lower()


def test_only_scopes_dry_run(monkeypatch, tiny_matrix, stub_models_root):
    _no_wandb(monkeypatch)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--only",
            "soybean-cylinder-primary-age2-3",
        ]
    )
    assert result.exit_code == 0
    assert "soybean-cylinder-primary-age2-3" in result.output
    assert "soybean-cylinder-lateral-age2-3" not in result.output  # scoped out


def test_verify_only_scopes(monkeypatch, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    seen = {}

    def fake_verify(cfg, expected, api=None):
        seen["expected"] = list(expected)
        return {"present": list(expected), "missing": []}

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--verify",
            "--only",
            "soybean-cylinder-primary-age2-3",
        ]
    )
    assert result.exit_code == 0
    assert seen["expected"] == ["soybean-cylinder-primary-age2-3"]  # scoped


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


def test_dry_run_resolves_real_zip(monkeypatch, tmp_path):
    # Compose the REAL resolver (sha-verify + extract + locate) through the CLI, not
    # just the pre-unzipped dir form.
    import hashlib
    import zipfile

    _no_wandb(monkeypatch)
    root = tmp_path / "snap"

    def make(model_id):
        path = root / f"{model_id}.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("best_model.h5", b"weights")
            zf.writestr("training_config.json", b"{}")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    sha_p, sha_l = make("soy/p"), make("soy/l")
    matrix = tmp_path / "m.yaml"
    matrix.write_text(
        "models:\n"
        "  - species: soybean\n"
        "    mode: cylinder\n"
        '    age: "2, 3"\n'
        "    primary_model_id: soy/p\n"
        "    lateral_model_id: soy/l\n"
        "    crown_model_id: null\n"
        "checksums:\n"
        f"  soy/p: {sha_p}\n"
        f"  soy/l: {sha_l}\n"
    )
    result = _invoke(["--selection-matrix", str(matrix), "--models-root", str(root)])
    assert result.exit_code == 0, result.output
    assert result.output.count("[ok]") == 2  # both real zips resolved (pinned)
    assert "MISSING" not in result.output.upper()
    assert "UNPINNED" not in result.output  # zip form is snapshot-pinned
