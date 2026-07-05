"""Group-0 smoke test: the registry runtime deps resolve and import."""


def test_wandb_imports():
    import wandb

    assert wandb.__version__


def test_model_card_imports_and_validates():
    from sleap_roots_contracts import ModelCard

    # The six selection keys the producer writes + the identity keys the
    # consumer injects; ``source_model_id`` is tolerated via ``extra="ignore"``.
    card = ModelCard.model_validate(
        {
            "species": "pennycress",
            "mode": "multiplant cylinder",
            "age_min": 2,
            "age_max": 14,
            "root_type": "primary",
            "source_model_id": "cpa/primary/x",
            "registry_id": "rid",
            "version": "v3",
            "weights_checksum": "sha",
        }
    )
    assert card.mode == "multiplant cylinder"  # space preserved, not slugged
    assert card.sleap_nn_version is None
