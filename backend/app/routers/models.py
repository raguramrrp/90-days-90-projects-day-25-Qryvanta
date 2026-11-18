"""Model Centre Router: version history, held-out metrics, controlled retraining, and activation."""

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.models.intelligence import ModelVersion, TicketFeedback
from app.models.user import User
from app.schemas.schemas import ModelTrainRequest
from app.services.audit_service import log_audit_event
from app.services.auth_service import require_roles
from app.services.intelligence_service import clear_predictor_cache
from ml.training.train_pipeline import train_hierarchical_classifier

router = APIRouter(prefix="/api/models", tags=["Model Centre"])


def _serialize_model(m: ModelVersion) -> dict:
    return {
        "id": m.id,
        "model_name": m.model_name,
        "version": m.version,
        "algorithm": m.algorithm,
        "dataset_reference": m.dataset_reference,
        "training_date": m.training_date.isoformat() if m.training_date else None,
        "evaluation_metrics": m.evaluation_metrics or {},
        "model_path": Path(m.model_path).name if m.model_path else None,
        "artifact_exists": bool(m.model_path and Path(m.model_path).exists()),
        "is_active": m.is_active,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("")
def list_models(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    models = db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    feedback_count = db.query(TicketFeedback).count()
    return {
        "models": [_serialize_model(m) for m in models],
        "pending_feedback_corrections": feedback_count,
        "has_active_model": any(m.is_active for m in models),
    }


@router.get("/active")
def get_active_model(
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if not active:
        return {
            "active_model": None,
            "message": "No trained model is currently active. Classification uses the transparent rule-based fallback until a model is trained and activated.",
        }
    return {"active_model": _serialize_model(active)}


@router.get("/{model_id}/metrics")
def get_model_metrics(
    model_id: int,
    current_user: User = Depends(require_roles("agent", "manager", "admin")),
    db: Session = Depends(get_db),
):
    model = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found.")
    return _serialize_model(model)


@router.post("/train", status_code=status.HTTP_201_CREATED)
def train_new_model(
    payload: ModelTrainRequest,
    request: Request,
    current_user: User = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Controlled retraining workflow: combines base training dataset with verified human corrections."""
    settings = get_settings()
    base_csv = Path(settings.SYNTHETIC_DATA_DIR) / "synthetic_support_tickets.csv"
    if not base_csv.exists():
        from data.synthetic.generate_dataset import generate_synthetic_dataset
        generate_synthetic_dataset(base_csv)

    df = pd.read_csv(base_csv)
    dataset_ref = f"synthetic_support_tickets.csv ({len(df)} base rows)"

    feedback_added = 0
    if payload.include_feedback_corrections:
        feedbacks = db.query(TicketFeedback).all()
        fb_rows = []
        for fb in feedbacks:
            if fb.ticket and fb.corrected_category:
                fb_rows.append(
                    {
                        "subject": fb.ticket.subject,
                        "description": fb.ticket.description,
                        "category": fb.corrected_category.name,
                        "subcategory": fb.corrected_subcategory.name if fb.corrected_subcategory else "",
                    }
                )
        if fb_rows:
            df = pd.concat([df, pd.DataFrame(fb_rows)], ignore_index=True)
            feedback_added = len(fb_rows)
            dataset_ref += f" + {feedback_added} human-verified corrections"

    existing_count = db.query(ModelVersion).count()
    version = payload.version_label.strip() if payload.version_label else f"v1.{existing_count}.0-{datetime.now(timezone.utc).strftime('%m%d%H%M')}"
    if db.query(ModelVersion).filter(ModelVersion.version == version).first():
        version = f"{version}-{int(datetime.now(timezone.utc).timestamp()) % 1000}"

    try:
        result = train_hierarchical_classifier(
            df=df,
            output_dir=Path(settings.ML_MODELS_DIR),
            version=version,
            dataset_reference=dataset_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if payload.activate_immediately:
        db.query(ModelVersion).update({ModelVersion.is_active: False})

    mv = ModelVersion(
        model_name=result["model_name"],
        version=result["version"],
        algorithm=result["algorithm"],
        dataset_reference=result["dataset_reference"],
        training_date=datetime.now(timezone.utc),
        evaluation_metrics=result["evaluation_metrics"],
        model_path=result["model_path"],
        is_active=payload.activate_immediately,
    )
    db.add(mv)
    db.flush()
    clear_predictor_cache()

    log_audit_event(
        db,
        action="model.train",
        entity_type="model_version",
        entity_id=mv.id,
        user_id=current_user.id,
        details={
            "version": mv.version,
            "feedback_added": feedback_added,
            "activated": payload.activate_immediately,
            "test_macro_f1": result["evaluation_metrics"].get("macro_f1"),
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(mv)
    return _serialize_model(mv)


@router.post("/{model_id}/activate")
def activate_model(
    model_id: int,
    request: Request,
    current_user: User = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    model = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found.")
    if not model.model_path or not Path(model.model_path).exists():
        raise HTTPException(status_code=400, detail="Model artifact file is missing from disk.")

    db.query(ModelVersion).update({ModelVersion.is_active: False})
    model.is_active = True
    clear_predictor_cache()

    log_audit_event(
        db,
        action="model.activate",
        entity_type="model_version",
        entity_id=model.id,
        user_id=current_user.id,
        details={"version": model.version},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(model)
    return _serialize_model(model)
