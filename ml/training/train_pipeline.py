"""Hierarchical Ticket Classification Training Pipeline (TF-IDF + Logistic Regression)."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.pipeline import Pipeline

from ml.preprocessing.text_cleaner import combine_ticket_text, normalize_text
from ml.evaluation.evaluator import evaluate_predictions, MIN_RELIABLE_SAMPLES_PER_CLASS


def deduplicate_records(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Remove duplicate normalized texts before splitting to prevent train/test data leakage."""
    df = df.copy()
    df["clean_text"] = df.apply(
        lambda r: combine_ticket_text(str(r.get("subject", "")), str(r.get("description", ""))),
        axis=1,
    )
    df = df[df["clean_text"].str.len() > 3].copy()
    before = len(df)
    df = df.drop_duplicates(subset=["clean_text"], keep="first").reset_index(drop=True)
    removed = before - len(df)
    return df, removed


def train_hierarchical_classifier(
    df: pd.DataFrame,
    output_dir: Path,
    version: str,
    dataset_reference: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Train a main-category TF-IDF + LogisticRegression classifier and per-category subcategory models.
    Enforces strict deduplication before stratified train/test splitting to guarantee zero leakage.
    """
    required_cols = {"subject", "description", "category"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Training dataset missing required columns: {sorted(missing)}")

    clean_df, duplicates_removed = deduplicate_records(df)
    if len(clean_df) < 16:
        raise ValueError("Insufficient deduplicated records to train a reliable classifier (minimum 16).")

    class_counts = Counter(clean_df["category"].astype(str))
    # Keep only classes with at least 2 samples for stratified split
    stratify_ok = all(cnt >= 2 for cnt in class_counts.values()) and len(class_counts) >= 2
    if not stratify_ok:
        raise ValueError("Each category requires at least 2 deduplicated samples for stratified evaluation.")

    X = clean_df["clean_text"].tolist()
    y_cat = clean_df["category"].astype(str).tolist()
    has_subcat = "subcategory" in clean_df.columns and clean_df["subcategory"].notna().any()
    y_sub = clean_df["subcategory"].fillna("").astype(str).tolist() if has_subcat else [""] * len(clean_df)

    indices = np.arange(len(clean_df))
    has_groups = "template_group_id" in clean_df.columns and clean_df["template_group_id"].notna().all()
    if has_groups and clean_df["template_group_id"].nunique() >= 10:
        groups = clean_df["template_group_id"].astype(str).tolist()
        n_splits = max(2, int(round(1.0 / max(test_size, 0.1))))
        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        train_idx, test_idx = next(sgkf.split(indices, y_cat, groups))
        split_label = f"Group-stratified {int((1-test_size)*100)}/{int(test_size*100)} split (zero template leakage across folds)"
    else:
        train_idx, test_idx = train_test_split(
            indices,
            test_size=test_size,
            random_state=random_state,
            stratify=y_cat,
        )
        split_label = f"Stratified {int((1-test_size)*100)}/{int(test_size*100)} train/test split after deduplication"

    X_train = [X[i] for i in train_idx]
    y_train = [y_cat[i] for i in train_idx]
    X_test = [X[i] for i in test_idx]
    y_test = [y_cat[i] for i in test_idx]

    main_pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=8000,
                    min_df=1,
                    sublinear_tf=True,
                    stop_words="english",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    C=3.0,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )

    main_pipeline.fit(X_train, y_train)
    y_pred = main_pipeline.predict(X_test).tolist()

    labels = sorted(list(set(y_cat)))
    train_counts = Counter(y_train)
    metrics = evaluate_predictions(y_test, y_pred, labels, dict(train_counts))

    # Train hierarchical subcategory classifiers on the training split only
    subcategory_models: Dict[str, Any] = {}
    sub_y_true_all: List[str] = []
    sub_y_pred_all: List[str] = []

    if has_subcat:
        sub_train_by_cat: Dict[str, Tuple[List[str], List[str]]] = {}
        for i in train_idx:
            cat_val = y_cat[i]
            sub_val = y_sub[i]
            if sub_val:
                sub_train_by_cat.setdefault(cat_val, ([], []))
                sub_train_by_cat[cat_val][0].append(X[i])
                sub_train_by_cat[cat_val][1].append(sub_val)

        for cat_val, (sx, sy) in sub_train_by_cat.items():
            unique_subs = sorted(set(sy))
            if len(unique_subs) == 1:
                subcategory_models[cat_val] = {"type": "constant", "label": unique_subs[0]}
            elif len(unique_subs) >= 2:
                sub_pipe = Pipeline(
                    [
                        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True)),
                        ("clf", LogisticRegression(max_iter=1000, C=2.5, class_weight="balanced", random_state=random_state)),
                    ]
                )
                sub_pipe.fit(sx, sy)
                subcategory_models[cat_val] = {"type": "pipeline", "pipeline": sub_pipe}

        # Evaluate subcategory predictions on held-out test records whose true category matches
        for i in test_idx:
            cat_val = y_cat[i]
            true_sub = y_sub[i]
            if not true_sub or cat_val not in subcategory_models:
                continue
            sub_entry = subcategory_models[cat_val]
            if sub_entry["type"] == "constant":
                pred_sub = sub_entry["label"]
            else:
                pred_sub = str(sub_entry["pipeline"].predict([X[i]])[0])
            sub_y_true_all.append(true_sub)
            sub_y_pred_all.append(pred_sub)

    sub_accuracy: Optional[float] = None
    if sub_y_true_all:
        matches = sum(1 for t, p in zip(sub_y_true_all, sub_y_pred_all) if t == p)
        sub_accuracy = round(matches / len(sub_y_true_all), 4)

    metrics["subcategory_test_accuracy"] = sub_accuracy
    metrics["train_samples"] = len(X_train)
    metrics["total_deduplicated_samples"] = len(clean_df)
    metrics["duplicates_removed_before_split"] = duplicates_removed
    metrics["split_strategy"] = split_label
    metrics["min_reliable_samples_per_class"] = MIN_RELIABLE_SAMPLES_PER_CLASS

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"ticket_classifier_{version}.joblib"

    artifact = {
        "model_name": "QRYVANTA Hierarchical Support Classifier",
        "version": version,
        "algorithm": "TF-IDF (1-2 grams) + Balanced Logistic Regression",
        "dataset_reference": dataset_reference,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "main_pipeline": main_pipeline,
        "subcategory_models": subcategory_models,
        "labels": labels,
        "train_class_counts": dict(train_counts),
        "evaluation_metrics": metrics,
    }
    joblib.dump(artifact, artifact_path)

    return {
        "version": version,
        "model_name": artifact["model_name"],
        "algorithm": artifact["algorithm"],
        "dataset_reference": dataset_reference,
        "model_path": str(artifact_path),
        "evaluation_metrics": metrics,
    }
