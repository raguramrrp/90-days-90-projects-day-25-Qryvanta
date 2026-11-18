"""Model evaluation utilities: strict held-out test metrics with leakage prevention."""

from typing import Any, Dict, List
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

MIN_RELIABLE_SAMPLES_PER_CLASS = 10


def evaluate_predictions(
    y_true: List[str],
    y_pred: List[str],
    labels: List[str],
    train_class_counts: Dict[str, int],
) -> Dict[str, Any]:
    """Compute held-out test evaluation metrics and flag classes with insufficient training support."""
    acc = float(accuracy_score(y_true, y_pred))
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )
    per_p, per_r, per_f1, per_support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    per_category = []
    warnings = []
    for idx, label in enumerate(labels):
        train_count = int(train_class_counts.get(label, 0))
        insufficient = train_count < MIN_RELIABLE_SAMPLES_PER_CLASS
        if insufficient:
            warnings.append(
                f"Category '{label}' has only {train_count} training examples "
                f"(minimum recommended: {MIN_RELIABLE_SAMPLES_PER_CLASS}). Predictions may be unreliable."
            )
        per_category.append(
            {
                "category": label,
                "precision": round(float(per_p[idx]), 4),
                "recall": round(float(per_r[idx]), 4),
                "f1": round(float(per_f1[idx]), 4),
                "test_support": int(per_support[idx]),
                "train_support": train_count,
                "insufficient_data": insufficient,
            }
        )

    return {
        "accuracy": round(acc, 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "labels": labels,
        "confusion_matrix": cm,
        "per_category": per_category,
        "warnings": warnings,
        "test_samples": len(y_true),
    }
