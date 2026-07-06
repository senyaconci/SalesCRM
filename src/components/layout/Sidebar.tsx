"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  roles: string[];
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", roles: ["ADMIN", "MANAGER"] },
  { href: "/my-projects", label: "My Projects", roles: ["SDR"] },
  { href: "/projects", label: "All Projects", roles: ["ADMIN", "MANAGER"] },
  { href: "/projects/new", label: "New Project", roles: ["ADMIN", "MANAGER"] },
  {
    href: "/vendor-customers",
    label: "Vendor Customers",
    roles: ["ADMIN", "MANAGER"],
  },
  {
    href: "/owner-organizations",
    label: "Owner Orgs",
    roles: ["ADMIN", "MANAGER"],
  },
  { href: "/work-sessions", label: "Work Sessions", roles: ["ADMIN", "MANAGER", "SDR"] },
  { href: "/users", label: "Users", roles: ["ADMIN"] },
];

export function Sidebar({ role }: { role: string }) {
  const pathname = usePathname();
  const items = NAV.filter((i) => i.roles.includes(role));

  return (
    <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-white md:block">
      <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          CS
        </div>
        <span className="text-sm font-semibold text-slate-900">
          CapEx Signal
        </span>
      </div>
      <nav className="space-y-0.5 p-3">
        {items.map((item) => {
          const active =
            item.href === "/projects"
              ? pathname === "/projects"
              : pathname === item.href ||
                (item.href !== "/dashboard" &&
                  item.href !== "/projects" &&
                  pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
