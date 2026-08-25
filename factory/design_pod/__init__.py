"""Design Pod contracts, workers, coordination and deterministic consistency checks."""

from .contracts import AcceptanceCriterion, ArchitectureDecision, DesignBundle, ProductRequirement, UXFlow
from .coordinator import DesignPodCoordinator
from .validator import DesignBundleValidator, ValidationFinding
from .workers import (
    ArchitectureDesignOutput,
    ProductArchitectWorker,
    ProductDesignOutput,
    RevisableProductArchitectWorker,
    RevisableSystemArchitectWorker,
    RevisableUXWorker,
    RevisionRequest,
    SystemArchitectWorker,
    UXDesignOutput,
    UXWorker,
)

__all__ = [
    "AcceptanceCriterion",
    "ArchitectureDecision",
    "DesignBundle",
    "ProductRequirement",
    "UXFlow",
    "DesignBundleCoordinator",
    "DesignPodCoordinator",
    "DesignBundleValidator",
    "ValidationFinding",
    "ArchitectureDesignOutput",
    "ProductArchitectWorker",
    "ProductDesignOutput",
    "RevisableProductArchitectWorker",
    "RevisableSystemArchitectWorker",
    "RevisableUXWorker",
    "RevisionRequest",
    "SystemArchitectWorker",
    "UXDesignOutput",
    "UXWorker",
]

# Backwards-friendly descriptive alias for callers that prefer artifact terminology.
DesignBundleCoordinator = DesignPodCoordinator
