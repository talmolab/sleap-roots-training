"""Exercise the shared ``conftest`` fixtures directly.

They are otherwise only hit transitively through the registry tests; this pins their
contract explicitly (per PR #14 review), most importantly that ``clean_wandb_env``
*actively* clears every managed var rather than passing by a coincidentally-empty env.
"""

import os

import pytest

from conftest import _WANDB_ENV_VARS


@pytest.fixture(autouse=True)
def _seed_wandb_env():
    """Set every managed var *before* ``clean_wandb_env`` runs, then restore.

    Autouse fixtures are set up before the non-autouse fixtures a test requests, so the
    sentinels are in place when ``clean_wandb_env`` runs -- proving it deletes live vars.
    """
    original = {var: os.environ.get(var) for var in _WANDB_ENV_VARS}
    for var in _WANDB_ENV_VARS:
        os.environ[var] = "sentinel"
    yield
    for var, value in original.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


def test_clean_wandb_env_clears_every_managed_var(clean_wandb_env):
    for var in _WANDB_ENV_VARS:
        assert var not in os.environ, f"clean_wandb_env left {var} set"


def test_clean_wandb_env_covers_the_documented_var_set():
    assert set(_WANDB_ENV_VARS) == {
        "WANDB_API_KEY",
        "WANDB_ENTITY",
        "SLEAP_ROOTS_MODEL_REGISTRY",
        "SLEAP_ROOTS_MODEL_ALIAS",
    }


def test_tiny_matrix_and_stub_models_root(tiny_matrix, stub_models_root):
    # The two staging fixtures produce the files the registry tests rely on.
    assert tiny_matrix.is_file()
    assert "soybean" in tiny_matrix.read_text()
    for model_id in ("soy/p", "soy/l"):
        assert (stub_models_root / model_id / "best_model.h5").is_file()
        assert (stub_models_root / model_id / "training_config.json").is_file()
