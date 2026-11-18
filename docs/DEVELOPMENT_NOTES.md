# QRYVANTA — Development Notes

## Key Architectural Decisions & Trade-Offs

1. **PostgreSQL Primary + SQLite Local Fallback**
   - `backend/app/database/session.py` accepts any SQLAlchemy `DATABASE_URL` (`postgresql+psycopg://...` or `sqlite:///./qryvanta.db`), enabling frictionless Windows setup while preserving full PostgreSQL compatibility and Docker Compose readiness.
   - SQLite foreign-key enforcement (`PRAGMA foreign_keys=ON`) is explicitly enabled on every connection so referential integrity behaves consistently across engines.

2. **Leakage-Free ML Evaluation (`StratifiedGroupKFold`)**
   - Early validation revealed that synthetic phrasing variants sharing the same base template inflated held-out accuracy to 100% under naive random splitting.
   - We resolved this by tagging synthetic template families with `template_group_id` and switching `train_pipeline.py` to `StratifiedGroupKFold`, yielding honest, realistic held-out metrics (88.9% main-category accuracy, 88.6% macro F1, 52.1% 24-way subcategory accuracy).

3. **Decoupled Priority & Sentiment**
   - Urgency detection (`priority_service.py`) is deliberately separated from both text classification and lexicon sentiment (`sentiment/analyzer.py`) so negative customer tone never auto-escalates non-critical tickets to Critical priority.

4. **Strict Customer Data Isolation**
   - Enforced at the backend service/router layer (`_ensure_ticket_access`, `serialize_ticket_detail`, `search_similar_tickets_for_user`): customers can only list or read their own tickets, never see `visibility='internal'` notes or ML internals, and never see other customers' tickets in similarity lookups.

5. **Direct `bcrypt` + `PyJWT` Authentication**
   - Used `bcrypt` directly instead of `passlib` for clean Python 3.14 compatibility without deprecation warnings.
   - Email validation uses a strict regex pattern (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) so both standard production domains and local `.local` demo accounts work smoothly.

6. **Editorial Enterprise UI Design**
   - Built with Tailwind CSS v4 (`@layer components` for utility override safety), horizontal top navigation, subtle 1px borders (`#E3E7E4`), restrained `#F5F6F4`/`#38685A` palette, and zero decorative animations or fabricated real-time feeds.
