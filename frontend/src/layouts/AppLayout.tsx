import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Plus } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { BrandMark, UserAvatar } from "../components/BrandMark";

interface NavItem {
  label: string;
  to: string;
  roles: string[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", to: "/", roles: ["agent", "manager", "admin"] },
  { label: "Tickets", to: "/tickets", roles: ["customer", "agent", "manager", "admin"] },
  { label: "Submit Ticket", to: "/submit", roles: ["customer", "agent", "manager", "admin"] },
  { label: "Incidents", to: "/incidents", roles: ["agent", "manager", "admin"] },
  { label: "Operations", to: "/operations", roles: ["agent", "manager", "admin"] },
  { label: "Portals", to: "/portals", roles: ["agent", "manager", "admin"] },
  { label: "Intelligence", to: "/intelligence", roles: ["agent", "manager", "admin"] },
  { label: "Analytics", to: "/analytics", roles: ["agent", "manager", "admin"] },
  { label: "Settings", to: "/settings", roles: ["customer", "agent", "manager", "admin"] },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  const visibleNav = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F6F4]">
      <header className="bg-white/95 backdrop-blur-md border-b border-[#E1E6E3] sticky top-0 z-30 shadow-[0_1px_2px_rgba(17,29,25,0.03)]">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6">
          <div className="h-15 flex items-center justify-between gap-4">
            <div className="flex items-center gap-6 min-w-0">
              <NavLink
                to={user.role === "customer" ? "/tickets" : "/"}
                className="shrink-0 focus:outline-none"
              >
                <BrandMark compact />
              </NavLink>

              <nav aria-label="Primary navigation" className="hidden lg:flex items-center gap-0.5">
                {visibleNav.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `px-3 py-1.5 text-[13px] rounded-[7px] transition-colors ${
                        isActive
                          ? "text-[#244F43] font-semibold bg-[#ECF4F1]"
                          : "text-[#5D6B66] hover:text-[#1D2825] hover:bg-[#F3F6F4]"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <button
                onClick={() => navigate("/submit")}
                className="btn-primary hidden sm:inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                New ticket
              </button>

              <div className="hidden md:flex items-center gap-2.5 pl-3 border-l border-[#E1E6E3]">
                <UserAvatar name={user.name} tone="sage" />
                <div className="leading-tight">
                  <div className="text-[12.5px] font-semibold text-[#1D2825]">{user.name}</div>
                  <div className="text-[11px] text-[#6B7974] capitalize">{user.role}</div>
                </div>
              </div>

              <button
                onClick={handleLogout}
                title="Sign out"
                className="btn-secondary inline-flex items-center gap-1.5"
              >
                <LogOut className="w-3.5 h-3.5 text-[#62706B]" />
                <span className="hidden sm:inline">Sign out</span>
              </button>
            </div>
          </div>

          {/* Mobile / tablet horizontal nav bar */}
          <nav
            aria-label="Mobile navigation"
            className="flex lg:hidden items-center gap-1 overflow-x-auto py-2 border-t border-[#E6EBE8]"
          >
            {visibleNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `px-2.5 py-1 text-[12.5px] rounded-[6px] whitespace-nowrap ${
                    isActive
                      ? "text-[#244F43] font-semibold bg-[#ECF4F1]"
                      : "text-[#62706B] hover:text-[#1D2825]"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-7">
        <Outlet />
      </main>

      <footer className="border-t border-[#E1E6E3] bg-white py-3.5 px-6 text-[11.5px] text-[#6E7C77]">
        <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row justify-between gap-2">
          <span>QRYVANTA — Intelligent Customer Support Operations &amp; Ticket Resolution Platform</span>
          <span>Classification and urgency outputs are decision-support recommendations requiring staff review where appropriate.</span>
        </div>
      </footer>
    </div>
  );
}
