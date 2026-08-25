from __future__ import annotations

from typing import Protocol

from factory.design_pod.contracts import DesignBundle
from factory.engineering_pod.integration import IntegrationManifest

from .contracts import AssuranceReport


class AssuranceWorker(Protocol):
    agent_id: str

    def review(
        self,
        *,
        design: DesignBundle,
        integration: IntegrationManifest,
    ) -> AssuranceReport:
        ...
