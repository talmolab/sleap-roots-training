"""Environment-driven wandb registry configuration.

Entity, the models-registry name, and the production alias are resolved from
environment variables with defaults so nothing is hardcoded and pointing at a
different registry later is a config change. These MUST resolve to the same target
the ``sleap-roots-predict`` consumer points ``SRP_WANDB_ENTITY`` /
``SRP_WANDB_REGISTRY`` at.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_ENTITY = "eberrigan-salk-institute-for-biological-studies"
DEFAULT_REGISTRY = "sleap-roots-models"
DEFAULT_ALIAS = "production"


@dataclass(frozen=True)
class RegistryConfig:
    """Resolved wandb registry target.

    Attributes:
        entity: The wandb entity.
        registry: The models-registry name.
        alias: The alias marking a version as production.
    """

    entity: str
    registry: str
    alias: str

    def registry_project(self) -> str:
        """Return the registry project string the consumer reads.

        Returns:
            ``f"{entity}-org/wandb-registry-{registry}"``.
        """
        return f"{self.entity}-org/wandb-registry-{self.registry}"


def resolve_registry_config() -> RegistryConfig:
    """Resolve the registry target from the environment (with defaults).

    Reads ``WANDB_ENTITY``, ``SLEAP_ROOTS_MODEL_REGISTRY``, and
    ``SLEAP_ROOTS_MODEL_ALIAS``.

    Returns:
        The resolved :class:`RegistryConfig`.
    """
    return RegistryConfig(
        entity=os.environ.get("WANDB_ENTITY", DEFAULT_ENTITY),
        registry=os.environ.get("SLEAP_ROOTS_MODEL_REGISTRY", DEFAULT_REGISTRY),
        alias=os.environ.get("SLEAP_ROOTS_MODEL_ALIAS", DEFAULT_ALIAS),
    )


def require_api_key() -> None:
    """Fail fast if ``WANDB_API_KEY`` is not set.

    Raises:
        RuntimeError: If ``WANDB_API_KEY`` is unset, before any network call.
    """
    if not os.environ.get("WANDB_API_KEY"):
        raise RuntimeError(
            "WANDB_API_KEY is not set; cannot contact the wandb registry."
        )
