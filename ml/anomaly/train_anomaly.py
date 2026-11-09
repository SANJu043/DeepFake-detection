"""
Train Isolation Forest anomaly detector on baseline traffic data.

This module trains an Isolation Forest on normal user behavior features:
- uploads_per_hour
- requests_per_minute
- unique_endpoints_per_session
- avg_response_time_ms
- failed_auth_attempts

Usage:
    python -m ml.anomaly.train_anomaly --data baseline_traffic.jsonl --output anomaly_model.pkl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Feature configuration
# ---------------------------------------------------------------------------

FEATURE_COLUMNS: List[str] = [
    "uploads_per_hour",
    "requests_per_minute",
    "unique_endpoints_per_session",
    "avg_response_time_ms",
    "failed_auth_attempts",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_jsonl(path: Path, feature_cols: List[str]) -> np.ndarray:
    """Load a JSONL file and extract numeric feature columns.

    Parameters
    ----------
    path:
        Path to the ``.jsonl`` file.  Each line must be a JSON object.
    feature_cols:
        Ordered list of keys to extract from every record.

    Returns
    -------
    np.ndarray
        Shape ``(n_samples, n_features)`` with dtype ``float64``.
        Rows where any feature is missing or non-numeric are skipped with a
        warning.
    """
    rows: List[List[float]] = []
    skipped = 0

    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  [WARN] Line {lineno}: JSON parse error – {exc}", file=sys.stderr)
                skipped += 1
                continue

            try:
                row = [float(record[col]) for col in feature_cols]
            except (KeyError, TypeError, ValueError) as exc:
                print(f"  [WARN] Line {lineno}: feature extraction error – {exc}", file=sys.stderr)
                skipped += 1
                continue

            rows.append(row)

    if not rows:
        raise ValueError(f"No valid samples found in {path}")

    if skipped:
        print(f"  [INFO] Skipped {skipped} malformed record(s).", file=sys.stderr)

    return np.array(rows, dtype=np.float64)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train(
    data_path: Path,
    output_path: Path,
    contamination: float = 0.05,
    n_estimators: int = 100,
    random_state: int = 42,
    feature_cols: Optional[List[str]] = None,
) -> None:
    """Train an Isolation Forest on baseline traffic data and save the model.

    Parameters
    ----------
    data_path:
        Path to the input ``.jsonl`` file.
    output_path:
        Destination ``.pkl`` file for the fitted ``(scaler, model)`` tuple.
    contamination:
        Expected proportion of anomalies in the training data (0 < c ≤ 0.5).
    n_estimators:
        Number of base estimators (trees) in the forest.
    random_state:
        Random seed for reproducibility.
    feature_cols:
        Feature columns to use; defaults to :data:`FEATURE_COLUMNS`.
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLUMNS

    print(f"Loading data from: {data_path}")
    X = load_jsonl(data_path, feature_cols)

    n_samples, n_features = X.shape
    print(f"\nTraining summary")
    print(f"  n_samples     : {n_samples}")
    print(f"  features ({n_features}) : {feature_cols}")
    print(f"  contamination : {contamination}")
    print(f"  n_estimators  : {n_estimators}")
    print(f"  random_state  : {random_state}")

    # Scale features to zero mean / unit variance before fitting
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X_scaled)

    # Quick sanity-check: fraction flagged as anomaly on training data
    preds = clf.predict(X_scaled)          # +1 normal, -1 anomaly
    n_anomaly = int((preds == -1).sum())
    print(f"\n  Anomalies detected in training set : {n_anomaly}/{n_samples} "
          f"({100 * n_anomaly / n_samples:.1f} %)")

    # Persist (scaler, model) tuple so inference code can use the same scaling
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "scaler": scaler,
        "model": clf,
        "feature_cols": feature_cols,
        "contamination": contamination,
        "n_estimators": n_estimators,
        "random_state": random_state,
        "n_training_samples": n_samples,
    }
    joblib.dump(artifact, output_path)
    print(f"\nModel saved to: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train an Isolation Forest anomaly detector on baseline traffic data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to baseline traffic JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("anomaly_model.pkl"),
        metavar="FILE",
        help="Output path for the fitted model artifact (.pkl).",
    )
    parser.add_argument(
        "--contamination",
        type=float,
        default=0.05,
        metavar="FLOAT",
        help="Expected fraction of anomalies in training data (0, 0.5].",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        dest="n_estimators",
        metavar="INT",
        help="Number of trees in the Isolation Forest.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        dest="random_state",
        metavar="INT",
        help="Random seed for reproducibility.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.data.exists():
        parser.error(f"Data file not found: {args.data}")

    if not (0 < args.contamination <= 0.5):
        parser.error("--contamination must be in (0, 0.5]")

    if args.n_estimators < 1:
        parser.error("--n-estimators must be a positive integer")

    train(
        data_path=args.data,
        output_path=args.output,
        contamination=args.contamination,
        n_estimators=args.n_estimators,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()
