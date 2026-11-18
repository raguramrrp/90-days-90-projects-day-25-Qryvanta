# QRYVANTA — REST API Documentation

Interactive OpenAPI documentation is automatically served at `http://127.0.0.1:8000/docs` when the backend is running.

All protected endpoints expect `Authorization: Bearer <JWT_TOKEN>`.

## Authentication (`/api/auth`)
- `POST /api/auth/register` — Register a customer account (returns JWT + user profile).
- `POST /api/auth/login` — Authenticate with email and password (rate-limited).
- `GET /api/auth/me` — Retrieve authenticated profile.
- `PATCH /api/auth/me` — Update own name, customer contact info, or agent availability.
- `POST /api/auth/logout` — Record sign-out audit event.

## Tickets (`/api/tickets`)
- `POST /api/tickets` — Submit a new ticket (runs classification, urgency, routing, SLA, KB recommendation).
- `GET /api/tickets` — Paginated, filtered, sortable ticket list (`preset`, `search`, `status`, `priority`, `department_id`, `sort_by`, `sort_order`). Scoped strictly by role.
- `GET /api/tickets/{id}` — Full ticket detail. Customers never receive `internal` messages or ML internals.
- `PATCH /api/tickets/{id}` — Update status, priority (with override reason), department, or category (staff only).
- `POST /api/tickets/{id}/reply` — Post public reply or private internal note (customers restricted to `public`).
- `POST /api/tickets/{id}/attachments` — Upload validated attachment (max 5 MB, allowlisted extensions).
- `GET /api/tickets/{id}/attachments/{att_id}` — Authorized attachment download.
- `POST /api/tickets/{id}/assign` — Assign/reassign agent or department with reason (staff).
- `POST /api/tickets/{id}/reclassify` — Submit human-in-the-loop classification correction & reason (staff).
- `POST /api/tickets/{id}/close` — Mark ticket resolved or closed (staff).
- `POST /api/tickets/{id}/reopen` — Reopen resolved/closed ticket with reason.
- `POST /api/tickets/{id}/rate` — Submit 1–5 customer satisfaction rating & comment.
- `POST /api/tickets/{id}/relations` — Manually link related or duplicate ticket (staff).
- `POST /api/tickets/{id}/escalate` — Record SLA escalation note (staff).
- `POST /api/tickets/{id}/verify` — Record QRYVANTA evidence verification, direct recommended company action, company case reference, and company handoff status (staff).
- `GET /api/tickets/{id}/company-report` — Generate structured company handoff dossier (JSON or `?download=true` Markdown brief) so the target company can act directly without redundant investigation (staff).
- `POST /api/tickets/bulk-action` — Bulk assign, move department, or update status (manager/admin).

## Portals & Companies
- `GET /api/companies` — List registered companies and platform types (filterable by `platform_type`, `active_only`).
- `POST /api/companies`, `PATCH /api/companies/{id}` — Register or edit target companies/portals (manager/admin).
- `GET /api/analytics/portals` — Portal-wise and company-wise verification pipeline, handoff status, and volume breakdown (staff).
- `GET /api/tickets/export/csv` — Download filtered tickets as CSV (staff).
- `POST /api/tickets/import/preview` & `POST /api/tickets/import/execute` — Preview CSV mapping and bulk-import/classify tickets with deduplication (manager/admin).

## Intelligence (`/api/intelligence`)
- `POST /api/intelligence/classify` — Live single-ticket inference sandbox (staff).
- `POST /api/intelligence/bulk-classify` — Batch classify up to 100 payloads (manager/admin).
- `GET /api/intelligence/predictions/{ticket_id}` — Prediction history for a ticket (staff).
- `GET /api/intelligence/similar/{ticket_id}` — TF-IDF cosine similarity search scoped by viewer permissions.
- `GET /api/intelligence/feedback` — Human correction rate, mismatches, low-confidence queue, sentiment distribution, and demand alerts (staff).

## Departments & Agents
- `GET /api/departments`, `POST /api/departments`, `PATCH /api/departments/{id}`, `GET /api/departments/{id}/metrics`
- `GET /api/agents`, `POST /api/agents`, `PATCH /api/agents/{id}`, `GET /api/agents/{id}/workload`, `POST /api/agents/recommend`

## Incident Centre (`/api/incidents`)
- `GET /api/incidents` — List incidents with status/severity/department filters + active summary counts.
- `POST /api/incidents/detect` — Run TF-IDF cosine similarity + time-window clustering to surface new candidate `detected` incidents (manager/admin).
- `POST /api/incidents` — Create incident manually (manager/admin).
- `GET /api/incidents/{id}` — Incident detail with linked tickets, unique affected customers, and timeline events.
- `PATCH /api/incidents/{id}` — Update status (`detected|investigating|confirmed|monitoring|resolved|dismissed`), severity, owner, investigation notes, resolution summary (manager/admin).
- `POST /api/incidents/{id}/tickets` & `DELETE /api/incidents/{id}/tickets/{ticket_id}` — Link/unlink tickets.

## Risk & Workload + Resolution Intelligence
- `GET /api/operations/overview` — SLA breach risk summary, at-risk tickets, unassigned high-priority tickets with recommendations, agent capacity bands, growing department backlogs, and manager actions.
- `GET /api/resolution/similar/{ticket_id}` — Retrieve genuine similar resolved tickets within authorized scope.
- `POST /api/resolution/feedback` — Submit `helpful` / `partially_helpful` / `not_helpful` feedback.
- `GET /api/resolution/overview` — Resolution effectiveness (FCR, reopen, recurrence), detected Knowledge Gaps, and reference resolutions.
- `POST /api/resolution/knowledge-gaps/{gap_id}/draft` — Create an **unpublished** draft Knowledge Base article from a detected gap (manager/admin).
- `PATCH /api/resolution/knowledge-gaps/{gap_id}/dismiss` — Dismiss a knowledge gap (manager/admin).
- `GET /api/analytics/effectiveness` — Resolution effectiveness breakdown by category and department.

## Analytics (`/api/analytics`)
- `GET /api/analytics/overview`, `/tickets`, `/departments`, `/agents`, `/sla`, `/classification`, `/customer-experience`, `/export/csv` (all support `start_date` and `end_date` ISO filters).

## Model Centre (`/api/models`)
- `GET /api/models`, `GET /api/models/active`, `GET /api/models/{id}/metrics`
- `POST /api/models/train` — Controlled retraining with optional human corrections (manager/admin).
- `POST /api/models/{id}/activate` — Activate a vetted model version (manager/admin).

## Settings & Administration
- `GET /api/settings`, `PATCH /api/settings`
- `GET|POST|PATCH /api/sla/policies`, `POST|DELETE /api/holidays`
- `GET|POST|PATCH /api/categories`, `GET|POST|PATCH /api/routing-rules`
- `GET|POST|PATCH /api/users` (admin only), `GET /api/audit-logs` (admin only)
- `GET|POST /api/knowledge`, `POST /api/knowledge/recommendations/{rec_id}/feedback`
