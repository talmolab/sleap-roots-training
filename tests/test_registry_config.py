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


def test_require_api_key_raises_when_unset(isolate_netrc):
    # isolate_netrc clears WANDB_API_KEY/NETRC and points HOME at an empty dir.
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_require_api_key_passes_when_set(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    config.require_api_key()  # no raise


def test_netrc_via_env_var_satisfies_guard(monkeypatch, isolate_netrc):
    netrc_file = isolate_netrc / "custom_netrc"
    netrc_file.write_text(_NETRC_ENTRY)
    monkeypatch.setenv("NETRC", str(netrc_file))
    config.require_api_key()  # no raise: netrc login resolves via NETRC


def test_unix_netrc_satisfies_guard(isolate_netrc):
    (isolate_netrc / ".netrc").write_text(_NETRC_ENTRY)
    config.require_api_key()  # no raise: ~/.netrc branch resolves


def test_windows_netrc_satisfies_guard(isolate_netrc):
    # Only ~/_netrc exists (the file `wandb login` writes on Windows); no ~/.netrc.
    (isolate_netrc / "_netrc").write_text(_NETRC_ENTRY)
    config.require_api_key()  # no raise: ~/_netrc branch resolves on any OS


def test_malformed_netrc_is_treated_as_no_credential(monkeypatch, isolate_netrc):
    netrc_file = isolate_netrc / "custom_netrc"
    # A bare top-level token with no machine/default keyword is a parse error.
    netrc_file.write_text("this is not a valid netrc file\n")
    monkeypatch.setenv("NETRC", str(netrc_file))
    # The guard swallows the NetrcParseError and reports "no credential".
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_blank_password_netrc_is_not_a_credential(isolate_netrc):
    # An entry for api.wandb.ai with a login but no password (a stale/interrupted
    # `wandb login`, hand-edited template, or redacted fixture) is NOT a usable
    # credential -- it must fail before the confirmation prompt, not deep inside
    # wandb.init(). Mirrors wandb==0.28.0 ("if not password: return None").
    (isolate_netrc / ".netrc").write_text("machine api.wandb.ai\n  login user\n")
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_other_machine_netrc_is_not_a_credential(isolate_netrc):
    # A netrc with entries for other machines but not api.wandb.ai resolves to
    # no credential (authenticators() returns None for the missing host).
    (isolate_netrc / ".netrc").write_text(
        "machine example.com\n  login u\n  password p\n"
    )
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
