import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { CategoryItem, DepartmentMetrics } from "../types";
import { PageHeader, LoadingSkeleton } from "../components/UI";

type SettingsTab =
  | "profile"
  | "routing"
  | "sla"
  | "categories"
  | "knowledge"
  | "users"
  | "audit";

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();

  const isAdmin = user?.role === "admin";
  const isManagerOrAdmin = user?.role === "manager" || user?.role === "admin";

  const [tab, setTab] = useState<SettingsTab>("profile");

  // Profile state
  const [profileName, setProfileName] = useState(user?.name || "");
  const [profileContact, setProfileContact] = useState(user?.contact_information || "");
  const [profileAvail, setProfileAvail] = useState(user?.availability_status || "available");

  // Threshold & Business Hours state
  const [highThreshold, setHighThreshold] = useState(0.8);
  const [medThreshold, setMedThreshold] = useState(0.55);
  const [simThreshold, setSimThreshold] = useState(0.25);
  const [startHour, setStartHour] = useState(9);
  const [endHour, setEndHour] = useState(17);
  const [holidayDate, setHolidayDate] = useState("");
  const [holidayName, setHolidayName] = useState("");

  // New Category state
  const [newCatName, setNewCatName] = useState("");
  const [newCatParent, setNewCatParent] = useState("");

  // New Knowledge Article state
  const [kbTitle, setKbTitle] = useState("");
  const [kbContent, setKbContent] = useState("");
  const [kbCatId, setKbCatId] = useState("");
  const [kbTags, setKbTags] = useState("");

  // New User state (Admin)
  const [uName, setUName] = useState("");
  const [uEmail, setUEmail] = useState("");
  const [uPassword, setUPassword] = useState("");
  const [uRole, setURole] = useState<"customer" | "agent" | "manager" | "admin">("agent");
  const [uDeptId, setUDeptId] = useState("");

  const { data: settingsData, isLoading: loadingSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<any>("/api/settings"),
  });

  useEffect(() => {
    if (settingsData) {
      setHighThreshold(settingsData.confidence_thresholds?.high ?? 0.8);
      setMedThreshold(settingsData.confidence_thresholds?.medium ?? 0.55);
      setSimThreshold(settingsData.similarity_threshold ?? 0.25);
      setStartHour(settingsData.business_hours?.start_hour ?? 9);
      setEndHour(settingsData.business_hours?.end_hour ?? 17);
    }
  }, [settingsData]);

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiRequest<CategoryItem[]>("/api/categories"),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => apiRequest<DepartmentMetrics[]>("/api/departments"),
    enabled: isManagerOrAdmin,
  });

  const { data: routingRules } = useQuery({
    queryKey: ["routing-rules"],
    queryFn: () => apiRequest<any[]>("/api/routing-rules"),
    enabled: isManagerOrAdmin,
  });

  const { data: slaPolicies } = useQuery({
    queryKey: ["sla-policies"],
    queryFn: () => apiRequest<any[]>("/api/sla/policies"),
    enabled: isManagerOrAdmin,
  });

  const { data: knowledge } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => apiRequest<any[]>("/api/knowledge"),
    enabled: isManagerOrAdmin,
  });

  const { data: users } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => apiRequest<any[]>("/api/users"),
    enabled: isAdmin && tab === "users",
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => apiRequest<any[]>("/api/audit-logs?limit=60"),
    enabled: isAdmin && tab === "audit",
  });

  const saveProfileMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          name: profileName,
          contact_information: user?.role === "customer" ? profileContact : undefined,
          availability_status: user?.role === "agent" ? profileAvail : undefined,
        }),
      }),
    onSuccess: async () => {
      await refreshUser();
      notify("Profile settings updated.", "success");
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to save profile.", "error"),
  });

  const saveSettingsMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiRequest("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      notify("Workspace configuration saved.", "success");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to update settings.", "error"),
  });

  const addHolidayMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/holidays", {
        method: "POST",
        body: JSON.stringify({ holiday_date: holidayDate, name: holidayName }),
      }),
    onSuccess: () => {
      setHolidayDate("");
      setHolidayName("");
      notify("Holiday added to SLA calendar.", "success");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to add holiday.", "error"),
  });

  const deleteHolidayMutation = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/holidays/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      notify("Holiday removed.", "info");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const createCategoryMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/categories", {
        method: "POST",
        body: JSON.stringify({
          name: newCatName,
          parent_category_id: newCatParent ? Number(newCatParent) : null,
        }),
      }),
    onSuccess: () => {
      setNewCatName("");
      setNewCatParent("");
      notify("Category created.", "success");
      qc.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create category.", "error"),
  });

  const toggleRuleAutoAssign = useMutation({
    mutationFn: ({ id, auto }: { id: number; auto: boolean }) =>
      apiRequest(`/api/routing-rules/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ auto_assign_agent: auto }),
      }),
    onSuccess: () => {
      notify("Routing rule updated.", "success");
      qc.invalidateQueries({ queryKey: ["routing-rules"] });
    },
  });

  const createKbMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/knowledge", {
        method: "POST",
        body: JSON.stringify({
          title: kbTitle,
          content: kbContent,
          category_id: kbCatId ? Number(kbCatId) : null,
          tags: kbTags || null,
          is_published: true,
        }),
      }),
    onSuccess: () => {
      setKbTitle(""); setKbContent(""); setKbTags("");
      notify("Knowledge article published.", "success");
      qc.invalidateQueries({ queryKey: ["knowledge"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create article.", "error"),
  });

  const createUserMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/users", {
        method: "POST",
        body: JSON.stringify({
          name: uName,
          email: uEmail,
          password: uPassword,
          role: uRole,
          department_id: uDeptId ? Number(uDeptId) : null,
        }),
      }),
    onSuccess: () => {
      setUName(""); setUEmail(""); setUPassword("");
      notify("User account created.", "success");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err) => notify(err instanceof ApiError ? err.message : "Failed to create user.", "error"),
  });

  const toggleUserActive = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      apiRequest(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify({ is_active: active }) }),
    onSuccess: () => {
      notify("User status updated.", "success");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const tabs: { id: SettingsTab; label: string; visible: boolean }[] = [
    { id: "profile", label: "Profile", visible: true },
    { id: "routing", label: "Routing & Thresholds", visible: isManagerOrAdmin },
    { id: "sla", label: "SLA & Business Hours", visible: isManagerOrAdmin },
    { id: "categories", label: "Categories", visible: isAdmin },
    { id: "knowledge", label: "Knowledge Base", visible: isManagerOrAdmin },
    { id: "users", label: "Users & Roles", visible: isAdmin },
    { id: "audit", label: "Audit Logs", visible: isAdmin },
  ];

  if (loadingSettings) return <LoadingSkeleton rows={5} />;

  return (
    <div>
      <PageHeader
        title="Settings & Administration"
        subtitle="Manage account preferences, confidence thresholds, SLA policies, taxonomy, and security audit history."
      />

      <div className="flex flex-wrap gap-1 border-b border-[#E3E7E4] mb-5">
        {tabs
          .filter((t) => t.visible)
          .map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
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

      {/* Profile */}
      {tab === "profile" && (
        <div className="surface-card p-5 max-w-lg space-y-4">
          <div className="text-[14px] font-semibold">Profile Settings</div>
          <div>
            <label className="block text-[12px] text-[#78817D] mb-1">Full name</label>
            <input value={profileName} onChange={(e) => setProfileName(e.target.value)} className="field-input" />
          </div>
          <div>
            <label className="block text-[12px] text-[#78817D] mb-1">Email (read-only)</label>
            <input value={user?.email || ""} disabled className="field-input bg-[#F5F6F4]" />
          </div>
          <div>
            <label className="block text-[12px] text-[#78817D] mb-1">Role</label>
            <input value={user?.role || ""} disabled className="field-input bg-[#F5F6F4] capitalize" />
          </div>
          {user?.role === "customer" && (
            <div>
              <label className="block text-[12px] text-[#78817D] mb-1">Contact information</label>
              <input value={profileContact} onChange={(e) => setProfileContact(e.target.value)} className="field-input" />
            </div>
          )}
          {user?.role === "agent" && (
            <div>
              <label className="block text-[12px] text-[#78817D] mb-1">Availability status</label>
              <select value={profileAvail} onChange={(e) => setProfileAvail(e.target.value)} className="field-input">
                <option value="available">Available</option>
                <option value="busy">Busy</option>
                <option value="away">Away</option>
                <option value="offline">Offline</option>
              </select>
            </div>
          )}
          <button className="btn-primary" onClick={() => saveProfileMutation.mutate()}>
            Save profile
          </button>
        </div>
      )}

      {/* Routing & Confidence Thresholds */}
      {tab === "routing" && isManagerOrAdmin && (
        <div className="space-y-5">
          <div className="surface-card p-5 max-w-2xl space-y-4">
            <div className="text-[14px] font-semibold">Classification Confidence & Similarity Thresholds</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-[12px] text-[#78817D] mb-1">High confidence (auto-route)</label>
                <input
                  type="number"
                  step="0.05"
                  min={0.5}
                  max={0.99}
                  value={highThreshold}
                  onChange={(e) => setHighThreshold(Number(e.target.value))}
                  className="field-input"
                />
              </div>
              <div>
                <label className="block text-[12px] text-[#78817D] mb-1">Medium confidence (review)</label>
                <input
                  type="number"
                  step="0.05"
                  min={0.1}
                  max={0.95}
                  value={medThreshold}
                  onChange={(e) => setMedThreshold(Number(e.target.value))}
                  className="field-input"
                />
              </div>
              <div>
                <label className="block text-[12px] text-[#78817D] mb-1">Duplicate similarity cutoff</label>
                <input
                  type="number"
                  step="0.05"
                  min={0.05}
                  max={0.95}
                  value={simThreshold}
                  onChange={(e) => setSimThreshold(Number(e.target.value))}
                  className="field-input"
                />
              </div>
            </div>
            <button
              className="btn-primary"
              onClick={() =>
                saveSettingsMutation.mutate({
                  confidence_thresholds: { high: highThreshold, medium: medThreshold },
                  similarity_threshold: simThreshold,
                })
              }
            >
              Update thresholds
            </button>
          </div>

          <div className="surface-card overflow-x-auto">
            <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
              Department Routing Rules
            </div>
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2 px-4">Rule</th>
                  <th className="py-2 px-3">Category</th>
                  <th className="py-2 px-3">Target Department</th>
                  <th className="py-2 px-3">Min Confidence</th>
                  <th className="py-2 px-3">Auto-assign Agent</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {routingRules?.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2.5 px-4 font-medium">{r.name}</td>
                    <td className="py-2.5 px-3">{r.category_name}</td>
                    <td className="py-2.5 px-3">{r.department_name}</td>
                    <td className="py-2.5 px-3">{(r.min_confidence * 100).toFixed(0)}%</td>
                    <td className="py-2.5 px-3">
                      <button
                        className="btn-secondary py-0.5 px-2 text-[12px]"
                        onClick={() => toggleRuleAutoAssign.mutate({ id: r.id, auto: !r.auto_assign_agent })}
                      >
                        {r.auto_assign_agent ? "Enabled" : "Queue only"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SLA & Business Hours */}
      {tab === "sla" && isManagerOrAdmin && (
        <div className="space-y-5">
          <div className="surface-card overflow-x-auto">
            <div className="px-4 py-3 border-b border-[#E3E7E4] text-[13.5px] font-semibold">
              Active SLA Policies
            </div>
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2 px-4">Policy Name</th>
                  <th className="py-2 px-3">Priority</th>
                  <th className="py-2 px-3">Department</th>
                  <th className="py-2 px-3">First Response</th>
                  <th className="py-2 px-3">Resolution Target</th>
                  <th className="py-2 px-3">Schedule</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {slaPolicies?.map((p) => (
                  <tr key={p.id}>
                    <td className="py-2.5 px-4 font-medium">{p.name}</td>
                    <td className="py-2.5 px-3 capitalize">{p.priority}</td>
                    <td className="py-2.5 px-3">{p.department_name}</td>
                    <td className="py-2.5 px-3">{p.first_response_minutes} min</td>
                    <td className="py-2.5 px-3">{p.resolution_minutes} min</td>
                    <td className="py-2.5 px-3">{p.business_hours_only ? "Business hours" : "24x7 clock"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="surface-card p-5 space-y-3">
              <div className="text-[13.5px] font-semibold">Business Hours (UTC, Mon–Fri)</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[12px] text-[#78817D]">Start hour (0–23)</label>
                  <input type="number" min={0} max={22} value={startHour} onChange={(e) => setStartHour(Number(e.target.value))} className="field-input mt-1" />
                </div>
                <div>
                  <label className="text-[12px] text-[#78817D]">End hour (1–23)</label>
                  <input type="number" min={1} max={23} value={endHour} onChange={(e) => setEndHour(Number(e.target.value))} className="field-input mt-1" />
                </div>
              </div>
              <button
                className="btn-primary"
                onClick={() =>
                  saveSettingsMutation.mutate({
                    business_hours: {
                      start_hour: startHour,
                      start_minute: 0,
                      end_hour: endHour,
                      end_minute: 0,
                      workdays: [0, 1, 2, 3, 4],
                    },
                  })
                }
              >
                Save business hours
              </button>
            </div>

            <div className="surface-card p-5 space-y-3">
              <div className="text-[13.5px] font-semibold">Configured Holidays (Excluded from Business-Hours SLA)</div>
              <div className="flex gap-2">
                <input type="date" value={holidayDate} onChange={(e) => setHolidayDate(e.target.value)} className="field-input w-40" />
                <input placeholder="Holiday name" value={holidayName} onChange={(e) => setHolidayName(e.target.value)} className="field-input" />
                <button
                  className="btn-primary shrink-0"
                  disabled={!holidayDate || holidayName.trim().length < 2}
                  onClick={() => addHolidayMutation.mutate()}
                >
                  Add
                </button>
              </div>
              <ul className="divide-y divide-[#E3E7E4] text-[12.5px]">
                {settingsData?.holidays?.map((h: any) => (
                  <li key={h.id} className="py-1.5 flex justify-between items-center">
                    <span>
                      <strong className="font-mono">{h.holiday_date}</strong> — {h.name}
                    </span>
                    <button className="text-[#B84C4C] text-[12px] hover:underline" onClick={() => deleteHolidayMutation.mutate(h.id)}>
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Categories (Admin) */}
      {tab === "categories" && isAdmin && (
        <div className="space-y-4">
          <div className="surface-card p-4 flex flex-wrap gap-2.5 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="text-[12px] text-[#78817D]">Category or subcategory name</label>
              <input value={newCatName} onChange={(e) => setNewCatName(e.target.value)} placeholder="e.g., Compliance Audit" className="field-input mt-1" />
            </div>
            <div className="w-60">
              <label className="text-[12px] text-[#78817D]">Parent category (optional)</label>
              <select value={newCatParent} onChange={(e) => setNewCatParent(e.target.value)} className="field-input mt-1">
                <option value="">Top-level category</option>
                {categories?.map((c) => (
                  <option key={c.id} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </div>
            <button
              className="btn-primary"
              disabled={newCatName.trim().length < 2}
              onClick={() => createCategoryMutation.mutate()}
            >
              Add category
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {categories?.map((c) => (
              <div key={c.id} className="surface-card p-4">
                <div className="font-semibold text-[#222C2A]">{c.name}</div>
                <div className="text-[12px] text-[#78817D] mt-1">
                  Subcategories:{" "}
                  {c.subcategories.length > 0 ? c.subcategories.map((s) => s.name).join(" · ") : "None"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge Base */}
      {tab === "knowledge" && isManagerOrAdmin && (
        <div className="space-y-4">
          <div className="surface-card p-5 space-y-3">
            <div className="text-[13.5px] font-semibold">Publish Knowledge Article</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input placeholder="Article title *" value={kbTitle} onChange={(e) => setKbTitle(e.target.value)} className="field-input" />
              <select value={kbCatId} onChange={(e) => setKbCatId(e.target.value)} className="field-input">
                <option value="">Associate category (optional)</option>
                {categories?.map((c) => (
                  <option key={c.id} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </div>
            <textarea rows={3} placeholder="Resolution steps and customer guidance..." value={kbContent} onChange={(e) => setKbContent(e.target.value)} className="field-input" />
            <div className="flex gap-2">
              <input placeholder="Tags (comma-separated)" value={kbTags} onChange={(e) => setKbTags(e.target.value)} className="field-input" />
              <button
                className="btn-primary shrink-0"
                disabled={kbTitle.trim().length < 4 || kbContent.trim().length < 10}
                onClick={() => createKbMutation.mutate()}
              >
                Publish
              </button>
            </div>
          </div>

          <div className="surface-card divide-y divide-[#E3E7E4]">
            {knowledge?.map((art) => (
              <div key={art.id} className="p-4">
                <div className="flex justify-between gap-2">
                  <span className="font-medium text-[#222C2A]">{art.title}</span>
                  <span className="text-[12px] text-[#78817D]">{art.category_name || "General"}</span>
                </div>
                <p className="text-[12.5px] text-[#78817D] mt-1">{art.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Users & Roles (Admin) */}
      {tab === "users" && isAdmin && (
        <div className="space-y-4">
          <div className="surface-card p-4 grid grid-cols-1 sm:grid-cols-6 gap-2.5 items-end">
            <input placeholder="Full name *" value={uName} onChange={(e) => setUName(e.target.value)} className="field-input" />
            <input placeholder="Email *" value={uEmail} onChange={(e) => setUEmail(e.target.value)} className="field-input" />
            <input placeholder="Password (8+ chars) *" type="password" value={uPassword} onChange={(e) => setUPassword(e.target.value)} className="field-input" />
            <select value={uRole} onChange={(e) => setURole(e.target.value as any)} className="field-input">
              <option value="customer">Customer</option>
              <option value="agent">Support Agent</option>
              <option value="manager">Support Manager</option>
              <option value="admin">Administrator</option>
            </select>
            <select value={uDeptId} onChange={(e) => setUDeptId(e.target.value)} className="field-input">
              <option value="">Department (if staff)</option>
              {departments?.map((d) => (
                <option key={d.department_id} value={String(d.department_id)}>{d.name}</option>
              ))}
            </select>
            <button
              className="btn-primary"
              disabled={!uName || !uEmail || uPassword.length < 8}
              onClick={() => createUserMutation.mutate()}
            >
              Add user
            </button>
          </div>

          <div className="surface-card overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="table-header">
                  <th className="py-2 px-4">Name</th>
                  <th className="py-2 px-3">Email</th>
                  <th className="py-2 px-3">Role</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7E4]">
                {users?.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5 px-4 font-medium">{u.name}</td>
                    <td className="py-2.5 px-3 text-[#78817D]">{u.email}</td>
                    <td className="py-2.5 px-3 capitalize">{u.role}</td>
                    <td className="py-2.5 px-3">{u.is_active ? "Active" : "Inactive"}</td>
                    <td className="py-2.5 px-3 text-right">
                      {u.id !== user?.id && (
                        <button
                          className="btn-secondary py-0.5 px-2 text-[12px]"
                          onClick={() => toggleUserActive.mutate({ id: u.id, active: !u.is_active })}
                        >
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Audit Logs (Admin) */}
      {tab === "audit" && isAdmin && (
        <div className="surface-card overflow-x-auto">
          <table className="w-full text-left border-collapse text-[12.5px]">
            <thead>
              <tr className="table-header">
                <th className="py-2 px-4">Timestamp</th>
                <th className="py-2 px-3">User</th>
                <th className="py-2 px-3">Action</th>
                <th className="py-2 px-3">Entity</th>
                <th className="py-2 px-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7E4]">
              {auditLogs?.map((log) => (
                <tr key={log.id}>
                  <td className="py-2 px-4 text-[#78817D] whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 px-3 font-medium">{log.user_name}</td>
                  <td className="py-2 px-3 font-mono text-[12px] text-[#38685A]">{log.action}</td>
                  <td className="py-2 px-3">
                    {log.entity_type} {log.entity_id ? `#${log.entity_id}` : ""}
                  </td>
                  <td className="py-2 px-3 text-[#78817D] max-w-md truncate">
                    {JSON.stringify(log.details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
