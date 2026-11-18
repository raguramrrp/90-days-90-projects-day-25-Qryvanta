import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { DepartmentMetrics } from "../types";
import { PageHeader, LoadingSkeleton, ErrorState, formatMinutes } from "../components/UI";

export function DepartmentsPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const canEdit = user?.role === "manager" || user?.role === "admin";

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DepartmentMetrics | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      if (editing) {
        return apiRequest(`/api/departments/${editing.department_id}`, {
          method: "PATCH",
          body: JSON.stringify({ name, description }),
        });
      }
      return apiRequest("/api/departments", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
    },
    onSuccess: () => {
      notify(editing ? "Department updated." : "Department created.", "success");
      setModalOpen(false);
      setEditing(null);
      setName("");
      setDescription("");
      qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to save department.", "error"),
  });

  if (isLoading) return <LoadingSkeleton rows={5} />;
  if (error || !data) return <ErrorState message="Failed to load departments." onRetry={() => refetch()} />;

  return (
    <div>
      <PageHeader
        title="Departments"
        subtitle="Operational queues, staffing coverage, resolution duration, and SLA compliance per department."
        actions={
          canEdit && (
            <button
              className="btn-primary"
              onClick={() => {
                setEditing(null);
                setName("");
                setDescription("");
                setModalOpen(true);
              }}
            >
              Add department
            </button>
          )
        }
      />

      <div className="surface-card overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="table-header">
              <th className="py-2.5 px-4">Department</th>
              <th className="py-2.5 px-3">Agents</th>
              <th className="py-2.5 px-3">Open tickets</th>
              <th className="py-2.5 px-3">Unassigned</th>
              <th className="py-2.5 px-3">Avg resolution</th>
              <th className="py-2.5 px-3">SLA compliance</th>
              <th className="py-2.5 px-3">Reopen rate</th>
              {canEdit && <th className="py-2.5 px-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E3E7E4] text-[13px]">
            {data.map((d) => (
              <tr key={d.department_id} className="hover:bg-[#FAFBF9]">
                <td className="py-3 px-4">
                  <div className="font-medium text-[#222C2A]">{d.name}</div>
                  {d.description && (
                    <div className="text-[12px] text-[#78817D] max-w-md">{d.description}</div>
                  )}
                </td>
                <td className="py-3 px-3">{d.agent_count}</td>
                <td className="py-3 px-3 font-medium">{d.open_tickets}</td>
                <td className="py-3 px-3 text-[#C08A3E]">{d.unassigned_tickets}</td>
                <td className="py-3 px-3">{formatMinutes(d.avg_resolution_minutes)}</td>
                <td className="py-3 px-3 font-medium text-[#38685A]">
                  {d.sla_compliance_rate !== null && d.sla_compliance_rate !== undefined
                    ? `${d.sla_compliance_rate}%`
                    : "N/A"}
                </td>
                <td className="py-3 px-3">{d.reopen_rate}%</td>
                {canEdit && (
                  <td className="py-3 px-3 text-right">
                    <button
                      className="btn-secondary py-1 px-2.5 text-[12px]"
                      onClick={() => {
                        setEditing(d);
                        setName(d.name);
                        setDescription(d.description || "");
                        setModalOpen(true);
                      }}
                    >
                      Edit
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="surface-card max-w-md w-full p-5 bg-white space-y-4">
            <h2 className="text-[15px] font-semibold">
              {editing ? "Edit department" : "Create department"}
            </h2>
            <div>
              <label className="block text-[12.5px] font-medium mb-1">Department name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="field-input" />
            </div>
            <div>
              <label className="block text-[12.5px] font-medium mb-1">Description</label>
              <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} className="field-input" />
            </div>
            <div className="flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button
                className="btn-primary"
                disabled={name.trim().length < 2 || saveMutation.isPending}
                onClick={() => saveMutation.mutate()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
