import Link from "next/link";
import {
  Activity,
  AlertOctagon,
  ListChecks,
  PlayCircle,
  Plus,
} from "lucide-react";
import { AgentPipeline } from "@/components/agent-pipeline";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { TaskTable } from "@/components/task-table";
import { TaskPipeline } from "@/components/task-pipeline";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { localizeValue } from "@/lib/i18n";
import type { Health, TaskRecord } from "@/types/task";

export const dynamic = "force-dynamic";

const runningStates = new Set([
  "RUNNING",
  "ANALYZING",
  "RESEARCHING",
  "PLANNING",
  "DEVELOPING",
  "VERIFYING",
  "REVIEWING",
  "REWORKING",
]);

export default async function DashboardPage() {
  let health: Health | null = null;
  let tasks: TaskRecord[] = [];
  let error = "";
  try {
    [health, tasks] = await Promise.all([api.health(), api.tasks()]);
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "后端服务不可用";
  }
  const running = tasks.filter((task) => runningStates.has(task.status));
  const queued = tasks.filter((task) =>
    ["QUEUED", "WAITING_DEPENDENCY"].includes(task.status),
  );
  const blocked = tasks.filter((task) =>
    ["BLOCKED", "REQUIREMENTS_REVISION"].includes(task.status),
  );

  return (
    <>
      <PageHeader
        eyebrow="系统总览"
        title="AI 开发控制中心"
        description="监控 AI 团队、跟踪开发任务，并在需要人工判断时及时介入。"
        action={
          <Link
            href="/tasks/new"
            className={cn(
              buttonVariants(),
              "bg-slate-900 text-white hover:bg-slate-800",
            )}
          >
            <Plus className="size-4" />
            新建任务
          </Link>
        }
      />
      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          FastAPI 连接失败：{error}
        </div>
      )}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="运行中任务"
          value={running.length}
          note="正在智能体流水线中执行"
          icon={PlayCircle}
          accent="text-emerald-700"
        />
        <MetricCard
          label="排队中任务"
          value={health?.queue_size ?? queued.length}
          note="等待本地 Worker 处理"
          icon={ListChecks}
          accent="text-blue-700"
        />
        <MetricCard
          label="阻塞任务"
          value={blocked.length}
          note="需要人工处理"
          icon={AlertOctagon}
          accent="text-red-700"
        />
        <MetricCard
          label="平台健康状态"
          value={health?.status === "healthy" ? "正常" : "异常"}
          note={`数据库 ${localizeValue(health?.database)} · Worker ${localizeValue(health?.worker)}`}
          icon={Activity}
          accent={
            health?.status === "healthy"
              ? "text-emerald-700"
              : "text-amber-700"
          }
        />
      </section>
      <div className="mt-6">
        <AgentPipeline tasks={tasks} />
      </div>
      <div className="mt-6">
        <TaskPipeline />
      </div>
      <section id="missions" className="mt-6 scroll-mt-6">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-sm font-semibold">最近任务</h2>
            <p className="mt-1 text-xs text-slate-500">
              所有工作区的最新活动
            </p>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">
            共 {tasks.length} 项
          </span>
        </div>
        <TaskTable tasks={tasks.slice(0, 8)} />
      </section>
    </>
  );
}
