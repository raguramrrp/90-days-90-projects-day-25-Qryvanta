"""CLI utility to bulk import tickets from a CSV file into QRYVANTA."""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.init_db import init_db
from app.database.session import SessionLocal
from app.models.user import Customer, User
from app.services.bulk_import_service import execute_csv_import, preview_csv_content


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk import support tickets from CSV into QRYVANTA.")
    parser.add_argument("csv_file", help="Path to CSV file containing subject and description columns.")
    parser.add_argument("--demo", action="store_true", help="Flag imported rows as synthetic demo data.")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}")
        sys.exit(1)

    init_db()
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    preview = preview_csv_content(csv_text)
    print(f"Detected columns: {preview['columns']} ({preview['total_rows']} rows)")

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        cust = db.query(Customer).first()
        if not admin or not cust:
            print("Database must be seeded before importing tickets. Run `python scripts/seed_database.py`.")
            sys.exit(1)
        res = execute_csv_import(
            db=db,
            csv_text=csv_text,
            column_mapping=preview["suggested_mapping"],
            default_customer=cust,
            actor=admin,
            is_demo_data=args.demo,
        )
        print(
            f"Import complete: {res['imported_count']} imported, "
            f"{res['skipped_duplicates']} duplicate(s) skipped, {res['failed_count']} failed."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
