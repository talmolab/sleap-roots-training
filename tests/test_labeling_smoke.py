"""Group-0 smoke test: the labeling runtime deps resolve and import.

Mirrors ``test_registry_smoke.py``. This is the first code in the repo to touch ``.slp``
files, so the point of these tests is that a *default* install (no ``train`` extra) can do
so — that is the whole content of design.md Decision 4.
"""


def test_sleap_io_imports_from_a_default_install():
    # Decision 4: sleap-io is a core dependency, so this must pass without `[train]`.
    import sleap_io

    assert sleap_io.__version__


def test_labeling_subpackage_imports():
    from sleap_roots_training import labeling

    assert labeling.__doc__


def test_save_slp_exposes_the_embed_parameter():
    # Section 5 turns `embed=True` on deliberately; pin that the pinned sleap-io line
    # actually offers the knob, so a dependency bump that drops it fails here rather than
    # in a builder that silently keeps writing external-reference files.
    import inspect

    import sleap_io

    embed = inspect.signature(sleap_io.save_slp).parameters["embed"]
    # The library default is external-reference — the port inherits it (4.1) until 5.2.
    assert embed.default is False
