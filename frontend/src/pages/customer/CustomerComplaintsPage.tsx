import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, ChevronRight, Plus } from "lucide-react";
import { apiRequest } from "../../services/api";
import type { TicketSummary } from "../../types";
import {
  formatShortDate,
  getCustomerStatusInfo,
} from "../../utils/customerStatus";

interface TicketListResponse {
  items: TicketSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

type FilterTab = "all" | "active" | "resolved";

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "resolved", label: "Resolved" },
];

export function CustomerComplaintsPage() {
  const [filter, setFilter] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("page_size", "12");
  queryParams.set("sort_by", "updated_at");
  queryParams.set("sort_order", "desc");
  if (filter !== "all") {
    queryParams.set("preset", filter);
  }
  if (search.trim()) {
    queryParams.set("search", search.trim());
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ["customer-complaints", filter, search, page],
    queryFn: () =>
      apiRequest<TicketListResponse>(`/api/tickets?${queryParams.toString()}`),
  });

  const complaints = data?.items || [];
  const total = data?.total || 0;
  const totalPages = data?.total_pages || 1;
  const hasFilters = filter !== "all" || search.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-bold text-[#1D2825] tracking-tight">
            My Complaints
          </h1>
          <p className="mt-1 text-[14.5px] text-[#556560]">
            Check the progress of your complaints and view replies from our support team.
          </p>
        </div>
        <Link
          to="/submit-complaint"
          className="btn-primary inline-flex items-center justify-center gap-1.5 px-4.5 py-2.5 text-[14px] shrink-0"
        >
          <Plus className="w-4 h-4" />
          Report a Problem
        </Link>
      </div>

      {/* Simple Filter & Search Bar */}
      <div className="surface-card p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div
          role="tablist"
          aria-label="Filter complaints"
          className="inline-flex items-center gap-1 p-1 rounded-[8px] bg-[#F2F5F3]"
        >
          {FILTER_TABS.map((tab) => {
            const active = filter === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  setFilter(tab.key);
                  setPage(1);
                }}
                className={`px-4 py-1.5 rounded-[6px] text-[13.5px] font-medium transition-all cursor-pointer ${
                  active
                    ? "bg-white text-[#1D2825] shadow-xs font-semibold"
                    : "text-[#5D6B66] hover:text-[#1D2825]"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-[#7D8B86] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by complaint ID or subject"
            aria-label="Search complaints by ID or subject"
            className="field-input pl-10 py-2 text-[13.5px]"
          />
        </div>
      </div>

      {/* Complaints List / Table */}
      <div className="surface-card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-14 bg-[#F2F5F3] rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[14px] text-[#556560]">
            We could not load your complaints right now. Please refresh the page and try again.
          </div>
        ) : complaints.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <p className="text-[16px] font-semibold text-[#1D2825]">
              {hasFilters
                ? "No complaints match your search or filter."
                : "You haven't submitted any complaints yet."}
            </p>
            <p className="mt-1.5 text-[13.5px] text-[#6E7C77]">
              {hasFilters
                ? "Try clearing your search or switching to All complaints."
                : "When you report a problem, you can track every update here."}
            </p>
            <div className="mt-5 flex justify-center gap-3">
              {hasFilters ? (
                <button
                  type="button"
                  onClick={() => {
                    setFilter("all");
                    setSearch("");
                    setPage(1);
                  }}
                  className="btn-secondary px-4 py-2 text-[13.5px]"
                >
                  Show all complaints
                </button>
              ) : (
                <Link
                  to="/submit-complaint"
                  className="btn-primary px-5 py-2.5 text-[14px]"
                >
                  Report a Problem
                </Link>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="table-header">
                    <th className="py-3.5 px-4 font-semibold whitespace-nowrap">Complaint ID</th>
                    <th className="py-3.5 px-4 font-semibold">Subject</th>
                    <th className="py-3.5 px-4 font-semibold whitespace-nowrap">Submitted</th>
                    <th className="py-3.5 px-4 font-semibold whitespace-nowrap">Last updated</th>
                    <th className="py-3.5 px-4 font-semibold whitespace-nowrap">Status</th>
                    <th className="py-3.5 px-4 font-semibold text-right whitespace-nowrap">
                      <span className="sr-only">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E6EBE8]">
                  {complaints.map((complaint) => {
                    const statusInfo = getCustomerStatusInfo(
                      complaint.status,
                      complaint.has_assigned_support
                    );
                    return (
                      <tr
                        key={complaint.id}
                        className="group hover:bg-[#F7FAF8] transition-colors"
                      >
                        <td className="py-4 px-4 font-mono text-[12.5px] font-semibold text-[#2F6354] whitespace-nowrap">
                          <Link
                            to={`/my-complaints/${complaint.id}`}
                            className="hover:underline"
                          >
                            {complaint.ticket_reference}
                          </Link>
                        </td>
                        <td className="py-4 px-4 text-[14px] font-medium text-[#1D2825] max-w-[260px] lg:max-w-[340px]">
                          <Link
                            to={`/my-complaints/${complaint.id}`}
                            className="group-hover:text-[#2F6354] transition-colors block truncate"
                            title={complaint.subject}
                          >
                            {complaint.subject}
                          </Link>
                        </td>
                        <td className="py-4 px-4 text-[13px] text-[#5D6B66] whitespace-nowrap">
                          {formatShortDate(complaint.created_at)}
                        </td>
                        <td className="py-4 px-4 text-[13px] text-[#5D6B66] whitespace-nowrap">
                          {formatShortDate(
                            complaint.updated_at || complaint.created_at
                          )}
                        </td>
                        <td className="py-4 px-4 whitespace-nowrap">
                          <span
                            className={`inline-block px-2.5 py-0.5 text-[12px] font-medium rounded-full border ${statusInfo.badgeClass}`}
                          >
                            {statusInfo.label}
                          </span>
                        </td>
                        <td className="py-4 px-4 text-right whitespace-nowrap">
                          <Link
                            to={`/my-complaints/${complaint.id}`}
                            className="inline-flex items-center gap-1 text-[13px] font-semibold text-[#2F6354] hover:underline"
                          >
                            <span>View</span>
                            <ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Card List */}
            <div className="md:hidden divide-y divide-[#E6EBE8]">
              {complaints.map((complaint) => {
                const statusInfo = getCustomerStatusInfo(
                  complaint.status,
                  complaint.has_assigned_support
                );
                return (
                  <Link
                    key={complaint.id}
                    to={`/my-complaints/${complaint.id}`}
                    className="block p-4 hover:bg-[#F7FAF8]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[12.5px] font-semibold text-[#2F6354]">
                        {complaint.ticket_reference}
                      </span>
                      <span
                        className={`inline-block px-2.5 py-0.5 text-[12px] font-medium rounded-full border ${statusInfo.badgeClass}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[14.5px] font-medium text-[#1D2825]">
                      {complaint.subject}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-[#6E7C77]">
                      <span>Submitted {formatShortDate(complaint.created_at)}</span>
                      <span>
                        Updated{" "}
                        {formatShortDate(
                          complaint.updated_at || complaint.created_at
                        )}
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="px-5 py-3.5 border-t border-[#E6EBE8] bg-[#FAFBF9] flex items-center justify-between text-[13px] text-[#5D6B66]">
                <span className="tabular-nums">
                  Showing page <strong className="text-[#1D2825]">{page}</strong> of {totalPages} ({total} complaints)
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="btn-secondary px-3 py-1.5 text-[13px]"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="btn-secondary px-3 py-1.5 text-[13px]"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
