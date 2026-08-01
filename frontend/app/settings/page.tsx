import type { Metadata } from "next";
import { CheckCircle2, Database, Server, Workflow } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { localizeValue } from "@/lib/i18n";
import type { Health } from "@/types/task";
import type { AgentModelOption } from "@/types/task";
import { ModelSettings } from "@/components/model-settings";

export const metadata: Metadata = { title: "设置" };
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  let health: Health | null = null;
  let models: AgentModelOption[] = [];
  try {
    [health, models] = await Promise.all([api.health(), api.models()]);
  } catch {
    health = null;
  }
  const rows = [
    {
      icon: Server,
      label: "FastAPI 服务",
      value: health ? "已连接" : "不可用",
    },
    {
      icon: Database,
      label: "SQLite 数据库",
      value: localizeValue(health?.database),
    },
    {
      icon: Workflow,
      label: "任务 Worker",
      value: localizeValue(health?.worker),
    },
  ];
  return (
    <>
      <PageHeader
        eyebrow="工作区配置"
        title="设置"
        description="查看运行状态，并管理模型能力、接口和安全凭证。"
      />
      <section className="max-w-3xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">运行环境连接</h2>
          <p className="mt-1 text-xs text-slate-500">
            运行参数由环境配置管理；模型与凭证可在下方安全配置。
          </p>
        </div>
        {rows.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center justify-between border-b border-slate-100 px-5 py-4 last:border-0">
            <div className="flex items-center gap-3 text-sm text-slate-700">
              <Icon className="size-4 text-slate-400" />
              {label}
            </div>
            <span className="flex items-center gap-2 text-xs font-medium capitalize text-slate-600">
              {health && <CheckCircle2 className="size-3.5 text-emerald-600" />}
              {value}
            </span>
          </div>
        ))}
      </section>
      <div className="mt-6">
        <ModelSettings initialModels={models} />
      </div>
    </>
  );
}
