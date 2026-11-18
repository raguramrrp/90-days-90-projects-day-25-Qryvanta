"""Tests for Multi-Platform Portals, Companies, Ticket Verification & Company Handoff Briefs."""

from tests.conftest import auth_headers


def test_portal_company_intake_verification_and_handoff_report(client, db_session):
    mgr_hdr = auth_headers(db_session, "manager@test.local")
    cust_hdr = auth_headers(db_session, "cust1@test.local")

    # 1. Manager registers an E-Commerce company
    c_res = client.post(
        "/api/companies",
        headers=mgr_hdr,
        json={
            "name": "CartWave E-Commerce",
            "platform_type": "E-Commerce",
            "portal_url": "https://cartwave.example.com",
            "support_email": "refunds@cartwave.example.com",
            "description": "Online retail marketplace.",
        },
    )
    assert c_res.status_code == 201
    company_id = c_res.json()["id"]

    # Customer can list companies to select where to raise the ticket
    list_c = client.get("/api/companies?active_only=true", headers=cust_hdr)
    assert list_c.status_code == 200
    assert any(c["id"] == company_id for c in list_c.json()["companies"])

    # 2. Customer raises an e-commerce unrefunded return ticket against CartWave
    t_res = client.post(
        "/api/tickets",
        headers=cust_hdr,
        json={
            "subject": "Returned product refund not issued after warehouse delivery",
            "description": "I returned my headphones to CartWave E-Commerce 10 days ago and tracking confirms delivery, yet no refund was issued.",
            "company_id": company_id,
            "platform_type": "E-Commerce",
            "external_reference": "ORD-CW-99210",
        },
    )
    assert t_res.status_code == 201
    ticket = t_res.json()
    tid = ticket["id"]
    assert ticket["company"]["name"] == "CartWave E-Commerce"
    assert ticket["platform_type"] == "E-Commerce"
    assert ticket["external_reference"] == "ORD-CW-99210"
    assert ticket["verification"]["status"] == "unverified"

    # 3. Customers cannot verify tickets (403 Forbidden)
    cust_verify = client.post(
        f"/api/tickets/{tid}/verify",
        headers=cust_hdr,
        json={
            "verification_status": "verified_ready",
            "verification_notes": "Attempted self verification.",
        },
    )
    assert cust_verify.status_code == 403

    # 4. Support Manager verifies evidence and reports directly to the company
    v_res = client.post(
        f"/api/tickets/{tid}/verify",
        headers=mgr_hdr,
        json={
            "verification_status": "reported_to_company",
            "verification_notes": "Confirmed courier return receipt signed at warehouse on Nov 10; no refund transaction exists on ledger.",
            "recommended_company_action": "Approve direct refund of $149 to original Visa ending 4421 for ORD-CW-99210 without repeat investigation.",
            "company_case_reference": "CW-REF-7781",
        },
    )
    assert v_res.status_code == 200
    verified = v_res.json()
    assert verified["verification"]["status"] == "reported_to_company"
    assert verified["verification"]["company_case_reference"] == "CW-REF-7781"
    assert verified["verification"]["verified_at"] is not None
    assert verified["verification"]["reported_to_company_at"] is not None

    # 5. Generate structured company handoff report (JSON and Markdown download)
    rep_json = client.get(f"/api/tickets/{tid}/company-report", headers=mgr_hdr)
    assert rep_json.status_code == 200
    body = rep_json.json()
    assert body["company_name"] == "CartWave E-Commerce"
    assert body["external_reference"] == "ORD-CW-99210"
    assert "Approve direct refund" in body["report_markdown"]

    rep_dl = client.get(f"/api/tickets/{tid}/company-report?download=true", headers=mgr_hdr)
    assert rep_dl.status_code == 200
    assert "QRYVANTA Verified Case Handoff Report" in rep_dl.text

    # 6. Portal-wise filtering on Ticket Queue & Portal Analytics
    filtered = client.get(
        f"/api/tickets?platform_type=E-Commerce&company_id={company_id}&verification_status=reported_to_company",
        headers=mgr_hdr,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    portal_stats = client.get("/api/analytics/portals", headers=mgr_hdr)
    assert portal_stats.status_code == 200
    p_data = portal_stats.json()
    assert p_data["total_tickets"] == 1
    assert p_data["by_portal"][0]["platform_type"] == "E-Commerce"
    assert p_data["by_portal"][0]["reported_to_company"] == 1
    assert p_data["by_company"][0]["company_name"] == "CartWave E-Commerce"
