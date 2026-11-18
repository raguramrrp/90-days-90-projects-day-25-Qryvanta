import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "../pages/LoginPage";
import { SubmitTicketPage } from "../pages/SubmitTicketPage";
import { TicketQueuePage } from "../pages/TicketQueuePage";
import { IncidentsPage } from "../pages/IncidentsPage";
import { OperationsPage } from "../pages/OperationsPage";
import { ResolutionIntelligencePage } from "../pages/ResolutionIntelligencePage";
import { AuthProvider } from "../hooks/useAuth";
import { ToastProvider } from "../hooks/useToast";
import {
  StatusLabel,
  PriorityIndicator,
  SLAIndicator,
  RiskBadge,
  IncidentStatusBadge,
  VerificationBadge,
  CollapsiblePanel,
  EmptyState,
} from "../components/UI";

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter>{ui}</MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("QRYVANTA Frontend Core UI & Workflows", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders clean login screen with email dropdown demo autofill and toggles registration mode", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByText("QRYVANTA")).toBeInTheDocument();
    expect(screen.getByText("Sign in to workspace")).toBeInTheDocument();
    expect(screen.queryByText("Local Development Demo Accounts")).not.toBeInTheDocument();

    // Open demo dropdown from email field and autofill both email and password
    fireEvent.click(screen.getByRole("button", { name: /Choose demo account/i }));
    expect(screen.getByText("Administrator")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByText("Administrator"));

    expect((screen.getByLabelText("Email address") as HTMLInputElement).value).toBe("admin@qryvanta.local");
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("DemoUser#2026");

    fireEvent.click(screen.getByText("Customer registration"));
    expect(screen.getByText("Create customer account")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Alex Morgan")).toBeInTheDocument();
  });

  it("validates submit ticket form fields before submitting to API", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })
    );

    renderWithProviders(<SubmitTicketPage />);
    fireEvent.click(screen.getByRole("button", { name: /Submit ticket/i }));

    await waitFor(() => {
      expect(screen.getByText(/Subject must be at least 4 characters/i)).toBeInTheDocument();
      expect(screen.getByText(/Please provide at least 10 characters/i)).toBeInTheDocument();
    });
  });

  it("renders ticket queue table and empty state cleanly from API responses", async () => {
    localStorage.setItem("qryvanta_access_token", "fake-token");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return new Response(
          JSON.stringify({ id: 1, name: "Maya Kapoor", email: "customer@qryvanta.local", role: "customer", is_active: true }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/companies")) {
        return new Response(
          JSON.stringify({ platform_types: ["E-Commerce", "SaaS / Software"], companies: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/tickets")) {
        return new Response(
          JSON.stringify({ items: [], total: 0, page: 1, page_size: 15, total_pages: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderWithProviders(<TicketQueuePage />);
    await waitFor(() => {
      expect(screen.getByText(/No tickets match the current view/i)).toBeInTheDocument();
    });
  });

  it("renders semantic status, priority, SLA, risk, incident badges and collapsible panels accurately", () => {
    render(
      <div>
        <StatusLabel status="in_progress" />
        <PriorityIndicator priority="critical" />
        <SLAIndicator state="overdue" />
        <RiskBadge level="critical" />
        <IncidentStatusBadge status="detected" />
        <VerificationBadge status="reported_to_company" />
        <CollapsiblePanel title="Details Panel" defaultOpen={false}>
          <div>Hidden content</div>
        </CollapsiblePanel>
        <EmptyState title="Nothing here" description="No items found." />
      </div>
    );
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("Critical risk")).toBeInTheDocument();
    expect(screen.getByText("Detected (Review)")).toBeInTheDocument();
    expect(screen.getByText("Reported to company")).toBeInTheDocument();
    expect(screen.queryByText("Hidden content")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Details Panel"));
    expect(screen.getByText("Hidden content")).toBeInTheDocument();
  });

  it("renders Incident Centre empty state, Risk & Workload, and Resolution Intelligence screens cleanly", async () => {
    localStorage.setItem("qryvanta_access_token", "fake-token");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return new Response(
          JSON.stringify({ id: 2, name: "Nadia Lin", email: "manager@qryvanta.local", role: "manager", is_active: true }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/incidents")) {
        return new Response(
          JSON.stringify({
            items: [],
            summary: { active_incidents: 0, newly_detected: 0, confirmed_or_investigating: 0, unique_affected_customers_active: 0 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/operations/overview")) {
        return new Response(
          JSON.stringify({
            risk_method: "deterministic_risk_rules",
            risk_summary: { critical: 0, high: 0, moderate: 0, low: 0 },
            at_risk_tickets: [],
            unassigned_high_priority: [],
            agent_capacity: { available: [], nearing_capacity: [], overloaded: [] },
            department_backlogs: [],
            manager_actions: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/resolution/overview")) {
        return new Response(
          JSON.stringify({
            effectiveness: {
              insufficient_data: false,
              sample_size: 10,
              metrics: { fcr_rate: 70, reopen_rate: 10, recurrence_after_closure_rate: 5 },
              by_category: [],
              by_department: [],
              recommendation_effectiveness: { total_ratings: 0, helpful: 0, partially_helpful: 0, not_helpful: 0, applied_to_replies: 0, helpful_rate: null },
              metric_definitions: {},
            },
            knowledge_gaps: [],
            recent_verified_resolutions: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    const { unmount } = renderWithProviders(<IncidentsPage />);
    await waitFor(() => expect(screen.getByText(/No active incidents detected/i)).toBeInTheDocument());
    unmount();

    const opView = renderWithProviders(<OperationsPage />);
    await waitFor(() => expect(screen.getByText(/Risk & Workload Operations/i)).toBeInTheDocument());
    opView.unmount();

    renderWithProviders(<ResolutionIntelligencePage />);
    await waitFor(() => expect(screen.getByText(/Resolution Intelligence & Knowledge Gaps/i)).toBeInTheDocument());
  });
});
