import pytest

from sleap_roots_training.registry import config

_ENV_VARS = [
    "WANDB_ENTITY",
    "SLEAP_ROOTS_MODEL_REGISTRY",
    "SLEAP_ROOTS_MODEL_ALIAS",
    "WANDB_API_KEY",
]


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


def test_require_api_key_raises_when_unset(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        config.require_api_key()


def test_require_api_key_passes_when_set(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "secret")
    config.require_api_key()  # no raise


def test_registry_project_string(monkeypatch):
    _clear_env(monkeypatch)
    cfg = config.resolve_registry_config()
    # The consumer reads this exact project string.
    assert (
        cfg.registry_project() == "eberrigan-salk-institute-for-biological-studies-org"
        "/wandb-registry-sleap-roots-models"
    )
