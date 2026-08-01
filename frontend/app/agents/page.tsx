import type { Metadata } from "next";
import { Bot, Circle } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { taskStatusLabels } from "@/lib/i18n";
import type { AgentCatalog, TaskRecord } from "@/types/task";

export const metadata: Metadata = { title: "智能体" };
export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  let tasks: TaskRecord[] = [];
  let catalog: AgentCatalog | null = null;
  let available = true;
  try {
    [tasks, catalog] = await Promise.all([
      api.tasks(),
      api.agentCatalog(),
    ]);
  } catch {
    available = false;
  }

  const modelNames = Object.fromEntries(
    (catalog?.models ?? []).map((model) => [model.id, model.name]),
  );

  return (
    <>
      <PageHeader
        eyebrow="AI 团队"
        title="智能体模板库"
        description="面向硬件产品工作的预置专业角色。创建任务时可选择参与角色，并为每个角色指定兼容的AI。"
      />
      {!catalog ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          智能体模板暂时不可用。
        </div>
      ) : (
        <div className="space-y-8">
          {Array.from(
            new Set(
              catalog.templates.map((template) => template.department),
            ),
          ).map((department) => (
            <section key={department}>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">
                  {department}
                </h2>
                <span className="text-xs text-slate-400">
                  {
                    catalog.templates.filter(
                      (template) =>
                        template.department === department,
                    ).length
                  }{" "}
                  个角色
                </span>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {catalog.templates
                  .filter(
                    (template) =>
                      template.department === department,
                  )
                  .map((template) => {
                    const active = tasks.find(
                      (task) => task.active_agent === template.id,
                    );
                    const state = !available
                      ? "不可用"
                      : active
                        ? "工作中"
                        : "空闲";
                    const configuredModel = active
                      ? active.agent_models[template.id] ??
                        template.default_model
                      : template.default_model;
                    return (
                      <article
                        key={template.id}
                        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                      >
                        <div className="flex items-start justify-between">
                          <span className="grid size-10 place-items-center rounded-lg border border-slate-200 bg-slate-50 text-slate-700">
                            <Bot className="size-5" />
                          </span>
                          <span
                            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                              state === "工作中"
                                ? "bg-blue-50 text-blue-700"
                                : state === "空闲"
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-red-50 text-red-700"
                            }`}
                          >
                            <Circle className="size-2 fill-current" />
                            {state}
                          </span>
                        </div>
                        <h3 className="mt-5 text-base font-semibold text-slate-950">
                          {template.name}
                        </h3>
                        <p className="mt-1 text-xs text-slate-500">
                          {template.role}
                        </p>
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {template.description}
                        </p>
                        <dl className="mt-5 space-y-4 border-t border-slate-100 pt-4">
                          <div>
                            <dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                              默认模型
                            </dt>
                            <dd className="mt-1 text-sm text-slate-700">
                              {modelNames[configuredModel] ??
                                configuredModel}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                              可选模型
                            </dt>
                            <dd className="mt-1 text-xs leading-5 text-slate-600">
                              {template.supported_models
                                .map(
                                  (model) =>
                                    modelNames[model] ?? model,
                                )
                                .join(" · ")}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                              当前任务
                            </dt>
                            <dd className="mt-1 truncate text-sm text-slate-700">
                              {active
                                ? `${active.project_name} · ${taskStatusLabels[active.status]}`
                                : "暂无执行中的任务"}
                            </dd>
                          </div>
                        </dl>
                      </article>
                    );
                  })}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
