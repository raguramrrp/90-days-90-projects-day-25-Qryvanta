"""CSV Bulk Ticket Import with preview, column mapping, validation, duplicate detection, and classification."""

import csv
import io
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.ticket import Category, Ticket
from app.models.user import Customer, User
from app.services.ticket_service import create_ticket_full


def preview_csv_content(csv_text: str, max_rows: int = 10) -> Dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = reader.fieldnames or []
    rows = []
    total_rows = 0
    for row in reader:
        total_rows += 1
        if len(rows) < max_rows:
            rows.append(dict(row))

    suggested_mapping = {}
    lower_cols = {c.lower().strip(): c for c in columns}
    for field, aliases in {
        "subject": ["subject", "title", "summary", "ticket_subject"],
        "description": ["description", "body", "message", "details", "ticket_description"],
        "category": ["category", "type", "topic"],
        "product_reference": ["product_reference", "product", "order_id", "service"],
    }.items():
        for alias in aliases:
            if alias in lower_cols:
                suggested_mapping[field] = lower_cols[alias]
                break

    return {
        "columns": columns,
        "total_rows": total_rows,
        "preview_rows": rows,
        "suggested_mapping": suggested_mapping,
    }


def execute_csv_import(
    db: Session,
    csv_text: str,
    column_mapping: Dict[str, str],
    default_customer: Customer,
    actor: User,
    is_demo_data: bool = False,
) -> Dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_text))
    subj_col = column_mapping.get("subject", "subject")
    desc_col = column_mapping.get("description", "description")
    cat_col = column_mapping.get("category")
    prod_col = column_mapping.get("product_reference")

    existing_signatures = {
        f"{t.subject.strip().lower()}||{t.description.strip().lower()}"
        for t in db.query(Ticket.subject, Ticket.description).all()
    }
    cat_by_name = {
        c.name.lower(): c.id
        for c in db.query(Category).filter(Category.parent_category_id.is_(None)).all()
    }

    imported: List[Dict[str, Any]] = []
    skipped_duplicates = 0
    failed: List[Dict[str, Any]] = []

    for row_num, row in enumerate(reader, start=2):
        subject = (row.get(subj_col) or "").strip()
        description = (row.get(desc_col) or "").strip()

        if len(subject) < 4 or len(description) < 8:
            failed.append(
                {
                    "row": row_num,
                    "reason": "Missing or too-short subject (min 4 chars) or description (min 8 chars).",
                }
            )
            continue

        sig = f"{subject.lower()}||{description.lower()}"
        if sig in existing_signatures:
            skipped_duplicates += 1
            continue
        existing_signatures.add(sig)

        cat_id = None
        if cat_col and row.get(cat_col):
            cat_id = cat_by_name.get(row.get(cat_col, "").strip().lower())

        product_ref = (row.get(prod_col) or "").strip() if prod_col else None

        try:
            ticket = create_ticket_full(
                db=db,
                customer=default_customer,
                actor=actor,
                subject=subject,
                description=description,
                category_id=cat_id,
                product_reference=product_ref or None,
                source="csv_bulk_import",
                is_demo_data=is_demo_data,
            )
            imported.append(
                {
                    "id": ticket.id,
                    "ticket_reference": ticket.ticket_reference,
                    "subject": ticket.subject,
                    "category": ticket.category.name if ticket.category else None,
                    "priority": ticket.priority,
                }
            )
        except Exception as exc:
            failed.append({"row": row_num, "reason": str(exc)})

    return {
        "imported_count": len(imported),
        "skipped_duplicates": skipped_duplicates,
        "failed_count": len(failed),
        "imported_tickets": imported[:50],
        "failures": failed[:50],
    }
