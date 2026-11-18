import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  ClipboardList,
  HelpCircle,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
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

export function CustomerHomePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["customer-recent-complaints"],
    queryFn: () =>
      apiRequest<TicketListResponse>(
        "/api/tickets?page=1&page_size=4&sort_by=updated_at&sort_order=desc"
      ),
  });

  const recentComplaints = data?.items || [];
  const totalComplaints = data?.total || 0;

  return (
    <div className="space-y-9">
      {/* Calm Welcoming Hero Banner */}
      <section className="customer-hero-surface p-7 sm:p-9">
        <div className="max-w-2xl">
          <h1 className="text-[28px] sm:text-[34px] font-bold tracking-tight text-[#1D2825] leading-tight">
            How can we help you today?
          </h1>
          <p className="mt-2.5 text-[15px] sm:text-[16px] text-[#556560] leading-relaxed">
            Tell us what happened. Our support team will help you resolve it.
          </p>
        </div>

        {/* Three Primary Actions */}
        <div className="mt-7 grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            to="/submit-complaint"
            className="group surface-card-interactive p-6 flex flex-col justify-between"
          >
            <div>
              <div className="w-11 h-11 rounded-[10px] bg-[#ECF4F1] text-[#2F6354] border border-[#D4E4DD] flex items-center justify-center group-hover:bg-[#2F6354] group-hover:text-white group-hover:border-[#2F6354] transition-colors">
                <FileText className="w-5 h-5" />
              </div>
              <h2 className="mt-4 text-[16.5px] font-semibold text-[#1D2825]">
                Report a Problem
              </h2>
              <p className="mt-1.5 text-[13.5px] text-[#5A6964] leading-relaxed">
                Submit a new complaint about an order, payment, refund, delivery, or account issue.
              </p>
            </div>
            <span className="mt-5 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-[#2F6354]">
              <span>Submit a complaint</span>
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          </Link>

          <Link
            to="/my-complaints"
            className="group surface-card-interactive p-6 flex flex-col justify-between"
          >
            <div>
              <div className="w-11 h-11 rounded-[10px] bg-[#ECF4F1] text-[#2F6354] border border-[#D4E4DD] flex items-center justify-center group-hover:bg-[#2F6354] group-hover:text-white group-hover:border-[#2F6354] transition-colors">
                <ClipboardList className="w-5 h-5" />
              </div>
              <h2 className="mt-4 text-[16.5px] font-semibold text-[#1D2825]">
                Track My Complaint
              </h2>
              <p className="mt-1.5 text-[13.5px] text-[#5A6964] leading-relaxed">
                Check the progress of an existing complaint and reply to messages from our team.
              </p>
            </div>
            <span className="mt-5 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-[#2F6354]">
              <span>View my complaints</span>
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          </Link>

          <Link
            to="/help"
            className="group surface-card-interactive p-6 flex flex-col justify-between"
          >
            <div>
              <div className="w-11 h-11 rounded-[10px] bg-[#ECF4F1] text-[#2F6354] border border-[#D4E4DD] flex items-center justify-center group-hover:bg-[#2F6354] group-hover:text-white group-hover:border-[#2F6354] transition-colors">
                <HelpCircle className="w-5 h-5" />
              </div>
              <h2 className="mt-4 text-[16.5px] font-semibold text-[#1D2825]">
                Get Help
              </h2>
              <p className="mt-1.5 text-[13.5px] text-[#5A6964] leading-relaxed">
                Find clear, step-by-step answers to common questions before contacting support.
              </p>
            </div>
            <span className="mt-5 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-[#2F6354]">
              <span>Browse Help Centre</span>
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          </Link>
        </div>
      </section>

      {/* Compact Recent Complaints Section */}
      <section aria-labelledby="recent-complaints-heading" className="surface-card overflow-hidden">
        <div className="px-6 py-4.5 border-b border-[#E6EBE8] flex items-center justify-between gap-4 bg-[#FAFBF9]">
          <h2
            id="recent-complaints-heading"
            className="text-[16px] font-semibold text-[#1D2825]"
          >
            Your Recent Complaints
          </h2>
          {totalComplaints > 0 && (
            <Link
              to="/my-complaints"
              className="text-[13.5px] font-semibold text-[#2F6354] hover:underline shrink-0"
            >
              View all ({totalComplaints})
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 bg-[#F2F5F3] rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : isError ? (
          <div className="p-6 text-[14px] text-[#5A6964]">
            We could not load your recent complaints right now. Please try again in a moment.
          </div>
        ) : recentComplaints.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-[15.5px] font-medium text-[#2E3B37]">
              You haven&apos;t submitted any complaints yet.
            </p>
            <p className="mt-1.5 text-[13.5px] text-[#6E7C77]">
              If something went wrong with an order, payment, delivery, or account, let us know.
            </p>
            <div className="mt-5">
              <Link
                to="/submit-complaint"
                className="btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-[14px]"
              >
                Report a Problem
              </Link>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-[#E6EBE8]">
            {recentComplaints.map((complaint) => {
              const statusInfo = getCustomerStatusInfo(
                complaint.status,
                complaint.has_assigned_support
              );
              return (
                <Link
                  key={complaint.id}
                  to={`/my-complaints/${complaint.id}`}
                  className="group px-6 py-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#F7FAF8] transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="font-mono text-[12.5px] font-semibold text-[#2F6354]">
                        {complaint.ticket_reference}
                      </span>
                      <span
                        className={`inline-block px-2.5 py-0.5 text-[12px] font-medium rounded-full border ${statusInfo.badgeClass}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="mt-1.5 text-[15px] font-medium text-[#1D2825] group-hover:text-[#2F6354] transition-colors truncate">
                      {complaint.subject}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-[#6E7C77]">
                      <span>Submitted {formatShortDate(complaint.created_at)}</span>
                      <span>
                        Last updated {formatShortDate(complaint.updated_at || complaint.created_at)}
                      </span>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-1 text-[13px] font-semibold text-[#2F6354] shrink-0">
                    <span>View</span>
                    <ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
