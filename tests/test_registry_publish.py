import pytest

from sleap_roots_contracts import Selector

from sleap_roots_training.registry import cards, chooser, publish
from sleap_roots_training.registry.cards import Card, card_to_metadata, collection_id
from sleap_roots_training.registry.config import RegistryConfig

CFG = RegistryConfig("ent", "reg", "production")
PROJECT = CFG.registry_project()
CPA_PRIMARY = "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
#: Collection ids are now derived from the source model id (each `/` and `=` -> `-`).
CPA_PRIMARY_COLLECTION = (
    "canola_pennycress_arabidopsis-primary-240611_102513.multi_instance.n-743"
)
RICE_OLD_CROWN = "rice-older-crown-221208_113552.multi_instance.n-574"
SOYBEAN_PRIMARY = "soybean-primary-221003_111420.multi_instance.n-1389"


def _card(root_type, source_model_id, *selectors):
    return Card(
        root_type=root_type,
        selectors=tuple(
            Selector(species=s, mode=m, age_min=lo, age_max=hi)
            for s, m, lo, hi in selectors
        ),
        source_model_id=source_model_id,
    )


def _all_cards():
    return cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)


def _resolved(card_list, model_dir):
    return [(card, model_dir) for card in card_list]


# --- fakes ---


class _FakeArtifact:
    def __init__(self, name, type, metadata=None, **kw):
        self.name = name
        self.type = type
        self.metadata = metadata
        self.added_dirs = []

    def add_dir(self, local_path, **kw):
        self.added_dirs.append(local_path)


class _FakeLogged:
    def __init__(self, art, order):
        self.art = art
        self._order = order

    def wait(self, **kw):
        self._order.append("wait")
        return self


class _FakeRun:
    def __init__(self):
        self.order = []
        self.logged = None
        self.linked = None

    def log_artifact(self, artifact, **kw):
        self.order.append("log")
        self.logged = _FakeLogged(artifact, self.order)
        return self.logged

    def link_artifact(self, artifact, target_path, aliases=None, **kw):
        self.order.append("link")
        self.linked = (artifact, target_path, aliases)


class _FakeCollection:
    """A registry collection.

    ``aliases`` is the lightweight per-collection query `--verify` uses to decide
    membership. ``versions`` exists only so a test can SPY that we never paginate it
    for an unexpected collection -- the registry holds far more collections than
    cards, most of them sweep/run artifacts.
    """

    def __init__(self, name, aliases=(), on_version_walk=None):
        self.name = name
        self._aliases = list(aliases)
        self._on_version_walk = on_version_walk
        self.deleted = False
        self.linked = []

    @property
    def aliases(self):
        return list(self._aliases)

    def versions(self):
        if self._on_version_walk is not None:
            self._on_version_walk(self.name)
        return []

    def delete(self):  # spy: the scenario says --verify never deletes
        raise AssertionError(f"--verify must not delete {self.name}")

    def link(self, *a, **kw):  # spy: nor move an alias
        raise AssertionError(f"--verify must not re-link {self.name}")


class _FakeArt:
    """An artifact with a local view and a distinct SERVER view.

    The distinction is the whole point: `publish_card` assigns `.metadata` locally and
    then must consult the server. A fake that returned its own local value on re-read
    would make the check circular and pass an implementation that never persists.
    """

    def __init__(self, aliases, metadata=None, digest="d0", save_takes=True):
        self.aliases = aliases
        self.metadata = metadata if metadata is not None else _SELECTORS_META
        self.server_metadata = self.metadata
        self.digest = digest
        self.saved = 0
        self.save_takes = save_takes

    def save(self):
        self.saved += 1
        if self.save_takes:
            self.server_metadata = self.metadata


#: The current shape and the legacy flat shape, as they appear in live metadata.
_SELECTORS_META = {
    "root_type": "primary",
    "selectors": [
        {"species": "soybean", "mode": "cylinder", "age_min": 2, "age_max": 8}
    ],
    "source_model_id": "soybean/primary/x",
}
_LEGACY_META = {
    "species": "soybean",
    "mode": "cylinder",
    "age_min": 2,
    "age_max": 8,
    "root_type": "primary",
    "source_model_id": "soybean/primary/x",
}


class _FakeApi:
    def __init__(
        self,
        collections=(),
        arts_by_name=None,
        fail=False,
        aliases_by_collection=None,
        on_version_walk=None,
    ):
        self._collections = list(collections)
        self._arts = arts_by_name or {}
        self._fail = fail
        self._aliases = aliases_by_collection or {}
        self._on_version_walk = on_version_walk

    def artifact_collections(self, project_name, type_name):
        if self._fail:
            raise ConnectionError("transient registry error")
        return [
            _FakeCollection(
                c,
                aliases=self._aliases.get(c, []),
                on_version_walk=self._on_version_walk,
            )
            for c in self._collections
        ]

    def artifacts(self, type_name, name):
        return self._arts.get(name, [])

    def artifact(self, name, type=None):
        """Mirrors ``wandb.Api.artifact``'s signature (name, type=None)."""
        found = self._arts.get(name)
        if not found:
            raise ValueError(f"no such artifact: {name}")
        return found[0]


# --- publish_card ---


def test_publish_card(monkeypatch, tmp_path):
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)

    # This test monkeypatches wandb.Artifact but historically not wandb.Api, so a
    # read-back reaching for a real Api would load ~/.netrc and hit api.wandb.ai from
    # a unit test. Confirmed live once; guarded here permanently.
    def _no_api(*a, **kw):  # pragma: no cover - only hit on a regression
        raise AssertionError("publish_card must not construct a real wandb.Api")

    monkeypatch.setattr(wandb, "Api", _no_api)
    run = _FakeRun()
    card = _card("primary", CPA_PRIMARY, ("arabidopsis", "multiplant cylinder", 2, 14))
    model_dir = tmp_path / "m"
    model_dir.mkdir()

    publish.publish_card(run, card, model_dir, CFG)

    art = run.logged.art
    assert art.type == "model"
    assert art.metadata == card_to_metadata(card)
    assert not ({"registry_id", "version", "weights_checksum"} & set(art.metadata))
    assert art.added_dirs == [str(model_dir)]
    assert run.order == ["log", "wait", "link"]  # wait before link
    _, target, aliases = run.linked
    assert target == "ent-org/wandb-registry-reg/" + CPA_PRIMARY_COLLECTION
    assert aliases == ["production"]


# --- resolve_all (validate-all, pure filesystem) ---


def test_resolve_all_passes_require_pinned(monkeypatch, tmp_path):
    seen = []

    def fake_resolve(mid, root, ck, **kw):
        seen.append(kw.get("require_pinned"))
        return tmp_path

    monkeypatch.setattr(publish, "resolve_model_dir", fake_resolve)
    publish.resolve_all(_all_cards(), tmp_path, {})
    assert seen and all(flag is True for flag in seen)  # driver enforces pinned


def test_resolve_all_raises_on_first_missing(monkeypatch, tmp_path):
    def fake_resolve(mid, root, ck, **kw):
        if "younger/crown" in mid:
            raise FileNotFoundError(mid)
        return tmp_path

    monkeypatch.setattr(publish, "resolve_model_dir", fake_resolve)
    with pytest.raises(FileNotFoundError):
        publish.resolve_all(_all_cards(), tmp_path, {})


# --- seed_registry (takes resolved pairs) ---


def test_seed_publishes_all_distinct(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        publish,
        "publish_card",
        lambda run, c, d, cfg, **kw: calls.append(collection_id(c)) or "published",
    )
    api = _FakeApi(collections=[])  # fresh registry: no collection exists yet
    report = publish.seed_registry(
        _resolved(_all_cards(), tmp_path), CFG, run=object(), api=api
    )
    assert len(calls) == 8 and len(set(calls)) == 8  # one per physical model
    assert sorted(report["published"]) == sorted(calls) and report["skipped"] == []


def test_seed_duplicate_collection_aborts(monkeypatch, tmp_path):
    # Re-authored for the id-derived-from-model scheme. The old "a"/"b" fixture DID NOT
    # RAISE under it, and id collisions are otherwise structurally impossible now:
    # grouping is by (source_model_id, root_type), and a model spanning two root types
    # is rejected upstream. The one remaining collision channel is the LOSSY SLUG --
    # `/` and `=` both map to `-`, so two ids differing only there collapse.
    def boom_publish(*a, **kw):
        raise AssertionError("must not publish before the duplicate check")

    monkeypatch.setattr(publish, "publish_card", boom_publish)
    dup = [
        _card("crown", "x/y", ("rice", "cylinder", 6, 10)),
        _card("crown", "x=y", ("rice", "cylinder", 6, 10)),
    ]
    assert collection_id(dup[0]) == collection_id(dup[1]) == "x-y"  # the premise
    with pytest.raises(ValueError, match="(?i)duplicate") as excinfo:
        publish.seed_registry(
            _resolved(dup, tmp_path), CFG, run=object(), api=_FakeApi()
        )
    # It must name both offending models, not just the collapsed id -- the operator
    # cannot act on "x-y" alone.
    message = str(excinfo.value)
    assert "x/y" in message and "x=y" in message


def test_the_eight_committed_model_ids_slug_to_eight_distinct_collections():
    # The sibling of the above: the lossy slug is a real hazard in principle, but it
    # does not bite the committed matrix. Asserted so a future matrix edit that DOES
    # collide fails here rather than at `--execute` time.
    all_cards = _all_cards()
    assert len(all_cards) == 8
    assert len({collection_id(c) for c in all_cards}) == 8


def test_seed_idempotent_skip_and_force(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        publish,
        "publish_card",
        lambda run, c, d, cfg, **kw: calls.append(collection_id(c)) or "published",
    )
    api = _FakeApi(
        collections=[RICE_OLD_CROWN],
        arts_by_name={f"{PROJECT}/{RICE_OLD_CROWN}": [_FakeArt(["production", "v3"])]},
    )
    report = publish.seed_registry(
        _resolved(_all_cards(), tmp_path), CFG, run=object(), api=api, force=False
    )
    assert RICE_OLD_CROWN not in calls and RICE_OLD_CROWN in report["skipped"]

    calls.clear()
    publish.seed_registry(
        _resolved(_all_cards(), tmp_path), CFG, run=object(), api=api, force=True
    )
    assert RICE_OLD_CROWN in calls  # --force re-publishes/re-points


def test_seed_read_error_fails_closed(monkeypatch, tmp_path):
    # A transient registry read error must PROPAGATE (fail closed), never be treated
    # as "no production" -> republish -> silent alias move.
    def boom_publish(*a, **kw):
        raise AssertionError("must not publish on a read error")

    monkeypatch.setattr(publish, "publish_card", boom_publish)
    with pytest.raises(ConnectionError):
        publish.seed_registry(
            _resolved(_all_cards(), tmp_path),
            CFG,
            run=object(),
            api=_FakeApi(fail=True),
            force=False,
        )


# --- verify_registry ---


def test_verify_reports_present_missing_and_alias_absent():
    # RICE_OLD_CROWN: present + production. NO_ALIAS: collection exists but the
    # production alias never landed -> must be reported MISSING. CANOLA: absent.
    no_alias = "soybean-cylinder-primary-age2-8"
    canola = "canola-cylinder-primary-age2-13"
    api = _FakeApi(
        collections=[RICE_OLD_CROWN, no_alias],
        arts_by_name={
            f"{PROJECT}/{RICE_OLD_CROWN}": [_FakeArt(["production", "latest"])],
            f"{PROJECT}/{no_alias}": [_FakeArt(["latest"])],  # no production alias
        },
    )
    report = publish.verify_registry(CFG, [RICE_OLD_CROWN, no_alias, canola], api=api)
    assert report["present"] == [RICE_OLD_CROWN]
    assert set(report["missing"]) == {no_alias, canola}


# --- 4.4: orphan reporting + the metadata shape check (zero coverage before) ---

EXPECTED = "soy-p"
ORPHAN = "canola-cylinder-primary-age2-13"  # an old-scheme collection, now unproduced


def _verify_api(collections, aliases, arts, on_version_walk=None):
    return _FakeApi(
        collections=collections,
        aliases_by_collection=aliases,
        arts_by_name=arts,
        on_version_walk=on_version_walk,
    )


def test_verify_names_a_production_aliased_orphan():
    api = _verify_api(
        collections=[EXPECTED, ORPHAN],
        aliases={EXPECTED: ["production"], ORPHAN: ["production"]},
        arts={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]},
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["orphans"] == [ORPHAN]
    assert report["present"] == [EXPECTED]


def test_verify_ignores_a_non_production_collection():
    # The registry holds ~87 sweep/run collections. None of them is an orphan.
    api = _verify_api(
        collections=[EXPECTED, "some-sweep-run"],
        aliases={EXPECTED: ["production"], "some-sweep-run": ["latest", "v3"]},
        arts={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]},
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["orphans"] == []


def test_an_orphan_alone_does_not_change_the_exit_code():
    # Orphans are reported, never acted on: retiring them is a separate, gated step.
    api = _verify_api(
        collections=[EXPECTED, ORPHAN],
        aliases={EXPECTED: ["production"], ORPHAN: ["production"]},
        arts={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]},
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["orphans"] and not report["missing"] and not report["legacy"]
    assert publish.verify_failed(report) is False


def test_verify_never_walks_versions_of_an_unexpected_collection():
    # Alias membership must come from the lightweight ArtifactCollection.aliases query,
    # NOT from paginating every version at 50/page. Fine for 8 expected collections,
    # ruinous across a registry of ~100. The spy is on the COLLECTION object, not on
    # _FakeApi.artifacts -- verify legitimately calls the latter for EXPECTED ones.
    walked = []
    api = _verify_api(
        collections=[EXPECTED, ORPHAN, "some-sweep-run"],
        aliases={EXPECTED: ["production"], ORPHAN: ["production"]},
        arts={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]},
        on_version_walk=walked.append,
    )
    publish.verify_registry(CFG, [EXPECTED], api=api)
    assert walked == [], f"paginated versions of {walked}"


def test_an_indeterminate_collection_is_reported_and_does_not_fail():
    class _Unreadable(_FakeCollection):
        @property
        def aliases(self):
            raise ConnectionError("alias read failed")

    class _Api(_FakeApi):
        def artifact_collections(self, project_name, type_name):
            return [
                _FakeCollection(EXPECTED, aliases=["production"]),
                _Unreadable("mystery"),
            ]

    api = _Api(arts_by_name={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]})
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["indeterminate"] == ["mystery"]
    assert publish.verify_failed(report) is False  # unknown != broken


def test_verify_only_suppresses_orphan_reporting():
    api = _verify_api(
        collections=[EXPECTED, ORPHAN],
        aliases={EXPECTED: ["production"], ORPHAN: ["production"]},
        arts={f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"])]},
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api, report_orphans=False)
    assert report["orphans"] == []
    assert report["orphans_suppressed"] is True


# --- 4.2 / 4.8 / 4.9: the metadata shape check must discriminate ---


def test_verify_names_a_legacy_shaped_expected_collection_and_fails():
    api = _verify_api(
        collections=[EXPECTED],
        aliases={EXPECTED: ["production"]},
        arts={
            f"{PROJECT}/{EXPECTED}": [_FakeArt(["production"], metadata=_LEGACY_META)]
        },
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["legacy"] == [EXPECTED]
    assert publish.verify_failed(report) is True  # an unreadable card IS a failure


def test_verify_passes_a_selectors_shaped_expected_collection():
    # 4.9's negative control: without it, a checker that fails EVERYTHING passes above.
    api = _verify_api(
        collections=[EXPECTED],
        aliases={EXPECTED: ["production"]},
        arts={
            f"{PROJECT}/{EXPECTED}": [
                _FakeArt(["production"], metadata=_SELECTORS_META)
            ]
        },
    )
    report = publish.verify_registry(CFG, [EXPECTED], api=api)
    assert report["legacy"] == [] and report["present"] == [EXPECTED]
    assert publish.verify_failed(report) is False


def test_the_shape_check_is_structural_not_contract_validation():
    # 4.8. Under a TOLERANT-READ contract the legacy blob validates fine, so a
    # validation-based check would report every stale collection as current. The check
    # must be structural: `selectors` present, and no card-level selection keys.
    assert publish._is_selectors_shape(_SELECTORS_META) is True
    assert publish._is_selectors_shape(_LEGACY_META) is False
    # A blob carrying BOTH is stale too -- a half-migrated write, not a current one.
    assert (
        publish._is_selectors_shape({**_SELECTORS_META, "species": "soybean"}) is False
    )
    assert publish._is_selectors_shape({}) is False
    assert publish._is_selectors_shape(None) is False


# --- 4.5 / 4.6 / 4.11: the re-publish metadata refresh ---


class _RefreshRun(_FakeRun):
    """A run whose linked artifact reads back with caller-chosen metadata."""

    def __init__(self, read_back, digest="d0", refresh_raises=False):
        super().__init__()
        self._read_back = read_back
        self._digest = digest
        self._refresh_raises = refresh_raises
        self.link_returns = []
        self.add_dir_count = 0

    def api(self, project, collection, alias):
        """An api whose artifact lookup returns the very object save() mutates."""
        art = self.link_returns[-1]
        return _FakeApi(arts_by_name={f"{project}/{collection}": [art]})

    def link_artifact(self, artifact, target_path, aliases=None, **kw):
        super().link_artifact(artifact, target_path, aliases=aliases, **kw)
        art = _FakeArt(
            list(aliases or []),
            metadata=self._read_back,
            digest=self._digest,
            save_takes=not self._refresh_raises,
        )
        if self._refresh_raises:

            def _boom():
                raise ConnectionError("updateArtifact failed")

            art.save = _boom
        self.link_returns.append(art)
        return art


class _ReReadApi:
    """Resolves the aliased artifact to the same object ``save()`` mutates.

    This is what makes the refresh check real rather than circular: publish_card must
    consult the server's view, not the local attribute it just assigned.
    """

    def __init__(self, run):
        self._run = run

    def artifacts(self, type_name, name):
        if not self._run.link_returns:
            return []
        art = self._run.link_returns[-1]
        return [_FakeArt(list(art.aliases), metadata=art.server_metadata)]


def test_a_stale_read_back_is_refreshed_in_place(monkeypatch, tmp_path):
    # 4.6. Metadata is NOT part of the manifest digest and log_artifact no-ops on an
    # unchanged digest, so a content-identical re-log can leave the previous metadata
    # live while the report says "published".
    #
    # SCOPE: this covers OUR CLASSIFIER ONLY. The premise it defends against -- that
    # wandb really does leave the previous metadata live after a content-identical
    # re-log -- is server behavior no offline fake can confirm. Task 6.5 settles that
    # against the live registry during the canary; if it turns out wandb refreshes on
    # its own, this requirement is over-built and should be downgraded.
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)
    run = _RefreshRun(read_back=_LEGACY_META)
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    model_dir = tmp_path / "m"
    model_dir.mkdir()

    outcome = publish.publish_card(run, card, model_dir, CFG, api=_ReReadApi(run))

    assert outcome == "published"
    assert run.link_returns[0].saved == 1  # refreshed in place...
    # ...and NOT by re-logging: the digest is unchanged, so a re-log cannot create a
    # new version. An implementation that "refreshes" that way must fail here rather
    # than silently no-op in production.
    assert run.order.count("log") == 1
    assert run.logged.art.added_dirs == [str(model_dir)]


def test_a_read_back_that_stays_stale_is_reported_failed(monkeypatch, tmp_path):
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)

    class _StubbornRun(_RefreshRun):
        def link_artifact(self, artifact, target_path, aliases=None, **kw):
            art = super().link_artifact(artifact, target_path, aliases=aliases, **kw)
            art.save_takes = False  # save() succeeds but the write never lands
            return art

    run = _StubbornRun(read_back=_LEGACY_META)
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    model_dir = tmp_path / "m"
    model_dir.mkdir()
    assert (
        publish.publish_card(run, card, model_dir, CFG, api=_ReReadApi(run)) == "failed"
    )


def test_a_current_read_back_needs_no_refresh(monkeypatch, tmp_path):
    # The negative control for the refresh path.
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)
    run = _RefreshRun(read_back=_SELECTORS_META)
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    model_dir = tmp_path / "m"
    model_dir.mkdir()
    assert (
        publish.publish_card(run, card, model_dir, CFG, api=_ReReadApi(run))
        == "published"
    )
    assert run.link_returns[0].saved == 0  # untouched


def test_force_alone_does_not_satisfy_the_refresh_check(monkeypatch, tmp_path):
    # 4.11. --force bypasses only the idempotency read (publish.py's `force` branch);
    # it cannot create a new version while the digest is unchanged, so it is not
    # evidence of a refresh. AND the remaining cards must still be attempted.
    outcomes = {"a": "published", "b": "failed", "c": "published"}
    monkeypatch.setattr(
        publish,
        "publish_card",
        lambda run, c, d, cfg, **kw: outcomes[c.source_model_id],
    )
    trio = [
        _card("primary", "a", ("soybean", "cylinder", 2, 8)),
        _card("primary", "b", ("canola", "cylinder", 2, 8)),
        _card("primary", "c", ("rice", "cylinder", 2, 8)),
    ]
    report = publish.seed_registry(
        _resolved(trio, tmp_path), CFG, run=object(), api=_FakeApi(), force=True
    )
    assert report["failed"] == ["b"]
    assert report["published"] == ["a", "c"]  # the middle one did not abort the seed


def test_a_raising_refresh_lands_in_failed_rather_than_aborting(monkeypatch, tmp_path):
    # The same shape, but the middle card's refresh RAISES rather than reading back
    # stale. A CommError from updateArtifact must land in `failed` too, not propagate.
    def fake_publish(run, card, model_dir, cfg, **kw):
        if card.source_model_id == "b":
            raise ConnectionError("updateArtifact failed")
        return "published"

    monkeypatch.setattr(publish, "publish_card", fake_publish)
    trio = [
        _card("primary", "a", ("soybean", "cylinder", 2, 8)),
        _card("primary", "b", ("canola", "cylinder", 2, 8)),
        _card("primary", "c", ("rice", "cylinder", 2, 8)),
    ]
    report = publish.seed_registry(
        _resolved(trio, tmp_path), CFG, run=object(), api=_FakeApi(), force=True
    )
    assert report["failed"] == ["b"]
    assert report["published"] == ["a", "c"]


# --- 4.10: the skip path is the default on every re-run ---


def test_the_skip_path_also_checks_the_metadata_shape(monkeypatch, tmp_path):
    # A collection that already carries `production` is SKIPPED, so a check scoped to
    # `published` never sees it -- and the skip path is the default on every re-run, so
    # a half-migrated collection would sit there undetected.
    monkeypatch.setattr(publish, "publish_card", lambda *a, **kw: "published")
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    api = _FakeApi(
        collections=["soy-p"],
        arts_by_name={
            f"{PROJECT}/soy-p": [_FakeArt(["production"], metadata=_LEGACY_META)]
        },
    )
    report = publish.seed_registry(
        _resolved([card], tmp_path), CFG, run=object(), api=api, force=False
    )
    assert report["stale"] == ["soy-p"]
    assert report["skipped"] == ["soy-p"]


def test_a_current_skip_is_not_reported_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "publish_card", lambda *a, **kw: "published")
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    api = _FakeApi(
        collections=["soy-p"],
        arts_by_name={
            f"{PROJECT}/soy-p": [_FakeArt(["production"], metadata=_SELECTORS_META)]
        },
    )
    report = publish.seed_registry(
        _resolved([card], tmp_path), CFG, run=object(), api=api, force=False
    )
    assert report["stale"] == [] and report["skipped"] == ["soy-p"]


# --- 4.7: a re-seed of unchanged weights keeps its weights_checksum ---


def test_a_reseed_of_unchanged_weights_keeps_its_digest(monkeypatch, tmp_path):
    # Bloom's idempotency key hashes (registry_id, version, weights_checksum), so a
    # rotating digest would silently reset it. Verified, not assumed -- and NOT
    # credited to selector ordering.
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)
    card = _card("primary", "soy/p", ("soybean", "cylinder", 2, 8))
    model_dir = tmp_path / "m"
    model_dir.mkdir()

    digests = []
    for _ in range(2):
        run = _RefreshRun(read_back=_SELECTORS_META, digest="sha-unchanged")
        publish.publish_card(run, card, model_dir, CFG, api=_ReReadApi(run))
        digests.append(run.link_returns[0].digest)
    assert digests[0] == digests[1] == "sha-unchanged"
