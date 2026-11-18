"""Business-hours & holiday-aware SLA deadline calculator and status engine."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models.operations import AppSetting, Holiday, SLAPolicy, SLATracking
from app.models.ticket import Ticket


DEFAULT_BUSINESS_HOURS = {
    "start_hour": 9,
    "start_minute": 0,
    "end_hour": 17,
    "end_minute": 0,
    "workdays": [0, 1, 2, 3, 4],  # Monday=0 .. Friday=4
}


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_business_hours_config(db: Session) -> Dict:
    setting = db.query(AppSetting).filter(AppSetting.key == "business_hours").first()
    if setting and isinstance(setting.value, dict):
        merged = dict(DEFAULT_BUSINESS_HOURS)
        merged.update(setting.value)
        return merged
    return dict(DEFAULT_BUSINESS_HOURS)


def get_holiday_dates(db: Session) -> Set[date]:
    rows = db.query(Holiday.holiday_date).all()
    return {r[0] for r in rows}


def _is_working_day(day: date, workdays: Set[int], holidays: Set[date]) -> bool:
    return day.weekday() in workdays and day not in holidays


def add_business_minutes(
    start_dt: datetime,
    minutes_to_add: int,
    business_hours_only: bool = True,
    business_hours: Optional[Dict] = None,
    holidays: Optional[Set[date]] = None,
) -> datetime:
    """
    Calculate an exact deadline by advancing only through configured working hours
    and skipping weekends and configured holidays when `business_hours_only=True`.
    """
    current = ensure_utc(start_dt)
    if minutes_to_add <= 0:
        return current
    if not business_hours_only:
        return current + timedelta(minutes=minutes_to_add)

    cfg = business_hours or DEFAULT_BUSINESS_HOURS
    workdays = set(cfg.get("workdays", [0, 1, 2, 3, 4]))
    if not workdays:
        workdays = {0, 1, 2, 3, 4}
    holiday_set = holidays or set()

    start_t = time(int(cfg.get("start_hour", 9)), int(cfg.get("start_minute", 0)))
    end_t = time(int(cfg.get("end_hour", 17)), int(cfg.get("end_minute", 0)))
    remaining = int(minutes_to_add)

    guard = 0
    while remaining > 0 and guard < 4000:
        guard += 1
        cur_date = current.date()
        if not _is_working_day(cur_date, workdays, holiday_set):
            next_day = cur_date + timedelta(days=1)
            current = datetime.combine(next_day, start_t, tzinfo=timezone.utc)
            continue

        day_start = datetime.combine(cur_date, start_t, tzinfo=timezone.utc)
        day_end = datetime.combine(cur_date, end_t, tzinfo=timezone.utc)

        if current < day_start:
            current = day_start
        elif current >= day_end:
            next_day = cur_date + timedelta(days=1)
            current = datetime.combine(next_day, start_t, tzinfo=timezone.utc)
            continue

        available_minutes = int((day_end - current).total_seconds() // 60)
        if available_minutes <= 0:
            next_day = cur_date + timedelta(days=1)
            current = datetime.combine(next_day, start_t, tzinfo=timezone.utc)
            continue

        if remaining <= available_minutes:
            current = current + timedelta(minutes=remaining)
            remaining = 0
        else:
            remaining -= available_minutes
            next_day = cur_date + timedelta(days=1)
            current = datetime.combine(next_day, start_t, tzinfo=timezone.utc)

    return current


def find_applicable_policy(db: Session, priority: str, department_id: Optional[int]) -> Optional[SLAPolicy]:
    """Select department-specific SLA policy first, falling back to global priority SLA policy."""
    if department_id is not None:
        dept_policy = (
            db.query(SLAPolicy)
            .filter(
                SLAPolicy.is_active.is_(True),
                SLAPolicy.priority == priority,
                SLAPolicy.department_id == department_id,
            )
            .first()
        )
        if dept_policy:
            return dept_policy

    return (
        db.query(SLAPolicy)
        .filter(
            SLAPolicy.is_active.is_(True),
            SLAPolicy.priority == priority,
            SLAPolicy.department_id.is_(None),
        )
        .first()
    )


def create_or_update_sla_tracking(
    db: Session,
    ticket: Ticket,
    reference_time: Optional[datetime] = None,
) -> Optional[SLATracking]:
    """Create or recalculate SLA tracking deadlines for a ticket."""
    policy = find_applicable_policy(db, ticket.priority, ticket.department_id)
    if not policy:
        return None

    cfg = get_business_hours_config(db)
    holidays = get_holiday_dates(db)
    base_time = ensure_utc(reference_time or ticket.created_at or datetime.now(timezone.utc))

    fr_deadline = add_business_minutes(
        base_time,
        policy.first_response_minutes,
        business_hours_only=policy.business_hours_only,
        business_hours=cfg,
        holidays=holidays,
    )
    res_deadline = add_business_minutes(
        base_time,
        policy.resolution_minutes,
        business_hours_only=policy.business_hours_only,
        business_hours=cfg,
        holidays=holidays,
    )

    existing = db.query(SLATracking).filter(SLATracking.ticket_id == ticket.id).first()
    if existing:
        existing.policy_id = policy.id
        existing.first_response_deadline = fr_deadline
        existing.resolution_deadline = res_deadline
        existing.current_state = compute_sla_state(existing, ticket.status)
        return existing

    tracking = SLATracking(
        ticket_id=ticket.id,
        policy_id=policy.id,
        first_response_deadline=fr_deadline,
        resolution_deadline=res_deadline,
        current_state="on_track",
    )
    tracking.current_state = compute_sla_state(tracking, ticket.status)
    db.add(tracking)
    return tracking


def compute_sla_state(tracking: SLATracking, ticket_status: str, now: Optional[datetime] = None) -> str:
    """Evaluate real-time SLA state: completed, paused, overdue, approaching_deadline, or on_track."""
    current = ensure_utc(now or datetime.now(timezone.utc))

    if ticket_status in ("resolved", "closed") or tracking.resolved_at is not None:
        return "completed"

    if ticket_status == "awaiting_customer" or tracking.paused_at is not None:
        return "paused"

    paused_delta = timedelta(minutes=tracking.paused_minutes or 0)
    eff_fr = ensure_utc(tracking.first_response_deadline) + paused_delta
    eff_res = ensure_utc(tracking.resolution_deadline) + paused_delta

    # Overdue if first response missed without reply OR resolution deadline passed
    if tracking.first_responded_at is None and current > eff_fr:
        return "overdue"
    if current > eff_res:
        return "overdue"

    # Approaching if within 25% of remaining window or under 60 minutes to next deadline
    next_deadline = eff_fr if tracking.first_responded_at is None else eff_res
    remaining_minutes = (next_deadline - current).total_seconds() / 60.0
    if remaining_minutes <= 60:
        return "approaching_deadline"

    return "on_track"


def compute_sla_metrics(tracking: SLATracking, ticket_created: datetime, ticket_status: str, now: Optional[datetime] = None) -> Dict:
    """Return remaining minutes, breach flags, first-response duration, and resolution duration."""
    current = ensure_utc(now or datetime.now(timezone.utc))
    created = ensure_utc(ticket_created)
    paused_delta = timedelta(minutes=tracking.paused_minutes or 0)
    eff_fr = ensure_utc(tracking.first_response_deadline) + paused_delta
    eff_res = ensure_utc(tracking.resolution_deadline) + paused_delta
    state = compute_sla_state(tracking, ticket_status, current)

    fr_minutes = None
    if tracking.first_responded_at is not None:
        fr_minutes = round((ensure_utc(tracking.first_responded_at) - created).total_seconds() / 60.0, 1)

    res_minutes = None
    if tracking.resolved_at is not None:
        res_minutes = round((ensure_utc(tracking.resolved_at) - created).total_seconds() / 60.0, 1)

    fr_breached = (
        (tracking.first_responded_at is not None and ensure_utc(tracking.first_responded_at) > eff_fr)
        or (tracking.first_responded_at is None and state != "completed" and current > eff_fr)
    )
    res_breached = (
        (tracking.resolved_at is not None and ensure_utc(tracking.resolved_at) > eff_res)
        or (tracking.resolved_at is None and state != "completed" and current > eff_res)
    )

    if state == "completed":
        remaining_minutes = 0.0
    else:
        remaining_minutes = round((eff_res - current).total_seconds() / 60.0, 1)

    return {
        "policy_id": tracking.policy_id,
        "policy_name": tracking.policy.name if tracking.policy else None,
        "first_response_deadline": eff_fr,
        "resolution_deadline": eff_res,
        "first_responded_at": tracking.first_responded_at,
        "resolved_at": tracking.resolved_at,
        "paused_minutes": tracking.paused_minutes,
        "current_state": state,
        "time_remaining_minutes": remaining_minutes,
        "first_response_time_minutes": fr_minutes,
        "resolution_time_minutes": res_minutes,
        "sla_breached": bool(fr_breached or res_breached),
        "escalated": tracking.escalated,
        "escalated_at": tracking.escalated_at,
        "escalation_notes": tracking.escalation_notes,
    }


def handle_sla_pause_resume(tracking: SLATracking, old_status: str, new_status: str, now: Optional[datetime] = None) -> None:
    """Pause SLA clock while awaiting customer response and accumulate paused minutes upon resume."""
    current = ensure_utc(now or datetime.now(timezone.utc))
    if new_status == "awaiting_customer" and tracking.paused_at is None:
        tracking.paused_at = current
        tracking.current_state = "paused"
    elif old_status == "awaiting_customer" and new_status != "awaiting_customer" and tracking.paused_at is not None:
        paused_elapsed = max(0, int((current - ensure_utc(tracking.paused_at)).total_seconds() // 60))
        tracking.paused_minutes = (tracking.paused_minutes or 0) + paused_elapsed
        tracking.paused_at = None
        tracking.current_state = compute_sla_state(tracking, new_status, current)
