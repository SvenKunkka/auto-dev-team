import { cn } from "@/lib/utils";
import { formatDate, localizeAgent, localizeEvent } from "@/lib/i18n";
import type { ExecutionLog } from "@/types/task";

export function LogList({
  logs,
  compact = false,
}: {
  logs: ExecutionLog[];
  compact?: boolean;
}) {
  if (!logs.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-10 text-center text-sm text-slate-500">
        暂无执行事件。
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {logs.map((log) => (
        <div
          key={log.id}
          className={cn(
            "grid gap-2 border-b border-slate-100 px-4 py-3 last:border-0 md:grid-cols-[140px_150px_1fr_160px] md:items-center",
            compact && "md:grid-cols-[130px_1fr_140px]",
          )}
        >
          <span
            className={cn(
              "font-mono text-[10px] font-semibold tracking-wide",
              log.level === "ERROR" ? "text-red-600" : "text-blue-600",
            )}
          >
            {localizeEvent(log.event_type)}
          </span>
          {!compact && (
            <span className="font-mono text-[10px] uppercase text-slate-600">
              {localizeAgent(log.agent_name)}
            </span>
          )}
          <p className="text-xs leading-5 text-slate-600">{log.message}</p>
          <time className="font-mono text-[10px] text-slate-600">
            {formatDate(log.created_at)}
          </time>
        </div>
      ))}
    </div>
  );
}
