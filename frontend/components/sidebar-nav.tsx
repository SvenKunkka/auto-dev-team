"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  ChartNoAxesColumnIncreasing,
  FileClock,
  LayoutDashboard,
  ListTodo,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "总览", icon: LayoutDashboard, exact: true },
  { href: "/missions", label: "任务", icon: ListTodo },
  { href: "/agents", label: "智能体", icon: Bot },
  {
    href: "/statistics",
    label: "统计部门",
    icon: ChartNoAxesColumnIncreasing,
  },
  { href: "/logs", label: "日志", icon: FileClock },
  { href: "/settings", label: "设置", icon: Settings },
];

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="mt-8 space-y-1">
      {navigation.map(({ href, label, icon: Icon, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
              active
                ? "bg-slate-200/70 font-medium text-slate-900"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
