import React from "react";
import { ChevronDown, ChevronUp, AlertTriangle, Inbox } from "lucide-react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3.5 pb-5 mb-6 border-b border-[#E1E6E3]">
      <div className="min-w-0">
        <h1 className="text-[22px] font-bold tracking-tight text-[#1D2825] leading-snug">
          {title}
        </h1>
        {subtitle && (
          <p className="text-[13.5px] text-[#62706B] mt-1 max-w-3xl leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
      )}
    </div>
  );
}

export function MetricSummary({
  label,
  value,
  sublabel,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  tone?: "default" | "accent" | "warning" | "critical";
}) {
  const styles = {
    default: {
      value: "text-[#1D2825]",
      bar: "bg-[#C7D2CD]",
      dot: "bg-[#8A9893]",
    },
    accent: {
      value: "text-[#255447]",
      bar: "bg-[#2F6354]",
      dot: "bg-[#2F6354]",
    },
    warning: {
      value: "text-[#A96F1F]",
      bar: "bg-[#C58A34]",
      dot: "bg-[#C58A34]",
    },
    critical: {
      value: "text-[#B03E3E]",
      bar: "bg-[#C44D4D]",
      dot: "bg-[#C44D4D]",
    },
  }[tone];

  return (
    <div className="surface-card relative overflow-hidden px-4 py-4">
      <div className={`absolute inset-x-0 top-0 h-[2.5px] ${styles.bar}`} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-[#62706B]">{label}</span>
        <span className={`w-1.5 h-1.5 rounded-full ${styles.dot}`} />
      </div>
      <div
        className={`text-[24px] font-bold mt-1.5 tracking-tight tabular-nums leading-none ${styles.value}`}
        style={{ fontFamily: '"Plus Jakarta Sans", "Inter", sans-serif' }}
      >
        {value}
      </div>
      {sublabel && (
        <div className="text-[11.5px] text-[#7D8B86] mt-2 leading-snug">
          {sublabel}
        </div>
      )}
    </div>
  );
}

export function StatusLabel({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; dot: string }> = {
    new: {
      label: "New",
      cls: "bg-[#EEF6F3] text-[#255447] border-[#CCE0D8]",
      dot: "bg-[#2F6354]",
    },
    open: {
      label: "Open",
      cls: "bg-[#F3F5F4] text-[#2C3935] border-[#D7DFDB]",
      dot: "bg-[#5E6E68]",
    },
    in_progress: {
      label: "In progress",
      cls: "bg-[#EAF3F0] text-[#244F43] border-[#C1D8CF]",
      dot: "bg-[#2F6354]",
    },
    awaiting_customer: {
      label: "Awaiting customer",
      cls: "bg-[#FEF7EC] text-[#8F5F1D] border-[#ECD5B1]",
      dot: "bg-[#C58A34]",
    },
    reopened: {
      label: "Reopened",
      cls: "bg-[#FEF3F3] text-[#AC3E3E] border-[#ECC5C5]",
      dot: "bg-[#C44D4D]",
    },
    resolved: {
      label: "Resolved",
      cls: "bg-[#EDF6F1] text-[#245A47] border-[#C3DFD2]",
      dot: "bg-[#2E7D5E]",
    },
    closed: {
      label: "Closed",
      cls: "bg-[#F4F5F4] text-[#6A7772] border-[#E0E5E2]",
      dot: "bg-[#97A39E]",
    },
  };
  const cfg = map[status] || {
    label: status,
    cls: "bg-[#F4F5F4] text-[#2C3935] border-[#DFE4E1]",
    dot: "bg-[#7A8782]",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[11.5px] font-medium rounded-full border whitespace-nowrap ${cfg.cls}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

export function PriorityIndicator({ priority }: { priority: string }) {
  const map: Record<string, { label: string; dot: string; text: string }> = {
    critical: { label: "Critical", dot: "bg-[#C44D4D]", text: "text-[#B03E3E] font-semibold" },
    high: { label: "High", dot: "bg-[#C58A34]", text: "text-[#9A651D] font-medium" },
    medium: { label: "Medium", dot: "bg-[#2F6354]", text: "text-[#263430]" },
    low: { label: "Low", dot: "bg-[#92A99F]", text: "text-[#6D7B76]" },
  };
  const cfg = map[priority] || { label: priority, dot: "bg-[#78817D]", text: "text-[#222C2A]" };
  return (
    <span className={`inline-flex items-center gap-1.5 text-[12.5px] whitespace-nowrap ${cfg.text}`}>
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

export function SLAIndicator({ state }: { state?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    on_track: { label: "On track", cls: "text-[#296150] font-medium" },
    approaching_deadline: { label: "Approaching", cls: "text-[#A96F1F] font-medium" },
    overdue: { label: "Overdue", cls: "text-[#B03E3E] font-semibold" },
    paused: { label: "Paused", cls: "text-[#717F7A]" },
    completed: { label: "Completed", cls: "text-[#717F7A]" },
  };
  const cfg = map[state || ""] || { label: state || "—", cls: "text-[#717F7A]" };
  return <span className={`text-[12.5px] whitespace-nowrap ${cfg.cls}`}>{cfg.label}</span>;
}

export function VerificationBadge({ status }: { status?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    unverified: { label: "Unverified", cls: "bg-[#F5F7F6] text-[#6B7974] border-[#DFE5E2]" },
    under_verification: { label: "Under verification", cls: "bg-[#FEF7EC] text-[#8F5F1D] border-[#ECD5B1]" },
    verified_ready: { label: "Verified — ready", cls: "bg-[#ECF5F1] text-[#255447] border-[#C5DDD3]" },
    reported_to_company: { label: "Reported to company", cls: "bg-[#E6F1ED] text-[#214B3F] border-[#B2CFC4] font-medium" },
    company_acknowledged: { label: "Company acknowledged", cls: "bg-[#ECF5F1] text-[#255447] border-[#C5DDD3]" },
    company_resolved: { label: "Company resolved", cls: "bg-[#EDF6F1] text-[#245A47] border-[#C3DFD2]" },
    insufficient_proof: { label: "Needs proof", cls: "bg-[#FEF3F3] text-[#AC3E3E] border-[#ECC5C5]" },
  };
  const cfg = map[status || "unverified"] || map.unverified;
  return (
    <span className={`inline-block px-2 py-0.5 text-[11px] font-medium rounded-md border whitespace-nowrap ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export function RiskBadge({ level }: { level?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    critical: { label: "Critical risk", cls: "bg-[#FEF2F2] text-[#B03E3E] border-[#EBC3C3] font-semibold" },
    high: { label: "High risk", cls: "bg-[#FEF7EC] text-[#96611A] border-[#ECD5B1] font-medium" },
    moderate: { label: "Moderate", cls: "bg-[#F4F6F5] text-[#35423E] border-[#D7DFDB]" },
    low: { label: "Low risk", cls: "bg-[#EDF6F1] text-[#255447] border-[#C5DDD3]" },
  };
  const cfg = map[level || "low"] || map.low;
  return (
    <span className={`inline-block px-2 py-0.5 text-[11px] rounded-md border whitespace-nowrap ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export function IncidentStatusBadge({ status }: { status?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    detected: { label: "Detected (Review)", cls: "bg-[#FEF7EC] text-[#8F5F1D] border-[#ECD5B1]" },
    investigating: { label: "Investigating", cls: "bg-[#FEF2F2] text-[#B03E3E] border-[#EBC3C3]" },
    confirmed: { label: "Confirmed", cls: "bg-[#FEF2F2] text-[#B03E3E] border-[#EBC3C3] font-semibold" },
    monitoring: { label: "Monitoring", cls: "bg-[#ECF5F1] text-[#244F43] border-[#C5DDD3]" },
    resolved: { label: "Resolved", cls: "bg-[#EDF6F1] text-[#245A47] border-[#C3DFD2]" },
    dismissed: { label: "Dismissed", cls: "bg-[#F4F5F4] text-[#6A7772] border-[#E0E5E2]" },
  };
  const cfg = map[status || "detected"] || map.detected;
  return (
    <span className={`inline-block px-2.5 py-0.5 text-[11.5px] font-medium rounded-full border whitespace-nowrap ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export function CollapsiblePanel({
  title,
  badge,
  defaultOpen = true,
  children,
}: {
  title: React.ReactNode;
  badge?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="surface-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3.5 flex items-center justify-between gap-2 text-left hover:bg-[#F8FAF9] transition-colors cursor-pointer"
      >
        <span className="text-[13.5px] font-semibold text-[#1D2825] flex items-center gap-2">
          {title}
        </span>
        <div className="flex items-center gap-2">
          {badge}
          <span className="inline-flex items-center gap-1 text-[11.5px] font-medium text-[#6B7974]">
            {open ? "Hide" : "Show"}
            {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </div>
      </button>
      {open && <div className="px-4 pb-4 pt-3 border-t border-[#E6EBE8]">{children}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="surface-card py-12 px-6 text-center">
      <div className="w-10 h-10 rounded-full bg-[#F1F5F3] text-[#6B7B75] flex items-center justify-center mx-auto mb-3">
        <Inbox className="w-5 h-5" />
      </div>
      <div className="text-[15px] font-semibold text-[#1D2825]">{title}</div>
      <p className="text-[13.5px] text-[#62706B] mt-1 max-w-md mx-auto leading-relaxed">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="surface-card p-6 space-y-3.5 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-[#E6EBE8] rounded-md"
          style={{ width: `${i === rows - 1 ? 65 : 100}%` }}
        />
      ))}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="surface-card p-5 border-[#EBC3C3] bg-[#FEF6F6] flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-[#B03E3E] shrink-0 mt-0.5" />
      <div>
        <div className="text-[14px] font-semibold text-[#B03E3E]">Unable to load data</div>
        <p className="text-[13px] text-[#6E5454] mt-0.5">{message}</p>
        {onRetry && (
          <button className="btn-secondary mt-3" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between pt-4 text-[12.5px] text-[#62706B]">
      <div className="tabular-nums">
        Page <span className="font-semibold text-[#1D2825]">{page}</span> of {totalPages} ({total} records)
      </div>
      <div className="flex gap-2">
        <button
          className="btn-secondary"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <button
          className="btn-secondary"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-[#14201C]/35 backdrop-blur-[2px] flex items-center justify-center p-4">
      <div className="surface-card max-w-md w-full p-6 bg-white shadow-xl">
        <h3 className="text-[16px] font-semibold text-[#1D2825]">{title}</h3>
        <p className="text-[13.5px] text-[#62706B] mt-1.5 leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2.5 mt-6">
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function formatMinutes(mins?: number | null): string {
  if (mins === null || mins === undefined) return "—";
  if (Math.abs(mins) < 60) return `${Math.round(mins)}m`;
  const hrs = mins / 60;
  if (Math.abs(hrs) < 24) return `${hrs.toFixed(1)}h`;
  return `${(hrs / 24).toFixed(1)}d`;
}

export function formatShortDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
