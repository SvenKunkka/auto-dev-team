import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { taskStatusLabels } from "@/lib/i18n";
import type { TaskStatus } from "@/types/task";

const styles: Record<TaskStatus, string> = {
  CREATED: "border-slate-200 bg-slate-50 text-slate-600",
  QUEUED: "border-blue-200 bg-blue-50 text-blue-700",
  WAITING_DEPENDENCY: "border-amber-200 bg-amber-50 text-amber-700",
  RUNNING: "border-blue-200 bg-blue-50 text-blue-700",
  ANALYZING: "border-violet-200 bg-violet-50 text-violet-700",
  RESEARCHING: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
  PLANNING: "border-blue-200 bg-blue-50 text-blue-700",
  REQUIREMENTS_REVISION: "border-violet-200 bg-violet-50 text-violet-700",
  DEVELOPING: "border-blue-200 bg-blue-50 text-blue-700",
  VERIFYING: "border-cyan-200 bg-cyan-50 text-cyan-700",
  REVIEWING: "border-blue-200 bg-blue-50 text-blue-700",
  REWORKING: "border-amber-200 bg-amber-50 text-amber-700",
  PAUSED: "border-amber-200 bg-amber-50 text-amber-700",
  CANCELED: "border-slate-200 bg-slate-50 text-slate-500",
  PASSED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  FAILED: "border-red-200 bg-red-50 text-red-700",
  BLOCKED: "border-red-200 bg-red-50 text-red-700",
};

export function StatusBadge({
  status,
  className,
}: {
  status: TaskStatus;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-md px-2 py-0.5 text-[10px] font-semibold tracking-wide",
        styles[status],
        className,
      )}
    >
      {taskStatusLabels[status]}
    </Badge>
  );
}
