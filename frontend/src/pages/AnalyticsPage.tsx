import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
} from "recharts";
import { apiDownloadBlob, apiRequest } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { DepartmentMetrics } from "../types";
import { PageHeader, MetricSummary, LoadingSkeleton, ErrorState, formatMinutes } from "../components/UI";

export function AnalyticsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const [tab, setTab] = useState<"operational" | "departments" | "cx" | "effectiveness" | "classification">("operational");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const qs = new URLSearchParams();
  if (startDate) qs.set("start_date", `${startDate}T00:00:00Z`);
  if (endDate) qs.set("end_date", `${endDate}T23:59:59Z`);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";

  const { data: ticketsData, isLoading: l1 } = useQuery({
    queryKey: ["analytics-tickets", suffix],
    queryFn: () => apiRequest<any>(`/api/analytics/tickets${suffix}`),
  });

  const { data: deptData, isLoading: l2 } = useQuery({
    queryKey: ["analytics-departments", suffix],
    queryFn: () => apiRequest<{ departments: DepartmentMetrics[] }>(`/api/analytics/departments${suffix}`),
  });

  const { data: classData, isLoading: l3 } = useQuery({
    queryKey: ["analytics-classification", suffix],
    queryFn: () => apiRequest<any>(`/api/analytics/classification${suffix}`),
  });

  const { data: effData } = useQuery({
    queryKey: ["analytics-effectiveness"],
    queryFn: () => apiRequest<any>("/api/analytics/effectiveness"),
  });

  const handleExport = async () => {
    try {
      await apiDownloadBlob(`/api/analytics/export/csv${suffix}`, "qryvanta_analytics_report.csv");
      notify("Exported analytics CSV report.", "success");
    } catch {
      notify("Export requires manager or administrator permissions.", "error");
    }
  };

  if (l1 || l2 || l3) return <LoadingSkeleton rows={6} />;
  if (!ticketsData) return <ErrorState message="Unable to load analytics." />;

  const m = ticketsData.metrics;
  const cx = ticketsData.customer_experience;
  const activeMetrics = classData?.active_model?.evaluation_metrics;

  return (
    <div>
      <PageHeader
        title="Analytics & Reporting"
        subtitle="Consistent database-calculated operational, department, customer experience, and classification metrics."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              aria-label="Start date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="field-input w-36"
            />
            <span className="text-[12px] text-[#78817D]">to</span>
            <input
              type="date"
              aria-label="End date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="field-input w-36"
            />
            {(user?.role === "manager" || user?.role === "admin") && (
              <button className="btn-secondary inline-flex items-center gap-1.5" onClick={handleExport}>
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </button>
            )}
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[#E3E7E4] mb-5">
        {[
          { id: "operational", label: "Operational" },
          { id: "departments", label: "Departments" },
          { id: "cx", label: "Customer Experience" },
          { id: "effectiveness", label: "Resolution Effectiveness" },
          { id: "classification", label: "Classification & Model" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as typeof tab)}
            className={`px-3.5 py-2 text-[13px] font-medium border-b-2 transition-colors ${
              tab === t.id
                ? "border-[#38685A] text-[#38685A]"
                : "border-transparent text-[#78817D] hover:text-[#222C2A]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "operational" && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricSummary label="Total tickets" value={m.total_tickets} />
            <MetricSummary label="Open backlog" value={m.open_tickets} tone="accent" />
            <MetricSummary label="Avg first response" value={formatMinutes(m.avg_first_response_minutes)} />
            <MetricSummary label="SLA compliance" value={m.sla_compliance_rate !== null ? `${m.sla_compliance_rate}%` : "N/A"} tone="accent" />
          </div>

          <div className="surface-card p-4">
            <div className="text-[13.5px] font-semibold mb-3">Created vs. Resolved Tickets</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={ticketsData.volume_over_time}>
                  <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#78817D" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="created" stroke="#38685A" fill="#38685A" fillOpacity={0.15} />
                  <Area type="monotone" dataKey="resolved" stroke="#8AA397" fill="#8AA397" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {tab === "departments" && deptData && (
        <div className="space-y-5">
          <div className="surface-card p-4">
            <div className="text-[13.5px] font-semibold mb-3">Ticket Volume & Open Backlog by Department</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={deptData.departments}>
                  <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#222C2A" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#78817D" }} />
                  <Tooltip />
                  <Bar dataKey="total_tickets" name="Total" fill="#38685A" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="open_tickets" name="Open" fill="#8AA397" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="surface-card overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2.5 px-4">Department</th>
                  <th className="py-2.5 px-3">Total</th>
                  <th className="py-2.5 px-3">Open</th>
                  <th className="py-2.5 px-3">Avg resolution</th>
                  <th className="py-2.5 px-3">SLA compliance</th>
                  <th className="py-2.5 px-3">Escalation rate</th>
                  <th className="py-2.5 px-3">Reassignment rate</th>
                  <th className="py-2.5 px-3">Reopen rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {deptData.departments.map((d) => (
                  <tr key={d.department_id}>
                    <td className="py-2.5 px-4 font-medium">{d.name}</td>
                    <td className="py-2.5 px-3">{d.total_tickets}</td>
                    <td className="py-2.5 px-3">{d.open_tickets}</td>
                    <td className="py-2.5 px-3">{formatMinutes(d.avg_resolution_minutes)}</td>
                    <td className="py-2.5 px-3 text-[#38685A] font-medium">
                      {d.sla_compliance_rate !== null ? `${d.sla_compliance_rate}%` : "N/A"}
                    </td>
                    <td className="py-2.5 px-3">{d.escalation_rate}%</td>
                    <td className="py-2.5 px-3">{d.reassignment_rate}%</td>
                    <td className="py-2.5 px-3">{d.reopen_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "cx" && cx && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricSummary
              label="Avg CSAT rating"
              value={cx.avg_satisfaction_score !== null ? `${cx.avg_satisfaction_score} / 5` : "N/A"}
              sublabel={`${cx.total_rated_tickets} rated ticket(s)`}
              tone="accent"
            />
            <MetricSummary
              label="Reopen rate"
              value={`${cx.reopen_rate}%`}
              sublabel={`${cx.reopened_count} of ${cx.resolved_population} resolved/reopened`}
              tone={cx.reopen_rate > 15 ? "warning" : "default"}
            />
            <MetricSummary label="Reopened tickets" value={cx.reopened_count} />
            <MetricSummary label="Demand spikes detected" value={cx.demand_alerts.length} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="surface-card p-4">
              <div className="text-[13.5px] font-semibold mb-3">Satisfaction Rating Distribution</div>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cx.rating_distribution}>
                    <CartesianGrid stroke="#E3E7E4" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="stars" tickFormatter={(v) => `${v} stars`} tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" name="Responses" fill="#38685A" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="surface-card p-4">
              <div className="text-[13.5px] font-semibold mb-3">Reopened Tickets by Category</div>
              {cx.reopen_by_category.length === 0 ? (
                <div className="text-[13px] text-[#78817D] py-8 text-center">No reopened tickets in selected period.</div>
              ) : (
                <div className="space-y-2 text-[13px]">
                  {cx.reopen_by_category.map((r: { category: string; count: number }) => (
                    <div key={r.category} className="flex justify-between border-b border-[#E3E7E4] pb-1.5">
                      <span>{r.category}</span>
                      <span className="font-semibold text-[#C08A3E]">{r.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "effectiveness" && effData && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricSummary
              label="First Contact Resolution"
              value={effData.metrics?.fcr_rate !== undefined ? `${effData.metrics.fcr_rate}%` : "N/A"}
              sublabel={`Sample size n=${effData.sample_size}`}
              tone="accent"
            />
            <MetricSummary
              label="Reopen rate"
              value={effData.metrics?.reopen_rate !== undefined ? `${effData.metrics.reopen_rate}%` : "N/A"}
            />
            <MetricSummary
              label="Repeat issue rate"
              value={effData.metrics?.repeat_issue_rate !== undefined ? `${effData.metrics.repeat_issue_rate}%` : "N/A"}
            />
            <MetricSummary
              label="Post-closure recurrence"
              value={effData.metrics?.recurrence_after_closure_rate !== undefined ? `${effData.metrics.recurrence_after_closure_rate}%` : "N/A"}
              sublabel="Same customer/category within 14d"
            />
          </div>
          <div className="surface-card overflow-x-auto">
            <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
              Resolution Effectiveness by Department
            </div>
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2 px-4">Department</th>
                  <th className="py-2 px-3">Sample (n)</th>
                  <th className="py-2 px-3">FCR %</th>
                  <th className="py-2 px-3">Reopen %</th>
                  <th className="py-2 px-3">Avg Resolution</th>
                  <th className="py-2 px-3">Avg CSAT</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {(effData.by_department || []).map((row: any) => (
                  <tr key={row.department}>
                    <td className="py-2 px-4 font-medium">
                      {row.department}
                      {row.small_sample_warning && <span className="text-[11px] text-[#C08A3E] ml-1">(small sample)</span>}
                    </td>
                    <td className="py-2 px-3 text-[#78817D]">{row.sample_size}</td>
                    <td className="py-2 px-3 text-[#38685A] font-medium">{row.fcr_rate}%</td>
                    <td className="py-2 px-3">{row.reopen_rate}%</td>
                    <td className="py-2 px-3">{formatMinutes(row.avg_resolution_minutes)}</td>
                    <td className="py-2 px-3">{row.avg_csat ? `${row.avg_csat} / 5` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "classification" && classData && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricSummary label="Total predictions" value={classData.total_predictions} />
            <MetricSummary label="Correction rate" value={`${classData.correction_rate}%`} tone="warning" />
            <MetricSummary
              label="Held-out test accuracy"
              value={activeMetrics?.accuracy ? `${(activeMetrics.accuracy * 100).toFixed(1)}%` : "No active model"}
              tone="accent"
            />
            <MetricSummary
              label="Held-out macro F1"
              value={activeMetrics?.macro_f1 ? `${(activeMetrics.macro_f1 * 100).toFixed(1)}%` : "N/A"}
            />
          </div>

          {activeMetrics?.per_category && (
            <div className="surface-card overflow-x-auto">
              <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
                Per-Category Held-Out Evaluation ({classData.active_model.version})
              </div>
              <table className="w-full text-left border-collapse text-[13px]">
                <thead>
                  <tr className="table-header">
                    <th className="py-2 px-4">Category</th>
                    <th className="py-2 px-3">Precision</th>
                    <th className="py-2 px-3">Recall</th>
                    <th className="py-2 px-3">F1 Score</th>
                    <th className="py-2 px-3">Train / Test Support</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E3E7E4]">
                  {activeMetrics.per_category.map((row: any) => (
                    <tr key={row.category}>
                      <td className="py-2 px-4 font-medium">{row.category}</td>
                      <td className="py-2 px-3">{(row.precision * 100).toFixed(1)}%</td>
                      <td className="py-2 px-3">{(row.recall * 100).toFixed(1)}%</td>
                      <td className="py-2 px-3 font-medium text-[#38685A]">{(row.f1 * 100).toFixed(1)}%</td>
                      <td className="py-2 px-3 text-[#78817D]">
                        {row.train_support} / {row.test_support}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
