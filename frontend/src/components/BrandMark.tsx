import React from "react";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <span className="w-7 h-7 rounded-[7px] bg-[#2F6354] text-white flex items-center justify-center shadow-[0_1px_3px_rgba(24,54,45,0.22)] shrink-0">
        <svg
          width="15"
          height="15"
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="9.2"
            cy="9.2"
            r="5.6"
            stroke="currentColor"
            strokeWidth="2.1"
          />
          <path
            d="M13.2 13.2L17 17"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <circle cx="9.2" cy="9.2" r="1.7" fill="#A8D1C3" />
        </svg>
      </span>
      <span
        className={`font-semibold tracking-tight text-[#1D2825] ${
          compact ? "text-[14.5px]" : "text-[15.5px]"
        }`}
        style={{ fontFamily: '"Plus Jakarta Sans", "Inter", sans-serif' }}
      >
        QRYVANTA
      </span>
    </span>
  );
}

export function UserAvatar({
  name,
  tone = "sage",
  size = "sm",
}: {
  name?: string | null;
  tone?: "sage" | "neutral";
  size?: "sm" | "md";
}) {
  const initials = (name || "U")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");

  const sizeClass =
    size === "md" ? "w-10 h-10 text-[13.5px]" : "w-7 h-7 text-[11px]";
  const toneClass =
    tone === "sage"
      ? "bg-[#ECF4F1] text-[#244F43] border border-[#CFE0D9]"
      : "bg-[#F1F4F2] text-[#45534F] border border-[#DCE3DF]";

  return (
    <span
      aria-hidden="true"
      className={`rounded-full inline-flex items-center justify-center font-semibold shrink-0 ${sizeClass} ${toneClass}`}
    >
      {initials || "U"}
    </span>
  );
}
