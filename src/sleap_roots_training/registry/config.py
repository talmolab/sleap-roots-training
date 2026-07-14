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


WANDB_NETRC_MACHINE = "api.wandb.ai"


def _resolve_netrc_path() -> str | None:
    """Locate the netrc file the same way wandb does.

    Mirrors ``wandb.sdk.lib.wbauth.wbnetrc._get_netrc_file_path`` so a
    ``wandb login`` session is found on every platform: the ``NETRC`` env var
    if set, else ``~/.netrc``, else ``~/_netrc`` (the file ``wandb login``
    writes on Windows). Kept wandb-free by using only the stdlib.

    Returns:
        The path to an existing netrc file, or ``None`` if none is found.
    """
    env_path = os.environ.get("NETRC")
    if env_path:
        return os.path.expanduser(env_path)
    unix_netrc = os.path.expanduser("~/.netrc")
    if os.path.exists(unix_netrc):
        return unix_netrc
    windows_netrc = os.path.expanduser("~/_netrc")
    if os.path.exists(windows_netrc):
        return windows_netrc
    return None


def _has_wandb_credential() -> bool:
    """Return whether a wandb credential is resolvable without contacting wandb.

    A credential is resolvable if ``WANDB_API_KEY`` is set or a netrc entry for
    ``api.wandb.ai`` exists (as written by ``wandb login``). A malformed,
    unreadable, or missing netrc is treated as "no credential" rather than
    raising, and the check never imports ``wandb``.

    Returns:
        ``True`` if a credential is resolvable, ``False`` otherwise.
    """
    if os.environ.get("WANDB_API_KEY"):
        return True
    netrc_path = _resolve_netrc_path()
    if netrc_path is None:
        return False
    try:
        import netrc

        return bool(netrc.netrc(netrc_path).authenticators(WANDB_NETRC_MACHINE))
    except Exception:
        return False


def require_api_key() -> None:
    """Fail fast if no wandb credential is resolvable.

    A credential is resolvable via ``WANDB_API_KEY`` or a netrc entry for
    ``api.wandb.ai`` written by ``wandb login`` (see :func:`_has_wandb_credential`).

    Raises:
        RuntimeError: If no credential is resolvable, before any network call.
    """
    if not _has_wandb_credential():
        raise RuntimeError(
            "No wandb credential found; set WANDB_API_KEY or run `wandb login` "
            "(a netrc entry for api.wandb.ai). Cannot contact the wandb registry."
        )
