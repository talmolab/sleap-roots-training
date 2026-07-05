import pytest

from sleap_roots_training.registry import cards, chooser, publish
from sleap_roots_training.registry.cards import Card, card_to_metadata, collection_id
from sleap_roots_training.registry.config import RegistryConfig

CFG = RegistryConfig("ent", "reg", "production")
CPA_PRIMARY = "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
ARAB_MULTI_PRIMARY = "arabidopsis-multiplant-cylinder-primary-age2-14"


def _all_cards():
    return cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)


# --- publish_card (mock wandb) ---


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

    def log_artifact(self, artifact, type=None, **kw):
        self.order.append("log")
        self.logged = _FakeLogged(artifact, self.order)
        return self.logged

    def link_artifact(self, artifact, target_path, aliases=None, **kw):
        self.order.append("link")
        self.linked = (artifact, target_path, aliases)


def test_publish_card(monkeypatch, tmp_path):
    import wandb

    monkeypatch.setattr(wandb, "Artifact", _FakeArtifact)
    run = _FakeRun()
    card = Card("arabidopsis", "multiplant cylinder", 2, 14, "primary", CPA_PRIMARY)
    model_dir = tmp_path / "m"
    model_dir.mkdir()

    publish.publish_card(run, card, model_dir, CFG)

    art = run.logged.art
    assert art.type == "model"
    assert art.metadata == card_to_metadata(card)
    assert not ({"registry_id", "version", "weights_checksum"} & set(art.metadata))
    assert art.added_dirs == [str(model_dir)]
    # log -> wait -> link (wait before link).
    assert run.order == ["log", "wait", "link"]
    linked_art, target, aliases = run.linked
    assert target == "ent-org/wandb-registry-reg/" + ARAB_MULTI_PRIMARY
    assert aliases == ["production"]


# --- seed_registry driver (spy publish_card / resolve / has_production) ---


def _spy_publish(monkeypatch):
    calls = []
    monkeypatch.setattr(
        publish, "publish_card", lambda run, c, d, cfg: calls.append(collection_id(c))
    )
    return calls


def test_seed_publishes_thirteen_distinct(monkeypatch, tmp_path):
    calls = _spy_publish(monkeypatch)
    monkeypatch.setattr(publish, "resolve_model_dir", lambda *a, **k: tmp_path)
    monkeypatch.setattr(publish, "_collection_has_production", lambda *a, **k: False)
    report = publish.seed_registry(
        _all_cards(), tmp_path, {}, CFG, run=object(), api=object()
    )
    assert len(calls) == 13 and len(set(calls)) == 13
    assert sorted(report["published"]) == sorted(calls)


def test_seed_validate_all_before_publish(monkeypatch, tmp_path):
    calls = _spy_publish(monkeypatch)

    def fake_resolve(mid, root, ck, **kw):
        if "younger/crown" in mid:
            raise FileNotFoundError(mid)
        return tmp_path

    monkeypatch.setattr(publish, "resolve_model_dir", fake_resolve)
    monkeypatch.setattr(publish, "_collection_has_production", lambda *a, **k: False)
    with pytest.raises(FileNotFoundError):
        publish.seed_registry(
            _all_cards(), tmp_path, {}, CFG, run=object(), api=object()
        )
    assert calls == []  # nothing published before the failing resolution


def test_seed_duplicate_collection_aborts(monkeypatch, tmp_path):
    _spy_publish(monkeypatch)
    monkeypatch.setattr(publish, "resolve_model_dir", lambda *a, **k: tmp_path)
    dup = [
        Card("rice", "cylinder", 6, 10, "crown", "a"),
        Card("rice", "cylinder", 6, 10, "crown", "b"),
    ]
    with pytest.raises(ValueError, match="(?i)duplicate"):
        publish.seed_registry(dup, tmp_path, {}, CFG, run=object(), api=object())


def test_seed_idempotent_skip_and_force(monkeypatch, tmp_path):
    calls = _spy_publish(monkeypatch)
    monkeypatch.setattr(publish, "resolve_model_dir", lambda *a, **k: tmp_path)
    monkeypatch.setattr(
        publish,
        "_collection_has_production",
        lambda api, proj, coll, alias: coll == "rice-cylinder-crown-age6-10",
    )
    report = publish.seed_registry(
        _all_cards(), tmp_path, {}, CFG, run=object(), api=object(), force=False
    )
    assert "rice-cylinder-crown-age6-10" not in calls
    assert "rice-cylinder-crown-age6-10" in report["skipped"]

    calls.clear()
    publish.seed_registry(
        _all_cards(), tmp_path, {}, CFG, run=object(), api=object(), force=True
    )
    assert "rice-cylinder-crown-age6-10" in calls


def test_seed_only_scopes_validation_and_publish(monkeypatch, tmp_path):
    calls = _spy_publish(monkeypatch)

    def fake_resolve(mid, root, ck, **kw):
        if mid == CPA_PRIMARY:
            return tmp_path
        raise FileNotFoundError(mid)  # other 12 models "missing"

    monkeypatch.setattr(publish, "resolve_model_dir", fake_resolve)
    monkeypatch.setattr(publish, "_collection_has_production", lambda *a, **k: False)
    # Canary: only its model staged; must NOT abort on the other 12 missing.
    report = publish.seed_registry(
        _all_cards(),
        tmp_path,
        {},
        CFG,
        run=object(),
        api=object(),
        only={ARAB_MULTI_PRIMARY},
    )
    assert calls == [ARAB_MULTI_PRIMARY]
    assert report["published"] == [ARAB_MULTI_PRIMARY]


def test_seed_only_unknown_raises(monkeypatch, tmp_path):
    _spy_publish(monkeypatch)
    monkeypatch.setattr(publish, "resolve_model_dir", lambda *a, **k: tmp_path)
    with pytest.raises(ValueError, match="unknown"):
        publish.seed_registry(
            _all_cards(),
            tmp_path,
            {},
            CFG,
            run=object(),
            api=object(),
            only={"does-not-exist"},
        )


# --- verify_registry (fake wandb.Api) ---


class _FakeCollection:
    def __init__(self, name):
        self.name = name


class _FakeArt:
    def __init__(self, aliases):
        self.aliases = aliases


class _FakeApi:
    def __init__(self, collections, arts_by_name):
        self._collections = collections
        self._arts = arts_by_name

    def artifact_collections(self, project_name, type_name):
        return [_FakeCollection(c) for c in self._collections]

    def artifacts(self, type_name, name):
        return self._arts.get(name, [])


def test_verify_registry_reports_present_and_missing():
    project = CFG.registry_project()
    api = _FakeApi(
        collections=["rice-cylinder-crown-age6-10"],
        arts_by_name={
            f"{project}/rice-cylinder-crown-age6-10": [
                _FakeArt(["production", "latest"])
            ]
        },
    )
    report = publish.verify_registry(
        CFG,
        ["rice-cylinder-crown-age6-10", "soybean-cylinder-primary-age2-8"],
        api=api,
    )
    assert report["present"] == ["rice-cylinder-crown-age6-10"]
    assert report["missing"] == ["soybean-cylinder-primary-age2-8"]
