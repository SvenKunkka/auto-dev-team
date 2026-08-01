import type { Metadata } from "next";
import Link from "next/link";
import {
  Bot,
  Braces,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  ShieldCheck,
  Sigma,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import type {
  AgentExecutionStatistics,
  DepartmentStatistics,
  TaskRecord,
} from "@/types/task";

export const metadata: Metadata = { title: "统计部门" };
export const dynamic = "force-dynamic";

const rolePresentation: Record<
  string,
  {
    description: string;
    icon: typeof Bot;
    color: string;
  }
> = {
  requirement_analyst: {
    description: "需求澄清与结构化规格输出",
    icon: ClipboardList,
    color: "bg-fuchsia-50 text-fuchsia-700",
  },
  supervisor: {
    description: "Claude 任务规划、验收标准和返工决策",
    icon: Bot,
    color: "bg-violet-50 text-violet-700",
  },
  developer: {
    description: "Codex 代码开发与测试执行",
    icon: Braces,
    color: "bg-blue-50 text-blue-700",
  },
  verification_engineer: {
    description: "Kimi K3 独立测试分析与开发证据核验",
    icon: ShieldCheck,
    color: "bg-cyan-50 text-cyan-700",
  },
  reviewer: {
    description: "DeepSeek 独立代码验收",
    icon: CheckCircle2,
    color: "bg-emerald-50 text-emerald-700",
  },
};

function RoleCard({ role }: { role: AgentExecutionStatistics }) {
  const presentation = rolePresentation[role.agent_name] ?? {
    description: "预置专业智能体角色",
    icon: Bot,
    color: "bg-slate-100 text-slate-700",
  };
  const Icon = presentation.icon;
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <span
          className={`grid size-10 place-items-center rounded-lg ${presentation.color}`}
        >
          <Icon className="size-5" />
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
          {role.agent_name}
        </span>
      </div>
      <h2 className="mt-4 text-base font-semibold text-slate-950">
        {role.role_name}
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        {presentation.description}
      </p>
      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4">
        <div className="rounded-lg bg-slate-50 p-3">
          <p className="text-[11px] text-slate-500">单个目标次数</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
            {role.goal_execution_count}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <p className="text-[11px] text-slate-500">累计执行次数</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
            {role.cumulative_execution_count}
          </p>
        </div>
      </div>
    </article>
  );
}

export default async function StatisticsPage({
  searchParams,
}: {
  searchParams: Promise<{ task_id?: string }>;
}) {
  const params = await searchParams;
  let tasks: TaskRecord[] = [];
  let statistics: DepartmentStatistics | null = null;
  let error = "";

  try {
    tasks = await api.tasks();
    const selectedTaskId =
      params.task_id && tasks.some((task) => task.task_id === params.task_id)
        ? params.task_id
        : tasks[0]?.task_id;
    statistics = await api.departmentStatistics(selectedTaskId);
  } catch {
    error = "暂时无法加载执行统计，请确认后端服务正常。";
  }

  return (
    <>
      <PageHeader
        eyebrow="运营与度量"
        title="任务统计部"
        description="按角色统计每个目标中的调用次数，以及平台运行以来的累计执行次数。"
      />

      <section className="mb-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <Sigma className="size-4 shrink-0 text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-900">
              统计目标
            </h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            每条 Agent Run 记为一次执行；自动返工会产生新的执行次数。
          </p>
        </div>
        {tasks.length > 0 ? (
          <form className="mt-5 grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
              <div className="relative min-w-0 overflow-hidden">
                <select
                  name="task_id"
                  defaultValue={statistics?.selected_goal?.task_id}
                  className="h-10 w-full max-w-full appearance-none truncate rounded-md border border-slate-200 bg-white py-1 pl-3 pr-9 text-sm text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                >
                  {tasks.map((task) => (
                    <option key={task.task_id} value={task.task_id}>
                      {task.project_name} · {task.goal || "文档需求目标"}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-2.5 size-4 text-slate-400" />
              </div>
              <button
                type="submit"
                className="h-10 w-full rounded-md bg-slate-900 px-5 text-sm font-medium text-white hover:bg-slate-800 sm:w-auto"
              >
                查看
              </button>
            </form>
        ) : null}
        {statistics?.selected_goal ? (
          <div className="mt-4 border-t border-slate-100 pt-4 text-sm text-slate-600">
            当前目标：
            <Link
              href={`/tasks/${statistics.selected_goal.task_id}`}
              className="ml-1 break-words font-medium text-blue-700 [overflow-wrap:anywhere] hover:underline"
            >
              {statistics.selected_goal.project_name} ·{" "}
              {statistics.selected_goal.goal || "文档需求目标"}
            </Link>
          </div>
        ) : null}
      </section>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : statistics ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {statistics.roles.map((role) => (
            <RoleCard key={role.agent_name} role={role} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500 shadow-sm">
          暂无任务。创建并运行任务后，这里会显示角色执行次数。
        </div>
      )}
    </>
  );
}
