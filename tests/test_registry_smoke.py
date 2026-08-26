"""Group-0 smoke test: the registry runtime deps resolve and import."""


def test_wandb_imports():
    import wandb

    assert wandb.__version__


def test_model_card_imports_and_validates():
    from sleap_roots_contracts import ModelCard

    # One card, one physical model: a scalar ``root_type`` plus the selection contexts
    # the weights were validated for. ``source_model_id`` is tolerated via
    # ``extra="ignore"``; the identity keys are injected by the consumer.
    card = ModelCard.model_validate(
        {
            "root_type": "primary",
            "selectors": [
                {
                    "species": "pennycress",
                    "mode": "multiplant cylinder",
                    "age_min": 2,
                    "age_max": 14,
                }
            ],
            "source_model_id": "cpa/primary/x",
            "registry_id": "rid",
            "version": "v3",
            "weights_checksum": "sha",
        }
    )
    assert (
        card.selectors[0].mode == "multiplant cylinder"
    )  # space preserved, not slugged
    assert card.sleap_nn_version is None  # stays card-level, never per-selector
