"""Train the initial QRYVANTA hierarchical ticket classifier and register it in model_versions."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config.settings import get_settings
from app.database.init_db import init_db
from app.database.session import SessionLocal
from app.models.intelligence import ModelVersion
from data.synthetic.generate_dataset import generate_synthetic_dataset
from ml.training.train_pipeline import train_hierarchical_classifier


def train_and_register(version: str = "v1.0.0", activate: bool = True) -> dict:
    init_db()
    settings = get_settings()
    dataset_path = Path(settings.SYNTHETIC_DATA_DIR) / "synthetic_support_tickets.csv"
    if not dataset_path.exists():
        generate_synthetic_dataset(dataset_path)

    df = pd.read_csv(dataset_path)
    result = train_hierarchical_classifier(
        df=df,
        output_dir=Path(settings.ML_MODELS_DIR),
        version=version,
        dataset_reference=f"synthetic_support_tickets.csv ({len(df)} synthetic demo rows)",
    )

    db = SessionLocal()
    try:
        existing = db.query(ModelVersion).filter(ModelVersion.version == version).first()
        if activate:
            db.query(ModelVersion).update({ModelVersion.is_active: False})

        if existing:
            existing.algorithm = result["algorithm"]
            existing.dataset_reference = result["dataset_reference"]
            existing.training_date = datetime.now(timezone.utc)
            existing.evaluation_metrics = result["evaluation_metrics"]
            existing.model_path = result["model_path"]
            existing.is_active = activate
        else:
            db.add(
                ModelVersion(
                    model_name=result["model_name"],
                    version=result["version"],
                    algorithm=result["algorithm"],
                    dataset_reference=result["dataset_reference"],
                    training_date=datetime.now(timezone.utc),
                    evaluation_metrics=result["evaluation_metrics"],
                    model_path=result["model_path"],
                    is_active=activate,
                )
            )
        db.commit()
    finally:
        db.close()

    m = result["evaluation_metrics"]
    print(f"Trained QRYVANTA classifier {version}")
    print(f"  Artifact : {result['model_path']}")
    print(f"  Split    : {m['train_samples']} train / {m['test_samples']} held-out test ({m['duplicates_removed_before_split']} duplicates removed)")
    print(f"  Accuracy : {m['accuracy']:.4f} | Macro F1: {m['macro_f1']:.4f} | Weighted F1: {m['weighted_f1']:.4f}")
    print(f"  Subcat Test Accuracy: {m.get('subcategory_test_accuracy')}")
    return result


if __name__ == "__main__":
    train_and_register()
