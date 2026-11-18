# QRYVANTA — Machine Learning & NLP Methodology

## 1. Hierarchical Ticket Classification

- **Preprocessing (`ml/preprocessing/text_cleaner.py`)**:
  - Unicode NFKC normalization and PII anonymization (emails, phone numbers, URLs, and order/invoice references replaced with neutral tokens).
  - Subject text is weighted 2x relative to body description before TF-IDF vectorization.
- **Model Architecture (`ml/training/train_pipeline.py`)**:
  - **Main Category Classifier**: `TfidfVectorizer(ngram_range=(1, 2), max_features=8000, sublinear_tf=True, stop_words="english")` paired with `LogisticRegression(class_weight="balanced", C=3.0)`.
  - **Subcategory Classifiers**: Per-category hierarchical TF-IDF + Logistic Regression pipelines trained strictly on the training split.
- **Leakage Prevention & Evaluation**:
  - Exact normalized duplicates are removed before splitting (`deduplicate_records`).
  - When `template_group_id` is present on synthetic data, `StratifiedGroupKFold` ensures no variants from the same template appear in both training and held-out test folds.
  - All reported metrics (accuracy, macro/weighted precision/recall/F1, confusion matrix, per-category metrics, subcategory test accuracy) are measured exclusively on the held-out test set.
  - Classes with fewer than 10 training samples automatically trigger a `low_support_warning` in both evaluation reports and inference explanations.

### Measured Initial Baseline (`v1.0.0`, Synthetic Demo Dataset — 459 Train / 117 Held-Out Test)

| Metric | Held-Out Test Score |
|---|---|
| Main Category Accuracy | **88.89%** |
| Macro Precision | **89.30%** |
| Macro Recall | **89.17%** |
| Macro F1 | **88.63%** |
| Weighted F1 | **88.45%** |
| Subcategory Test Accuracy | **52.14%** |

> **Honest Interpretation**: Main-category classification performs reliably on unseen phrasing groups (~88.9%), while fine-grained 24-way subcategory accuracy (52.1%) reflects genuine lexical overlap across closely related sub-issues when training support per subcategory is small (~19 rows each). This directly motivates QRYVANTA's confidence-threshold routing and human-in-the-loop correction workflow.

## 2. Confidence-Based Routing

Configured via Settings (`confidence_thresholds`, adjustable without code changes):
- **High confidence (`>= 0.80`)**: Eligible for automatic department routing.
- **Medium confidence (`0.55 – 0.79`)**: Routed to suggested department flagged for staff review.
- **Low confidence (`< 0.55`)**: Sent to manual triage (`department_id = None`).

## 3. Priority / Urgency Separation

Priority (`critical`, `high`, `medium`, `low`) is evaluated independently from ticket category and negative sentiment (`backend/app/services/priority_service.py`). Angry tone alone never triggers Critical priority; outage, security incident, data loss, safety hazard, or multi-user operational blocking signals do, with every rationale displayed and staff overrides recorded.

## 4. Duplicate & Related Ticket Detection

Uses TF-IDF (1–2 grams) cosine similarity (`ml/duplicate_detection/similarity.py`) with a configurable cutoff (default `0.25`). Candidate comparison is strictly scoped by role authorization (customers never see other customers' tickets). Tickets are never automatically merged or closed.

## 5. Supporting Sentiment Analysis

Uses a transparent rule-based lexicon with negation and intensifier handling (`ml/sentiment/analyzer.py`), explicitly labeled `rule_based_lexicon` in the UI and API. Displayed purely as agent context alongside conversation sentiment trends.
