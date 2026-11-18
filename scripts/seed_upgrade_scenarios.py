"""
Additive, Idempotent Demo Scenarios Seeder for QRYVANTA Upgrade (Section 11).
- NEVER deletes or modifies existing users, companies, or tickets.
- Clearly marks every generated record with `is_demo_data=True`.
- Deterministic generation so metrics stay consistent across runs.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.session import SessionLocal
from app.models.incidents import Incident, IncidentTicket, ResolutionFeedback
from app.models.operations import Company
from app.models.ticket import Ticket, TicketMessage
from app.models.user import Agent, Customer, Department, User
from app.services.auth_service import hash_password
from app.services.incident_service import (
    detect_candidate_incidents,
    record_incident_event,
)
from app.services.resolution_service import detect_knowledge_gaps
from app.services.sla_service import compute_sla_state
from app.services.ticket_service import create_ticket_full


DEMO_PASSWORD = "DemoUser#2026"

PAYMENT_SUBJECTS = [
    "Money deducted from card but order not confirmed",
    "Payment deducted yet order missing from account",
    "Transaction successful on bank app but checkout stuck pending",
    "Card charged at checkout with no order confirmation",
    "UPI/card payment deducted and order not created",
]

PAYMENT_DESCRIPTIONS = [
    "My bank statement shows {amt} deducted under reference {txn}, but the CartWave checkout stayed on payment pending and no order confirmation email arrived.",
    "Payment was deducted immediately for {amt} (ref {txn}), yet my order history shows nothing and checkout says order not confirmed.",
    "Transaction {txn} succeeded with my issuing bank for {amt}, however the order is completely missing from my portal and payment remains pending.",
    "Money was debited ({amt}, txn {txn}) during checkout five minutes ago, but the order was never confirmed and the cart emptied.",
]

REFUND_DELAY_TEMPLATES = [
    ("Refund delayed 14 days after warehouse return receipt", "Returned my order {ref} on {dt}; courier tracking confirms warehouse delivery, yet refund of {amt} has not been credited.", False),
    ("Returned item refund still pending past 10 business days", "Return shipment for {ref} arrived at returns center on {dt}, still waiting on {amt} refund to original Visa.", False),
    ("Delayed refund for cancelled prepaid order", "Cancelled order {ref} on {dt} before shipment; payment gateway still shows refund {amt} pending.", False),
    ("No refund posted after approved RMA return", "RMA return for {ref} was inspected on {dt} and approved for {amt}, yet bank card shows no credit.", False),
    ("Resolved: delayed return refund processed via manual credit memo", "Warehouse received returned package {ref} on {dt}; refund {amt} was stuck in settlement batch.", True),
    ("Resolved: missing refund for returned electronics order", "Returned headset order {ref} delivered on {dt}; automated refund of {amt} failed gateway retry.", True),
    ("Resolved: duplicate settlement refund delayed past 7 days", "Approved refund of {amt} for {ref} initiated on {dt} did not settle to Mastercard.", True),
]

OTP_SUBJECTS = [
    "Login OTP SMS verification code never arrives",
    "Cannot sign in — two-factor OTP code not received",
    "OTP verification failing during account login",
    "Login blocked because 6-digit OTP never reaches phone",
]

OTP_DESCRIPTIONS = [
    "Attempting to sign into AuthVault portal since this morning; requested login OTP verification code three times on registered phone but no SMS arrives.",
    "Every login attempt triggers two-factor OTP prompt yet the verification code never arrives, leaving our team locked out of the workspace.",
    "OTP login verification fails repeatedly — SMS code arrives 20 minutes late and says expired when entered.",
]


def seed_upgrade_scenarios() -> None:
    db = SessionLocal()
    try:
        # Idempotency check: skip if Scenario A payment incident already exists
        existing_inc = db.query(Incident).filter(Incident.incident_reference == "INC-2026-0001").first()
        if existing_inc:
            print("Upgrade scenarios already seeded (INC-2026-0001 exists); preserving existing records.")
            return

        rng = random.Random(2525)
        now = datetime.now(timezone.utc)
        pw_hash = hash_password(DEMO_PASSWORD)

        manager = db.query(User).filter(User.email == "manager@qryvanta.local").first()
        billing_agent = db.query(Agent).join(User).filter(User.email == "billing.agent@qryvanta.local").first()
        tech_agent = db.query(Agent).join(User).filter(User.email == "tech.agent@qryvanta.local").first()
        account_agent = db.query(Agent).join(User).filter(User.email == "account.agent@qryvanta.local").first()

        billing_dept = db.query(Department).filter(Department.name == "Billing").first()
        account_dept = db.query(Department).filter(Department.name == "Account Services").first()
        cartwave = db.query(Company).filter(Company.name == "CartWave E-Commerce").first()
        payledger = db.query(Company).filter(Company.name == "PayLedger Fintech").first()
        authvault = db.query(Company).filter(Company.name == "AuthVault Identity").first()

        # Create 32 deterministic demo customers (so 50 payment tickets come from 32 unique customers!)
        pool_customers = []
        first_names = [
            "Aisha", "Rohan", "Clara", "Devon", "Meera", "Noah", "Zara", "Ethan",
            "Kavya", "Lucas", "Nikhil", "Hannah", "Omar", "Chloe", "Vikram", "Grace",
            "Arjun", "Mila", "Toby", "Ananya", "Samir", "Freya", "Kiran", "Owen",
            "Diya", "Mateo", "Isha", "Caleb", "Riya", "Leo", "Tara", "Julian",
        ]
        for idx, fname in enumerate(first_names, start=1):
            email = f"demo.cust{idx:02d}@qryvanta.local"
            u = db.query(User).filter(User.email == email).first()
            if not u:
                u = User(name=f"{fname} Patel (Demo)", email=email, password_hash=pw_hash, role="customer", is_active=True)
                db.add(u)
                db.flush()
            c = db.query(Customer).filter(Customer.user_id == u.id).first()
            if not c:
                c = Customer(
                    user_id=u.id,
                    customer_reference=f"CUST-SCN-{idx:03d}",
                    contact_information=f"+1-555-02{idx:02d} | Demo Cohort",
                )
                db.add(c)
                db.flush()
            pool_customers.append(c)
        db.commit()

        # ------------------------------------------------------------------
        # SCENARIO A: Payment Incident (~50 related tickets from 32 unique customers)
        # ------------------------------------------------------------------
        payment_tickets = []
        for i in range(50):
            # First 32 tickets map 1-to-1 across all 32 customers; remaining 18 are repeat complaints
            cust = pool_customers[i] if i < 32 else pool_customers[i % 18]
            minutes_ago = rng.randint(25, 1100)
            created_at = now - timedelta(minutes=minutes_ago)
            txn_ref = f"TXN-PG-{88000 + i}"
            amt = f"${rng.choice([49, 79, 129, 149, 199, 249])}"
            subj = PAYMENT_SUBJECTS[i % len(PAYMENT_SUBJECTS)]
            desc = PAYMENT_DESCRIPTIONS[i % len(PAYMENT_DESCRIPTIONS)].format(amt=amt, txn=txn_ref)

            t = create_ticket_full(
                db=db,
                customer=cust,
                actor=cust.user,
                subject=subj,
                description=desc,
                product_reference="Checkout Gateway v3",
                company_id=cartwave.id if (cartwave and i % 2 == 0) else (payledger.id if payledger else None),
                platform_type="E-Commerce" if i % 2 == 0 else "Fintech / Payments",
                external_reference=txn_ref,
                source="web_portal",
                is_demo_data=True,
                created_at_override=created_at,
            )
            t.priority = "high" if i % 4 != 0 else "critical"
            t.priority_reason = "Rule-based urgency assessment: blocked checkout payment with funds deducted across multiple customers."
            if billing_dept:
                t.department_id = billing_dept.id
            # Leave 8 high-priority tickets unassigned for Scenario D SLA pressure
            if i < 42 and billing_agent:
                t.assigned_agent_id = billing_agent.id if i % 2 == 0 else (tech_agent.id if tech_agent else billing_agent.id)
                t.status = "in_progress" if i % 3 == 0 else "open"
            else:
                t.assigned_agent_id = None
                t.status = "new"
            if t.sla_tracking:
                t.sla_tracking.current_state = compute_sla_state(t.sla_tracking, t.status, now)
            payment_tickets.append(t)

        # Group the 50 payment tickets into a confirmed active incident (INC-2026-0001)
        pay_times = [t.created_at for t in payment_tickets]
        pay_inc = Incident(
            incident_reference="INC-2026-0001",
            title="Payment gateway debit without order confirmation (Checkout v3)",
            description=(
                "Widespread checkout failure affecting 32 unique customers across 50 tickets: "
                "card/UPI payment succeeds at the bank gateway while order confirmation remains pending or missing."
            ),
            severity="critical",
            status="investigating",
            department_id=billing_dept.id if billing_dept else None,
            owner_id=manager.id if manager else None,
            common_symptoms=["payment deducted", "order not confirmed", "payment pending", "transaction successful", "order missing"],
            investigation_notes=(
                "Correlated 50 tickets from 32 unique customers within 18 hours. "
                "Gateway callback webhook timeouts observed on Checkout v3; awaiting PayLedger settlement reconciliation."
            ),
            is_auto_detected=True,
            is_demo_data=True,
            first_reported_at=min(pay_times),
            last_reported_at=max(pay_times),
        )
        db.add(pay_inc)
        db.flush()
        for t in payment_tickets:
            db.add(
                IncidentTicket(
                    incident_id=pay_inc.id,
                    ticket_id=t.id,
                    similarity_score=round(rng.uniform(0.58, 0.89), 4),
                    linked_by=manager.id if manager else None,
                )
            )
        record_incident_event(
            db,
            pay_inc.id,
            "incident_detected",
            "Detected 50 semantically similar payment tickets across 32 unique customers; moved to Investigating by Support Manager.",
            actor_id=manager.id if manager else None,
            new_value="investigating",
        )
        db.commit()

        # ------------------------------------------------------------------
        # SCENARIO B: Refund Delays (open + genuinely resolved reference cases)
        # ------------------------------------------------------------------
        resolved_refund_sources = []
        open_refund_tickets = []
        for idx, (subj, desc_tpl, is_resolved) in enumerate(REFUND_DELAY_TEMPLATES):
            cust = pool_customers[(idx + 5) % len(pool_customers)]
            created_at = now - timedelta(days=rng.randint(2, 10), hours=rng.randint(1, 8))
            ref = f"ORD-RF-{7210 + idx}"
            dt_str = (created_at - timedelta(days=11)).strftime("%b %d")
            amt = f"${rng.choice([89, 135, 210, 299])}"
            t = create_ticket_full(
                db=db,
                customer=cust,
                actor=cust.user,
                subject=subj,
                description=desc_tpl.format(ref=ref, dt=dt_str, amt=amt),
                product_reference="Returns & Refunds",
                company_id=cartwave.id if cartwave else None,
                platform_type="E-Commerce",
                external_reference=ref,
                source="web_portal",
                is_demo_data=True,
                created_at_override=created_at,
            )
            if billing_agent:
                t.assigned_agent_id = billing_agent.id
            if is_resolved:
                res_ts = created_at + timedelta(hours=3, minutes=20)
                t.status = "resolved"
                t.resolved_at = res_ts
                t.satisfaction_rating = 5
                t.satisfaction_comment = "Clear breakdown of the credit memo and fast reimbursement."
                db.add(
                    TicketMessage(
                        ticket_id=t.id,
                        sender_id=billing_agent.user_id if billing_agent else (manager.id if manager else None),
                        message=(
                            f"Verified warehouse return scan and payment settlement batch for {ref}. "
                            f"Triggered manual credit memo refund of {amt} directly to the original payment card "
                            "and attached settlement receipt. Funds post within 2-3 business days."
                        ),
                        visibility="public",
                        created_at=res_ts,
                    )
                )
                if t.sla_tracking:
                    t.sla_tracking.first_responded_at = res_ts
                    t.sla_tracking.resolved_at = res_ts
                    t.sla_tracking.current_state = "completed"
                resolved_refund_sources.append(t)
            else:
                t.status = "open"
                open_refund_tickets.append(t)

        # Record 3 genuine resolution feedback items linking open refund tickets to resolved sources
        if open_refund_tickets and resolved_refund_sources and billing_agent:
            for k in range(min(3, len(open_refund_tickets))):
                db.add(
                    ResolutionFeedback(
                        ticket_id=open_refund_tickets[k].id,
                        source_ticket_id=resolved_refund_sources[k % len(resolved_refund_sources)].id,
                        recommendation_type="similar_ticket",
                        rating="helpful" if k < 2 else "partially_helpful",
                        applied_to_reply=k < 2,
                        submitted_by=billing_agent.user_id,
                    )
                )
        db.commit()

        # ------------------------------------------------------------------
        # SCENARIO C: Emerging Login / OTP Issue Burst (12 open tickets within 12 hours)
        # Left as unlinked initially so `detect_candidate_incidents` auto-detects it cleanly!
        # ------------------------------------------------------------------
        for i in range(12):
            cust = pool_customers[(i + 12) % len(pool_customers)]
            created_at = now - timedelta(minutes=rng.randint(20, 680))
            t = create_ticket_full(
                db=db,
                customer=cust,
                actor=cust.user,
                subject=OTP_SUBJECTS[i % len(OTP_SUBJECTS)],
                description=OTP_DESCRIPTIONS[i % len(OTP_DESCRIPTIONS)],
                product_reference="MFA / SMS OTP",
                company_id=authvault.id if authvault else None,
                platform_type="SaaS / Software",
                external_reference=f"OTP-{4100 + i}",
                source="web_portal",
                is_demo_data=True,
                created_at_override=created_at,
            )
            t.priority = "high"
            if account_dept:
                t.department_id = account_dept.id
            # Leave some unassigned for SLA pressure & workload balancing
            if i < 6 and account_agent:
                t.assigned_agent_id = account_agent.id
                t.status = "open"
            else:
                t.assigned_agent_id = None
                t.status = "new"
            if t.sla_tracking:
                # Place half approaching deadline within 45 minutes for Scenario D SLA Risk
                if i % 2 == 0:
                    t.sla_tracking.resolution_deadline = now + timedelta(minutes=35 + i * 4)
                    t.sla_tracking.first_response_deadline = now + timedelta(minutes=15 + i * 2)
                t.sla_tracking.current_state = compute_sla_state(t.sla_tracking, t.status, now)

        db.commit()

        # Run real TF-IDF incident detection to automatically surface Scenario C (OTP burst) & Scenario B (Refund delays) as `detected` candidate incidents!
        detect_res = detect_candidate_incidents(
            db=db,
            window_days=14,
            similarity_threshold=0.25,
            min_cluster_size=3,
            actor=manager,
        )
        gaps = detect_knowledge_gaps(db)

        print("Successfully seeded additive QRYVANTA upgrade scenarios (existing records preserved):")
        print("  - Scenario A: 50 payment incident tickets across 32 unique customers -> INC-2026-0001 (investigating)")
        print("  - Scenario B: 7 refund delay tickets (4 open + 3 resolved with verified resolutions & feedback)")
        print("  - Scenario C & D: 12 Login/OTP burst tickets with approaching SLA deadlines & unassigned high-priority load")
        print(f"  - Auto-detected candidate incidents: {detect_res['detected_count']} (status='detected' awaiting manager review)")
        print(f"  - Detected knowledge gaps: {len(gaps)}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_upgrade_scenarios()
