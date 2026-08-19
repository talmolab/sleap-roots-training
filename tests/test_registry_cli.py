from types import SimpleNamespace

from click.testing import CliRunner

from sleap_roots_training import cli
from sleap_roots_training.registry import publish

# ``tiny_matrix`` and ``stub_models_root`` are shared fixtures (see tests/conftest.py).


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
    assert "soy-p" in result.output
    assert "soy-l" in result.output
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
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    # isolate_wandb_env clears WANDB_API_KEY/NETRC (+ registry vars) and repoints HOME at
    # an empty dir, so this fails on the guard even for a contributor who has run
    # `wandb login` locally -- not just on CI runners that happen to lack an ambient netrc.
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
        return {"published": ["soy-p"], "skipped": []}

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
            "soy-p",
        ]
    )
    assert result.exit_code == 0, result.output
    assert init_calls["config"]["git_sha"]  # lineage recorded
    # --only scoped BOTH resolution and publishing to the one canary card.
    assert resolve_calls["collections"] == ["soy-p"]
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
            "soy-p",
        ]
    )
    assert result.exit_code == 0
    assert "soy-p" in result.output
    assert "soy-l" not in result.output  # scoped out


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
            "soy-p",
        ]
    )
    assert result.exit_code == 0
    assert seen["expected"] == ["soy-p"]  # scoped


def test_verify_needs_no_models_root(monkeypatch, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        publish,
        "verify_registry",
        lambda cfg, expected, api=None: {
            "present": ["soy-p"],
            "missing": ["soy-l"],
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


def test_off_vocabulary_mode_is_a_clean_error_not_a_traceback(
    monkeypatch, tmp_path, stub_models_root
):
    # The loader's row-numbered message is what the spec promises operators, but raw it
    # arrives as an unhandled ValueError traceback with the message buried in it. This is
    # the surface a future upstream narrowing of `Mode` would hand to every operator
    # running `seed-registry`, so it has to read like an error, not like a crash.
    _no_wandb(monkeypatch)
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "models:\n"
        "  - species: soybean\n"
        "    mode: teacup\n"
        '    age: "2, 3"\n'
        "    primary_model_id: x/p/1\n"
        "    lateral_model_id: null\n"
        "    crown_model_id: null\n"
        "checksums:\n"
        "  x/p/1: " + "0" * 64 + "\n"
    )
    result = _invoke(
        ["--selection-matrix", str(bad), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code != 0
    # click renders a ClickException as "Error: <message>" and exits; an unhandled
    # ValueError would instead surface here as a non-None exc_info with a traceback.
    assert "Error:" in result.output
    assert "teacup" in result.output
    assert "row 0" in result.output
    assert not isinstance(result.exception, ValueError)


def test_unreadable_matrix_is_a_clean_error_not_a_traceback(
    monkeypatch, tmp_path, stub_models_root
):
    """The CHANGELOG promises a clean error for an *unreadable* matrix, not just a
    rejected one -- and that half was the untested half.

    Only ``mode: teacup`` (a ``ValueError``) was covered above. These three are the ways
    the file itself fails, and each raised a different uncaught type straight through
    the CLI: a directory (click's ``exists=True`` has no ``dir_okay=False``, so it gets
    as far as ``OmegaConf.load``), malformed YAML (``yaml.ParserError``), and a top-level
    sequence (``AttributeError`` from ``data.get``).
    """
    _no_wandb(monkeypatch)

    a_directory = tmp_path / "matrix_dir"
    a_directory.mkdir()
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("models: [\n  - species: soybean\n")
    a_list = tmp_path / "list.yaml"
    a_list.write_text("- species: soybean\n")

    for path in (a_directory, malformed, a_list):
        result = _invoke(
            ["--selection-matrix", str(path), "--models-root", str(stub_models_root)]
        )
        assert result.exit_code != 0, f"{path.name}: expected a failure"
        assert "Error" in result.output, f"{path.name}: {result.output!r}"
        # The name of the thing the operator passed has to be in the message, or the
        # error is unactionable when a script passes the path.
        assert path.name in result.output, f"{path.name}: {result.output!r}"
        # Anything other than a click exception is an unhandled crash: click's test
        # runner stores the raised exception here and would have printed a traceback.
        assert result.exception is None or isinstance(
            result.exception, SystemExit
        ), f"{path.name}: unhandled {type(result.exception).__name__}"


def test_a_stale_old_scheme_only_id_fails_fast(
    monkeypatch, tiny_matrix, stub_models_root
):
    # 3.26. `test_only_unknown_fails_fast` covers only a synthetic "does-not-exist".
    # The collection ids just changed scheme, so the realistic operator error is a
    # runbook/README id from the OLD scheme -- which must fail fast and actionably
    # rather than silently scoping to nothing.
    _no_wandb(monkeypatch)
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--only",
            "canola-cylinder-primary-age2-13",  # the old scheme, as in runbooks
        ]
    )
    assert result.exit_code != 0
    assert "unknown" in result.output.lower()
    assert "canola-cylinder-primary-age2-13" in result.output


def test_publish_only_and_verify_all_use_one_collection_id_scheme(
    monkeypatch, tiny_matrix, stub_models_root
):
    # 3.24: the one-scheme invariant. Patch BOTH `publish.collection_id` and
    # `cards.collection_id` -- publish.py does `from ...cards import collection_id`, so
    # patching only the `cards` attribute leaves the publish path on the real function
    # while cli.py (which goes through `cards.collection_id`) observes the patch, and
    # the test silently proves nothing.
    #
    # The sentinel must be INJECTIVE per card; a constant one trips the duplicate-id
    # guards in cli.py / publish.py before the assertion runs.
    import wandb

    from sleap_roots_training.registry import cards

    def sentinel(card):
        return f"SENTINEL-{card.root_type}-{card.source_model_id.replace('/', '_')}"

    monkeypatch.setattr(cards, "collection_id", sentinel)
    monkeypatch.setattr(publish, "collection_id", sentinel)

    seen = {}

    def fake_seed(resolved, cfg, run, *, api=None, force=False):
        seen["published"] = [publish.collection_id(c) for c, _ in resolved]
        return {"published": seen["published"], "skipped": []}

    monkeypatch.setattr(
        wandb, "init", lambda **kw: SimpleNamespace(finish=lambda: None)
    )
    monkeypatch.setattr(
        publish,
        "resolve_all",
        lambda card_list, root, ck: [(c, root) for c in card_list],
    )
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
            "SENTINEL-primary-soy_p",  # cli.py's --only filter must see the sentinel
        ]
    )
    assert result.exit_code == 0, result.output
    # The publish path agrees with the --only filter...
    assert seen["published"] == ["SENTINEL-primary-soy_p"]

    # ...and so does the --verify expected set, through the same one function.
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    verified = {}

    def fake_verify(cfg, expected, api=None, **kw):
        verified["expected"] = list(expected)
        return {"present": list(expected), "missing": []}

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code == 0, result.output
    assert verified["expected"] == sorted(
        ["SENTINEL-primary-soy_p", "SENTINEL-lateral-soy_l"]
    )
