"""
Transparent rule-based Priority & Urgency Detection service.
Designed explicitly separate from ticket category and customer sentiment:
- Negative sentiment / anger alone NEVER upgrades a ticket to Critical.
- Priority is determined by operational impact, outage, security risk, or explicit business impact.
"""

from typing import Dict, List, Optional, Tuple


CRITICAL_SIGNALS: List[Tuple[str, str]] = [
    ("security breach", "potential security incident"),
    ("unauthorized access", "potential unauthorized account access"),
    ("data breach", "potential data security breach"),
    ("compromised", "potential account or system compromise"),
    ("production down", "production outage reported"),
    ("complete outage", "service interruption reported"),
    ("system down", "service interruption reported"),
    ("service unavailable", "service unavailability reported"),
    ("all users affected", "organization-wide business impact"),
    ("battery swelling", "hardware safety hazard reported"),
    ("data loss", "potential customer data loss"),
    ("500 internal server error", "server-side application failure"),
]

HIGH_SIGNALS: List[Tuple[str, str]] = [
    ("urgent", "explicit urgency indicator"),
    ("asap", "explicit urgency indicator"),
    ("immediately", "explicit time-sensitive operational need"),
    ("locked out", "blocked user access"),
    ("cannot login", "blocked user access"),
    ("cannot sign in", "blocked user access"),
    ("double charged", "duplicate financial charge"),
    ("overcharged", "financial billing discrepancy"),
    ("card declined", "blocked payment processing"),
    ("payment failed", "blocked payment processing"),
    ("crashes", "application stability failure"),
    ("missing package", "missing delivered shipment"),
    ("lost in transit", "lost customer shipment"),
    ("multiple team members", "multi-user operational impact"),
    ("enterprise", "enterprise operational context"),
    ("deadline", "time-bound business deadline"),
]

LOW_SIGNALS: List[Tuple[str, str]] = [
    ("feature suggestion", "non-urgent enhancement request"),
    ("suggestion", "general feedback or suggestion"),
    ("positive feedback", "customer feedback note"),
    ("general question", "informational inquiry"),
    ("pricing inquiry", "pre-sales informational inquiry"),
    ("partnership", "business inquiry"),
    ("affiliate", "business inquiry"),
    ("how does", "general product question"),
    ("documentation", "documentation inquiry"),
]


def assess_priority(
    subject: str,
    description: str,
    custom_rules: Optional[Dict[str, List[str]]] = None,
) -> Tuple[str, str]:
    """
    Evaluate ticket urgency independently from category and sentiment.
    Returns (priority_level, transparent_reason).
    """
    combined = f"{subject or ''} {description or ''}".lower()

    # Check administrator-configured custom overrides first if provided
    if custom_rules:
        for level in ("critical", "high", "low"):
            for kw in custom_rules.get(level, []):
                if kw and kw.lower() in combined:
                    return (
                        level,
                        f"Rule-based urgency assessment ({level.title()}): matched configured policy indicator '{kw}'.",
                    )

    matched_critical = [reason for kw, reason in CRITICAL_SIGNALS if kw in combined]
    if matched_critical:
        reasons = ", ".join(dict.fromkeys(matched_critical))
        return (
            "critical",
            f"Rule-based urgency assessment (Critical): detected {reasons}. "
            "Assessed independently from category and sentiment; staff may override with reason.",
        )

    matched_high = [reason for kw, reason in HIGH_SIGNALS if kw in combined]
    if matched_high:
        reasons = ", ".join(dict.fromkeys(matched_high[:3]))
        return (
            "high",
            f"Rule-based urgency assessment (High): detected {reasons}. "
            "Assessed independently from category and sentiment; staff may override with reason.",
        )

    matched_low = [reason for kw, reason in LOW_SIGNALS if kw in combined]
    if matched_low:
        reasons = ", ".join(dict.fromkeys(matched_low[:2]))
        return (
            "low",
            f"Rule-based urgency assessment (Low): detected {reasons}. "
            "Standard informational priority applied.",
        )

    return (
        "medium",
        "Rule-based urgency assessment (Medium): standard operational support request with no outage, "
        "security, or severe blocking impact indicators.",
    )
