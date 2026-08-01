"use client";

import { useState } from "react";
import {
  CheckCircle2,
  CircleX,
  Clock3,
  FileCode2,
  GitBranch,
  TestTube2,
} from "lucide-react";
import { LogList } from "@/components/log-list";
import { StatusBadge } from "@/components/status-badge";
import { parseDeveloperEvidence } from "@/lib/developer-evidence";
import {
  localizeAgent,
  localizeValue,
  taskStageLabel,
} from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { TaskDetail } from "@/types/task";

const tabs = ["概览", "执行过程", "开发证据", "日志", "验收结果"] as const;
type Tab = (typeof tabs)[number];

export function TaskDetailTabs({ task }: { task: TaskDetail }) {
  const [active, setActive] = useState<Tab>("概览");
  const evidence = parseDeveloperEvidence(task.developer_output);

  return (
    <div>
      <div className="mb-5 overflow-x-auto border-b border-slate-200">
        <div role="tablist" aria-label="任务详情分区" className="flex min-w-max gap-6">
          {tabs.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={active === tab}
              onClick={() => setActive(tab)}
              className={cn(
                "-mb-px border-b-2 px-0.5 pb-3 text-sm font-medium transition",
                active === tab
                  ? "border-slate-900 text-slate-950"
                  : "border-transparent text-slate-500 hover:text-slate-800",
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>
      <div role="tabpanel">
        {active === "概览" && <Overview task={task} />}
        {active === "执行过程" && <Execution task={task} />}
        {active === "开发证据" && <Evidence task={task} evidence={evidence} />}
        {active === "日志" && <LogList logs={task.logs} />}
        {active === "验收结果" && <Review task={task} />}
      </div>
    </div>
  );
}

function Overview({ task }: { task: TaskDetail }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">任务概览</h2>
        <p className="mt-4 text-sm leading-6 text-slate-700">{task.goal}</p>
        <div className="mt-6 border-t border-slate-100 pt-5">
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">需求</p>
          <ul className="mt-3 space-y-2">
            {task.requirements.map((requirement) => (
              <li key={requirement} className="flex gap-2 text-sm text-slate-600">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                {requirement}
              </li>
            ))}
          </ul>
        </div>
        {task.documents.length > 0 && (
          <div className="mt-6 border-t border-slate-100 pt-5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              需求文档
            </p>
            <ul className="mt-3 space-y-2">
              {task.documents.map((document) => (
                <li
                  key={document.sha256}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                >
                  <span className="truncate text-sm text-slate-700">
                    {document.filename}
                  </span>
                  <span className="ml-3 shrink-0 text-[10px] text-slate-400">
                    {formatFileSize(document.size)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-6 border-t border-slate-100 pt-5">
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
            有序工作链
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(task.workflow_steps?.length
              ? task.workflow_steps
              : (task.selected_agents ?? []).map((agentId, order) => ({
                  step_id: `${agentId}-${order}`,
                  role_id: agentId,
                  model_id: task.agent_models?.[agentId] ?? "deepseek",
                  order,
                }))
            ).map((step) => (
              <span
                key={step.step_id}
                className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700"
              >
                {step.order + 1}. {localizeAgent(step.role_id)}
                <span className="ml-1 text-slate-400">
                  · {step.model_id}
                </span>
              </span>
            ))}
          </div>
        </div>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">任务信息</h2>
        <dl className="mt-4 space-y-4">
          <Definition label="状态"><StatusBadge status={task.status} /></Definition>
          <Definition label="迭代次数">{task.iteration} / {task.max_retry + 1}</Definition>
          <Definition label="当前阶段">{taskStageLabel(task.status, task.current_agent)}</Definition>
          <Definition label="工作区顺序">
            {task.sequence_no ? `第 ${task.sequence_no} 项` : "历史任务"}
          </Definition>
          {task.predecessor_task_id && (
            <Definition label="前置任务">
              <span className="font-mono text-[11px]">
                {task.predecessor_task_id.slice(0, 8)}
              </span>
            </Definition>
          )}
          <Definition label="优先级">{localizeValue(task.priority)}</Definition>
          <Definition label="执行模式">
            <span
              className={
                task.execution_mode === "execute"
                  ? "text-blue-700"
                  : "text-amber-700"
              }
            >
              {task.execution_mode === "execute"
                ? "正式执行"
                : "试运行"}
            </span>
          </Definition>
          <Definition label="心跳时间">
            {task.heartbeat ? new Date(task.heartbeat).toLocaleString("zh-CN") : "尚未开始"}
          </Definition>
          <Definition label="工作区">
            <span className="break-all font-mono text-[11px]">{task.workspace_path}</span>
          </Definition>
        </dl>
      </section>
    </div>
  );
}

function Execution({ task }: { task: TaskDetail }) {
  const coreSteps = [
    { name: "需求分析师", output: task.requirements_output, status: "需求澄清与结构化" },
    { name: "产品交付规划师", output: task.supervisor_output, status: "规划与验收标准" },
    { name: "软件实现工程师", output: task.developer_output, status: "代码实现与证据采集" },
    { name: "验证工程师", output: task.verification_output, status: "独立测试与证据核验" },
    { name: "产品质量验收经理", output: task.reviewer_output, status: "独立验收" },
  ];
  const specialistSteps = (task.specialist_outputs ?? []).map((item) => ({
    name: item.agent_name,
    output: item.output,
    status: `专业分析 · ${item.model}`,
  }));
  const steps = [
    coreSteps[0],
    ...specialistSteps,
    ...coreSteps.slice(1).filter((_, index) =>
      (task.selected_agents ?? []).includes(
        ["supervisor", "developer", "verification_engineer", "reviewer"][
          index
        ],
      ),
    ),
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="space-y-0">
        {steps.map((step, index) => (
          <div key={step.name} className="relative flex gap-4 pb-7 last:pb-0">
            {index < steps.length - 1 && <span className="absolute left-[11px] top-6 h-full w-px bg-slate-200" />}
            <span className={cn(
              "relative mt-0.5 size-6 shrink-0 rounded-full border-4 border-white",
              step.output ? "bg-emerald-500" : "bg-slate-300",
            )} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-900">{step.name}</p>
                <span className="text-xs text-slate-400">{step.status}</span>
              </div>
              <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-slate-600">
                {step.output || "等待进入此阶段"}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Evidence({
  task,
  evidence,
}: {
  task: TaskDetail;
  evidence: ReturnType<typeof parseDeveloperEvidence>;
}) {
  const available =
    evidence.changed_files.length > 0 ||
    evidence.git_diff ||
    evidence.test_results.length > 0 ||
    evidence.codex_output;
  if (!available) {
    return <Empty title="暂无详细开发证据" description="Codex 开发运行完成后，证据将显示在这里。" />;
  }
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <EvidenceMetric icon={FileCode2} label="变更文件" value={evidence.changed_files.length || task.evidence_summary.changed_files_count} />
        <EvidenceMetric icon={TestTube2} label="通过测试" value={`${evidence.test_results.filter((item) => item.exit_code === 0).length}/${evidence.test_results.length || task.evidence_summary.test_count}`} />
        <EvidenceMetric icon={GitBranch} label="Git 分支" value={evidence.git_branch || "未知"} />
      </div>
      <EvidenceSection title="变更文件">
        {evidence.changed_files.length ? (
          <ul className="divide-y divide-slate-100">
            {evidence.changed_files.map((file) => <li key={file} className="px-4 py-2.5 font-mono text-xs text-slate-700">{file}</li>)}
          </ul>
        ) : <EmptyInline text="未记录变更文件。" />}
      </EvidenceSection>
      <EvidenceSection title="Git 差异">
        <CodeBlock value={evidence.git_diff || "未记录 Git 差异。"} />
      </EvidenceSection>
      <EvidenceSection title="测试结果">
        {evidence.test_results.length ? evidence.test_results.map((result, index) => (
          <div key={index} className="border-b border-slate-100 p-4 last:border-0">
            <div className="flex items-center gap-2">
              {result.exit_code === 0 ? <CheckCircle2 className="size-4 text-emerald-600" /> : <CircleX className="size-4 text-red-600" />}
              <code className="text-xs text-slate-700">{Array.isArray(result.command) ? result.command.join(" ") : result.command}</code>
            </div>
            {(result.stdout || result.stderr) && <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-[11px] leading-5 text-slate-200">{result.stdout || result.stderr}</pre>}
          </div>
        )) : <EmptyInline text="未记录测试输出。" />}
      </EvidenceSection>
      <EvidenceSection title="Codex 输出">
        <CodeBlock value={evidence.codex_output || "未记录 Codex 输出。"} />
      </EvidenceSection>
    </div>
  );
}

function Review({ task }: { task: TaskDetail }) {
  const output = task.reviewer_output?.trim() ?? "";
  const explicit = output.match(/FINAL_RESULT:\s*(PASS|FAIL|BLOCKED)/i)?.[1];
  const first = output.split(/\s/, 1)[0]?.toUpperCase();
  const candidate = explicit?.toUpperCase() ?? first;
  const verdict = candidate === "PASS" || candidate === "FAIL" || candidate === "BLOCKED" ? candidate : null;
  if (!task.reviewer_output) {
    return <Empty title="等待验收" description="产品质量验收经理尚未给出结果。" />;
  }
  const style = verdict === "PASS" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : verdict === "FAIL" ? "border-red-200 bg-red-50 text-red-700" : "border-amber-200 bg-amber-50 text-amber-700";
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`inline-flex rounded-md border px-3 py-1.5 text-sm font-semibold ${style}`}>
        {verdict === "PASS"
          ? "通过"
          : verdict === "FAIL"
            ? "失败"
            : verdict === "BLOCKED"
              ? "阻塞"
              : "验收结果"}
      </div>
      <pre className="mt-5 overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-6 text-slate-700">
        {task.reviewer_output}
      </pre>
    </section>
  );
}

function Definition({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{label}</dt><dd className="mt-1 text-sm capitalize text-slate-700">{children}</dd></div>;
}

function EvidenceMetric({ icon: Icon, label, value }: { icon: typeof Clock3; label: string; value: string | number }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><Icon className="size-4 text-slate-400" /><p className="mt-4 text-xl font-semibold text-slate-900">{value}</p><p className="mt-1 text-xs text-slate-500">{label}</p></div>;
}

function EvidenceSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><h3 className="border-b border-slate-200 bg-slate-50/70 px-4 py-3 text-xs font-semibold text-slate-700">{title}</h3>{children}</section>;
}

function CodeBlock({ value }: { value: string }) {
  return <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap bg-slate-950 p-4 font-mono text-[11px] leading-5 text-slate-200">{value}</pre>;
}

function EmptyInline({ text }: { text: string }) {
  return <p className="px-4 py-8 text-center text-sm text-slate-500">{text}</p>;
}

function Empty({ title, description }: { title: string; description: string }) {
  return <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-14 text-center"><p className="text-sm font-medium text-slate-800">{title}</p><p className="mt-1 text-xs text-slate-500">{description}</p></div>;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
