import pytest

from sleap_roots_training.registry import config

_ENV_VARS = [
    "WANDB_ENTITY",
    "SLEAP_ROOTS_MODEL_REGISTRY",
    "SLEAP_ROOTS_MODEL_ALIAS",
    "WANDB_API_KEY",
]

_NETRC_ENTRY = "machine api.wandb.ai\n  login user\n  password " + "k" * 40 + "\n"


def _clear_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _isolate_netrc(monkeypatch, home):
    """Point netrc resolution at an isolated (empty) home; clear NETRC.

    Ensures tests never read the developer's real ``~/.netrc`` and behave
    identically on every OS.
    """
    monkeypatch.delenv("NETRC", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_defaults_when_unset(monkeypatch):
    _clear_env(monkeypatch)
    cfg = config.resolve_registry_config()
    assert cfg.entity == "eberrigan-salk-institute-for-biological-studies"
    assert cfg.registry == "sleap-roots-models"
    assert cfg.alias == "production"


def test_overrides_from_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("WANDB_ENTITY", "some-entity")
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_REGISTRY", "other-registry")
    monkeypatch.setenv("SLEAP_ROOTS_MODEL_ALIAS", "staging")
    cfg = config.resolve_registry_config()
    assert (cfg.entity, cfg.registry, cfg.alias) == (
        "some-entity",
        "other-registry",
        "staging",
    )


def test_require_api_key_raises_when_unset(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    _isolate_netrc(monkeypatch, tmp_path)  # empty home => no netrc credential
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_require_api_key_passes_when_set(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    config.require_api_key()  # no raise


def test_netrc_via_env_var_satisfies_guard(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    _isolate_netrc(monkeypatch, tmp_path)
    netrc_file = tmp_path / "custom_netrc"
    netrc_file.write_text(_NETRC_ENTRY)
    monkeypatch.setenv("NETRC", str(netrc_file))
    config.require_api_key()  # no raise: netrc login resolves via NETRC


def test_unix_netrc_satisfies_guard(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    _isolate_netrc(monkeypatch, tmp_path)
    (tmp_path / ".netrc").write_text(_NETRC_ENTRY)
    config.require_api_key()  # no raise: ~/.netrc branch resolves


def test_windows_netrc_satisfies_guard(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    _isolate_netrc(monkeypatch, tmp_path)
    # Only ~/_netrc exists (the file `wandb login` writes on Windows); no ~/.netrc.
    (tmp_path / "_netrc").write_text(_NETRC_ENTRY)
    config.require_api_key()  # no raise: ~/_netrc branch resolves on any OS


def test_malformed_netrc_is_treated_as_no_credential(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    _isolate_netrc(monkeypatch, tmp_path)
    netrc_file = tmp_path / "custom_netrc"
    # A bare top-level token with no machine/default keyword is a parse error.
    netrc_file.write_text("this is not a valid netrc file\n")
    monkeypatch.setenv("NETRC", str(netrc_file))
    # The guard swallows the NetrcParseError and reports "no credential".
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_registry_project_string(monkeypatch):
    _clear_env(monkeypatch)
    cfg = config.resolve_registry_config()
    # The consumer reads this exact project string.
    assert (
        cfg.registry_project() == "eberrigan-salk-institute-for-biological-studies-org"
        "/wandb-registry-sleap-roots-models"
    )
