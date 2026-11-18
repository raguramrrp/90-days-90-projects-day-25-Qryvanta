"""ML classification, confidence thresholds, priority separation, and duplicate detection tests."""

from pathlib import Path
import pandas as pd
import pytest

from app.services.priority_service import assess_priority
from app.services.routing_service import route_ticket_by_confidence
from app.models.ticket import Category
from data.synthetic.generate_dataset import generate_synthetic_dataset
from ml.duplicate_detection.similarity import find_similar_tickets
from ml.prediction.predictor import TicketClassifierPredictor
from ml.training.train_pipeline import train_hierarchical_classifier
from tests.conftest import auth_headers


def test_ml_training_evaluation_and_prediction(tmp_path):
    csv_path = tmp_path / "synth.csv"
    df = generate_synthetic_dataset(csv_path, seed=42)
    assert len(df) >= 400

    # Deliberately inject duplicates to verify deduplication before train/test split
    dup_df = pd.concat([df, df.head(20)], ignore_index=True)
    res = train_hierarchical_classifier(
        df=dup_df,
        output_dir=tmp_path / "models",
        version="v-test-1",
        dataset_reference="unit_test_synth",
    )
    metrics = res["evaluation_metrics"]
    assert metrics["duplicates_removed_before_split"] >= 20
    assert metrics["accuracy"] > 0.75
    assert metrics["macro_f1"] > 0.75
    assert len(metrics["confusion_matrix"]) == len(metrics["labels"])

    predictor = TicketClassifierPredictor(res["model_path"])
    assert predictor.is_loaded
    pred = predictor.predict(
        "Double charged on monthly billing statement",
        "My Visa card was charged twice for the October invoice and I need a refund.",
    )
    assert pred["category"] == "Billing and Payments"
    assert pred["confidence"] > 0.5
    assert pred["model_version"] == "v-test-1"
    assert pred["prediction_source"] == "ml_model"

    with pytest.raises(ValueError):
        predictor.predict("", "   ")


def test_priority_independent_of_negative_sentiment():
    # Angry customer with no outage/security/blocking issue should NOT be auto-escalated to critical
    prio, reason = assess_priority(
        "Very frustrated with your slow response",
        "I am angry and extremely disappointed with your color theme choice.",
    )
    assert prio != "critical"
    assert "independently" in reason.lower() or "standard" in reason.lower()

    # Genuine outage or security breach IS critical
    crit_prio, crit_reason = assess_priority(
        "Production down across all users",
        "Complete outage on reporting API returning 500 internal server error.",
    )
    assert crit_prio == "critical"
    assert "outage" in crit_reason.lower() or "failure" in crit_reason.lower()


def test_confidence_threshold_routing(db_session):
    billing_cat = db_session.query(Category).filter(Category.name == "Billing and Payments").first()

    high = route_ticket_by_confidence(db_session, billing_cat.id, 0.91)
    assert high["routing_decision"] == "auto_routed"
    assert high["final_department_id"] is not None

    med = route_ticket_by_confidence(db_session, billing_cat.id, 0.65)
    assert med["routing_decision"] == "review_suggested"
    assert med["final_department_id"] is not None

    low = route_ticket_by_confidence(db_session, billing_cat.id, 0.42)
    assert low["routing_decision"] == "manual_triage"
    assert low["final_department_id"] is None


def test_duplicate_detection_and_privacy(client, db_session):
    candidates = [
        {"id": 1, "ticket_reference": "QRY-1", "subject": "Double charged on Visa invoice", "description": "Charged twice on October billing statement, need refund.", "category_name": "Billing", "status": "open", "priority": "high"},
        {"id": 2, "ticket_reference": "QRY-2", "subject": "WiFi antenna firmware release notes", "description": "Looking for datasheet on hardware radio specifications.", "category_name": "General", "status": "closed", "priority": "low"},
    ]
    sims = find_similar_tickets(
        "Visa statement double charged for October",
        "I was charged twice on my October invoice and request a refund.",
        candidates,
        threshold=0.20,
    )
    assert len(sims) == 1
    assert sims[0]["ticket_id"] == 1

    # Verify customer privacy on /api/intelligence/similar/{id}
    c1 = auth_headers(db_session, "cust1@test.local")
    c2 = auth_headers(db_session, "cust2@test.local")
    mgr = auth_headers(db_session, "manager@test.local")

    t1 = client.post("/api/tickets", headers=c1, json={"subject": "Visa double charge October", "description": "Charged twice on October Visa billing statement."}).json()
    t2 = client.post("/api/tickets", headers=c2, json={"subject": "Visa double charge October", "description": "Charged twice on October Visa billing statement."}).json()

    # Customer 1 must NEVER see Customer 2's ticket in similar results
    sim_c1 = client.get(f"/api/intelligence/similar/{t1['id']}", headers=c1).json()
    assert all(item["ticket_id"] != t2["id"] for item in sim_c1["similar_tickets"])

    # Manager CAN see cross-customer similar ticket and manually link it
    sim_mgr = client.get(f"/api/intelligence/similar/{t1['id']}?threshold=0.15", headers=mgr).json()
    assert any(item["ticket_id"] == t2["id"] for item in sim_mgr["similar_tickets"])

    link = client.post(
        f"/api/tickets/{t1['id']}/relations",
        headers=mgr,
        json={"related_ticket_id": t2["id"], "relation_type": "duplicate", "similarity_score": 0.85},
    )
    assert link.status_code == 201
