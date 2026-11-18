import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Menu, X } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { BrandMark, UserAvatar } from "../components/BrandMark";

const CUSTOMER_NAV_ITEMS = [
  { to: "/", label: "Home", end: true },
  { to: "/submit-complaint", label: "Submit a Complaint", end: false },
  { to: "/my-complaints", label: "My Complaints", end: false },
  { to: "/help", label: "Help Centre", end: false },
  { to: "/account", label: "Account", end: false },
];

export function CustomerLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleSignOut = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F6F4] text-[#1D2825]">
      <header className="bg-white/95 backdrop-blur-md border-b border-[#E1E6E3] sticky top-0 z-20 shadow-[0_1px_2px_rgba(17,29,25,0.03)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-7 min-w-0">
            <NavLink
              to="/"
              className="shrink-0 focus:outline-none"
              aria-label="QRYVANTA Customer Support Home"
            >
              <BrandMark compact />
            </NavLink>

            <nav
              aria-label="Customer navigation"
              className="hidden md:flex items-center gap-1"
            >
              {CUSTOMER_NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `px-3.5 py-2 rounded-[7px] text-[13.5px] font-medium transition-colors ${
                      isActive
                        ? "bg-[#ECF4F1] text-[#244F43] font-semibold"
                        : "text-[#586662] hover:text-[#1D2825] hover:bg-[#F3F6F4]"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden lg:flex items-center gap-2 pr-1">
                <UserAvatar name={user.name} tone="neutral" />
                <span className="text-[13px] font-medium text-[#465550] truncate max-w-[150px]">
                  {user.name}
                </span>
              </div>
            )}
            <button
              type="button"
              onClick={handleSignOut}
              className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[7px] border border-[#DFE5E2] bg-white text-[13px] font-medium text-[#2C3935] hover:bg-[#F5F7F6] hover:border-[#C7D2CD] transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5 text-[#6B7974]" />
              Sign out
            </button>

            <button
              type="button"
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="md:hidden p-2 rounded-[7px] border border-[#DFE5E2] text-[#1D2825] hover:bg-[#F5F7F6]"
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? (
                <X className="w-4 h-4" />
              ) : (
                <Menu className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-[#E6EBE8] bg-white px-4 py-3 space-y-1 shadow-md">
            {CUSTOMER_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-3.5 py-2.5 rounded-[7px] text-[14px] font-medium ${
                    isActive
                      ? "bg-[#ECF4F1] text-[#244F43] font-semibold"
                      : "text-[#465550] hover:bg-[#F4F6F4]"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <div className="pt-2.5 mt-2 border-t border-[#E6EBE8] flex items-center justify-between px-3.5 py-1.5">
              <div className="flex items-center gap-2 min-w-0">
                <UserAvatar name={user?.name} tone="neutral" />
                <span className="text-[13px] font-medium text-[#52605B] truncate">
                  {user?.name}
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setMobileMenuOpen(false);
                  handleSignOut();
                }}
                className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-[#1D2825] hover:text-[#2F6354]"
              >
                <LogOut className="w-3.5 h-3.5" />
                Sign out
              </button>
            </div>
          </div>
        )}
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-11">
        <Outlet />
      </main>

      <footer className="border-t border-[#E1E6E3] bg-white mt-auto">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-2 text-[12.5px] text-[#6E7C77]">
          <span className="font-medium text-[#4A5954]">QRYVANTA Customer Support</span>
          <div className="flex items-center gap-5">
            <NavLink to="/help" className="hover:text-[#1D2825] transition-colors">
              Help Centre
            </NavLink>
            <NavLink to="/submit-complaint" className="hover:text-[#1D2825] transition-colors">
              Submit a Complaint
            </NavLink>
            <NavLink to="/my-complaints" className="hover:text-[#1D2825] transition-colors">
              My Complaints
            </NavLink>
          </div>
        </div>
      </footer>
    </div>
  );
}
