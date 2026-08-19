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
    def __init__(self, name):
        self.name = name


class _FakeArt:
    def __init__(self, aliases):
        self.aliases = aliases


class _FakeApi:
    def __init__(self, collections=(), arts_by_name=None, fail=False):
        self._collections = list(collections)
        self._arts = arts_by_name or {}
        self._fail = fail

    def artifact_collections(self, project_name, type_name):
        if self._fail:
            raise ConnectionError("transient registry error")
        return [_FakeCollection(c) for c in self._collections]

    def artifacts(self, type_name, name):
        return self._arts.get(name, [])


# --- publish_card ---


def test_publish_card(monkeypatch, tmp_path):
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)
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
        publish, "publish_card", lambda run, c, d, cfg: calls.append(collection_id(c))
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
    def boom_publish(*a):
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
        publish, "publish_card", lambda run, c, d, cfg: calls.append(collection_id(c))
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
    def boom_publish(*a):
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
