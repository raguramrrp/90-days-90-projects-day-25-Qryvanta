"""
Idempotent Demo Seed Script for QRYVANTA.
Safe to run multiple times without creating duplicate records.
WARNING: Demo passwords are for local development ONLY — change before any production deployment.
All seeded tickets are explicitly marked `is_demo_data=True`.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.init_db import init_db
from app.database.session import SessionLocal
from app.models.intelligence import KnowledgeArticle, TicketFeedback, TicketPrediction
from app.models.operations import AppSetting, Company, Holiday, RoutingRule, SLAPolicy
from app.models.ticket import (
    Category,
    Ticket,
    TicketAssignment,
    TicketMessage,
    TicketRelation,
)
from app.models.user import Agent, AgentDepartment, Customer, Department, User
from app.services.auth_service import hash_password
from app.services.sla_service import compute_sla_state
from app.services.ticket_service import create_ticket_full, record_ticket_event


DEMO_PASSWORD = "DemoUser#2026"

COMPANIES_SEED = [
    ("CartWave E-Commerce", "E-Commerce", "https://cartwave.example.com", "resolutions@cartwave.example.com", "Online retail marketplace covering orders, returns, and buyer refund protection."),
    ("ShopSphere Retail", "E-Commerce", "https://shopsphere.example.com", "support@shopsphere.example.com", "Direct-to-consumer electronics & accessories storefront."),
    ("CloudTrellis SaaS", "SaaS / Software", "https://cloudtrellis.example.com", "enterprise-support@cloudtrellis.example.com", "B2B cloud analytics, reporting APIs, and workspace software."),
    ("AuthVault Identity", "SaaS / Software", "https://authvault.example.com", "trust@authvault.example.com", "Enterprise SSO, MFA, and identity management portal."),
    ("PayLedger Fintech", "Fintech / Payments", "https://payledger.example.com", "disputes@payledger.example.com", "Corporate billing gateway, card settlement, and VAT invoicing."),
    ("SwiftHaul Express", "Logistics / Courier", "https://swifthaul.example.com", "claims@swifthaul.example.com", "Domestic & cross-border parcel delivery and freight tracking."),
    ("CoreDesk Hardware", "Hardware & Devices", "https://coredesk.example.com", "warranty@coredesk.example.com", "Commercial POS terminals, scanners, docks, and display hardware."),
]

DEPARTMENTS_SEED = [
    ("Billing", "Handles invoices, refunds, payment failures, tax adjustments, and subscription billing."),
    ("Technical Support", "Resolves software bugs, API errors, installation blockers, and performance incidents."),
    ("Account Services", "Manages authentication, SSO/SAML, MFA recovery, lockouts, and workspace permissions."),
    ("Logistics", "Oversees carrier shipments, tracking issues, customs holds, and missing packages."),
    ("Returns and Refunds", "Processes RMAs, order cancellations, exchanges, and defective hardware returns."),
    ("General Support", "Addresses product inquiries, compliance documentation, policies, and general triage."),
]

CATEGORIES_SEED = {
    "Billing and Payments": ("Billing", ["Refund Request", "Payment Failure", "Incorrect Charge"]),
    "Technical Support": ("Technical Support", ["Application Error", "Installation Issue", "Performance Issue"]),
    "Account and Login": ("Account Services", ["Password Reset", "Account Lockout", "Verification Issue"]),
    "Delivery and Shipping": ("Logistics", ["Delayed Delivery", "Missing Package", "Tracking Issue"]),
    "Orders and Returns": ("Returns and Refunds", ["Order Cancellation", "Return Request", "Exchange Request"]),
    "Product Issues": ("Returns and Refunds", ["Defective Item", "Missing Parts", "Quality Concern"]),
    "Subscription Management": ("Billing", ["Plan Upgrade or Downgrade", "Subscription Cancellation", "Seat or License Change"]),
    "General Enquiries": ("General Support", ["Product Information", "Policy Question", "Partnership or Feedback"]),
}

KNOWLEDGE_ARTICLES_SEED = [
    (
        "Billing and Payments",
        "Processing Duplicate Charge Refunds and Credit Memos",
        "Verify both transaction IDs in the payment gateway ledger. Confirm settlement status (settled vs pending authorization). For settled duplicates, issue a full refund to the original card and attach the credit memo reference. Refunds appear within 3-5 business days.",
        "refund,duplicate charge,billing,credit memo",
    ),
    (
        "Billing and Payments",
        "Troubleshooting Declined Corporate Cards and Error 402",
        "Error 402 indicates issuer decline, AVS mismatch, or 3D-Secure timeout. Ask the customer to verify billing postal code, confirm international SaaS charges are whitelisted with their corporate bank, or switch to ACH/SEPA direct debit.",
        "payment failure,card declined,402,invoice",
    ),
    (
        "Technical Support",
        "Diagnosing HTTP 500 Errors and Export Timeouts",
        "Collect the correlation request ID, timestamp, browser console logs, and report filter parameters. Check whether the export exceeds 50,000 rows; if so, instruct the user to partition the date window or trigger an asynchronous CSV job.",
        "500 error,export,crash,application error",
    ),
    (
        "Technical Support",
        "Resolving Windows MSI Installer VCRUNTIME140 Dependencies",
        "Install the latest Microsoft Visual C++ Redistributable (x64) package, reboot if pending OS updates exist, and rerun the QRYVANTA desktop MSI installer from an elevated prompt.",
        "install,windows,dll,setup",
    ),
    (
        "Account and Login",
        "MFA / Two-Factor Recovery and Authenticator Sync Checklist",
        "Confirm identity using two out-of-band organization verifiers (admin email confirmation plus last invoice date). Have the user enable automatic network time sync before resetting TOTP enrollment.",
        "2fa,mfa,otp,verification,lockout",
    ),
    (
        "Delivery and Shipping",
        "Investigating Delivered-But-Not-Received Parcels",
        "Retrieve carrier proof-of-delivery photo and GPS drop coordinates. Check mailroom/reception logs within 24 hours. If misdelivered, open a carrier trace claim and prepare an advance replacement shipment.",
        "missing package,delivery,tracking,courier",
    ),
    (
        "Orders and Returns",
        "Standard 30-Day RMA Return Label & Exchange Procedure",
        "Validate order number and delivery date within 30 calendar days. Generate a prepaid RMA barcode label, note condition requirements for exchanges, and notify warehouse intake for automated inspection upon arrival.",
        "return,rma,exchange,cancellation",
    ),
    (
        "Subscription Management",
        "Seat Proration and Annual Plan Upgrade Guide",
        "Mid-cycle upgrades are prorated to the exact remaining days of the active billing period. Additional agent seats take effect immediately upon confirmation and sync with SSO provisioning within 5 minutes.",
        "subscription,upgrade,seats,license",
    ),
]

DEMO_TICKET_SCENARIOS = [
    # Billing & Payments
    ("Double charged on October invoice INV-4410", "Our finance team noticed two identical charges of 299 dollars on our corporate Visa for October billing. Please refund the duplicate charge urgently.", "Billing Plan Pro", "resolved", 5, False),
    ("Duplicate charge appeared on Visa statement for October", "We were double charged 299 dollars on our Visa statement this morning for our workspace subscription. Need assistance reversing the second charge.", "Billing Plan Pro", "open", None, False),
    ("Corporate Mastercard declined with error 402", "Attempting to pay our quarterly invoice fails with gateway error 402 even though the card is active and has plenty of limit.", "Enterprise Billing", "in_progress", None, False),
    ("Requesting refund for cancelled workshop registration", "I cancelled our onboarding workshop seven days ahead of schedule and need a refund back to our original payment card.", "Training", "resolved", 4, False),
    ("Wrong VAT tax rate applied to Berlin office invoice", "We entered our German VAT number in billing settings yet the invoice still applied 19 percent VAT.", "EU Billing", "awaiting_customer", None, False),
    ("Credit memo refund still pending after 12 days", "Support approved our refund two weeks ago but the reimbursement has not posted to our bank account.", "Billing Plan Pro", "reopened", 2, True),
    # Technical Support
    ("Production down: HTTP 500 error across reporting API", "All users affected in our analytics department — every PDF export and reporting API request returns HTTP 500 internal server error since 09:15 UTC.", "Reporting API v2", "in_progress", None, False),
    ("HTTP 500 internal server error when exporting PDF reports", "Clicking export to PDF on the weekly operations dashboard consistently fails with a 500 server error across Chrome and Edge.", "Reporting API v2", "open", None, False),
    ("Windows desktop client crashes immediately on launch", "After upgrading to release 4.2 on Windows 11 the desktop application crashes with a null reference exception before login loads.", "Desktop Client 4.2", "open", None, False),
    ("MSI installer stops with missing VCRUNTIME140 DLL", "Rolling out the Windows installer to new support hires fails at 60 percent due to missing VCRUNTIME140 runtime library.", "Desktop Client 4.2", "resolved", 5, False),
    ("Severe query latency on main ticket search bar", "Searching customer tickets now takes 16 seconds compared to sub-second response earlier this week.", "Search Engine", "in_progress", None, False),
    ("CSV export downloads empty zero-byte file", "Every time I export filtered tickets from the queue screen the browser downloads a 0 KB empty CSV.", "Web Portal", "reopened", 3, True),
    ("API webhook payloads arriving with truncated JSON", "Our downstream integration started rejecting webhook events due to malformed truncated JSON since last night's deploy.", "Webhooks", "open", None, False),
    # Account and Login
    ("Urgent: five agents locked out after SSO rotation", "Multiple team members in our Austin office are locked out after our Okta certificate rotation and cannot sign in to answer customers.", "SSO / SAML", "in_progress", None, False),
    ("Security alert: potential unauthorized access attempt", "Our audit trail shows suspicious login attempts from an unrecognized IP range. Please lock legacy API tokens immediately.", "Workspace Security", "open", None, False),
    ("Password reset email never arrives in Outlook inbox", "I requested a password reset link three times and verified junk mail filters, yet no recovery email arrived.", "Identity Portal", "resolved", 5, False),
    ("Google Authenticator TOTP codes rejected as invalid", "Even after syncing my phone clock, six-digit two-factor verification codes are rejected during login.", "MFA", "awaiting_customer", None, False),
    ("Lost mobile device and need MFA recovery reset", "My work phone was replaced yesterday and I cannot locate backup recovery codes to sign into my account.", "MFA", "resolved", 4, False),
    ("Email verification link returns 404 not found", "New contractor clicked their invitation verification link and received a 404 broken page error.", "Identity Portal", "closed", 5, False),
    # Delivery and Shipping
    ("Express hardware shipment three days overdue", "We paid for next-day courier delivery for branch scanner terminals and the parcel is now three business days late.", "Hardware Kit H2", "in_progress", None, False),
    ("Package marked delivered but missing from reception", "Carrier tracking says left at front desk at 14:20 but our building security desk has no record of any delivery.", "Hardware Kit H2", "open", None, False),
    ("Tracking number shows not found on courier site", "We received a dispatch notice 48 hours ago yet the tracking ID returns invalid on UPS tracking.", "Logistics", "resolved", 4, False),
    ("Shipment held at customs clearance in Toronto", "International parcel has been stuck awaiting commercial invoice documentation at customs for five days.", "Hardware Kit H2", "awaiting_customer", None, False),
    ("Delivered to wrong porch in carrier photo", "The proof-of-delivery photo shows a residential porch that does not match our commercial office building.", "Hardware Kit H2", "reopened", 2, True),
    ("Tracking status stuck on label created for four days", "Shipping label was created Monday morning with no pickup scan from the courier since.", "Logistics", "open", None, False),
    # Orders and Returns
    ("Cancel unshipped order before warehouse pickup", "I accidentally selected the wrong docking kit configuration an hour ago and need the order cancelled before dispatch.", "Dock Pro", "resolved", 5, False),
    ("Need prepaid RMA return shipping label for scanner", "The scanner kit is incompatible with our POS terminals and we want to initiate a 30-day return.", "Scanner S1", "open", None, False),
    ("Exchange EU power adapters for US plug version", "Our office shipment included European plugs instead of North American adapters; please arrange a direct exchange.", "Power Kit", "in_progress", None, False),
    ("Cancel duplicate purchase order submitted by clerk", "Two identical purchase orders were submitted within five minutes; please void the duplicate order.", "Bulk Order", "closed", 5, False),
    ("Return authorization QR code expired before drop-off", "My return barcode expired yesterday before I could visit the drop-off point; please reissue a fresh RMA.", "Scanner S1", "resolved", 4, False),
    # Product Issues
    ("Battery swelling noticed on handheld tablet", "One of our warehouse tablets shows slight casing separation near the battery compartment and runs unusually hot.", "Tablet T4", "open", None, False),
    ("Cracked LCD display straight out of sealed box", "We unboxed the new kiosk monitor today and discovered a diagonal hairline crack and dead vertical lines.", "Monitor M24", "in_progress", None, False),
    ("Power adapter cable missing from sealed retail box", "The main terminal and manual arrived intact, but the AC power brick and USB-C cord were missing.", "Dock Pro", "resolved", 4, False),
    ("Thermal printer outputs faint unreadable receipts", "Brand new thermal printer feeds rolls normally yet prints barely visible striped receipts.", "Printer P8", "reopened", 3, True),
    ("Scratched aluminum enclosure on new docking unit", "Chassis arrived with deep cosmetic scratches that look like a refurbished unit rather than brand new.", "Dock Pro", "closed", 4, False),
    # Subscription Management
    ("Upgrade team workspace from Growth to Enterprise", "We need SAML SSO, custom SLA policies, and audit retention starting next month. Please send upgrade steps.", "Enterprise Tier", "open", None, False),
    ("Add eight new agent seats for regional rollout", "Eight new support specialists join on Monday and require licensed agent seats added to our subscription.", "Agent Licenses", "resolved", 5, False),
    ("Cancel auto-renewal before upcoming annual billing", "Please disable automatic renewal on our subsidiary workspace and confirm termination in writing.", "Growth Tier", "in_progress", None, False),
    ("Seat limit error when inviting new team manager", "We deactivated two departed users yesterday yet inviting one new manager still triggers seat quota exceeded.", "Agent Licenses", "open", None, False),
    ("Switch monthly billing cadence to annual invoice", "Finance approved converting our monthly workspace subscription to annual invoicing for the yearly discount.", "Business Tier", "closed", 5, False),
    # General Enquiries & Ambiguous / Low-confidence Triage Examples
    ("Question about SOC 2 Type II report and EU residency", "Could you share your latest SOC 2 Type II compliance report and confirm EU data residency options?", "Compliance", "resolved", 5, False),
    ("Feature suggestion: keyboard shortcuts for ticket queue", "Our power agents would really appreciate customizable keyboard shortcuts for assigning and resolving tickets.", "Web Portal", "closed", 5, False),
    ("Interested in regional reseller partnership in APAC", "Our consulting practice implements customer operations platforms across Singapore and Australia.", "Partnerships", "open", None, False),
    ("Follow up regarding our recent conversation", "Hi team, just checking in on what we discussed earlier this week about our workspace setup and next steps.", None, "new", None, False),
    ("Need help sorting out account and invoice items", "Hello, we have a couple of mixed items spanning user access, hardware shipment timing, and invoice formatting.", None, "new", None, False),
    ("Quick check on onboarding timeline", "Can someone advise when our team onboarding sessions can begin next week?", None, "new", None, False),
]


def seed_all() -> None:
    init_db()
    db = SessionLocal()
    try:
        # 1. Default App Settings
        default_settings = [
            ("confidence_thresholds", {"high": 0.80, "medium": 0.55}, "Confidence bands for automatic department routing"),
            ("similarity_threshold", {"threshold": 0.25}, "Minimum TF-IDF cosine similarity for related ticket suggestions"),
            ("business_hours", {"start_hour": 9, "start_minute": 0, "end_hour": 17, "end_minute": 0, "workdays": [0, 1, 2, 3, 4]}, "Configured SLA business hours (UTC)"),
            ("notifications", {"sla_warning_enabled": True, "reopen_alert_enabled": True}, "Operational notification settings"),
        ]
        for key, val, desc in default_settings:
            if not db.query(AppSetting).filter(AppSetting.key == key).first():
                db.add(AppSetting(key=key, value=val, description=desc))

        # 2. Holidays
        year = datetime.now(timezone.utc).year
        for h_date, h_name in [
            (date(year, 1, 1), "New Year's Day"),
            (date(year, 12, 25), "Christmas Day"),
            (date(year, 7, 4), "Independence Day"),
        ]:
            if not db.query(Holiday).filter(Holiday.holiday_date == h_date).first():
                db.add(Holiday(holiday_date=h_date, name=h_name))

        # 3. Departments
        dept_map = {}
        for d_name, d_desc in DEPARTMENTS_SEED:
            dept = db.query(Department).filter(Department.name == d_name).first()
            if not dept:
                dept = Department(name=d_name, description=d_desc, is_active=True)
                db.add(dept)
                db.flush()
            dept_map[d_name] = dept

        # 3b. Target Companies & Portals
        company_map = {}
        for c_name, p_type, p_url, s_email, c_desc in COMPANIES_SEED:
            comp = db.query(Company).filter(Company.name == c_name).first()
            if not comp:
                comp = Company(
                    name=c_name,
                    platform_type=p_type,
                    portal_url=p_url,
                    support_email=s_email,
                    description=c_desc,
                    is_active=True,
                )
                db.add(comp)
                db.flush()
            company_map[c_name] = comp

        # 4. Categories & Subcategories + Routing Rules
        cat_map = {}
        subcat_map = {}
        for cat_name, (dept_name, subs) in CATEGORIES_SEED.items():
            parent = (
                db.query(Category)
                .filter(Category.name == cat_name, Category.parent_category_id.is_(None))
                .first()
            )
            if not parent:
                parent = Category(name=cat_name, description=f"Support requests related to {cat_name.lower()}.", is_active=True)
                db.add(parent)
                db.flush()
            cat_map[cat_name] = parent

            for sub_name in subs:
                sub = (
                    db.query(Category)
                    .filter(Category.name == sub_name, Category.parent_category_id == parent.id)
                    .first()
                )
                if not sub:
                    sub = Category(name=sub_name, parent_category_id=parent.id, is_active=True)
                    db.add(sub)
                    db.flush()
                subcat_map[(cat_name, sub_name)] = sub

            rule_name = f"Route {cat_name} -> {dept_name}"
            if not db.query(RoutingRule).filter(RoutingRule.name == rule_name).first():
                db.add(
                    RoutingRule(
                        name=rule_name,
                        category_id=parent.id,
                        department_id=dept_map[dept_name].id,
                        min_confidence=0.55,
                        auto_assign_agent=False,
                        is_active=True,
                    )
                )

        # 5. SLA Policies
        sla_defs = [
            ("Critical Priority SLA", "critical", None, 30, 240, False),
            ("High Priority SLA", "high", None, 60, 480, True),
            ("Medium Priority SLA", "medium", None, 240, 1440, True),
            ("Low Priority SLA", "low", None, 480, 2880, True),
            ("Technical Critical 24x7 SLA", "critical", dept_map["Technical Support"].id, 15, 180, False),
        ]
        for s_name, prio, dept_id, fr_min, res_min, bh_only in sla_defs:
            if not db.query(SLAPolicy).filter(SLAPolicy.name == s_name).first():
                db.add(
                    SLAPolicy(
                        name=s_name,
                        priority=prio,
                        department_id=dept_id,
                        first_response_minutes=fr_min,
                        resolution_minutes=res_min,
                        business_hours_only=bh_only,
                        is_active=True,
                    )
                )

        # 6. Knowledge Articles
        for cat_name, title, content, tags in KNOWLEDGE_ARTICLES_SEED:
            if not db.query(KnowledgeArticle).filter(KnowledgeArticle.title == title).first():
                db.add(
                    KnowledgeArticle(
                        title=title,
                        content=content,
                        category_id=cat_map[cat_name].id,
                        tags=tags,
                        is_published=True,
                    )
                )

        # 7. Demo Users (Admin, Manager, Agents across departments, Customers)
        pw_hash = hash_password(DEMO_PASSWORD)

        def _ensure_user(name: str, email: str, role: str) -> User:
            u = db.query(User).filter(User.email == email).first()
            if not u:
                u = User(name=name, email=email, password_hash=pw_hash, role=role, is_active=True)
                db.add(u)
                db.flush()
            else:
                # Ensure local demo seed accounts retain expected demo role, active status, and dev password
                u.role = role
                u.is_active = True
                u.password_hash = pw_hash
            return u

        admin_user = _ensure_user("Aarav Mehta (Admin)", "admin@qryvanta.local", "admin")
        manager_user = _ensure_user("Nadia Lin (Support Manager)", "manager@qryvanta.local", "manager")

        agent_specs = [
            ("Priya Nair", "billing.agent@qryvanta.local", "Billing", ["Billing", "Returns and Refunds"], "Billing, Refunds, Invoices, Subscription Management", 14, "available"),
            ("Daniel Brooks", "tech.agent@qryvanta.local", "Technical Support", ["Technical Support", "Account Services"], "Technical Support, API Errors, Performance, Installation", 12, "available"),
            ("Elena Gomez", "logistics.agent@qryvanta.local", "Logistics", ["Logistics", "Returns and Refunds"], "Delivery, Shipping, Missing Packages, Returns, Exchanges", 15, "available"),
            ("Marcus Reed", "account.agent@qryvanta.local", "Account Services", ["Account Services", "General Support"], "Account Lockout, SSO, SAML, MFA Verification, General Enquiries", 14, "busy"),
        ]
        agents_by_dept = {}
        all_agents = []
        for a_name, a_email, primary_d, all_ds, exp, max_t, avail in agent_specs:
            u = _ensure_user(a_name, a_email, "agent")
            ag = db.query(Agent).filter(Agent.user_id == u.id).first()
            if not ag:
                ag = Agent(
                    user_id=u.id,
                    department_id=dept_map[primary_d].id,
                    expertise=exp,
                    max_open_tickets=max_t,
                    availability_status=avail,
                )
                db.add(ag)
                db.flush()
            for d_name in all_ds:
                did = dept_map[d_name].id
                if not db.query(AgentDepartment).filter(AgentDepartment.agent_id == ag.id, AgentDepartment.department_id == did).first():
                    db.add(AgentDepartment(agent_id=ag.id, department_id=did))
            agents_by_dept[primary_d] = ag
            all_agents.append(ag)

        customer_specs = [
            ("Maya Kapoor", "customer@qryvanta.local", "CUST-DEMO-1001", "+1-555-0142 | Acme Retail Ops"),
            ("Liam O'Connor", "liam.customer@qryvanta.local", "CUST-DEMO-1002", "+1-555-0198 | Northstar Logistics"),
            ("Sofia Alvarez", "sofia.customer@qryvanta.local", "CUST-DEMO-1003", "+44-20-7946-0112 | FinEdge Europe"),
        ]
        customers = []
        for c_name, c_email, c_ref, c_info in customer_specs:
            u = _ensure_user(c_name, c_email, "customer")
            c = db.query(Customer).filter(Customer.user_id == u.id).first()
            if not c:
                c = Customer(user_id=u.id, customer_reference=c_ref, contact_information=c_info)
                db.add(c)
                db.flush()
            customers.append(c)

        db.commit()

        # 8. Seed Demo Tickets (idempotent check: skip if demo tickets already exist)
        existing_demo_count = db.query(Ticket).filter(Ticket.is_demo_data.is_(True)).count()
        if existing_demo_count > 0:
            print(f"Seed check: {existing_demo_count} demo tickets already present; skipping duplicate ticket generation.")
            return

        rng = random.Random(2026)
        now = datetime.now(timezone.utc)
        created_tickets = []

        for idx, (subj, desc, prod_ref, target_status, rating, is_reopened) in enumerate(DEMO_TICKET_SCENARIOS):
            cust = customers[idx % len(customers)]
            days_back = rng.randint(0, 20)
            hours_back = rng.randint(1, 20)
            created_at = now - timedelta(days=days_back, hours=hours_back)

            # Map each demo scenario to a fitting real-world platform & company
            if idx < 6:
                comp = company_map["PayLedger Fintech"] if idx % 2 == 0 else company_map["CartWave E-Commerce"]
                ext_ref = f"INV-{4400 + idx}"
            elif idx < 13:
                comp = company_map["CloudTrellis SaaS"]
                ext_ref = f"APP-{8100 + idx}"
            elif idx < 19:
                comp = company_map["AuthVault Identity"]
                ext_ref = f"SSO-{3200 + idx}"
            elif idx < 25:
                comp = company_map["SwiftHaul Express"]
                ext_ref = f"TRK-SH-{9010 + idx}"
            elif idx < 30:
                comp = company_map["CartWave E-Commerce"] if idx % 2 == 0 else company_map["ShopSphere Retail"]
                ext_ref = f"ORD-EC-{6610 + idx}"
            elif idx < 35:
                comp = company_map["CoreDesk Hardware"] if idx % 2 == 0 else company_map["ShopSphere Retail"]
                ext_ref = f"RMA-HW-{5120 + idx}"
            elif idx < 40:
                comp = company_map["CloudTrellis SaaS"]
                ext_ref = f"SUB-{7710 + idx}"
            else:
                comp = company_map["CartWave E-Commerce"] if idx % 2 == 0 else company_map["CloudTrellis SaaS"]
                ext_ref = f"REF-{1200 + idx}"

            ticket = create_ticket_full(
                db=db,
                customer=cust,
                actor=cust.user,
                subject=subj,
                description=desc,
                product_reference=prod_ref,
                company_id=comp.id,
                platform_type=comp.platform_type,
                external_reference=ext_ref,
                source="web_portal" if idx % 5 != 0 else "email_intake",
                is_demo_data=True,
                created_at_override=created_at,
            )

            # Populate realistic QRYVANTA verification & company handoff stages
            if target_status in ("resolved", "closed"):
                ticket.verification_status = "company_resolved"
                ticket.verified_by = manager_user.id
                ticket.verified_at = created_at + timedelta(minutes=45)
                ticket.reported_to_company_at = created_at + timedelta(minutes=60)
                ticket.company_case_reference = f"{comp.name[:3].upper()}-CASE-{2000 + idx}"
                ticket.verification_notes = (
                    f"Verified customer order/reference {ext_ref} and supporting claim details against {comp.name} policy."
                )
                ticket.recommended_company_action = (
                    f"Direct execution approved for {comp.name}: process resolution immediately for {ext_ref} without repeat customer investigation."
                )
            elif target_status == "in_progress":
                ticket.verification_status = "reported_to_company" if idx % 2 == 0 else "company_acknowledged"
                ticket.verified_by = manager_user.id
                ticket.verified_at = created_at + timedelta(minutes=35)
                ticket.reported_to_company_at = created_at + timedelta(minutes=50)
                ticket.company_case_reference = f"{comp.name[:3].upper()}-ESC-{3100 + idx}"
                ticket.verification_notes = (
                    f"Pre-verified evidence for {ext_ref} on {comp.platform_type} portal ({comp.name}); no duplicate open claims found."
                )
                ticket.recommended_company_action = (
                    f"{comp.name} operations team can directly execute remediation on {ext_ref} using the attached verified dossier."
                )
            elif target_status == "open":
                ticket.verification_status = "verified_ready" if idx % 2 == 0 else "under_verification"
                if ticket.verification_status == "verified_ready":
                    ticket.verified_by = manager_user.id
                    ticket.verified_at = created_at + timedelta(minutes=40)
                    ticket.verification_notes = f"Evidence and reference {ext_ref} verified by QRYVANTA; ready for company handoff."
                    ticket.recommended_company_action = f"Approve direct refund/replacement or technical fix for {ext_ref} upon handoff."
            elif target_status == "awaiting_customer":
                ticket.verification_status = "insufficient_proof"
                ticket.verification_notes = f"Requested invoice/return tracking proof for {ext_ref} before reporting to {comp.name}."
            else:
                ticket.verification_status = "unverified"

            # Assign an eligible agent for non-new tickets
            dept_name = ticket.department.name if ticket.department else None
            chosen_agent = agents_by_dept.get(dept_name) if dept_name else None
            if not chosen_agent and target_status != "new":
                chosen_agent = all_agents[idx % len(all_agents)]

            if target_status != "new" and chosen_agent:
                ticket.assigned_agent_id = chosen_agent.id
                db.add(
                    TicketAssignment(
                        ticket_id=ticket.id,
                        agent_id=chosen_agent.id,
                        department_id=ticket.department_id or chosen_agent.department_id,
                        assigned_by=manager_user.id,
                        assignment_reason="Demo seed assignment based on department coverage.",
                        assigned_at=created_at + timedelta(minutes=15),
                    )
                )

                # Add realistic conversation + private internal note
                first_resp_time = created_at + timedelta(minutes=rng.randint(20, 180))
                if idx % 9 == 0:
                    # Simulate a few genuine SLA breaches for realistic analytics
                    first_resp_time = created_at + timedelta(hours=18)

                db.add(
                    TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=chosen_agent.user_id,
                        message="Thank you for contacting QRYVANTA Support. I have reviewed your request and started investigating the details on your account.",
                        visibility="public",
                        created_at=first_resp_time,
                    )
                )
                db.add(
                    TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=chosen_agent.user_id,
                        message="[Internal note] Checked account logs and verified routing classification. Escalate to Tier 2 if issue persists after patch.",
                        visibility="internal",
                        created_at=first_resp_time + timedelta(minutes=10),
                    )
                )

                if ticket.sla_tracking:
                    ticket.sla_tracking.first_responded_at = first_resp_time

                if target_status in ("resolved", "closed"):
                    res_time = first_resp_time + timedelta(minutes=rng.randint(45, 360))
                    if res_time > now:
                        res_time = now - timedelta(minutes=15)
                    ticket.status = target_status
                    ticket.resolved_at = res_time
                    db.add(
                        TicketMessage(
                            ticket_id=ticket.id,
                            sender_id=chosen_agent.user_id,
                            message="This issue has been resolved and verified. Please let us know if you need any further assistance.",
                            visibility="public",
                            created_at=res_time,
                        )
                    )
                    if ticket.sla_tracking:
                        ticket.sla_tracking.resolved_at = res_time
                        ticket.sla_tracking.current_state = "completed"
                elif target_status == "reopened" or is_reopened:
                    res_time = first_resp_time + timedelta(hours=3)
                    reopen_time = min(res_time + timedelta(hours=5), now - timedelta(hours=1))
                    ticket.status = "reopened"
                    ticket.reopen_count = 1
                    ticket.reopened_at = reopen_time
                    ticket.reopen_reason = "Issue recurred after initial fix; customer requested further review."
                    db.add(
                        TicketMessage(
                            ticket_id=ticket.id,
                            sender_id=cust.user_id,
                            message="Reopening ticket: the original issue happened again this morning.",
                            visibility="public",
                            created_at=reopen_time,
                        )
                    )
                    if ticket.sla_tracking:
                        ticket.sla_tracking.current_state = compute_sla_state(ticket.sla_tracking, "reopened", now)
                else:
                    ticket.status = target_status
                    if ticket.sla_tracking:
                        if target_status == "awaiting_customer":
                            ticket.sla_tracking.paused_at = now - timedelta(hours=2)
                            ticket.sla_tracking.current_state = "paused"
                        else:
                            ticket.sla_tracking.current_state = compute_sla_state(ticket.sla_tracking, target_status, now)
                        if idx % 11 == 0:
                            ticket.sla_tracking.escalated = True
                            ticket.sla_tracking.escalated_at = now - timedelta(hours=1)
                            ticket.sla_tracking.escalation_notes = "Escalated due to approaching SLA breach on high-impact request."

                if rating is not None:
                    ticket.satisfaction_rating = rating
                    ticket.satisfaction_comment = (
                        "Prompt and clear resolution from the support specialist."
                        if rating >= 4
                        else "Took longer than expected and required a follow-up."
                    )

            created_tickets.append(ticket)

        # Link two genuine duplicate pairs for demonstration
        if len(created_tickets) >= 8:
            db.add(
                TicketRelation(
                    source_ticket_id=created_tickets[0].id,
                    related_ticket_id=created_tickets[1].id,
                    relation_type="duplicate",
                    similarity_score=0.68,
                    confirmed_by=manager_user.id,
                )
            )
            db.add(
                TicketRelation(
                    source_ticket_id=created_tickets[6].id,
                    related_ticket_id=created_tickets[7].id,
                    relation_type="related",
                    similarity_score=0.59,
                    confirmed_by=manager_user.id,
                )
            )

        # Record 4 realistic Human-in-the-Loop prediction corrections so Feedback Analytics is populated
        correction_targets = [
            (created_tickets[-1], "General Enquiries", "General Support", "Ambiguous onboarding inquiry manually triaged to General Support."),
            (created_tickets[-2], "Billing and Payments", "Billing", "Mixed request primarily concerned invoice formatting; routed to Billing."),
            (created_tickets[-3], "Account and Login", "Account Services", "Follow-up referred to workspace SSO setup; reassigned to Account Services."),
            (created_tickets[15], "Account and Login", "Account Services", "Confirmed security-related access check belongs to Account Services."),
        ]
        for tkt, corr_cat_name, corr_dept_name, reason in correction_targets:
            pred = db.query(TicketPrediction).filter(TicketPrediction.ticket_id == tkt.id).first()
            corr_cat = cat_map[corr_cat_name]
            corr_dept = dept_map[corr_dept_name]
            tkt.category_id = corr_cat.id
            tkt.department_id = corr_dept.id
            db.add(
                TicketFeedback(
                    ticket_id=tkt.id,
                    prediction_id=pred.id if pred else None,
                    corrected_category_id=corr_cat.id,
                    corrected_department_id=corr_dept.id,
                    correction_reason=reason,
                    corrected_by=manager_user.id,
                    model_version_id=pred.model_version_id if pred else None,
                )
            )
            record_ticket_event(
                db,
                tkt.id,
                "prediction_corrected",
                f"Manager verified classification -> {corr_cat_name}. Reason: {reason}",
                manager_user.id,
            )

        db.commit()
        print(f"Successfully seeded QRYVANTA demo workspace with {len(created_tickets)} clearly marked demo tickets.")
        print("Local Demo Accounts (Password for all: DemoUser#2026 — CHANGE BEFORE PRODUCTION):")
        print("  Admin            : admin@qryvanta.local")
        print("  Support Manager  : manager@qryvanta.local")
        print("  Billing Agent    : billing.agent@qryvanta.local")
        print("  Technical Agent  : tech.agent@qryvanta.local")
        print("  Logistics Agent  : logistics.agent@qryvanta.local")
        print("  Account Agent    : account.agent@qryvanta.local")
        print("  Customer         : customer@qryvanta.local")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
