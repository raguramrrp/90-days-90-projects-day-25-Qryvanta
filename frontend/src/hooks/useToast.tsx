import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, Info } from "lucide-react";

interface ToastItem {
  id: number;
  type: "success" | "error" | "info";
  message: string;
}

interface ToastContextValue {
  notify: (message: string, type?: "success" | "error" | "info") => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const notify = useCallback((message: string, type: "success" | "error" | "info" = "info") => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`px-4 py-3 rounded-[9px] border border-l-[3.5px] text-[13px] font-medium shadow-lg bg-white flex items-start gap-2.5 ${
              t.type === "error"
                ? "border-[#EBC3C3] border-l-[#C44D4D] text-[#A23535]"
                : t.type === "success"
                ? "border-[#CBE0D7] border-l-[#2F6354] text-[#1D2825]"
                : "border-[#DCE3DF] border-l-[#62706B] text-[#1D2825]"
            }`}
          >
            {t.type === "error" ? (
              <AlertCircle className="w-4 h-4 text-[#C44D4D] shrink-0 mt-0.5" />
            ) : t.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-[#2F6354] shrink-0 mt-0.5" />
            ) : (
              <Info className="w-4 h-4 text-[#62706B] shrink-0 mt-0.5" />
            )}
            <span className="leading-snug">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
