"""Evaluate the currently active QRYVANTA classifier and print per-category test metrics."""

from pathlib import Path
import sys
import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.session import SessionLocal
from app.models.intelligence import ModelVersion


def main() -> None:
    db = SessionLocal()
    try:
        active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        if not active:
            print("No active trained model found. Run `python scripts/train_classifier.py` first.")
            return
        print(f"Active Model: {active.model_name} ({active.version})")
        print(f"Algorithm   : {active.algorithm}")
        print(f"Dataset     : {active.dataset_reference}")
        print(f"Trained At  : {active.training_date}")
        m = active.evaluation_metrics or {}
        print(f"Held-out Test Accuracy : {m.get('accuracy')}")
        print(f"Macro Precision/Recall/F1: {m.get('macro_precision')} / {m.get('macro_recall')} / {m.get('macro_f1')}")
        print(f"Weighted F1            : {m.get('weighted_f1')}")
        print(f"Subcategory Accuracy   : {m.get('subcategory_test_accuracy')}")
        print("\nPer-category performance (held-out test set):")
        for row in m.get("per_category", []):
            warn = " [LOW SUPPORT]" if row.get("insufficient_data") else ""
            print(
                f"  - {row['category']:28s} | P={row['precision']:.3f} R={row['recall']:.3f} "
                f"F1={row['f1']:.3f} | train={row['train_support']} test={row['test_support']}{warn}"
            )
        if active.model_path and Path(active.model_path).exists():
            art = joblib.load(active.model_path)
            print(f"\nVerified joblib artifact loads cleanly ({len(art.get('labels', []))} classes).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
