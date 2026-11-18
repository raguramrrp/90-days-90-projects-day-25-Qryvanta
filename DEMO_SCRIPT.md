# QRYVANTA — 90-Second Portfolio Demo Script

**Preparation**: Run `run.bat` and open `http://127.0.0.1:5173`.

## Walkthrough Sequence

1. **0:00 – 0:15 | Login & Role-Based Architecture (`login.png`)**
   - Show the editorial login screen and local demo role selector.
   - Sign in as **Customer** (`customer@qryvanta.local` / `DemoUser#2026`).
   - Point out that customers only see **Tickets**, **Submit Ticket**, and **Settings (Profile)** — no internal operational screens.

2. **0:15 – 0:35 | Customer Ticket Submission & Automatic Intelligence**
   - Open **Submit Ticket**, enter a billing or technical outage request (e.g., *"Production API returning HTTP 500 errors on PDF export"*), leave Category as *Auto-detect*, and submit.
   - Show the confirmation screen with the unique `QRY-2026-XXXXX` reference and tracking link.

3. **0:35 – 1:05 | Staff Operations & Three-Column Ticket Workspace (`ticket-detail.png`)**
   - Sign out and sign in as **Administrator** (`admin@qryvanta.local`) or **Support Manager** (`manager@qryvanta.local`).
   - Open **Overview** (`overview.png`) to show real database-backed KPIs, SLA compliance, and volume trends.
   - Open **Ticket Queue** (`ticket-queue.png`), filter by *Critical & high* or *Low confidence*, and open the newly created ticket.
   - Walk through the 3 columns:
     - **Right**: Live TF-IDF + Logistic Regression prediction with confidence, top explanatory keywords, separate rule-based urgency rationale, TF-IDF cosine-similarity related tickets, Knowledge Base recommendations, workload-based agent recommendations, and SLA clock.
     - **Centre**: Post a private **Internal note** (amber lock badge) and explain how backend serialization strips internal notes from customer responses.
     - **Human-in-the-Loop**: Click **Correct prediction**, change category/department with a reason, and save.

4. **1:05 – 1:30 | Intelligence, Analytics & Model Centre (`intelligence.png`, `model-centre.png`)**
   - Open **Intelligence** to test any text live in the Classification Test Bench and view the Human Correction Rate.
   - Open **Model Centre** to display honest held-out test metrics (`88.9%` accuracy, `88.6%` macro F1, zero-leakage group-stratified split, confusion matrix) and demonstrate clicking **Train new model version** with verified human corrections.
