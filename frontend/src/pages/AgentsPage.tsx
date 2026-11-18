import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { AgentMetrics, DepartmentMetrics } from "../types";
import { PageHeader, LoadingSkeleton, ErrorState, formatMinutes } from "../components/UI";

export function AgentsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const canManage = user?.role === "manager" || user?.role === "admin";

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [deptId, setDeptId] = useState("");
  const [expertise, setExpertise] = useState("");
  const [maxOpen, setMaxOpen] = useState(15);

  const [editing, setEditing] = useState<AgentMetrics | null>(null);
  const [editAvail, setEditAvail] = useState("available");
  const [editDept, setEditDept] = useState("");
  const [editExpertise, setEditExpertise] = useState("");
  const [editMaxOpen, setEditMaxOpen] = useState(15);

  const { data: agents, isLoading, error, refetch } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiRequest<AgentMetrics[]>("/api/agents"),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          password,
          department_id: Number(deptId),
          expertise,
          max_open_tickets: maxOpen,
        }),
      }),
    onSuccess: () => {
      notify("Support agent created.", "success");
      setCreateOpen(false);
      setName(""); setEmail(""); setPassword(""); setExpertise("");
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create agent.", "error"),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/agents/${editing?.agent_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          department_id: editDept ? Number(editDept) : undefined,
          availability_status: editAvail,
          expertise: editExpertise,
          max_open_tickets: editMaxOpen,
        }),
      }),
    onSuccess: () => {
      notify("Agent profile updated.", "success");
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Update failed.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={5} />;
  if (error || !agents) return <ErrorState message="Failed to load agents." onRetry={() => refetch()} />;

  return (
    <div>
      <PageHeader
        title="Support Agents"
        subtitle="Workload balance, priority complexity context, SLA compliance, and availability. Performance is presented with ticket-complexity context rather than raw count rankings."
        actions={
          canManage && (
            <button className="btn-primary" onClick={() => setCreateOpen(true)}>
              Add support agent
            </button>
          )
        }
      />

      <div className="surface-card overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="table-header">
              <th className="py-2.5 px-4">Agent</th>
              <th className="py-2.5 px-3">Department</th>
              <th className="py-2.5 px-3">Availability</th>
              <th className="py-2.5 px-3">Open workload</th>
              <th className="py-2.5 px-3">High/Critical handled</th>
              <th className="py-2.5 px-3">Avg resolution</th>
              <th className="py-2.5 px-3">SLA compliance</th>
              <th className="py-2.5 px-3">CSAT</th>
              {canManage && <th className="py-2.5 px-3 text-right">Manage</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E3E7E4] text-[13px]">
            {agents.map((a) => (
              <tr key={a.agent_id} className="hover:bg-[#FAFBF9]">
                <td className="py-3 px-4">
                  <div className="font-medium text-[#222C2A]">{a.name}</div>
                  <div className="text-[11.5px] text-[#78817D]">{a.expertise || a.email}</div>
                </td>
                <td className="py-3 px-3 text-[#222C2A]">{a.department_name || "Unassigned"}</td>
                <td className="py-3 px-3">
                  <span
                    className={`inline-block px-2 py-0.5 text-[11.5px] rounded border capitalize ${
                      a.availability_status === "available"
                        ? "bg-[#EFF5F2] text-[#38685A] border-[#CDE0D7]"
                        : a.availability_status === "busy"
                        ? "bg-[#FBF6EE] text-[#9A6D2E] border-[#E8D7BC]"
                        : "bg-[#F3F4F3] text-[#78817D] border-[#E3E7E4]"
                    }`}
                  >
                    {a.availability_status}
                  </span>
                </td>
                <td className="py-3 px-3">
                  <div className="font-medium">
                    {a.open_tickets} / {a.max_open_tickets}
                  </div>
                  <div className="w-24 h-1.5 bg-[#E3E7E4] rounded mt-1 overflow-hidden">
                    <div
                      className={`h-full ${a.utilization_pct >= 85 ? "bg-[#B84C4C]" : "bg-[#38685A]"}`}
                      style={{ width: `${Math.min(a.utilization_pct, 100)}%` }}
                    />
                  </div>
                </td>
                <td className="py-3 px-3 text-[#78817D]">
                  {a.high_priority_tickets} of {a.total_assigned}
                </td>
                <td className="py-3 px-3">{formatMinutes(a.avg_resolution_minutes)}</td>
                <td className="py-3 px-3 font-medium text-[#38685A]">
                  {a.sla_compliance_rate !== null && a.sla_compliance_rate !== undefined
                    ? `${a.sla_compliance_rate}%`
                    : "N/A"}
                </td>
                <td className="py-3 px-3">
                  {a.avg_satisfaction !== null && a.avg_satisfaction !== undefined
                    ? `${a.avg_satisfaction} / 5`
                    : "—"}
                </td>
                {canManage && (
                  <td className="py-3 px-3 text-right">
                    <button
                      className="btn-secondary py-1 px-2.5 text-[12px]"
                      onClick={() => {
                        setEditing(a);
                        setEditAvail(a.availability_status);
                        setEditDept(a.department_id ? String(a.department_id) : "");
                        setEditExpertise(a.expertise || "");
                        setEditMaxOpen(a.max_open_tickets);
                      }}
                    >
                      Configure
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Agent Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-md w-full p-5 bg-white space-y-3">
            <h2 className="text-[15px] font-semibold">Add Support Agent</h2>
            <input placeholder="Full name *" value={name} onChange={(e) => setName(e.target.value)} className="field-input" />
            <input placeholder="Email *" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field-input" />
            <input placeholder="Temporary password (min 8 chars) *" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="field-input" />
            <select value={deptId} onChange={(e) => setDeptId(e.target.value)} className="field-input">
              <option value="">Select primary department *</option>
              {departments?.map((d) => (
                <option key={d.department_id} value={String(d.department_id)}>{d.name}</option>
              ))}
            </select>
            <input placeholder="Expertise keywords (e.g., Billing, Refunds, API)" value={expertise} onChange={(e) => setExpertise(e.target.value)} className="field-input" />
            <div>
              <label className="text-[12px] text-[#78817D]">Max open ticket capacity</label>
              <input type="number" min={1} max={100} value={maxOpen} onChange={(e) => setMaxOpen(Number(e.target.value))} className="field-input mt-1" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setCreateOpen(false)}>Cancel</button>
              <button
                className="btn-primary"
                disabled={!name || !email || password.length < 8 || !deptId || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                Create agent
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Agent Modal */}
      {editing && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-md w-full p-5 bg-white space-y-3">
            <h2 className="text-[15px] font-semibold">Configure {editing.name}</h2>
            <div>
              <label className="text-[12px] text-[#78817D]">Primary department</label>
              <select value={editDept} onChange={(e) => setEditDept(e.target.value)} className="field-input mt-1">
                {departments?.map((d) => (
                  <option key={d.department_id} value={String(d.department_id)}>{d.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[12px] text-[#78817D]">Availability status</label>
              <select value={editAvail} onChange={(e) => setEditAvail(e.target.value)} className="field-input mt-1">
                <option value="available">Available</option>
                <option value="busy">Busy</option>
                <option value="away">Away</option>
                <option value="offline">Offline</option>
              </select>
            </div>
            <div>
              <label className="text-[12px] text-[#78817D]">Expertise areas</label>
              <input value={editExpertise} onChange={(e) => setEditExpertise(e.target.value)} className="field-input mt-1" />
            </div>
            <div>
              <label className="text-[12px] text-[#78817D]">Max open ticket limit</label>
              <input type="number" min={1} max={100} value={editMaxOpen} onChange={(e) => setEditMaxOpen(Number(e.target.value))} className="field-input mt-1" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn-primary" disabled={updateMutation.isPending} onClick={() => updateMutation.mutate()}>
                Save changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
