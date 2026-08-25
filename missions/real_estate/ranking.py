from __future__ import annotations

from dataclasses import dataclass

from .contracts import ListingCandidate, ListingState, SearchSignals


@dataclass(frozen=True)
class RankingDecision:
    eligible: bool
    score: float
    reasons: tuple[str, ...]


_WEIGHTS = {
    "relevance": 0.40,
    "freshness": 0.25,
    "completeness": 0.15,
    "publisher_trust": 0.20,
}


def rank_listing(candidate: ListingCandidate, signals: SearchSignals) -> RankingDecision:
    candidate.validate()
    signals.validate()

    if candidate.state not in {ListingState.ACTIVE, ListingState.UNDER_OFFER}:
        return RankingDecision(False, 0.0, (f"state:{candidate.state.value}:not-rank-eligible",))
    if signals.freshness <= 0.0:
        return RankingDecision(False, 0.0, ("freshness:expired",))

    positive = (
        signals.relevance * _WEIGHTS["relevance"]
        + signals.freshness * _WEIGHTS["freshness"]
        + signals.completeness * _WEIGHTS["completeness"]
        + signals.publisher_trust * _WEIGHTS["publisher_trust"]
    )
    score = max(0.0, min(1.0, positive - (signals.anomaly_penalty * 0.25)))
    reasons = (
        f"relevance:{signals.relevance:.3f}",
        f"freshness:{signals.freshness:.3f}",
        f"completeness:{signals.completeness:.3f}",
        f"publisher_trust:{signals.publisher_trust:.3f}",
        f"anomaly_penalty:{signals.anomaly_penalty:.3f}",
    )
    return RankingDecision(True, round(score, 6), reasons)
