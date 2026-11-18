"""Customer Portal privacy isolation, friendly presets, Help Centre published-only filtering, and RBAC separation tests."""

from app.models.intelligence import KnowledgeArticle
from tests.conftest import auth_headers


def test_customer_ticket_responses_strip_internal_operational_fields(client, db_session):
    cust_hdr = auth_headers(db_session, "cust1@test.local")
    agent_hdr = auth_headers(db_session, "agent@test.local")

    created = client.post(
        "/api/tickets",
        headers=cust_hdr,
        json={
            "subject": "Double charge on monthly card billing",
            "description": "My credit card was charged twice for the same subscription invoice this morning.",
            "external_reference": "INV-8821",
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    ticket_id = created_body["id"]

    # Staff adds an internal note, a public reply, and internal verification notes
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/reply",
            headers=agent_hdr,
            json={"message": "Internal check: possible gateway duplicate.", "visibility": "internal"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/reply",
            headers=agent_hdr,
            json={
                "message": "We are reviewing your duplicate charge and will update you shortly.",
                "visibility": "public",
                "new_status": "awaiting_customer",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/verify",
            headers=agent_hdr,
            json={
                "verification_status": "verified_ready",
                "verification_notes": "Secret staff note for escalation",
                "recommended_company_action": "Reverse charge ID 4421",
            },
        ).status_code
        == 200
    )

    # Customer list payload must hide internal fields
    list_res = client.get("/api/tickets", headers=cust_hdr)
    assert list_res.status_code == 200
    item = list_res.json()["items"][0]
    for forbidden in (
        "priority",
        "priority_reason",
        "department_id",
        "department_name",
        "assigned_agent",
        "sla_state",
        "sla_breached",
        "resolution_deadline",
        "sentiment",
        "prediction_confidence",
        "routing_decision",
        "sla_risk_level",
        "sla_risk_score",
        "linked_incidents",
        "verification_status",
    ):
        assert forbidden not in item, f"Customer list unexpectedly exposed '{forbidden}'"
    assert item["ticket_reference"].startswith("QRY-")
    assert "has_assigned_support" in item

    # Customer detail payload must hide internal fields & internal notes
    detail_res = client.get(f"/api/tickets/{ticket_id}", headers=cust_hdr)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    for forbidden in (
        "priority",
        "department_name",
        "assigned_agent",
        "sla",
        "sla_risk",
        "prediction",
        "feedback_history",
        "sentiment_trend",
        "recommended_agents",
        "knowledge_recommendations",
        "confirmed_relations",
        "customer_impact",
    ):
        assert forbidden not in detail, f"Customer detail unexpectedly exposed '{forbidden}'"

    # Verification object should not expose internal notes or recommended company action
    assert "notes" not in detail.get("verification", {})
    assert "recommended_company_action" not in detail.get("verification", {})
    assert "verified_by_name" not in detail.get("verification", {})

    # Only public messages returned
    msgs = detail["messages"]
    assert len(msgs) == 1
    assert msgs[0]["visibility"] == "public"
    assert "Internal check" not in msgs[0]["message"]

    # Staff detail still sees full operational data
    staff_detail = client.get(f"/api/tickets/{ticket_id}", headers=agent_hdr).json()
    assert "sla" in staff_detail
    assert "sla_risk" in staff_detail
    assert "prediction" in staff_detail
    assert staff_detail["verification"]["notes"] == "Secret staff note for escalation"
    assert len(staff_detail["messages"]) == 2


def test_customer_active_and_resolved_presets(client, db_session):
    cust_hdr = auth_headers(db_session, "cust1@test.local")
    agent_hdr = auth_headers(db_session, "agent@test.local")

    t1 = client.post(
        "/api/tickets",
        headers=cust_hdr,
        json={
            "subject": "Order package still in transit",
            "description": "My delivery has been delayed for five days without tracking updates.",
        },
    ).json()
    t2 = client.post(
        "/api/tickets",
        headers=cust_hdr,
        json={
            "subject": "Receipt needed for completed order",
            "description": "Please send a downloadable receipt for my recent order payment.",
        },
    ).json()

    # Resolve second ticket
    assert (
        client.post(
            f"/api/tickets/{t2['id']}/close",
            headers=agent_hdr,
            json={"status": "resolved", "resolution_note": "Receipt sent to your email."},
        ).status_code
        == 200
    )

    active_items = client.get("/api/tickets?preset=active", headers=cust_hdr).json()["items"]
    resolved_items = client.get("/api/tickets?preset=resolved", headers=cust_hdr).json()["items"]

    assert [t["id"] for t in active_items] == [t1["id"]]
    assert [t["id"] for t in resolved_items] == [t2["id"]]


def test_customer_help_centre_published_only_and_search(client, db_session):
    cust_hdr = auth_headers(db_session, "cust1@test.local")
    admin_hdr = auth_headers(db_session, "admin@test.local")

    db_session.add(
        KnowledgeArticle(
            title="How return refunds work",
            content="Refunds are issued to your original payment method within 5 business days.",
            tags="refund,return,payment",
            is_published=True,
        )
    )
    db_session.add(
        KnowledgeArticle(
            title="Internal Draft Refund Runbook",
            content="Unpublished staff-only draft procedure for refund escalations.",
            tags="refund,internal",
            is_published=False,
        )
    )
    db_session.commit()

    cust_res = client.get("/api/knowledge?search=refund", headers=cust_hdr)
    assert cust_res.status_code == 200
    cust_titles = [a["title"] for a in cust_res.json()]
    assert "How return refunds work" in cust_titles
    assert "Internal Draft Refund Runbook" not in cust_titles

    admin_res = client.get("/api/knowledge?search=refund", headers=admin_hdr)
    assert admin_res.status_code == 200
    admin_titles = [a["title"] for a in admin_res.json()]
    assert "Internal Draft Refund Runbook" in admin_titles


def test_customer_blocked_from_all_staff_endpoints(client, db_session):
    cust_hdr = auth_headers(db_session, "cust1@test.local")
    for path in (
        "/api/sla/policies",
        "/api/incidents",
        "/api/operations/overview",
        "/api/resolution/overview",
        "/api/analytics/overview",
        "/api/departments",
        "/api/agents",
        "/api/models",
        "/api/routing-rules",
        "/api/users",
    ):
        res = client.get(path, headers=cust_hdr)
        assert res.status_code == 403, f"Expected 403 for customer on {path}, got {res.status_code}"
