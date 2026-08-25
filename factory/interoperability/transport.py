from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import ExternalTaskRequest


class InteropTransport(Protocol):
    transport_id: str

    def discover(self) -> tuple[dict[str, Any], ...]: ...

    def invoke(self, request: ExternalTaskRequest) -> dict[str, Any]: ...


@dataclass
class InMemoryInteropTransport:
    """Deterministic qualification fixture; performs no network I/O."""

    transport_id: str
    descriptors: tuple[dict[str, Any], ...]
    results_by_capability: dict[str, dict[str, Any]]

    def __post_init__(self) -> None:
        if not self.transport_id.strip():
            raise ValueError("transport_id is required")

    def discover(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self.descriptors)

    def invoke(self, request: ExternalTaskRequest) -> dict[str, Any]:
        request.validate()
        if request.capability_id not in self.results_by_capability:
            raise KeyError(f"no fixture result for capability:{request.capability_id}")
        return dict(self.results_by_capability[request.capability_id])
