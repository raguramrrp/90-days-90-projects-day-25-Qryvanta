# QRYVANTA — User Guide

## Role Workflows

### 1. Customer Workflow
1. Sign in as a customer (`customer@qryvanta.local` / `DemoUser#2026` for local demo) or register a new customer account.
2. Open **Submit Ticket**, enter a subject, detailed description, optional category/product reference, and optional attachment (up to 5 MB).
3. After submission, note the generated reference (`QRY-YYYY-NNNNN`) and click **Track ticket progress**.
4. View public support responses, reply directly, upload additional files, rate resolved tickets (1–5 stars), or reopen resolved tickets with a reason.

### 2. Support Agent Workflow
1. Sign in as a department agent (e.g., `billing.agent@qryvanta.local` or `tech.agent@qryvanta.local`).
2. Use **Ticket Queue** presets (`My tickets`, `Unassigned`, `Overdue SLA`, `Low confidence`, `Reopened`) to focus daily work.
3. Open any ticket to access the **three-column Ticket Detail workspace**:
   - **Left Column**: Inspect customer details, attachments, status, priority, department, and assignment controls.
   - **Centre Column**: Reply publicly to the customer or toggle **Internal note** for private staff-only commentary (never visible to customers).
   - **Right Column**: Inspect ML category/subcategory predictions, confidence score, top TF-IDF terms, independent urgency rationale, similar/duplicate tickets, knowledge base guides (click **Insert into reply**), workload-based agent recommendations, and SLA timers.
4. If an AI prediction is inaccurate, click **Correct prediction**, select the right category/department/priority, enter a correction reason, and save. Corrections feed Intelligence analytics and future controlled retraining.

### 3. Support Manager Workflow
1. Monitor **Overview** KPIs, overdue SLA alerts, and low-confidence triage queues.
2. Select multiple rows in **Ticket Queue** to bulk-assign agents or update statuses, export filtered tickets to CSV, or run **Bulk CSV import** with preview and column mapping.
3. Review **Departments**, **Agents** (workload utilization alongside priority complexity context), **Intelligence**, and **Analytics** (with date filters and CSV exports).
4. Use **Model Centre** to trigger controlled retraining incorporating verified human corrections and promote candidate models after reviewing held-out test metrics.

### 4. Administrator Workflow
1. Open **Settings** to configure confidence routing thresholds, similarity cutoffs, SLA policies, business hours, holidays, hierarchical categories/subcategories, routing rules, knowledge articles, user accounts/roles, and **Audit Logs**.
