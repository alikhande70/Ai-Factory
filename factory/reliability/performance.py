from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import platform
from pathlib import Path
import sys
import time
from typing import Callable, TypeVar

from .slo import OperationSample, SLOEvidence, ServiceLevelObjective, evaluate_slo


T = TypeVar("T")


@dataclass(frozen=True)
class EnvironmentFingerprint:
    python_version: str
    implementation: str
    platform: str
    machine: str

    @classmethod
    def current(cls) -> "EnvironmentFingerprint":
        return cls(
            python_version=platform.python_version(),
            implementation=platform.python_implementation(),
            platform=platform.platform(),
            machine=platform.machine() or "unknown",
        )

    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PerformanceQualificationReport:
    report_version: int
    environment: str
    environment_fingerprint: EnvironmentFingerprint
    environment_fingerprint_sha256: str
    objective: ServiceLevelObjective
    evidence: SLOEvidence

    def to_dict(self) -> dict[str, object]:
        return {
            "report_version": self.report_version,
            "environment": self.environment,
            "environment_fingerprint": asdict(self.environment_fingerprint),
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "objective": asdict(self.objective),
            "evidence": asdict(self.evidence),
        }


def qualify_operation(
    *,
    objective: ServiceLevelObjective,
    iterations: int,
    operation: Callable[[], T],
    environment: str = "CI",
    warmup_iterations: int = 5,
) -> PerformanceQualificationReport:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")

    for _ in range(warmup_iterations):
        operation()

    samples: list[OperationSample] = []
    start = time.perf_counter()
    for _ in range(iterations):
        sample_start = time.perf_counter()
        success = True
        try:
            operation()
        except Exception:
            success = False
        latency_ms = (time.perf_counter() - sample_start) * 1000.0
        samples.append(OperationSample(objective.operation, latency_ms, success))
    duration = time.perf_counter() - start

    evidence = evaluate_slo(
        objective,
        samples,
        duration_seconds=max(duration, sys.float_info.epsilon),
        environment=environment,  # type: ignore[arg-type]
    )
    fingerprint = EnvironmentFingerprint.current()
    return PerformanceQualificationReport(
        report_version=1,
        environment=environment,
        environment_fingerprint=fingerprint,
        environment_fingerprint_sha256=fingerprint.digest(),
        objective=objective,
        evidence=evidence,
    )


def write_report(report: PerformanceQualificationReport, path: str | Path, *, overwrite: bool = False) -> None:
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
