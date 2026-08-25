from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissionIntake:
    mission_id: str
    objective: str
    quality_profile: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]


class MissionIntakeService:
    ALLOWED_QUALITY = {"MVP", "PRODUCTION", "CRITICAL"}

    def prepare(
        self,
        *,
        mission_id: str,
        objective: str,
        quality_profile: str = "PRODUCTION",
        constraints: tuple[str, ...] = (),
        non_goals: tuple[str, ...] = (),
    ) -> MissionIntake:
        mission_id = mission_id.strip()
        objective = objective.strip()
        quality_profile = quality_profile.upper().strip()
        if not mission_id or not objective:
            raise ValueError("mission_id and objective are required")
        if quality_profile not in self.ALLOWED_QUALITY:
            raise ValueError(f"unsupported quality_profile: {quality_profile}")
        return MissionIntake(
            mission_id=mission_id,
            objective=objective,
            quality_profile=quality_profile,
            constraints=tuple(item.strip() for item in constraints if item.strip()),
            non_goals=tuple(item.strip() for item in non_goals if item.strip()),
        )
