"""Comprehensive backend tests for QRYVANTA Upgrade Phases 1–3:
- Incident Detection & Grouping (unique affected customers vs ticket count, permissions, linking/unlinking)
- Customer Impact Analysis
- Deterministic SLA Breach Risk Prediction
- Risk & Workload Optimization
- Resolution Intelligence (genuine resolved retrieval, privacy, feedback)
- Knowledge Gap Detection & unpublished draft creation
- Resolution Effectiveness Analytics
"""

from datetime import datetime, timedelta, timezone
from app.models.ticket import Ticket
from app.services.sla_risk_service import compute_ticket_sla_risk
from tests.conftest import auth_headers


def test_incident_detection_grouping_unique_customers_and_permissions(client, db_session):
    c1 = auth_headers(db_session, "cust1@test.local")
    c2 = auth_headers(db_session, "cust2@test.local")
    agent = auth_headers(db_session, "agent@test.local")
    mgr = auth_headers(db_session, "manager@test.local")

    # Create 4 semantically similar payment tickets across 2 unique customers (cust1 submits 3, cust2 submits 1)
    created_ids = []
    for i, hdr in enumerate([c1, c1, c1, c2]):
        r = client.post(
            "/api/tickets",
            headers=hdr,
            json={
                "subject": "Money deducted from card but order not confirmed",
                "description": f"Payment was deducted for ref TXN-{900 + i} during checkout yet order is missing and payment stays pending.",
            },
        )
        assert r.status_code == 201
        created_ids.append(r.json()["id"])

    # Customers cannot access Incident Centre
    assert client.get("/api/incidents", headers=c1).status_code == 403
    # Agents cannot run detection or confirm/dismiss incidents
    assert client.post("/api/incidents/detect", headers=agent, json={}).status_code == 403

    # Manager runs TF-IDF incident detection
    det = client.post(
        "/api/incidents/detect",
        headers=mgr,
        json={"window_days": 14, "similarity_threshold": 0.25, "min_cluster_size": 3},
    )
    assert det.status_code == 200
    body = det.json()
    assert body["detected_count"] == 1
    inc = body["incidents"][0]
    # Must NEVER auto-confirm; starts as detected
    assert inc["status"] == "detected"
    # 4 tickets from 2 unique customers -> must report 2 affected customers, NOT 4!
    assert inc["ticket_count"] == 4
    assert inc["affected_customer_count"] == 2

    inc_id = inc["id"]

    # Manager confirms incident and adds investigation notes
    upd = client.patch(
        f"/api/incidents/{inc_id}",
        headers=mgr,
        json={"status": "confirmed", "investigation_notes": "Confirmed webhook drop on gateway v3."},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "confirmed"
    assert upd.json()["customer_impact"]["unique_affected_customers"] == 2
    assert upd.json()["customer_impact"]["repeat_complaint_customers"] == 1

    # Ticket detail exposes Customer Impact to staff, never to customer
    t_staff = client.get(f"/api/tickets/{created_ids[0]}", headers=mgr).json()
    assert t_staff["customer_impact"]["unique_affected_customers"] == 2
    assert t_staff["customer_impact"]["related_incident_count"] == 1
    assert t_staff["customer_impact"]["customer_unresolved_tickets"] == 3

    t_cust = client.get(f"/api/tickets/{created_ids[0]}", headers=c1).json()
    assert "customer_impact" not in t_cust

    # Unlink & re-link ticket
    unlnk = client.delete(f"/api/incidents/{inc_id}/tickets/{created_ids[-1]}", headers=agent)
    assert unlnk.status_code == 200
    assert unlnk.json()["ticket_count"] == 3
    assert unlnk.json()["affected_customer_count"] == 1

    relnk = client.post(f"/api/incidents/{inc_id}/tickets", headers=agent, json={"ticket_id": created_ids[-1]})
    assert relnk.status_code == 201
    assert relnk.json()["ticket_count"] == 4
    assert relnk.json()["affected_customer_count"] == 2

    # Manager dismisses incident
    dis = client.patch(f"/api/incidents/{inc_id}", headers=mgr, json={"status": "dismissed"})
    assert dis.status_code == 200
    assert dis.json()["status"] == "dismissed"


def test_sla_breach_risk_and_operations_workload(client, db_session):
    c1 = auth_headers(db_session, "cust1@test.local")
    mgr = auth_headers(db_session, "manager@test.local")

    r = client.post(
        "/api/tickets",
        headers=c1,
        json={
            "subject": "Production down: HTTP 500 across billing checkout",
            "description": "Complete outage affecting all users with 500 internal server error.",
        },
    )
    assert r.status_code == 201
    tid = r.json()["id"]

    # Force deadline to be 20 minutes from now to verify high/critical SLA risk detection
    t = db_session.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.now(timezone.utc)
    t.sla_tracking.resolution_deadline = now + timedelta(minutes=20)
    t.sla_tracking.first_response_deadline = now + timedelta(minutes=10)
    db_session.commit()

    risk = compute_ticket_sla_risk(db_session, t)
    assert risk["method"] == "deterministic_risk_rules"
    assert risk["risk_level"] in ("high", "critical")
    assert len(risk["factors"]) >= 2

    # Missing SLA tracking handled gracefully
    t.sla_tracking = None
    missing_risk = compute_ticket_sla_risk(db_session, t)
    assert missing_risk["sla_state"] == "unknown"

    # Risk & Workload overview endpoint works and surfaces unassigned critical ticket + agent recommendation
    ops = client.get("/api/operations/overview", headers=mgr)
    assert ops.status_code == 200
    ops_data = ops.json()
    assert ops_data["risk_method"] == "deterministic_risk_rules"
    assert len(ops_data["unassigned_high_priority"]) >= 1
    assert "available" in ops_data["agent_capacity"]


def test_resolution_intelligence_privacy_feedback_and_knowledge_gaps(client, db_session):
    c1 = auth_headers(db_session, "cust1@test.local")
    c2 = auth_headers(db_session, "cust2@test.local")
    mgr = auth_headers(db_session, "manager@test.local")

    # Resolved historical ticket from customer 1
    t_res = client.post(
        "/api/tickets",
        headers=c1,
        json={
            "subject": "Returned laptop refund delayed past 14 days",
            "description": "Warehouse confirmed receipt of my returned laptop order ORD-7712 yet refund never posted.",
        },
    ).json()
    client.post(
        f"/api/tickets/{t_res['id']}/close",
        headers=mgr,
        json={
            "status": "resolved",
            "resolution_note": "Issued manual credit memo refund for ORD-7712; funds clear in 3 business days.",
        },
    )

    # New open similar ticket from customer 2
    t_new = client.post(
        "/api/tickets",
        headers=c2,
        json={
            "subject": "Delayed refund for returned laptop order",
            "description": "My returned laptop arrived at warehouse two weeks ago and refund has not posted.",
        },
    ).json()

    # Manager retrieves genuine resolved case with real resolution text
    sim_mgr = client.get(f"/api/resolution/similar/{t_new['id']}", headers=mgr)
    assert sim_mgr.status_code == 200
    matches = sim_mgr.json()["similar_resolved"]
    assert len(matches) >= 1
    assert matches[0]["source_ticket_id"] == t_res["id"]
    assert "manual credit memo refund" in matches[0]["actual_resolution"]

    # Strict customer isolation: customer 2 must NEVER see customer 1's resolved ticket
    sim_c2 = client.get(f"/api/resolution/similar/{t_new['id']}", headers=c2).json()
    assert all(m["source_ticket_id"] != t_res["id"] for m in sim_c2["similar_resolved"])

    # Submit helpful feedback on the recommendation
    fb = client.post(
        "/api/resolution/feedback",
        headers=mgr,
        json={
            "ticket_id": t_new["id"],
            "source_ticket_id": t_res["id"],
            "recommendation_type": "similar_ticket",
            "rating": "helpful",
            "applied_to_reply": True,
        },
    )
    assert fb.status_code == 201

    # Resolution Intelligence overview & Knowledge Gaps
    res_ov = client.get("/api/resolution/overview", headers=mgr)
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert ov_data["effectiveness"]["sample_size"] >= 1
    assert ov_data["effectiveness"]["recommendation_effectiveness"]["helpful"] == 1
    assert len(ov_data["knowledge_gaps"]) >= 1

    # Create UNPUBLISHED draft KB article from detected gap
    gap_id = ov_data["knowledge_gaps"][0]["id"]
    draft = client.post(f"/api/resolution/knowledge-gaps/{gap_id}/draft", headers=mgr, json={})
    assert draft.status_code == 201
    assert draft.json()["is_published"] is False
