"""
Policy engine: maps detection scores to verdicts.

Section 5a locked decisions — these are the ONLY verdict labels:
- NO_MANIPULATION_DETECTED  (fake_probability < threshold_clean)
- INCONCLUSIVE              (between thresholds, or special cases)
- LIKELY_MANIPULATED        (fake_probability > threshold_manipulated)

Special INCONCLUSIVE reasons:
- NO_FACE_DETECTED: no face found in the video
- TOO_SHORT: video is under 2 seconds

The word "authentic" is NEVER used as a verdict because a detector
cannot prove authenticity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.app.services.manifest import (
    VERDICT_INCONCLUSIVE,
    VERDICT_LIKELY_MANIPULATED,
    VERDICT_NO_MANIPULATION,
)


# ---------------------------------------------------------------------------
# Inconclusive reasons
# ---------------------------------------------------------------------------

REASON_NO_FACE = "NO_FACE_DETECTED"
REASON_TOO_SHORT = "TOO_SHORT"


# ---------------------------------------------------------------------------
# Policy result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyResult:
    """Immutable result from the policy engine."""

    verdict: str
    fake_probability: float
    inconclusive_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.verdict not in {
            VERDICT_NO_MANIPULATION,
            VERDICT_INCONCLUSIVE,
            VERDICT_LIKELY_MANIPULATED,
        }:
            raise ValueError(f"Invalid verdict: {self.verdict}")


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """
    Maps ensemble detection scores to verdict labels.

    Thresholds are configurable (from environment / config) but
    default to the values in the spec.
    """

    def __init__(
        self,
        threshold_clean: float = 0.30,
        threshold_manipulated: float = 0.70,
    ) -> None:
        if not (0.0 < threshold_clean < threshold_manipulated < 1.0):
            raise ValueError(
                f"Thresholds must satisfy 0 < clean ({threshold_clean}) "
                f"< manipulated ({threshold_manipulated}) < 1"
            )
        self.threshold_clean = threshold_clean
        self.threshold_manipulated = threshold_manipulated

    @property
    def thresholds_dict(self) -> dict:
        return {
            "clean_lt": self.threshold_clean,
            "manipulated_gt": self.threshold_manipulated,
        }

    def evaluate(
        self,
        fake_probability: float,
        face_detected: bool = True,
        duration_s: float = 10.0,
    ) -> PolicyResult:
        """
        Evaluate the detection score and produce a verdict.

        Args:
            fake_probability: Ensemble output in [0, 1].
            face_detected: Whether at least one face was found.
            duration_s: Video duration in seconds.

        Returns:
            PolicyResult with verdict, probability, and optional reason.
        """
        # Special cases first
        if not face_detected:
            return PolicyResult(
                verdict=VERDICT_INCONCLUSIVE,
                fake_probability=fake_probability,
                inconclusive_reason=REASON_NO_FACE,
            )

        if duration_s < 2.0:
            return PolicyResult(
                verdict=VERDICT_INCONCLUSIVE,
                fake_probability=fake_probability,
                inconclusive_reason=REASON_TOO_SHORT,
            )

        # Score-based verdict
        if fake_probability < self.threshold_clean:
            return PolicyResult(
                verdict=VERDICT_NO_MANIPULATION,
                fake_probability=fake_probability,
            )
        elif fake_probability > self.threshold_manipulated:
            return PolicyResult(
                verdict=VERDICT_LIKELY_MANIPULATED,
                fake_probability=fake_probability,
            )
        else:
            return PolicyResult(
                verdict=VERDICT_INCONCLUSIVE,
                fake_probability=fake_probability,
            )
