import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppRoutes } from "../App";
import { AuthProvider } from "../hooks/useAuth";
import { ToastProvider } from "../hooks/useToast";
import { CustomerHomePage } from "../pages/customer/CustomerHomePage";
import { CustomerSubmitComplaintPage } from "../pages/customer/CustomerSubmitComplaintPage";
import { CustomerComplaintsPage } from "../pages/customer/CustomerComplaintsPage";
import { CustomerComplaintDetailPage } from "../pages/customer/CustomerComplaintDetailPage";
import { CustomerHelpCentrePage } from "../pages/customer/CustomerHelpCentrePage";

function renderWithAppProviders(ui: React.ReactElement, initialEntries = ["/"]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

const CUSTOMER_USER = {
  id: 9,
  name: "Maya Kapoor",
  email: "customer@qryvanta.local",
  role: "customer",
  is_active: true,
  contact_information: "+1 555-0199",
};

describe("QRYVANTA Customer Portal Redesign", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("shows minimal customer navigation and never exposes staff workspace links", async () => {
    localStorage.setItem("qryvanta_access_token", "cust-token");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return new Response(JSON.stringify(CUSTOMER_USER), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/tickets")) {
        return new Response(
          JSON.stringify({ items: [], total: 0, page: 1, page_size: 4, total_pages: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    renderWithAppProviders(<AppRoutes />, ["/"]);

    await waitFor(() => {
      expect(screen.getByText("How can we help you today?")).toBeInTheDocument();
    });

    // Customer nav items present
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Submit a Complaint" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "My Complaints" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Help Centre" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign out/i })).toBeInTheDocument();

    // Staff nav items strictly absent
    expect(screen.queryByText("Incident Centre")).not.toBeInTheDocument();
    expect(screen.queryByText("Risk & Workload")).not.toBeInTheDocument();
    expect(screen.queryByText("Model Centre")).not.toBeInTheDocument();
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
    expect(screen.queryByText("Departments")).not.toBeInTheDocument();
  });

  it("renders welcoming Customer Home Page with 3 primary actions and empty recent complaints state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 1, page_size: 4, total_pages: 0 }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    renderWithAppProviders(<CustomerHomePage />);

    expect(screen.getByText("How can we help you today?")).toBeInTheDocument();
    expect(
      screen.getByText("Tell us what happened. Our support team will help you resolve it.")
    ).toBeInTheDocument();
    expect(screen.getByText("Report a Problem")).toBeInTheDocument();
    expect(screen.getByText("Track My Complaint")).toBeInTheDocument();
    expect(screen.getByText("Get Help")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText("You haven't submitted any complaints yet.")
      ).toBeInTheDocument();
    });
  });

  it("validates simplified complaint form and shows calm confirmation after submission", async () => {
    localStorage.setItem("qryvanta_access_token", "cust-token");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return new Response(JSON.stringify(CUSTOMER_USER), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/categories")) {
        return new Response(
          JSON.stringify([{ id: 1, name: "Billing & Payments", is_active: true, subcategories: [] }]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/companies")) {
        return new Response(
          JSON.stringify({ platform_types: ["E-Commerce"], companies: [{ id: 1, name: "ShopSphere", platform_type: "E-Commerce", is_active: true }] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/tickets") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: 42,
            ticket_reference: "QRY-2026-00042",
            subject: "Refund not received for returned shoes",
            description: "Returned the order last week and still waiting for my refund.",
            status: "new",
            has_assigned_support: false,
            created_at: "2026-11-18T10:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    renderWithAppProviders(<CustomerSubmitComplaintPage />);

    // Validate empty submit
    fireEvent.click(screen.getByRole("button", { name: "Submit Complaint" }));
    await waitFor(() => {
      expect(screen.getByText(/Please select what your issue is about/i)).toBeInTheDocument();
      expect(screen.getByText(/Please enter a short subject/i)).toBeInTheDocument();
    });

    // Complete simplified form
    fireEvent.click(screen.getByRole("button", { name: /Refund/i }));
    fireEvent.change(screen.getByLabelText(/2\. Subject/i), {
      target: { value: "Refund not received for returned shoes" },
    });
    fireEvent.change(screen.getByLabelText(/3\. Describe your problem/i), {
      target: { value: "Returned the order last week and still waiting for my refund." },
    });

    fireEvent.click(screen.getByRole("button", { name: "Submit Complaint" }));

    await waitFor(() => {
      expect(
        screen.getByText("Your complaint has been submitted successfully.")
      ).toBeInTheDocument();
      expect(screen.getByText("QRY-2026-00042")).toBeInTheDocument();
      expect(screen.getByText("Received")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View Complaint" })).toBeInTheDocument();
    });

    // No internal ML jargon on confirmation
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Priority/i)).not.toBeInTheDocument();
  });

  it("displays friendly statuses on My Complaints and hides internal columns", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: 10,
              ticket_reference: "QRY-2026-00010",
              subject: "Parcel arrived damaged",
              description: "Box was crushed.",
              status: "awaiting_customer",
              has_assigned_support: true,
              created_at: "2026-11-17T09:00:00Z",
              updated_at: "2026-11-18T08:00:00Z",
            },
            {
              id: 11,
              ticket_reference: "QRY-2026-00011",
              subject: "Invoice correction",
              description: "Need updated billing address.",
              status: "resolved",
              has_assigned_support: true,
              created_at: "2026-11-15T09:00:00Z",
              updated_at: "2026-11-16T08:00:00Z",
            },
          ],
          total: 2,
          page: 1,
          page_size: 12,
          total_pages: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    renderWithAppProviders(<CustomerComplaintsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("QRY-2026-00010").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Waiting for your response").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Resolved").length).toBeGreaterThan(0);
    });

    expect(screen.queryByText("Department")).not.toBeInTheDocument();
    expect(screen.queryByText("Priority")).not.toBeInTheDocument();
    expect(screen.queryByText("SLA")).not.toBeInTheDocument();
  });

  it("renders Complaint Tracking progress timeline, Waiting for your response callout, and public conversation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 10,
          ticket_reference: "QRY-2026-00010",
          subject: "Parcel arrived damaged",
          description: "The outer box was torn and the item inside is broken.",
          external_reference: "ORD-5540",
          status: "awaiting_customer",
          has_assigned_support: true,
          created_at: "2026-11-17T09:00:00Z",
          updated_at: "2026-11-18T08:00:00Z",
          messages: [
            {
              id: 1,
              sender_name: "Alex Support",
              sender_role: "agent",
              message: "Could you please share a photo of the damaged item?",
              visibility: "public",
              created_at: "2026-11-18T08:00:00Z",
            },
          ],
          attachments: [],
          events: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    renderWithAppProviders(
      <Routes>
        <Route path="/my-complaints/:id" element={<CustomerComplaintDetailPage />} />
      </Routes>,
      ["/my-complaints/10"]
    );

    await waitFor(() => {
      expect(screen.getByText("Parcel arrived damaged")).toBeInTheDocument();
      expect(screen.getByText("Complaint submitted")).toBeInTheDocument();
      expect(screen.getByText("Under review")).toBeInTheDocument();
      expect(screen.getByText("Being resolved")).toBeInTheDocument();
      expect(screen.getByText("Resolved")).toBeInTheDocument();
      expect(screen.getByText("Waiting for your response")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Reply now" })).toBeInTheDocument();
      expect(screen.getByText("Support Team")).toBeInTheDocument();
      expect(
        screen.getByText("Could you please share a photo of the damaged item?")
      ).toBeInTheDocument();
    });
  });

  it("renders Help Centre published articles, reader view, and Contact Support CTA", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: 1,
            title: "How return refunds are processed",
            content: "Refunds are issued back to your original payment method within 5 business days.",
            category_name: "Billing & Payments",
            tags: "refund,payment",
            is_published: true,
            updated_at: "2026-11-18T08:00:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    renderWithAppProviders(<CustomerHelpCentrePage />);

    await waitFor(() => {
      expect(screen.getByText("How return refunds are processed")).toBeInTheDocument();
    });
    expect(screen.getByText("Didn't find what you need?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contact Support" })).toBeInTheDocument();

    fireEvent.click(screen.getByText("How return refunds are processed"));
    expect(screen.getByRole("button", { name: /Back to Help Centre/i })).toBeInTheDocument();
  });
});
