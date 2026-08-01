import {
  Bot,
  Braces,
  CheckCircle2,
  ClipboardList,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { TaskRecord } from "@/types/task";
import { localizeAgent, taskStatusLabels } from "@/lib/i18n";

const agents = [
  {
    key: "requirement_analyst",
    name: "需求分析师",
    role: "澄清与结构化需求",
    icon: ClipboardList,
    statuses: ["ANALYZING"],
  },
  {
    key: "specialists",
    name: "专业智能体",
    role: "按任务选择的硬件产品角色",
    icon: Users,
    statuses: ["RESEARCHING"],
  },
  {
    key: "supervisor",
    name: "产品交付规划师",
    role: "交付规划与范围决策",
    icon: Bot,
    statuses: ["PLANNING", "REWORKING"],
  },
  {
    key: "developer",
    name: "软件实现工程师",
    role: "代码实现与测试",
    icon: Braces,
    statuses: ["DEVELOPING"],
  },
  {
    key: "verification_engineer",
    name: "Kimi 验证工程师",
    role: "独立运行测试",
    icon: ShieldCheck,
    statuses: ["VERIFYING"],
  },
  {
    key: "reviewer",
    name: "产品质量验收经理",
    role: "质量门禁与交付验收",
    icon: CheckCircle2,
    statuses: ["REVIEWING"],
  },
];

export function AgentPipeline({ tasks }: { tasks: TaskRecord[] }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">智能体状态</h2>
          <p className="mt-1 text-xs text-slate-500">
            实时查看执行流水线中的职责分配
          </p>
        </div>
        <span className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-emerald-700">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          已连接
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        {agents.map((agent, index) => {
          const active = tasks.find((task) =>
            agent.statuses.includes(task.status),
          );
          const Icon = agent.icon;
          return (
            <div
              key={agent.key}
              className="relative rounded-lg border border-slate-200 bg-slate-50/70 p-4"
            >
              {index < agents.length - 1 && (
                <span className="absolute -right-2.5 top-8 hidden h-px w-5 bg-slate-200 xl:block" />
              )}
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white shadow-sm">
                  <Icon className="size-4 text-slate-600" />
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {agent.key === "specialists" && active?.active_agent
                        ? localizeAgent(active.active_agent)
                        : agent.name}
                    </p>
                    <span
                      className={`size-1.5 rounded-full ${
                        active ? "bg-blue-500" : "bg-slate-300"
                      }`}
                    />
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{agent.role}</p>
                </div>
              </div>
              <p className="mt-4 truncate text-[10px] font-medium uppercase tracking-wide text-slate-500">
                {active ? `${active.project_name} · ${taskStatusLabels[active.status]}` : "空闲"}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
