from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from conftest import write_matrix

from sleap_roots_training import cli
from sleap_roots_training.registry import publish

# ``tiny_matrix`` and ``stub_models_root`` are shared fixtures (see tests/conftest.py).


def _invoke(args, **kw):
    return CliRunner().invoke(cli.main, ["seed-registry", *args], **kw)


#: Every ``wandb.Api()`` construction attempted by a CLI test, recorded by the backstop.
API_CALLS: list = []


@pytest.fixture(autouse=True)
def _no_live_wandb_api(monkeypatch):
    """Backstop: no CLI test may build a real ``wandb.Api``.

    Constructing one validates the key over the network (wandb 0.28), so a test that
    reaches it by accident would contact api.wandb.ai with a fake key. This spy records
    the attempt and raises; a test that needs a registry patches ``wandb.Api`` with an
    offline fake after this runs.
    """
    import wandb

    API_CALLS.clear()

    def spy(*a, **k):
        API_CALLS.append("Api")
        raise AssertionError("a CLI test built a real wandb.Api")

    monkeypatch.setattr(wandb, "Api", spy)


#: The real pre-pass, kept so a test can opt back out of the module-wide stub below.
_REAL_UNPROMOTED = getattr(publish, "unpromoted_collections", None)


@pytest.fixture(autouse=True)
def _promotion_check_passes(monkeypatch):
    """Default: every in-scope collection already carries the alias.

    The pre-pass reads the registry, so without this every default-alias --execute test
    would reach the network. Guard-2 tests override it with ``_stub_promotion_check``
    or restore ``_REAL_UNPROMOTED``.
    """
    _stub_promotion_check(monkeypatch)


def _verify_report(
    present=(),
    missing=(),
    legacy=(),
    orphans=(),
    indeterminate=(),
    orphans_suppressed=False,
):
    return {
        "present": list(present),
        "missing": list(missing),
        "legacy": list(legacy),
        "orphans": list(orphans),
        "indeterminate": list(indeterminate),
        "orphans_suppressed": orphans_suppressed,
    }


def _no_wandb(monkeypatch):
    """Make any wandb.init / publish_card call fail the test loudly."""
    import wandb

    def boom(*a, **k):  # pragma: no cover - only hit on a bug
        raise AssertionError("unexpected wandb call")

    monkeypatch.setattr(wandb, "init", boom)
    monkeypatch.setattr(publish, "publish_card", boom)


def _stub_promotion_check(monkeypatch, unpromoted=()):
    """Stub the default-alias promotion pre-pass to report ``unpromoted``."""
    monkeypatch.setattr(
        publish,
        "unpromoted_collections",
        lambda *a, **k: sorted(unpromoted),
        raising=False,
    )


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


def test_execute_declined_publishes_nothing(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
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
    # It must be the DECLINE that stopped it, not some earlier refusal.
    assert "Publish" in result.output
    assert calls == []  # nothing resolved, no run created, nothing published


def test_execute_yes_seeds_and_reports(monkeypatch, tiny_matrix, stub_models_root):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    import wandb

    from sleap_roots_training.registry import cards

    init_calls = {}

    def fake_init(job_type=None, config=None, project=None, entity=None, **kw):
        init_calls["config"] = config
        # A real run reports the project it was started in; the seed checks it.
        return SimpleNamespace(project=project, entity=entity, finish=lambda: None)

    resolve_calls = {}

    def fake_resolve_all(card_list, root, checksums):
        resolve_calls["collections"] = [cards.collection_id(c) for c in card_list]
        return [(c, root) for c in card_list]

    seed_calls = {}

    def fake_seed(resolved, cfg, run, *, api=None, force=False):
        seed_calls["n"] = len(resolved)
        seed_calls["force"] = force
        return {"published": ["soy-p"], "skipped": [], "failed": [], "stale": []}

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

    def fake_verify(cfg, expected, api=None, *, report_orphans=True):
        seen["expected"] = list(expected)
        seen["report_orphans"] = report_orphans
        return _verify_report(
            present=list(expected), orphans_suppressed=not report_orphans
        )

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
        lambda cfg, expected, api=None, **kw: _verify_report(
            present=["soy-p"], missing=["soy-l"]
        ),
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
        '    source: "test row"\n'
        "checksums:\n"
        f"  soy/p: {sha_p}\n"
        f"  soy/l: {sha_l}\n"
        "origins:\n"
        '  soy/p: {snapshot: null, location: "test location", pinned_by: "test pin"}\n'
        '  soy/l: {snapshot: null, location: "test location", pinned_by: "test pin"}\n'
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


@pytest.mark.parametrize(
    "kw, needles",
    [
        ({"drop": [("row", 0, "source")]}, ("row 0", "source")),
        ({"drop": [("origin", "x/p/1")]}, ("x/p/1",)),
    ],
    ids=["no source", "no origin"],
)
def test_missing_provenance_is_a_clean_error_not_a_traceback(
    monkeypatch, tmp_path, stub_models_root, kw, needles
):
    _no_wandb(monkeypatch)
    row = {"species": "soybean", "mode": "cylinder", "age": "2, 3"}
    bad = write_matrix(
        tmp_path / "bad.yaml", [{**row, "primary_model_id": "x/p/1"}], **kw
    )
    result = _invoke(
        ["--selection-matrix", str(bad), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code != 0
    assert "Error:" in result.output
    for needle in needles:
        assert needle in result.output
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
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    monkeypatch.setenv("WANDB_API_KEY", "secret")

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
        return {
            "published": seen["published"],
            "skipped": [],
            "failed": [],
            "stale": [],
        }

    monkeypatch.setattr(
        wandb,
        "init",
        lambda **kw: SimpleNamespace(
            project=kw.get("project"), entity=kw.get("entity"), finish=lambda: None
        ),
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
        return _verify_report(present=list(expected))

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code == 0, result.output
    assert verified["expected"] == sorted(
        ["SENTINEL-primary-soy_p", "SENTINEL-lateral-soy_l"]
    )


def test_verify_only_suppresses_orphans_and_says_so(monkeypatch, tiny_matrix):
    # 4.3. cli.py filters all_cards BEFORE the expected set is computed, so a canary
    # `--verify --only <one>` would report every other collection as orphaned.
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    seen = {}

    def fake_verify(cfg, expected, api=None, *, report_orphans=True):
        seen["report_orphans"] = report_orphans
        return _verify_report(
            present=list(expected), orphans_suppressed=not report_orphans
        )

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--verify", "--only", "soy-p"]
    )
    assert result.exit_code == 0, result.output
    assert seen["report_orphans"] is False
    assert "suppressed under --only" in result.output


def test_verify_without_only_asks_for_orphans(monkeypatch, tiny_matrix):
    # The negative control: suppression must be scoped to --only, not always on.
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    seen = {}

    def fake_verify(cfg, expected, api=None, *, report_orphans=True):
        seen["report_orphans"] = report_orphans
        return _verify_report(present=list(expected), orphans=["old-collection"])

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code == 0, result.output  # an orphan alone does not fail
    assert seen["report_orphans"] is True
    assert "orphan: old-collection" in result.output


def test_verify_fails_on_legacy_metadata(monkeypatch, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        publish,
        "verify_registry",
        lambda cfg, expected, api=None, **kw: _verify_report(
            present=["soy-p", "soy-l"], legacy=["soy-l"]
        ),
    )
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code != 0  # a card the consumer cannot read IS a failure
    assert "LEGACY METADATA: soy-l" in result.output


def test_seed_reports_failed_and_exits_non_zero(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    # 4.13's operator-facing half: a partial failure must be visible AND non-zero.
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    import wandb

    monkeypatch.setattr(
        wandb,
        "init",
        lambda **kw: SimpleNamespace(
            project=kw.get("project"), entity=kw.get("entity"), finish=lambda: None
        ),
    )
    monkeypatch.setattr(
        publish,
        "resolve_all",
        lambda card_list, root, ck: [(c, root) for c in card_list],
    )
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda resolved, cfg, run, **kw: {
            "published": ["soy-p"],
            "skipped": [],
            "failed": ["soy-l"],
            "stale": [],
        },
    )
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
            "--yes",
        ]
    )
    assert result.exit_code != 0
    assert "FAILED (1): ['soy-l']" in result.output
    assert "published (1): ['soy-p']" in result.output  # the partial report survives


def test_seed_reports_stale_skips_and_exits_non_zero(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    # 4.10's operator-facing half: the skip path is the default on every re-run, so a
    # half-migrated collection must not be reported as a clean no-op.
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    import wandb

    monkeypatch.setattr(
        wandb,
        "init",
        lambda **kw: SimpleNamespace(
            project=kw.get("project"), entity=kw.get("entity"), finish=lambda: None
        ),
    )
    monkeypatch.setattr(
        publish,
        "resolve_all",
        lambda card_list, root, ck: [(c, root) for c in card_list],
    )
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda resolved, cfg, run, **kw: {
            "published": [],
            "skipped": ["soy-p"],
            "failed": [],
            "stale": ["soy-p"],
        },
    )
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
            "--yes",
        ]
    )
    assert result.exit_code != 0
    assert "STALE metadata on already-seeded (1): ['soy-p']" in result.output


def _execute_with_fake_run(
    monkeypatch,
    tiny_matrix,
    stub_models_root,
    *,
    run_project=None,
    run_entity=None,
    disabled=False,
    finish_raises=False,
):
    """Run ``seed-registry --execute --yes`` against faked wandb; return the call log.

    ``run_project`` / ``run_entity`` are what the fake run reports. ``None`` means "what
    it was asked for", which is what wandb does outside a sweep/launch context.
    Callers isolate the environment (``isolate_wandb_env``) first; this sets only the
    API key the credential guard needs.
    """
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    calls = {"init": 0, "finish": [], "seed": 0}

    def fake_init(job_type=None, config=None, project=None, entity=None, **kw):
        calls["init"] += 1
        calls["project"], calls["entity"] = project, entity

        def finish(exit_code=None):
            calls["finish"].append(exit_code)
            if finish_raises:
                raise ConnectionError("teardown failed")

        return SimpleNamespace(
            project=project if run_project is None else run_project,
            entity=entity if run_entity is None else run_entity,
            disabled=disabled,
            finish=finish,
        )

    def fake_seed(resolved, cfg, run, *, api=None, force=False):
        calls["seed"] += 1
        return {"published": [], "skipped": [], "failed": [], "stale": []}

    monkeypatch.setattr(wandb, "init", fake_init)
    monkeypatch.setattr(
        publish, "resolve_all", lambda cards, root, sums: [(c, root) for c in cards]
    )
    monkeypatch.setattr(publish, "seed_registry", fake_seed)
    calls["result"] = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            "--execute",
            "--yes",
        ]
    )
    return calls


@pytest.mark.parametrize("seed_env", [None, "", "   "], ids=["unset", "empty", "blank"])
def test_seed_run_uses_the_default_project(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env, seed_env
):
    if seed_env is not None:
        monkeypatch.setenv("SLEAP_ROOTS_SEED_PROJECT", seed_env)
    calls = _execute_with_fake_run(monkeypatch, tiny_matrix, stub_models_root)
    assert calls["result"].exit_code == 0, calls["result"].output
    assert calls["project"] == "sleap-roots-training"
    assert calls["entity"] == "eberrigan-salk-institute-for-biological-studies"
    assert calls["finish"] == [None]  # a normal run is closed normally


def test_seed_project_is_overridable(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    monkeypatch.setenv("SLEAP_ROOTS_SEED_PROJECT", "other")
    monkeypatch.setenv("WANDB_ENTITY", "some-entity")
    calls = _execute_with_fake_run(monkeypatch, tiny_matrix, stub_models_root)
    assert calls["result"].exit_code == 0, calls["result"].output
    # The configured entity is passed, not a hard-coded default.
    assert (calls["entity"], calls["project"]) == ("some-entity", "other")


def test_seed_project_does_not_depend_on_the_working_directory(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env, tmp_path
):
    # Not redundant with the default test: it catches a default built from
    # `Path.cwd().name`, which CI would mask because its checkout directory is itself
    # named `sleap-roots-training`.
    projects = []
    for name in ("a", "b"):
        workdir = tmp_path / name
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        calls = _execute_with_fake_run(monkeypatch, tiny_matrix, stub_models_root)
        assert calls["result"].exit_code == 0, calls["result"].output
        projects.append(calls["project"])
    assert projects == ["sleap-roots-training", "sleap-roots-training"]


@pytest.mark.parametrize(
    "reported",
    [{"run_project": "some-cwd-name"}, {"run_entity": "someone-personal"}],
    ids=["project", "entity"],
)
def test_a_dropped_target_aborts_the_seed(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env, reported
):
    # Inside a sweep/launch context wandb drops project= AND entity= with only a
    # printed warning.
    calls = _execute_with_fake_run(
        monkeypatch, tiny_matrix, stub_models_root, **reported
    )
    output = calls["result"].output
    assert calls["result"].exit_code != 0
    assert calls["seed"] == 0  # nothing published
    assert calls["finish"] == [1]  # the stray run is closed as FAILED, not finished
    assert "nothing published" in output
    assert list(reported.values())[0] in output
    assert (
        "eberrigan-salk-institute-for-biological-studies/sleap-roots-training" in output
    )


def test_a_disabled_run_aborts_with_a_disabled_hint(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    # WANDB_MODE=disabled returns a no-op run whose project is hard-coded to "dummy".
    calls = _execute_with_fake_run(
        monkeypatch, tiny_matrix, stub_models_root, run_project="dummy", disabled=True
    )
    assert calls["result"].exit_code != 0
    assert calls["seed"] == 0
    assert "WANDB_MODE=disabled" in calls["result"].output
    assert "sweep" not in calls["result"].output


def test_a_failing_teardown_does_not_mask_the_refusal(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env
):
    calls = _execute_with_fake_run(
        monkeypatch,
        tiny_matrix,
        stub_models_root,
        run_project="some-cwd-name",
        finish_raises=True,
    )
    assert calls["result"].exit_code != 0
    assert calls["seed"] == 0
    assert "nothing published" in calls["result"].output
    assert not isinstance(calls["result"].exception, ConnectionError)


@pytest.mark.parametrize("var", ["WANDB_SWEEP_ID", "WANDB_LAUNCH"])
def test_a_sweep_or_launch_context_is_refused_before_any_run(
    monkeypatch, tiny_matrix, stub_models_root, isolate_wandb_env, var
):
    # Refusing up front leaves no stray run behind at all.
    monkeypatch.setenv(var, "abc123" if var == "WANDB_SWEEP_ID" else "True")
    calls = _execute_with_fake_run(monkeypatch, tiny_matrix, stub_models_root)
    assert calls["result"].exit_code != 0
    assert calls["init"] == 0
    assert calls["seed"] == 0
    assert var in calls["result"].output


# --- alias normalization and the target line (add-wheat-sorghum-production-cards) ---


@pytest.mark.parametrize(
    "mode_args",
    [[], ["--verify"], ["--execute", "--yes"]],
    ids=["dry run", "verify", "execute"],
)
def test_a_blank_alias_is_refused_in_every_mode(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root, mode_args
):
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "")
    calls = []
    monkeypatch.setattr(wandb, "init", lambda *a, **k: calls.append("init"))
    monkeypatch.setattr(
        publish, "verify_registry", lambda *a, **k: calls.append("verify")
    )
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            *mode_args,
        ]
    )
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "SLEAP_ROOTS_MODEL_ALIAS" in result.output
    assert not isinstance(result.exception, ValueError)
    assert calls == [] and API_CALLS == []


def test_a_dry_run_prints_the_target_alias_and_where_it_came_from(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    _no_wandb(monkeypatch)
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "candidate")
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code == 0, result.output
    first = result.output.splitlines()[0]
    assert first.startswith("target: ")
    assert "alias 'candidate' (from SLEAP_ROOTS_MODEL_ALIAS)" in first
    assert "seed project sleap-roots-training" in first


def test_the_default_alias_is_labelled_as_the_default(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    _no_wandb(monkeypatch)
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code == 0, result.output
    assert "alias 'production' (default)" in result.output.splitlines()[0]


def test_verify_prints_the_target_line(monkeypatch, isolate_wandb_env, tiny_matrix):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "candidate")
    monkeypatch.setattr(
        publish,
        "verify_registry",
        lambda cfg, expected, api=None, *, report_orphans=True: _verify_report(
            present=expected
        ),
    )
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0].startswith("target: ")
    assert "alias 'candidate'" in result.output.splitlines()[0]


def test_execute_prints_the_target_line_first(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        wandb,
        "init",
        lambda project=None, entity=None, **kw: SimpleNamespace(
            project=project, entity=entity, finish=lambda: None
        ),
    )
    monkeypatch.setattr(publish, "resolve_all", lambda cs, root, sums: [])
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda *a, **k: {"published": [], "skipped": [], "failed": [], "stale": []},
    )
    _stub_promotion_check(monkeypatch)
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
    assert result.output.splitlines()[0].startswith("target: ")
    assert "alias 'production' (default)" in result.output.splitlines()[0]


# --- guard 1: a non-default alias under --execute requires --only ---


def _spy_everything(monkeypatch):
    """Record (never raise in) every step past the guards. CliRunner swallows raises."""
    import click
    import wandb

    from sleap_roots_training.registry import config as registry_config

    calls = []
    monkeypatch.setattr(
        registry_config, "require_api_key", lambda: calls.append("credential")
    )
    monkeypatch.setattr(click, "confirm", lambda *a, **k: calls.append("confirm"))
    monkeypatch.setattr(wandb, "init", lambda *a, **k: calls.append("init"))
    monkeypatch.setattr(
        publish, "resolve_all", lambda *a, **k: calls.append("resolve_all") or []
    )
    return calls


def _execute(matrix, root, *extra, **kw):
    return _invoke(
        [
            "--selection-matrix",
            str(matrix),
            "--models-root",
            str(root),
            "--execute",
            *extra,
        ],
        **kw,
    )


@pytest.mark.parametrize(
    "extra, kw",
    [
        (["--yes"], {}),
        ([], {"input": "y\n"}),
        (["--yes", "--force"], {}),
    ],
    ids=["--yes", "prompted", "--force"],
)
def test_a_non_default_alias_without_only_is_refused_before_anything(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root, extra, kw
):
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "candidate")
    calls = _spy_everything(monkeypatch)
    result = _execute(tiny_matrix, stub_models_root, *extra, **kw)
    assert result.exit_code == 2, result.output  # click usage error
    assert "candidate" in result.output
    assert "--only" in result.output
    assert calls == [] and API_CALLS == []


def test_a_non_default_alias_dry_run_without_only_is_allowed(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    _no_wandb(monkeypatch)
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "candidate")
    result = _invoke(
        ["--selection-matrix", str(tiny_matrix), "--models-root", str(stub_models_root)]
    )
    assert result.exit_code == 0, result.output


def test_a_non_default_alias_verify_without_only_is_allowed(
    monkeypatch, isolate_wandb_env, tiny_matrix
):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "candidate")
    seen = {}

    def fake_verify(cfg, expected, api=None, *, report_orphans=True):
        seen["alias"] = cfg.alias
        seen["expected"] = sorted(expected)
        return _verify_report(present=expected)

    monkeypatch.setattr(publish, "verify_registry", fake_verify)
    result = _invoke(["--selection-matrix", str(tiny_matrix), "--verify"])
    assert result.exit_code == 0, result.output
    assert seen == {"alias": "candidate", "expected": ["soy-l", "soy-p"]}


def test_the_default_alias_without_only_is_not_refused_by_the_alias_guard(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        wandb,
        "init",
        lambda project=None, entity=None, **kw: SimpleNamespace(
            project=project, entity=entity, finish=lambda: None
        ),
    )
    monkeypatch.setattr(publish, "resolve_all", lambda cs, root, sums: [])
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda *a, **k: {"published": [], "skipped": [], "failed": [], "stale": []},
    )
    _stub_promotion_check(monkeypatch)
    result = _execute(tiny_matrix, stub_models_root, "--yes")
    assert result.exit_code == 0, result.output


# --- guard 2: a first-time production link requires --promote ---


@pytest.mark.parametrize(
    "extra, kw",
    [(["--yes"], {}), ([], {"input": "y\n"}), (["--yes", "--force"], {})],
    ids=["--yes", "prompted", "--force"],
)
def test_a_first_time_production_link_without_promote_is_refused(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root, extra, kw
):
    calls = _spy_everything(monkeypatch)
    checked = []

    def unpromoted(cfg, cards_, api=None):
        checked.append(cfg.alias)
        return ["soy-p"]

    monkeypatch.setattr(publish, "unpromoted_collections", unpromoted)
    result = _execute(tiny_matrix, stub_models_root, "--only", "soy-p", *extra, **kw)
    assert result.exit_code == 1, result.output  # a CLI error, not a usage error
    assert "soy-p" in result.output
    assert "--promote" in result.output
    assert checked == ["production"]  # the check ran, --force or not
    assert calls == ["credential"]  # no prompt, no resolve, no run


def test_promote_lets_a_first_time_link_proceed(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    _stub_promotion_check(monkeypatch, unpromoted=["soy-p"])
    seeded = []
    monkeypatch.setattr(
        wandb,
        "init",
        lambda project=None, entity=None, **kw: SimpleNamespace(
            project=project, entity=entity, finish=lambda: None
        ),
    )
    monkeypatch.setattr(publish, "resolve_all", lambda cs, root, sums: [])
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda *a, **k: seeded.append(1)
        or {"published": ["soy-p"], "skipped": [], "failed": [], "stale": []},
    )
    result = _execute(
        tiny_matrix, stub_models_root, "--yes", "--only", "soy-p", "--promote"
    )
    assert result.exit_code == 0, result.output
    assert seeded == [1]


@pytest.mark.parametrize("promote", [[], ["--promote"]], ids=["plain", "--promote"])
def test_an_already_promoted_scope_proceeds_with_or_without_promote(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root, promote
):
    import wandb

    monkeypatch.setenv("WANDB_API_KEY", "secret")
    monkeypatch.setattr(
        wandb,
        "init",
        lambda project=None, entity=None, **kw: SimpleNamespace(
            project=project, entity=entity, finish=lambda: None
        ),
    )
    monkeypatch.setattr(publish, "resolve_all", lambda cs, root, sums: [])
    monkeypatch.setattr(
        publish,
        "seed_registry",
        lambda *a, **k: {
            "published": [],
            "skipped": ["soy-p"],
            "failed": [],
            "stale": [],
        },
    )
    result = _execute(
        tiny_matrix, stub_models_root, "--yes", "--only", "soy-p", *promote
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "args, alias",
    [
        (["--execute", "--yes", "--promote"], None),  # no --only
        (["--execute", "--yes", "--only", "soy-p", "--promote"], "candidate"),
        (["--only", "soy-p", "--promote"], None),  # dry run
        (["--verify", "--only", "soy-p", "--promote"], None),
    ],
    ids=["no --only", "non-default alias", "dry run", "verify"],
)
def test_promote_is_a_usage_error_where_it_does_not_apply(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root, args, alias
):
    if alias:
        monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", alias)
    calls = _spy_everything(monkeypatch)
    monkeypatch.setattr(
        publish, "verify_registry", lambda *a, **k: calls.append("verify")
    )
    result = _invoke(
        [
            "--selection-matrix",
            str(tiny_matrix),
            "--models-root",
            str(stub_models_root),
            *args,
        ]
    )
    assert result.exit_code == 2, result.output
    assert "--promote" in result.output
    assert calls == [] and API_CALLS == []


def test_a_promotion_check_error_fails_closed_without_a_traceback(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    calls = _spy_everything(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("registry unreachable")

    monkeypatch.setattr(publish, "unpromoted_collections", boom)
    result = _execute(tiny_matrix, stub_models_root, "--yes", "--only", "soy-p")
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "registry unreachable" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "init" not in calls


def test_a_padded_default_alias_is_the_default_and_gets_the_promotion_check(
    monkeypatch, isolate_wandb_env, tiny_matrix, stub_models_root
):
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", " production ")
    calls = _spy_everything(monkeypatch)
    _stub_promotion_check(monkeypatch, unpromoted=["soy-p"])
    result = _execute(tiny_matrix, stub_models_root, "--yes")
    # Not guard 1 (that would be exit 2 naming --only); guard 2 refuses it.
    assert result.exit_code == 1, result.output
    assert "--promote" in result.output
    assert "init" not in calls
