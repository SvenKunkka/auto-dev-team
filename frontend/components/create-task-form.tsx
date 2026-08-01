"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  FileText,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { AgentSelector } from "@/components/agent-selector";
import type { AgentCatalog, WorkflowStep } from "@/types/task";

const DEFAULT_WORKFLOW: WorkflowStep[] = [
  {
    step_id: "requirement_analyst-1",
    role_id: "requirement_analyst",
    model_id: "deepseek",
    order: 0,
  },
  {
    step_id: "supervisor-1",
    role_id: "supervisor",
    model_id: "claude",
    order: 1,
  },
  {
    step_id: "developer-1",
    role_id: "developer",
    model_id: "codex",
    order: 2,
  },
  {
    step_id: "verification_engineer-1",
    role_id: "verification_engineer",
    model_id: "kimi",
    order: 3,
  },
  {
    step_id: "reviewer-1",
    role_id: "reviewer",
    model_id: "deepseek",
    order: 4,
  },
];

export function CreateTaskForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState<File[]>([]);
  const [catalog, setCatalog] = useState<AgentCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [workflowSteps, setWorkflowSteps] =
    useState<WorkflowStep[]>(DEFAULT_WORKFLOW);

  useEffect(() => {
    api
      .agentCatalog()
      .then((loaded) => {
        setCatalog(loaded);
      })
      .catch((cause) =>
        setError(
          cause instanceof Error
            ? cause.message
            : "智能体模板加载失败",
        ),
      )
      .finally(() => setCatalogLoading(false));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const normalizedWorkflow = workflowSteps.map((step, order) => ({
        ...step,
        order,
      }));
      const selectedAgents = Array.from(
        new Set(normalizedWorkflow.map((step) => step.role_id)),
      );
      const payload = {
        project_name: String(data.get("project_name")),
        workspace_path: String(data.get("workspace_path")),
        goal: String(data.get("goal")),
        requirements: String(data.get("requirements"))
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        priority: String(data.get("priority")),
        execution_mode: String(data.get("execution_mode")) as
          | "dry_run"
          | "execute",
        selected_agents: selectedAgents,
        agent_models: Object.fromEntries(
          normalizedWorkflow.map((step) => [
            step.role_id,
            step.model_id,
          ]),
        ),
        workflow_steps: normalizedWorkflow,
      };
      const created = documents.length
        ? await api.createTaskWithDocuments(payload, documents)
        : await api.createTask(payload);
      router.push(`/tasks/${created.task_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "任务创建失败");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="grid gap-6 p-5 sm:p-7">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="项目名称" htmlFor="project_name">
            <Input
              id="project_name"
              name="project_name"
              placeholder="产品知识系统"
              required
            />
          </Field>
          <Field label="优先级" htmlFor="priority">
            <select
              id="priority"
              name="priority"
              defaultValue="normal"
              className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="low">低</option>
              <option value="normal">普通</option>
              <option value="high">高</option>
              <option value="critical">紧急</option>
            </select>
          </Field>
        </div>
        <Field label="执行模式" htmlFor="execution_mode">
          <select
            id="execution_mode"
            name="execution_mode"
            defaultValue="dry_run"
            className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          >
            <option value="dry_run">
              研究与规划 — 不修改工作区文件
            </option>
            <option value="execute">
              正式执行 — Codex、证据收集、验收与提交
            </option>
          </select>
          <p className="mt-2 text-xs text-slate-600">
            只有明确选择正式执行后，系统才会修改文件。
          </p>
        </Field>
        <Field label="工作区路径" htmlFor="workspace_path">
          <Input
            id="workspace_path"
            name="workspace_path"
            placeholder="/Users/you/AutoDevPlatform/workspaces/product"
            className="border-slate-300 bg-white font-mono"
            required
          />
          <p className="mt-2 text-xs text-slate-600">
            请输入运行 Worker 的 Mac 上的绝对路径。
          </p>
        </Field>
        <Field label="任务目标" htmlFor="goal">
          <Textarea
            id="goal"
            name="goal"
            placeholder="定义一款面向移动办公用户的下一代输入设备。"
            className="min-h-28 resize-y border-slate-300 bg-white"
            required={documents.length === 0}
          />
          <p className="mt-2 text-xs text-slate-600">
            上传需求文档后，此项可以留空。
          </p>
        </Field>
        <Field label="需求列表" htmlFor="requirements">
          <Textarea
            id="requirements"
            name="requirements"
            placeholder={"提供统一查询接口\n支持型号识别\n增加 API 测试"}
            className="min-h-36 resize-y border-slate-300 bg-white font-mono text-xs"
          />
          <p className="mt-2 text-xs text-slate-600">
            每行填写一项需求；上传需求文档后可以留空。
          </p>
        </Field>
        <Field label="需求文档" htmlFor="documents">
          <label
            htmlFor="documents"
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/70 px-5 py-8 text-center transition hover:border-indigo-400 hover:bg-indigo-50/40"
          >
            <UploadCloud className="size-6 text-slate-500" />
            <span className="mt-3 text-sm font-medium text-slate-800">
              点击上传需求文档
            </span>
            <span className="mt-1 text-xs text-slate-500">
              文档可代替上方开发目标和需求列表。支持 TXT、Markdown、CSV、JSON、PDF、DOCX
            </span>
          </label>
          <input
            id="documents"
            name="documents"
            type="file"
            multiple
            accept=".txt,.md,.csv,.json,.pdf,.docx"
            className="sr-only"
            onChange={(event) => {
              const selected = Array.from(event.target.files ?? []);
              if (selected.length > 5) {
                setError("最多只能上传 5 个文档");
                event.target.value = "";
                return;
              }
              setError("");
              setDocuments(selected);
            }}
          />
          {documents.length > 0 && (
            <ul className="mt-3 space-y-2">
              {documents.map((document, index) => (
                <li
                  key={`${document.name}-${document.lastModified}`}
                  className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5"
                >
                  <FileText className="size-4 shrink-0 text-slate-500" />
                  <span className="min-w-0 flex-1 truncate text-xs text-slate-700">
                    {document.name}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {formatFileSize(document.size)}
                  </span>
                  <button
                    type="button"
                    aria-label={`移除 ${document.name}`}
                    className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-red-600"
                    onClick={() =>
                      setDocuments((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    <X className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Field>
        <Field label="参与智能体与模型" htmlFor="agent-team">
          <div id="agent-team">
            <AgentSelector
              catalog={catalog}
              loading={catalogLoading}
              workflowSteps={workflowSteps}
              onWorkflowStepsChange={setWorkflowSteps}
            />
          </div>
          <p className="mt-2 text-xs text-slate-600">
            可使用预设快速生成链条，也可重复添加专业角色、逐步选择模型并调整执行顺序。
          </p>
        </Field>
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/60 px-5 py-4 sm:px-7">
        <p className="hidden text-xs text-slate-600 sm:block">
          提交后任务会立即进入本地队列。
        </p>
        <Button
          type="submit"
          disabled={submitting}
          className="ml-auto bg-slate-900 text-white hover:bg-slate-800"
        >
          {submitting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowRight className="size-4" />
          )}
          {submitting ? "正在创建…" : "创建任务"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-2 block text-xs font-medium text-slate-700"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
