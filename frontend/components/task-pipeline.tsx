import {
  Bot,
  Braces,
  ClipboardList,
  ShieldCheck,
  GitPullRequest,
  ArrowRight,
  Users,
} from "lucide-react";

const steps = [
  { name: "需求分析师", detail: "澄清需求", icon: ClipboardList },
  { name: "专业智能体", detail: "按需研究", icon: Users },
  { name: "产品交付规划师", detail: "规划", icon: Bot },
  { name: "软件实现工程师", detail: "开发", icon: Braces },
  { name: "验证工程师", detail: "独立验证", icon: ShieldCheck },
  { name: "产品质量验收经理", detail: "决策", icon: GitPullRequest },
];

export function TaskPipeline() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">任务流水线</h2>
        <p className="mt-1 text-xs text-slate-500">
          专业角色按需参与，开发与验收闭环由任务配置决定
        </p>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
        {steps.map(({ name, detail, icon: Icon }, index) => (
          <div key={name} className="relative flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-md border border-slate-200 bg-white text-slate-600 shadow-sm">
              <Icon className="size-4" />
            </span>
            <div>
              <p className="text-xs font-medium text-slate-900">{name}</p>
              <p className="text-[10px] text-slate-500">{detail}</p>
            </div>
            {index < steps.length - 1 && (
              <ArrowRight className="absolute -right-3 z-10 hidden size-4 text-slate-300 xl:block" />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
