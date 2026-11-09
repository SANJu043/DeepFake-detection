"""
Anomaly and threat detection service (Section 7.5).

Watches the system's own usage to detect attacks on the detector and
the verifier. Uses a combination of:
- **Isolation Forest** (scikit-learn) on windowed audit-log features
- **Hard rule thresholds** for known attack patterns

Attacks it targets:
- Credential stuffing (many failed logins)
- Upload floods
- Verification scraping
- Adversarial probing (many slightly perturbed copies of one video)

Responses:
- Level 1: log and flag
- Level 2: throttle and require re-authentication
- Level 3: temporary lock and admin notification
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Alert levels
# ---------------------------------------------------------------------------

class AlertLevel(IntEnum):
    NONE = 0
    LOG_AND_FLAG = 1
    THROTTLE = 2
    LOCK = 3


# ---------------------------------------------------------------------------
# Feature vector
# ---------------------------------------------------------------------------

@dataclass
class WindowFeatures:
    """Features computed per subject (user or IP) per 10-minute window."""

    subject_type: str  # "user" or "ip"
    subject_id: str
    window_start: datetime
    uploads: int = 0
    total_bytes_uploaded: int = 0
    failed_logins: int = 0
    verify_requests: int = 0
    distinct_attestation_ids_queried: int = 0
    requests_per_minute: float = 0.0
    near_duplicate_ratio: float = 0.0  # same perceptual hash, different bytes
    fake_score_spread: float = 0.0  # variance of returned fake scores for near-dupes

    def to_vector(self) -> np.ndarray:
        """Convert to a numpy feature vector for the Isolation Forest."""
        return np.array([
            self.uploads,
            self.total_bytes_uploaded / 1e6,  # normalize to MB
            self.failed_logins,
            self.verify_requests,
            self.distinct_attestation_ids_queried,
            self.requests_per_minute,
            self.near_duplicate_ratio,
            self.fake_score_spread,
        ], dtype=np.float64)


# ---------------------------------------------------------------------------
# Anomaly event
# ---------------------------------------------------------------------------

@dataclass
class AnomalyEvent:
    """An anomaly detection alert."""

    event_id: str
    subject_type: str
    subject_id: str
    window_start: datetime
    features: Dict[str, Any]
    anomaly_score: float
    rule_hits: List[str]
    alert_level: AlertLevel
    action: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False


# ---------------------------------------------------------------------------
# Anomaly detector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Combines Isolation Forest anomaly scoring with hard rule thresholds.

    The model is trained on baseline (benign) traffic. At inference time,
    both the model score and rule hits contribute to the final alert.
    """

    def __init__(
        self,
        anomaly_threshold: float = -0.3,
        failed_login_limit: int = 5,
        upload_rate_limit: int = 20,
        verify_rate_limit: int = 100,
    ) -> None:
        self._anomaly_threshold = anomaly_threshold
        self._failed_login_limit = failed_login_limit
        self._upload_rate_limit = upload_rate_limit
        self._verify_rate_limit = verify_rate_limit

        # Isolation Forest model (lazy-loaded)
        self._model = None
        self._is_trained = False

    def train(self, baseline_features: np.ndarray) -> None:
        """
        Train the Isolation Forest on baseline (benign) traffic features.

        Args:
            baseline_features: (N, 8) array of feature vectors from benign traffic.
        """
        from sklearn.ensemble import IsolationForest

        self._model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(baseline_features)
        self._is_trained = True
        logger.info("anomaly.trained", n_samples=baseline_features.shape[0])

    def score(self, features: WindowFeatures) -> Tuple[float, List[str]]:
        """
        Score a feature window.

        Returns:
            (anomaly_score, list_of_rule_hits)
            Lower anomaly_score = more anomalous (sklearn convention).
        """
        rule_hits: List[str] = []

        # Hard rules
        if features.failed_logins >= self._failed_login_limit:
            rule_hits.append(
                f"FAILED_LOGINS: {features.failed_logins} >= {self._failed_login_limit}"
            )
        if features.uploads >= self._upload_rate_limit:
            rule_hits.append(
                f"UPLOAD_FLOOD: {features.uploads} >= {self._upload_rate_limit}"
            )
        if features.verify_requests >= self._verify_rate_limit:
            rule_hits.append(
                f"VERIFY_SCRAPING: {features.verify_requests} >= {self._verify_rate_limit}"
            )
        if features.near_duplicate_ratio > 0.5 and features.uploads > 3:
            rule_hits.append(
                f"ADVERSARIAL_PROBING: near_dup_ratio={features.near_duplicate_ratio:.2f}"
            )

        # Isolation Forest score
        anomaly_score = 0.0
        if self._is_trained and self._model is not None:
            vec = features.to_vector().reshape(1, -1)
            anomaly_score = float(self._model.score_samples(vec)[0])
        else:
            # Without a trained model, rely on rules only
            anomaly_score = -1.0 if rule_hits else 0.0

        return anomaly_score, rule_hits

    def evaluate(self, features: WindowFeatures) -> Optional[AnomalyEvent]:
        """
        Evaluate a window and return an AnomalyEvent if an alert is warranted.

        Returns:
            AnomalyEvent if alert level > NONE, else None.
        """
        import uuid

        anomaly_score, rule_hits = self.score(features)

        # Determine alert level
        is_anomalous = (
            anomaly_score < self._anomaly_threshold
            or len(rule_hits) > 0
        )

        if not is_anomalous:
            return None

        # Escalation
        if any("LOCK" in h or "ADVERSARIAL" in h for h in rule_hits):
            level = AlertLevel.LOCK
            action = "TEMPORARY_LOCK_AND_ADMIN_NOTIFY"
        elif len(rule_hits) >= 2 or anomaly_score < (self._anomaly_threshold * 2):
            level = AlertLevel.THROTTLE
            action = "THROTTLE_AND_REAUTH"
        else:
            level = AlertLevel.LOG_AND_FLAG
            action = "LOG_AND_FLAG"

        event = AnomalyEvent(
            event_id=str(uuid.uuid4()),
            subject_type=features.subject_type,
            subject_id=features.subject_id,
            window_start=features.window_start,
            features={
                "uploads": features.uploads,
                "total_bytes_uploaded": features.total_bytes_uploaded,
                "failed_logins": features.failed_logins,
                "verify_requests": features.verify_requests,
                "distinct_attestation_ids": features.distinct_attestation_ids_queried,
                "requests_per_minute": features.requests_per_minute,
                "near_duplicate_ratio": features.near_duplicate_ratio,
                "fake_score_spread": features.fake_score_spread,
            },
            anomaly_score=anomaly_score,
            rule_hits=rule_hits,
            alert_level=level,
            action=action,
        )

        logger.warning(
            "anomaly.alert",
            event_id=event.event_id,
            subject=features.subject_id,
            level=level.name,
            action=action,
            score=anomaly_score,
            rules=rule_hits,
        )

        return event
