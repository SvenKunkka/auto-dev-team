import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { formatDate } from "@/lib/i18n";
import type { TaskRecord } from "@/types/task";

export function TaskTable({ tasks }: { tasks: TaskRecord[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="hidden grid-cols-[1.25fr_2fr_.8fr_.8fr_32px] gap-4 border-b border-slate-200 bg-slate-50/70 px-5 py-3 text-[10px] font-medium uppercase tracking-wider text-slate-500 md:grid">
        <span>项目</span>
        <span>目标</span>
        <span>状态</span>
        <span>更新时间</span>
        <span />
      </div>
      {tasks.length === 0 ? (
        <div className="px-5 py-14 text-center text-sm text-slate-500">
          暂无任务，请创建第一个开发任务。
        </div>
      ) : (
        tasks.map((task) => (
          <Link
            key={task.task_id}
            href={`/tasks/${task.task_id}`}
            className="grid gap-3 border-b border-slate-100 px-5 py-4 transition last:border-0 hover:bg-slate-50 md:grid-cols-[1.25fr_2fr_.8fr_.8fr_32px] md:items-center md:gap-4"
          >
            <div>
              <p className="truncate text-sm font-medium text-slate-900">
                {task.project_name}
              </p>
              <p className="mt-1 truncate font-mono text-[10px] text-slate-400">
                {task.task_id.slice(0, 8)}
              </p>
            </div>
            <p className="truncate text-sm text-slate-400">{task.goal}</p>
            <div>
              <StatusBadge status={task.status} />
            </div>
            <p className="text-xs text-slate-500">
              {formatDate(task.updated_at)}
            </p>
            <ArrowUpRight className="hidden size-4 text-slate-400 md:block" />
          </Link>
        ))
      )}
    </div>
  );
}
