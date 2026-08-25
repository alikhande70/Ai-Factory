from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, TypeVar


REDACTED_SECRET = "***SECRET***"
T = TypeVar("T")


@dataclass(frozen=True)
class SecretReference:
    """Opaque canonical pointer to secret material.

    Canonical/runtime state may persist this object (or its JSON projection), but never
    the resolved value. Access is bound to a mission and required capability.
    """

    secret_id: str
    provider: str
    mission_id: str
    required_capability: str
    purpose: str
    version: str | None = None

    def __post_init__(self) -> None:
        required = {
            "secret_id": self.secret_id,
            "provider": self.provider,
            "mission_id": self.mission_id,
            "required_capability": self.required_capability,
            "purpose": self.purpose,
        }
        for field_name, value in required.items():
            if not value or not value.strip():
                raise ValueError(f"{field_name} is required")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "secret_id": self.secret_id,
            "provider": self.provider,
            "mission_id": self.mission_id,
            "required_capability": self.required_capability,
            "purpose": self.purpose,
            "version": self.version,
        }


class SecretProvider(Protocol):
    """Trusted host-side secret provider.

    Deliberately exposes resolve only. Enumeration/listing is not part of the contract.
    """

    provider_name: str

    def resolve(self, reference: SecretReference) -> str:
        ...


class SecretMaterial:
    """Resolved secret value with deliberately non-revealing display semantics.

    The raw value is kept behind a private attribute and is only consumed by
    SecretBroker while invoking a trusted executor callback.
    """

    __slots__ = ("__value", "reference")

    def __init__(self, *, reference: SecretReference, value: str) -> None:
        if not value:
            raise ValueError("resolved secret must not be empty")
        self.reference = reference
        self.__value = value

    def __repr__(self) -> str:
        return f"SecretMaterial(reference={self.reference.secret_id!r}, value={REDACTED_SECRET!r})"

    def __str__(self) -> str:
        return REDACTED_SECRET

    def _for_trusted_executor(self) -> str:
        return self.__value


@dataclass(frozen=True)
class SecretBinding:
    env_name: str
    reference: SecretReference

    def __post_init__(self) -> None:
        if not self.env_name or not self.env_name.strip():
            raise ValueError("env_name is required")
        if "=" in self.env_name or "\x00" in self.env_name:
            raise ValueError("invalid env_name")


class SecretBroker:
    """Deterministic host-side authorization and injection boundary.

    AI-facing callers provide opaque references. The broker verifies mission/capability
    scope, resolves only the requested references, and gives raw values exclusively to
    the supplied trusted executor callback. It never offers a list/enumerate API.
    """

    def __init__(self, providers: Mapping[str, SecretProvider]) -> None:
        self._providers = dict(providers)
        for name, provider in self._providers.items():
            if provider.provider_name != name:
                raise ValueError("provider mapping/name mismatch")

    def execute_with_bindings(
        self,
        *,
        mission_id: str,
        actor_id: str,
        agent_capabilities: tuple[str, ...],
        bindings: tuple[SecretBinding, ...],
        executor: Callable[[Mapping[str, str]], T],
    ) -> T:
        if not mission_id or not actor_id:
            raise ValueError("mission_id and actor_id are required")
        if not bindings:
            return executor({})

        capabilities = set(agent_capabilities)
        env: dict[str, str] = {}
        seen_env_names: set[str] = set()

        for binding in bindings:
            reference = binding.reference
            if binding.env_name in seen_env_names:
                raise ValueError("duplicate secret env binding")
            seen_env_names.add(binding.env_name)

            if reference.mission_id != mission_id:
                raise PermissionError("cross_mission_secret_access_denied")
            if reference.required_capability not in capabilities:
                raise PermissionError("missing_secret_capability")

            provider = self._providers.get(reference.provider)
            if provider is None:
                raise KeyError(f"unknown secret provider: {reference.provider}")

            material = SecretMaterial(reference=reference, value=provider.resolve(reference))
            env[binding.env_name] = material._for_trusted_executor()

        return executor(env)


def contains_secret_material(value: object) -> bool:
    """Detect resolved SecretMaterial before persistence/serialization boundaries."""

    if isinstance(value, SecretMaterial):
        return True
    if isinstance(value, dict):
        return any(contains_secret_material(key) or contains_secret_material(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_secret_material(item) for item in value)
    return False


def secret_safe_projection(value: object) -> object:
    """Recursively redact SecretMaterial while preserving opaque SecretReference metadata."""

    if isinstance(value, SecretMaterial):
        return REDACTED_SECRET
    if isinstance(value, SecretReference):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): secret_safe_projection(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [secret_safe_projection(item) for item in value]
    return value
