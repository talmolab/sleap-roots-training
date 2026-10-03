"""Offline fakes for the wandb registry surface the publish path touches.

Shared by ``test_registry_publish.py`` and ``test_registry_cli.py``. Not collected by
pytest: the file name does not match ``test_*.py``.
"""


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
    """A run. ``entity``/``project``/``finish`` make it usable behind ``wandb.init``.

    ``linked`` keeps the last link (what the single-card tests read); ``links`` keeps
    every ``(target_path, aliases)`` so a multi-card seed can be asserted per card.
    """

    def __init__(self, entity=None, project=None):
        self.entity = entity
        self.project = project
        self.order = []
        self.logged = None
        self.linked = None
        self.links = []
        self.finished = []

    def log_artifact(self, artifact, **kw):
        self.order.append("log")
        self.logged = _FakeLogged(artifact, self.order)
        return self.logged

    def link_artifact(self, artifact, target_path, aliases=None, **kw):
        self.order.append("link")
        self.linked = (artifact, target_path, aliases)
        self.links.append((target_path, aliases))

    def finish(self, exit_code=None):
        self.finished.append(exit_code)


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
        """Mirror wandb 0.28: asking for an absent collection's versions RAISES.

        ``wandb/apis/public/artifacts.py:918-924`` raises ``ValueError("Unable to parse
        'Artifacts' response data")`` rather than returning nothing, so a caller that
        reads a collection without first checking it exists would fail live. Returning
        ``[]`` here hid exactly that.
        """
        if name in self._arts:
            return self._arts[name]
        if name.rsplit("/", 1)[-1] in self._collections:
            return []
        raise ValueError("Unable to parse 'Artifacts' response data")

    def artifact(self, name, type=None):
        """Mirrors ``wandb.Api.artifact``'s signature (name, type=None)."""
        found = self._arts.get(name)
        if not found:
            raise ValueError(f"no such artifact: {name}")
        return found[0]
