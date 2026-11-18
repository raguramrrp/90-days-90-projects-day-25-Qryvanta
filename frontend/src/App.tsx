import React from "react";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { ToastProvider } from "./hooks/useToast";
import { AppLayout } from "./layouts/AppLayout";
import { CustomerLayout } from "./layouts/CustomerLayout";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { TicketQueuePage } from "./pages/TicketQueuePage";
import { SubmitTicketPage } from "./pages/SubmitTicketPage";
import { TicketDetailPage } from "./pages/TicketDetailPage";
import { DepartmentsPage } from "./pages/DepartmentsPage";
import { PortalsPage } from "./pages/PortalsPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { OperationsPage } from "./pages/OperationsPage";
import { ResolutionIntelligencePage } from "./pages/ResolutionIntelligencePage";
import { AgentsPage } from "./pages/AgentsPage";
import { IntelligencePage } from "./pages/IntelligencePage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ModelCentrePage } from "./pages/ModelCentrePage";
import { SettingsPage } from "./pages/SettingsPage";
import { CustomerHomePage } from "./pages/customer/CustomerHomePage";
import { CustomerSubmitComplaintPage } from "./pages/customer/CustomerSubmitComplaintPage";
import { CustomerComplaintsPage } from "./pages/customer/CustomerComplaintsPage";
import { CustomerComplaintDetailPage } from "./pages/customer/CustomerComplaintDetailPage";
import { CustomerHelpCentrePage } from "./pages/customer/CustomerHelpCentrePage";
import { CustomerAccountPage } from "./pages/customer/CustomerAccountPage";
import { LoadingSkeleton } from "./components/UI";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function LegacyCustomerTicketRedirect() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={id ? `/my-complaints/${id}` : "/my-complaints"} replace />;
}

function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: React.ReactNode;
  allowedRoles?: string[];
}) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="max-w-3xl mx-auto mt-16 px-4">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="max-w-3xl mx-auto mt-16 px-4">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  // Strictly separate Customer Portal experience from Staff Operations Workspace
  if (user?.role === "customer") {
    return (
      <Routes>
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route
          element={
            <ProtectedRoute allowedRoles={["customer"]}>
              <CustomerLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<CustomerHomePage />} />
          <Route path="/submit-complaint" element={<CustomerSubmitComplaintPage />} />
          <Route path="/my-complaints" element={<CustomerComplaintsPage />} />
          <Route path="/my-complaints/:id" element={<CustomerComplaintDetailPage />} />
          <Route path="/help" element={<CustomerHelpCentrePage />} />
          <Route path="/account" element={<CustomerAccountPage />} />

          {/* Clean redirects for legacy customer paths */}
          <Route path="/tickets" element={<Navigate to="/my-complaints" replace />} />
          <Route path="/tickets/:id" element={<LegacyCustomerTicketRedirect />} />
          <Route path="/submit" element={<Navigate to="/submit-complaint" replace />} />
          <Route path="/settings" element={<Navigate to="/account" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        element={
          <ProtectedRoute allowedRoles={["agent", "manager", "admin"]}>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<OverviewPage />} />
        <Route path="/tickets" element={<TicketQueuePage />} />
        <Route path="/tickets/:id" element={<TicketDetailPage />} />
        <Route path="/submit" element={<SubmitTicketPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/operations" element={<OperationsPage />} />
        <Route path="/resolution-intelligence" element={<ResolutionIntelligencePage />} />
        <Route path="/portals" element={<PortalsPage />} />
        <Route path="/departments" element={<DepartmentsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/models" element={<ModelCentrePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? "/" : "/login"} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
