import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Eye,
  EyeOff,
  ArrowRight,
  ChevronDown,
  ShieldCheck,
  UserCircle2,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { BrandMark } from "../components/BrandMark";

const DEMO_ACCOUNTS = [
  {
    group: "Customer Portal",
    items: [{ role: "Customer", email: "customer@qryvanta.local" }],
  },
  {
    group: "Staff Operations Workspace",
    items: [
      { role: "Administrator", email: "admin@qryvanta.local" },
      { role: "Support Manager", email: "manager@qryvanta.local" },
      { role: "Billing Agent", email: "billing.agent@qryvanta.local" },
      { role: "Technical Agent", email: "tech.agent@qryvanta.local" },
      { role: "Logistics Agent", email: "logistics.agent@qryvanta.local" },
    ],
  },
];

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [contact, setContact] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [demoMenuOpen, setDemoMenuOpen] = useState(false);

  const emailWrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (
        emailWrapperRef.current &&
        !emailWrapperRef.current.contains(e.target as Node)
      ) {
        setDemoMenuOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDemoMenuOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await (mode === "login"
        ? login(email, password)
        : register(name, email, password, contact || undefined));
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to authenticate. Check backend connection."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const selectDemoAccount = (demoEmail: string) => {
    setMode("login");
    setEmail(demoEmail);
    setPassword("DemoUser#2026");
    setError(null);
    setDemoMenuOpen(false);
  };

  const normalizedQuery = email.trim().toLowerCase();
  const filteredGroups = DEMO_ACCOUNTS.map((grp) => ({
    ...grp,
    items: grp.items.filter(
      (acc) =>
        !normalizedQuery ||
        acc.email.toLowerCase().includes(normalizedQuery) ||
        acc.role.toLowerCase().includes(normalizedQuery)
    ),
  })).filter((grp) => grp.items.length > 0);

  return (
    <div
      className="min-h-screen flex flex-col justify-center items-center py-10 px-4"
      style={{
        background:
          "radial-gradient(circle at 18% 14%, rgba(47, 99, 84, 0.08) 0%, transparent 45%), radial-gradient(circle at 82% 84%, rgba(47, 99, 84, 0.06) 0%, transparent 45%), #F4F6F4",
      }}
    >
      <div className="w-full max-w-[440px]">
        <div className="surface-card p-7 sm:p-8">
          <div className="mb-5">
            <BrandMark />
          </div>

          <h1 className="text-[23px] font-bold text-[#1D2825] tracking-tight">
            {mode === "login" ? "Sign in to workspace" : "Create customer account"}
          </h1>
          <p className="text-[13.5px] text-[#62706B] mt-1">
            Understand every request. Route it right. Resolve it better.
          </p>

          {/* Segmented Mode Switcher */}
          <div className="mt-6 p-1 bg-[#F2F5F3] rounded-[8px] grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`py-2 px-3 rounded-[6px] text-[13px] font-medium transition-all cursor-pointer ${
                mode === "login"
                  ? "bg-white text-[#1D2825] shadow-xs font-semibold"
                  : "text-[#62706B] hover:text-[#1D2825]"
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setDemoMenuOpen(false);
                setError(null);
              }}
              className={`py-2 px-3 rounded-[6px] text-[13px] font-medium transition-all cursor-pointer ${
                mode === "register"
                  ? "bg-white text-[#1D2825] shadow-xs font-semibold"
                  : "text-[#62706B] hover:text-[#1D2825]"
              }`}
            >
              Customer registration
            </button>
          </div>

          {error && (
            <div
              role="alert"
              className="mt-4 px-3.5 py-2.5 rounded-[7px] border border-[#ECC5C5] bg-[#FEF5F5] text-[#B03E3E] text-[13px]"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-[13px] font-medium text-[#1D2825] mb-1.5">
                  Full name
                </label>
                <input
                  type="text"
                  required
                  minLength={2}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Morgan"
                  className="field-input py-2.5"
                />
              </div>
            )}

            <div ref={emailWrapperRef} className="relative">
              <label
                htmlFor="login-email"
                className="block text-[13px] font-medium text-[#1D2825] mb-1.5"
              >
                Email address
              </label>
              <div className="relative">
                <input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onFocus={() => {
                    if (mode === "login") setDemoMenuOpen(true);
                  }}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (mode === "login") setDemoMenuOpen(true);
                  }}
                  placeholder="name@company.com"
                  className={`field-input py-2.5 ${mode === "login" ? "pr-10" : ""}`}
                />
                {mode === "login" && (
                  <button
                    type="button"
                    onClick={() => setDemoMenuOpen((v) => !v)}
                    aria-label="Choose demo account"
                    aria-expanded={demoMenuOpen}
                    title="Choose demo account"
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-[#6E7C77] hover:text-[#1D2825] hover:bg-[#F2F5F3] transition-colors cursor-pointer"
                  >
                    <ChevronDown
                      className={`w-4 h-4 transition-transform ${
                        demoMenuOpen ? "rotate-180" : ""
                      }`}
                    />
                  </button>
                )}
              </div>

              {mode === "login" && demoMenuOpen && filteredGroups.length > 0 && (
                <div
                  role="listbox"
                  aria-label="Demo accounts"
                  className="absolute left-0 right-0 mt-1.5 z-30 bg-white border border-[#DCE4E0] rounded-[10px] shadow-[0_10px_28px_-6px_rgba(17,29,25,0.16)] overflow-hidden py-1.5 max-h-72 overflow-y-auto"
                >
                  {filteredGroups.map((grp, gIdx) => (
                    <div
                      key={grp.group}
                      className={gIdx > 0 ? "mt-1 pt-1.5 border-t border-[#E6EBE8]" : ""}
                    >
                      <div className="px-3 py-1 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-[#72817C]">
                        {grp.group === "Customer Portal" ? (
                          <UserCircle2 className="w-3.5 h-3.5 text-[#2F6354]" />
                        ) : (
                          <ShieldCheck className="w-3.5 h-3.5 text-[#62706B]" />
                        )}
                        {grp.group}
                      </div>
                      {grp.items.map((acc) => (
                        <button
                          key={acc.email}
                          type="button"
                          role="option"
                          aria-selected={email === acc.email}
                          onMouseDown={(e) => {
                            e.preventDefault();
                            selectDemoAccount(acc.email);
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-[#ECF4F1] flex items-center justify-between gap-2 transition-colors cursor-pointer"
                        >
                          <div className="min-w-0">
                            <div className="text-[13px] font-medium text-[#1D2825] truncate">
                              {acc.role}
                            </div>
                            <div className="text-[11.5px] text-[#62706B] truncate">
                              {acc.email}
                            </div>
                          </div>
                          <span className="text-[11px] font-medium text-[#2F6354] shrink-0">
                            Autofill
                          </span>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label
                htmlFor="login-password"
                className="block text-[13px] font-medium text-[#1D2825] mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="field-input py-2.5 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-[#7D8B86] hover:text-[#1D2825] cursor-pointer"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {mode === "register" && (
              <div>
                <label className="block text-[13px] font-medium text-[#1D2825] mb-1.5">
                  Contact / organization{" "}
                  <span className="font-normal text-[#7D8B86]">(optional)</span>
                </label>
                <input
                  type="text"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder="Phone number or company reference"
                  className="field-input py-2.5"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full py-2.5 text-[14px] inline-flex items-center justify-center gap-2 mt-1"
            >
              <span>
                {submitting
                  ? "Authenticating..."
                  : mode === "login"
                  ? "Sign in"
                  : "Create account"}
              </span>
              {!submitting && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
