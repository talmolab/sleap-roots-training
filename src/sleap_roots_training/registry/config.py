"""Environment-driven wandb registry configuration.

Entity, the models-registry name, and the production alias are resolved from
environment variables with defaults so nothing is hardcoded and pointing at a
different registry later is a config change. These MUST resolve to the same target
the ``sleap-roots-predict`` consumer points ``SRP_WANDB_ENTITY`` /
``SRP_WANDB_REGISTRY`` at.
"""

from __future__ import annotations

import netrc
import os
from dataclasses import dataclass
from pathlib import Path

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


def _resolve_netrc_path() -> Path | None:
    """Locate the netrc file the same way wandb does.

    Mirrors ``wandb.sdk.lib.wbauth.wbnetrc._get_netrc_file_path`` (verified
    against ``wandb==0.28.0``) so a ``wandb login`` session is found on every
    platform: the ``NETRC`` env var if set, else ``~/.netrc``, else ``~/_netrc``
    (the file ``wandb login`` writes on Windows). Kept wandb-free by using only
    the stdlib.

    Returns:
        A netrc path, or ``None`` if none is found. When ``NETRC`` is set its
        path is returned as-is (existence is not checked, matching wandb); the
        ``~/.netrc`` / ``~/_netrc`` fallbacks are only returned when they exist.
    """
    env_path = os.environ.get("NETRC")
    if env_path:
        return Path(env_path).expanduser()
    unix_netrc = Path("~/.netrc").expanduser()
    if unix_netrc.exists():
        return unix_netrc
    windows_netrc = Path("~/_netrc").expanduser()
    if windows_netrc.exists():
        return windows_netrc
    return None


def _has_wandb_credential() -> bool:
    """Return whether a wandb credential is resolvable without contacting wandb.

    A credential is resolvable if ``WANDB_API_KEY`` is set or a netrc entry for
    ``api.wandb.ai`` with a non-empty password exists (as written by
    ``wandb login``). A malformed, unreadable, or missing netrc is treated as
    "no credential" rather than raising, and the check never imports ``wandb``.

    Returns:
        ``True`` if a credential is resolvable, ``False`` otherwise.
    """
    if os.environ.get("WANDB_API_KEY"):
        return True
    netrc_path = _resolve_netrc_path()
    if netrc_path is None:
        return False
    try:
        creds = netrc.netrc(netrc_path).authenticators(WANDB_NETRC_MACHINE)
    except (netrc.NetrcParseError, OSError):
        # Malformed/unreadable/missing netrc -> no credential. Mirrors the
        # narrow catch in wandb==0.28.0 wbnetrc.read_netrc_auth_with_source;
        # FileNotFoundError is an OSError, so a stale NETRC path is covered too.
        return False
    # authenticators() returns a truthy 3-tuple even when the password field is
    # empty/absent, so require a non-empty password (creds[2]) -- matching
    # wandb==0.28.0 wbnetrc.read_netrc_auth_with_source ("if not password").
    return bool(creds and creds[2])


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
