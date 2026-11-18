import type { CategoryItem } from "../types";

export interface CustomerStatusInfo {
  label: string;
  shortDescription: string;
  needsCustomerAction: boolean;
  badgeClass: string;
  stepIndex: number; // 0: Submitted, 1: Under review, 2: Being resolved, 3: Resolved
}

export const PROGRESS_STEPS = [
  { key: "submitted", label: "Complaint submitted" },
  { key: "under_review", label: "Under review" },
  { key: "being_resolved", label: "Being resolved" },
  { key: "resolved", label: "Resolved" },
] as const;

export function getCustomerStatusInfo(
  internalStatus: string,
  hasAssignedSupport?: boolean
): CustomerStatusInfo {
  switch (internalStatus) {
    case "new":
      return {
        label: "Received",
        shortDescription:
          "We have received your complaint and will review the details shortly.",
        needsCustomerAction: false,
        badgeClass: "bg-[#F3F5F4] text-[#42524D] border-[#DCE2DF]",
        stepIndex: 0,
      };
    case "open":
      if (hasAssignedSupport) {
        return {
          label: "Being reviewed",
          shortDescription:
            "A member of our support team is reviewing your complaint and checking the details.",
          needsCustomerAction: false,
          badgeClass: "bg-[#EFF5F3] text-[#2D5549] border-[#CFE0DA]",
          stepIndex: 1,
        };
      }
      return {
        label: "Received",
        shortDescription:
          "Your complaint is in our queue and will be reviewed by our support team soon.",
        needsCustomerAction: false,
        badgeClass: "bg-[#F3F5F4] text-[#42524D] border-[#DCE2DF]",
        stepIndex: 0,
      };
    case "in_progress":
    case "reopened":
      return {
        label: "In progress",
        shortDescription:
          "Our support team is actively working to resolve your complaint and will share updates here.",
        needsCustomerAction: false,
        badgeClass: "bg-[#EFF5F3] text-[#2D5549] border-[#CFE0DA]",
        stepIndex: 2,
      };
    case "awaiting_customer":
      return {
        label: "Waiting for your response",
        shortDescription:
          "Our support team sent a message and needs a reply from you before we can continue.",
        needsCustomerAction: true,
        badgeClass: "bg-[#FDF6EC] text-[#8F6324] border-[#EBD5B3]",
        stepIndex: 2,
      };
    case "resolved":
      return {
        label: "Resolved",
        shortDescription:
          "This complaint has been marked as resolved. If anything is still unresolved, you can reopen it below.",
        needsCustomerAction: false,
        badgeClass: "bg-[#EDF5F1] text-[#2A5D4B] border-[#C5DDD2]",
        stepIndex: 3,
      };
    case "closed":
      return {
        label: "Closed",
        shortDescription:
          "This complaint is closed. If the same problem comes back, you can reopen it or submit a new complaint.",
        needsCustomerAction: false,
        badgeClass: "bg-[#F3F5F4] text-[#5D6864] border-[#DCE2DF]",
        stepIndex: 3,
      };
    default:
      return {
        label: "Being reviewed",
        shortDescription:
          "Our support team is reviewing your complaint.",
        needsCustomerAction: false,
        badgeClass: "bg-[#F3F5F4] text-[#42524D] border-[#DCE2DF]",
        stepIndex: 1,
      };
  }
}

export function formatShortDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export interface CustomerIssueOption {
  id: string;
  label: string;
  hint: string;
  showOrderField: boolean;
  categoryKeywords: string[];
}

export const CUSTOMER_ISSUE_OPTIONS: CustomerIssueOption[] = [
  {
    id: "payment",
    label: "Payment",
    hint: "Charges, failed payments, or invoices",
    showOrderField: true,
    categoryKeywords: ["billing", "payment", "invoice", "charge"],
  },
  {
    id: "orders",
    label: "Orders",
    hint: "Missing items, wrong item, or order changes",
    showOrderField: true,
    categoryKeywords: ["order", "fulfillment", "logistics", "delivery", "shipping"],
  },
  {
    id: "refund",
    label: "Refund",
    hint: "Pending return refund or reimbursement",
    showOrderField: true,
    categoryKeywords: ["refund", "billing", "payment", "return"],
  },
  {
    id: "delivery",
    label: "Delivery",
    hint: "Delayed parcel, tracking, or damaged package",
    showOrderField: true,
    categoryKeywords: ["delivery", "shipping", "logistics", "fulfillment"],
  },
  {
    id: "account",
    label: "Account or Login",
    hint: "Sign-in issues, password, or profile access",
    showOrderField: false,
    categoryKeywords: ["account", "access", "login", "auth", "security"],
  },
  {
    id: "product",
    label: "Product or Service",
    hint: "Defective item, feature issue, or technical trouble",
    showOrderField: true,
    categoryKeywords: ["technical", "product", "service", "bug", "hardware", "software"],
  },
  {
    id: "other",
    label: "Other",
    hint: "Anything else we can help with",
    showOrderField: false,
    categoryKeywords: ["general", "other", "inquiry"],
  },
];

export function matchBackendCategoryId(
  issueId: string,
  categories: CategoryItem[]
): number | null {
  const option = CUSTOMER_ISSUE_OPTIONS.find((item) => item.id === issueId);
  if (!option || !categories.length) return null;

  for (const kw of option.categoryKeywords) {
    const match = categories.find(
      (c) =>
        c.is_active &&
        (c.name.toLowerCase().includes(kw) ||
          (c.description || "").toLowerCase().includes(kw))
    );
    if (match) return match.id;
  }
  return null;
}

export interface HelpCategoryOption {
  id: string;
  label: string;
  description: string;
  keywords: string[];
}

export const HELP_CATEGORIES: HelpCategoryOption[] = [
  {
    id: "all",
    label: "All topics",
    description: "Browse all help articles",
    keywords: [],
  },
  {
    id: "payments",
    label: "Payments",
    description: "Billing, charges, and payment methods",
    keywords: ["payment", "billing", "invoice", "charge", "card", "subscription", "duplicate"],
  },
  {
    id: "orders",
    label: "Orders",
    description: "Order changes, cancellations, and items",
    keywords: ["order", "purchase", "item", "cancel", "checkout", "return"],
  },
  {
    id: "refunds",
    label: "Refunds",
    description: "Return timelines and refund status",
    keywords: ["refund", "reimburse", "credit", "return", "chargeback"],
  },
  {
    id: "delivery",
    label: "Delivery",
    description: "Shipping updates, delays, and damaged parcels",
    keywords: ["delivery", "shipping", "parcel", "package", "courier", "logistics", "damaged", "tracking"],
  },
  {
    id: "account",
    label: "Account access",
    description: "Sign-in help, passwords, and verification",
    keywords: ["account", "login", "password", "sign in", "2fa", "mfa", "access", "reset", "locked"],
  },
  {
    id: "general",
    label: "General support",
    description: "How support works and common questions",
    keywords: ["general", "support", "contact", "technical", "service", "app", "error", "outage", "privacy"],
  },
];

export interface KnowledgeArticleItem {
  id: number;
  title: string;
  content: string;
  category_id?: number | null;
  category_name?: string | null;
  tags?: string | null;
  is_published: boolean;
  updated_at?: string | null;
}

export function articleMatchesHelpCategory(
  article: KnowledgeArticleItem,
  helpCategoryId: string
): boolean {
  if (helpCategoryId === "all") return true;
  const cat = HELP_CATEGORIES.find((c) => c.id === helpCategoryId);
  if (!cat || cat.keywords.length === 0) return true;
  const haystack = `${article.title} ${article.category_name || ""} ${article.tags || ""} ${article.content}`.toLowerCase();
  return cat.keywords.some((kw) => haystack.includes(kw));
}
