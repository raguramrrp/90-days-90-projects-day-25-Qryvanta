"""Authentication, RBAC enforcement, and strict customer data isolation tests."""

from tests.conftest import auth_headers


def test_login_success_and_invalid_credentials(client):
    res = client.post("/api/auth/login", json={"email": "cust1@test.local", "password": "TestPass#2026"})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["user"]["role"] == "customer"

    bad = client.post("/api/auth/login", json={"email": "cust1@test.local", "password": "WrongPassword"})
    assert bad.status_code == 401


def test_register_new_customer(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "New Customer", "email": "newcust@test.local", "password": "Password#123"},
    )
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "customer"
    assert res.json()["user"]["customer_reference"].startswith("CUST-")


def test_unauthorized_and_role_enforcement(client, db_session):
    # Unauthenticated request must fail with 401
    assert client.get("/api/tickets").status_code == 401

    cust_hdr = auth_headers(db_session, "cust1@test.local")
    agent_hdr = auth_headers(db_session, "agent@test.local")
    admin_hdr = auth_headers(db_session, "admin@test.local")

    # Customers cannot access analytics, users, or audit logs
    assert client.get("/api/analytics/overview", headers=cust_hdr).status_code == 403
    assert client.get("/api/users", headers=cust_hdr).status_code == 403
    assert client.get("/api/audit-logs", headers=cust_hdr).status_code == 403

    # Agents cannot access admin-only user list or audit logs
    assert client.get("/api/users", headers=agent_hdr).status_code == 403
    assert client.get("/api/audit-logs", headers=agent_hdr).status_code == 403

    # Admins can access both
    assert client.get("/api/users", headers=admin_hdr).status_code == 200
    assert client.get("/api/audit-logs", headers=admin_hdr).status_code == 200


def test_customer_cannot_access_other_customer_ticket(client, db_session):
    cust1_hdr = auth_headers(db_session, "cust1@test.local")
    cust2_hdr = auth_headers(db_session, "cust2@test.local")

    created = client.post(
        "/api/tickets",
        headers=cust1_hdr,
        json={
            "subject": "Private refund inquiry for invoice 998",
            "description": "Please refund my duplicate invoice charge back to my Visa card.",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    # Customer 1 can read own ticket
    assert client.get(f"/api/tickets/{ticket_id}", headers=cust1_hdr).status_code == 200

    # Customer 2 gets 403 Forbidden by ID and does not see it in list
    assert client.get(f"/api/tickets/{ticket_id}", headers=cust2_hdr).status_code == 403
    list_c2 = client.get("/api/tickets", headers=cust2_hdr).json()
    assert list_c2["total"] == 0
