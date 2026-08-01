import Link from "next/link";
import { Braces, CircleHelp, Search } from "lucide-react";
import { SidebarNav } from "@/components/sidebar-nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#20242c]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 border-r border-slate-200 bg-[#fbfbfc] px-3 py-5 md:block">
        <Link href="/" className="flex items-center gap-3 px-2">
          <span className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white text-slate-700 shadow-sm">
            <Braces className="size-4" />
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-tight">
              Auto Dev 平台
            </span>
            <span className="block text-[10px] text-slate-500">
              AI 开发工作台
            </span>
          </span>
        </Link>
        <SidebarNav />
        <div className="absolute inset-x-3 bottom-4 space-y-1 border-t border-slate-200 pt-3">
          <div className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-slate-500">
            <CircleHelp className="size-4" />
            内部工作区
          </div>
          <p className="px-3 text-[10px] text-slate-400">
            v1.6 · Mac 本地运行环境
          </p>
        </div>
      </aside>
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:hidden">
        <Link href="/" className="text-sm font-semibold">
          Auto Dev 平台
        </Link>
        <Link
          href="/missions"
          aria-label="浏览任务"
          className="rounded-md border border-slate-200 p-2 text-slate-500"
        >
          <Search className="size-4" />
        </Link>
      </header>
      <main className="min-h-screen md:pl-60">
        <div className="mx-auto max-w-[1480px] px-4 py-7 sm:px-7 lg:px-10">
          {children}
        </div>
      </main>
    </div>
  );
}
