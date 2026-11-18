"""Business-hours/holiday SLA engine, analytics calculations, and CSV bulk import tests."""

from datetime import date, datetime, timedelta, timezone

from app.models.operations import SLATracking
from app.services.sla_service import add_business_minutes, compute_sla_state
from tests.conftest import auth_headers


def test_business_hours_and_holiday_sla_calculation():
    # Friday 2026-11-20 at 16:00 UTC (1 hour left before 17:00 end of business day)
    start = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
    # Monday 2026-11-23 is a configured holiday -> should roll over to Tuesday 2026-11-24
    holidays = {date(2026, 11, 23)}

    # Adding 120 business minutes: 60 min on Fri (16:00-17:00), skip Sat/Sun/Mon holiday, 60 min Tue (09:00-10:00)
    deadline = add_business_minutes(start, 120, business_hours_only=True, holidays=holidays)
    assert deadline == datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)

    # Non-business-hours policy adds exact wall-clock minutes
    raw_deadline = add_business_minutes(start, 120, business_hours_only=False, holidays=holidays)
    assert raw_deadline == datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)


def test_sla_states_overdue_paused_completed():
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    t_overdue = SLATracking(
        ticket_id=1,
        first_response_deadline=now - timedelta(minutes=30),
        resolution_deadline=now + timedelta(hours=4),
        paused_minutes=0,
    )
    assert compute_sla_state(t_overdue, "open", now) == "overdue"
    assert compute_sla_state(t_overdue, "awaiting_customer", now) == "paused"
    assert compute_sla_state(t_overdue, "resolved", now) == "completed"


def test_analytics_empty_and_populated_with_filters(client, db_session):
    mgr = auth_headers(db_session, "manager@test.local")
    cust = auth_headers(db_session, "cust1@test.local")

    # Empty state handling
    empty = client.get("/api/analytics/overview", headers=mgr)
    assert empty.status_code == 200
    assert empty.json()["metrics"]["total_tickets"] == 0
    assert empty.json()["metrics"]["sla_compliance_rate"] is None

    # Create two tickets
    client.post(
        "/api/tickets",
        headers=cust,
        json={"subject": "Production down on API server", "description": "Complete outage affecting all users with 500 internal server error."},
    )
    client.post(
        "/api/tickets",
        headers=cust,
        json={"subject": "General question about documentation", "description": "How does your export documentation explain CSV fields?"},
    )

    pop = client.get("/api/analytics/overview", headers=mgr).json()
    assert pop["metrics"]["total_tickets"] == 2
    assert pop["metrics"]["open_tickets"] == 2

    # Priority filter
    crit_only = client.get("/api/analytics/overview?priority=critical", headers=mgr).json()
    assert crit_only["metrics"]["total_tickets"] == 1

    # Department & agent & SLA endpoints return valid structures
    assert client.get("/api/analytics/departments", headers=mgr).status_code == 200
    assert client.get("/api/analytics/agents", headers=mgr).status_code == 200
    assert client.get("/api/analytics/sla", headers=mgr).status_code == 200
    assert client.get("/api/analytics/classification", headers=mgr).status_code == 200


def test_bulk_csv_import_deduplication_and_validation(client, db_session):
    mgr = auth_headers(db_session, "manager@test.local")
    csv_body = (
        "subject,description,category\n"
        "Refund request for order 101,Please issue a full refund for our cancelled annual plan.,Billing and Payments\n"
        "Refund request for order 101,Please issue a full refund for our cancelled annual plan.,Billing and Payments\n"
        "Bad,Short,\n"
    )
    res = client.post(
        "/api/tickets/import/execute",
        headers=mgr,
        json={
            "csv_text": csv_body,
            "column_mapping": {"subject": "subject", "description": "description", "category": "category"},
            "is_demo_data": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["imported_count"] == 1
    assert data["skipped_duplicates"] == 1
    assert data["failed_count"] == 1
