"""End-to-end ticket lifecycle, internal note privacy, reassignment, reclassification, and reopening tests."""

from app.models.ticket import Category
from app.models.user import Agent, Department
from tests.conftest import auth_headers


def test_full_ticket_lifecycle_and_internal_note_privacy(client, db_session):
    cust_hdr = auth_headers(db_session, "cust1@test.local")
    agent_hdr = auth_headers(db_session, "agent@test.local")
    mgr_hdr = auth_headers(db_session, "manager@test.local")

    # 1. Customer submits ticket
    create_res = client.post(
        "/api/tickets",
        headers=cust_hdr,
        json={
            "subject": "Double charged on monthly billing statement",
            "description": "My credit card was double charged this afternoon and I need a refund promptly.",
            "product_reference": "Plan-Pro",
        },
    )
    assert create_res.status_code == 201
    t = create_res.json()
    tid = t["id"]
    assert t["ticket_reference"].startswith("QRY-")
    # Customers must NOT receive internal ML prediction details
    assert "prediction" not in t

    # 2. Manager assigns ticket to billing agent
    agent = db_session.query(Agent).first()
    assign_res = client.post(
        f"/api/tickets/{tid}/assign",
        headers=mgr_hdr,
        json={"agent_id": agent.id, "reason": "Lowest workload in Billing."},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_agent"]["id"] == agent.id

    # 3. Agent posts a public reply AND a private internal note
    pub_res = client.post(
        f"/api/tickets/{tid}/reply",
        headers=agent_hdr,
        json={"message": "We are reviewing your duplicate charge now.", "visibility": "public"},
    )
    assert pub_res.status_code == 201

    priv_res = client.post(
        f"/api/tickets/{tid}/reply",
        headers=agent_hdr,
        json={"message": "INTERNAL SECRET: fraud team flag checked, clean.", "visibility": "internal"},
    )
    assert priv_res.status_code == 201

    # 4. Verify agent sees both messages, customer NEVER sees the internal note
    agent_view = client.get(f"/api/tickets/{tid}", headers=agent_hdr).json()
    assert len(agent_view["messages"]) == 2
    assert any(m["visibility"] == "internal" for m in agent_view["messages"])

    cust_view = client.get(f"/api/tickets/{tid}", headers=cust_hdr).json()
    assert len(cust_view["messages"]) == 1
    assert all(m["visibility"] == "public" for m in cust_view["messages"])
    assert "INTERNAL SECRET" not in str(cust_view)

    # 5. Customer replies back
    c_reply = client.post(
        f"/api/tickets/{tid}/reply",
        headers=cust_hdr,
        json={"message": "Thank you, attaching my invoice reference INV-223.", "visibility": "internal"},
    )
    assert c_reply.status_code == 201
    # Customer cannot force visibility='internal'
    assert c_reply.json()["messages"][-1]["visibility"] == "public"

    # 6. Agent corrects classification with feedback reason
    tech_cat = db_session.query(Category).filter(Category.name == "Technical Support").first()
    tech_dept = db_session.query(Department).filter(Department.name == "Technical Support").first()
    reclass = client.post(
        f"/api/tickets/{tid}/reclassify",
        headers=mgr_hdr,
        json={
            "corrected_category_id": tech_cat.id,
            "corrected_department_id": tech_dept.id,
            "corrected_priority": "high",
            "correction_reason": "Gateway webhook bug caused duplicate debit.",
        },
    )
    assert reclass.status_code == 200
    assert reclass.json()["category_id"] == tech_cat.id
    assert len(reclass.json()["feedback_history"]) == 1

    # 7. Manager resolves ticket, customer rates and reopens it
    close_res = client.post(
        f"/api/tickets/{tid}/close",
        headers=mgr_hdr,
        json={"resolution_note": "Refund issued and webhook patched.", "status": "resolved"},
    )
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "resolved"

    rate_res = client.post(
        f"/api/tickets/{tid}/rate",
        headers=cust_hdr,
        json={"rating": 5, "comment": "Very clear update."},
    )
    assert rate_res.status_code == 200
    assert rate_res.json()["satisfaction_rating"] == 5

    reopen_res = client.post(
        f"/api/tickets/{tid}/reopen",
        headers=cust_hdr,
        json={"reason": "Refund confirmation email not yet received."},
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["status"] == "reopened"
    assert reopen_res.json()["reopen_count"] == 1
