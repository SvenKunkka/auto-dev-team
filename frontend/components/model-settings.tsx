"use client";

import { FormEvent, useState } from "react";
import {
  Brain,
  CheckCircle2,
  Eye,
  KeyRound,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  AgentModelOption,
  ModelConfigCreate,
} from "@/types/task";

const BUILTIN_IDS = new Set([
  "deepseek",
  "claude",
  "kimi",
  "codex",
  "claude_opus_design",
  "claude_design_handoff",
]);
const CAPABILITIES = [
  ["reasoning", "复杂推理"],
  ["multimodal", "多模态"],
  ["vision", "视觉理解"],
  ["long_context", "长上下文"],
  ["coding", "代码开发"],
  ["tool_use", "工具调用"],
  ["design", "视觉设计"],
  ["fast", "快速响应"],
] as const;

export function ModelSettings({
  initialModels,
}: {
  initialModels: AgentModelOption[];
}) {
  const [models, setModels] = useState(initialModels);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function saveCredential(modelId: string) {
    if (!keys[modelId]?.trim()) return;
    setSaving(`key:${modelId}`);
    setError("");
    try {
      const updated = await api.updateModelCredential(
        modelId,
        keys[modelId],
      );
      setModels((current) =>
        current.map((model) =>
          model.id === modelId ? updated : model,
        ),
      );
      setKeys((current) => ({ ...current, [modelId]: "" }));
      setSuccess("API Key 已安全保存到 macOS Keychain");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "API Key 保存失败");
    } finally {
      setSaving("");
    }
  }

  async function createModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving("create");
    setError("");
    setSuccess("");
    const data = new FormData(event.currentTarget);
    const payload: ModelConfigCreate = {
      id: String(data.get("id")),
      name: String(data.get("name")),
      provider: String(data.get("provider")),
      model_id: String(data.get("model_id")),
      base_url: String(data.get("base_url")),
      api_style: String(data.get("api_style")) as ModelConfigCreate["api_style"],
      description: String(data.get("description")),
      capabilities: data.getAll("capabilities").map(String),
      api_key: String(data.get("api_key")),
    };
    try {
      const created = await api.createModel(payload);
      setModels((current) => [...current, created]);
      event.currentTarget.reset();
      setSuccess("新模型已加入模型目录");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模型创建失败");
    } finally {
      setSaving("");
    }
  }

  async function removeModel(modelId: string) {
    setSaving(`delete:${modelId}`);
    setError("");
    try {
      await api.deleteModel(modelId);
      setModels((current) =>
        current.filter((model) => model.id !== modelId),
      );
      setSuccess("模型配置已删除，Keychain 凭证也已清理");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "删除失败");
    } finally {
      setSaving("");
    }
  }

  return (
    <div className="space-y-6">
      {(error || success) && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            error
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {error || success}
        </div>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">模型目录</h2>
          <p className="mt-1 text-xs text-slate-500">
            能力标签用于帮助为角色选择合适模型；密钥明文不会进入数据库或API响应。
          </p>
        </div>
        <div className="divide-y divide-slate-100">
          {models.map((model) => (
            <article key={model.id} className="px-5 py-4">
              <div className="flex flex-col justify-between gap-3 lg:flex-row">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      {model.name}
                    </h3>
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                      {model.provider}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] ${
                        model.configured
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {model.configured && <CheckCircle2 className="size-3" />}
                      {model.configured ? "已配置" : "未配置"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {model.description}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {model.capabilities.map((item) => (
                      <span
                        key={item}
                        className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-600"
                      >
                        {capabilityName(item)}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 font-mono text-[10px] text-slate-400">
                    {model.id} · {model.model_id} · {model.api_style}
                  </p>
                </div>
                <div className="flex min-w-0 items-end gap-2 lg:w-[360px]">
                  {!["manual", "cli"].includes(model.api_style) && (
                    <>
                      <label className="min-w-0 flex-1">
                        <span className="mb-1 block text-[10px] font-medium text-slate-500">
                          API Key
                        </span>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={keys[model.id] ?? ""}
                          placeholder={model.configured ? "•••••••• 已保存" : "输入API Key"}
                          onChange={(event) =>
                            setKeys((current) => ({
                              ...current,
                              [model.id]: event.target.value,
                            }))
                          }
                          className="h-9 w-full rounded-md border border-slate-300 px-3 text-xs"
                        />
                      </label>
                      <button
                        type="button"
                        disabled={
                          !keys[model.id]?.trim() ||
                          saving === `key:${model.id}`
                        }
                        onClick={() => saveCredential(model.id)}
                        className="inline-flex h-9 items-center gap-1.5 rounded-md bg-slate-900 px-3 text-xs font-medium text-white disabled:opacity-40"
                      >
                        {saving === `key:${model.id}` ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <KeyRound className="size-3.5" />
                        )}
                        保存
                      </button>
                    </>
                  )}
                  {!BUILTIN_IDS.has(model.id) && (
                    <button
                      type="button"
                      aria-label={`删除 ${model.name}`}
                      onClick={() => removeModel(model.id)}
                      className="grid size-9 place-items-center rounded-md border border-red-200 text-red-600 hover:bg-red-50"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <form
        onSubmit={createModel}
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="mb-5">
          <h2 className="text-sm font-semibold text-slate-900">新增模型</h2>
          <p className="mt-1 text-xs text-slate-500">
            支持OpenAI兼容接口、Anthropic Messages API及人工工具交接。
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="配置ID">
            <input name="id" required placeholder="my_model" className={inputClass} />
          </Field>
          <Field label="显示名称">
            <input name="name" required placeholder="公司内部模型" className={inputClass} />
          </Field>
          <Field label="供应商">
            <input name="provider" required placeholder="OpenAI / Anthropic / 自建" className={inputClass} />
          </Field>
          <Field label="模型ID">
            <input name="model_id" required placeholder="模型API中的真实ID" className={inputClass} />
          </Field>
          <Field label="接口类型">
            <select name="api_style" className={inputClass}>
              <option value="openai_compatible">OpenAI Compatible</option>
              <option value="anthropic_messages">Anthropic Messages</option>
              <option value="manual">人工工具交接</option>
            </select>
          </Field>
          <Field label="Base URL">
            <input name="base_url" placeholder="https://api.example.com/v1" className={inputClass} />
          </Field>
          <Field label="API Key">
            <input name="api_key" type="password" autoComplete="new-password" placeholder="仅写入macOS Keychain" className={inputClass} />
          </Field>
          <Field label="能力说明">
            <input name="description" placeholder="适用任务、优势和限制" className={inputClass} />
          </Field>
        </div>
        <fieldset className="mt-5">
          <legend className="text-xs font-medium text-slate-700">能力标签</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {CAPABILITIES.map(([value, label]) => (
              <label
                key={value}
                className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs text-slate-600"
              >
                <input type="checkbox" name="capabilities" value={value} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <button
          type="submit"
          disabled={saving === "create"}
          className="mt-5 inline-flex h-9 items-center gap-2 rounded-md bg-indigo-600 px-4 text-xs font-medium text-white disabled:opacity-50"
        >
          {saving === "create" ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Plus className="size-4" />
          )}
          新增模型
        </button>
      </form>

      <div className="grid gap-3 md:grid-cols-2">
        <CapabilityNote
          icon={Brain}
          title="推理模型"
          text="适合复杂决策、技术方案、风险分析和多阶段规划，通常速度较慢、成本较高。"
        />
        <CapabilityNote
          icon={Eye}
          title="多模态与视觉模型"
          text="适合分析产品图片、界面截图、结构图、PDF和视觉设计，不应只用于纯文字分类。"
        />
      </div>
    </div>
  );
}

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label>
      <span className="mb-1.5 block text-xs font-medium text-slate-700">
        {label}
      </span>
      {children}
    </label>
  );
}

function CapabilityNote({
  icon: Icon,
  title,
  text,
}: {
  icon: typeof Brain;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <Icon className="size-5 text-indigo-600" />
      <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 text-xs leading-5 text-slate-500">{text}</p>
    </div>
  );
}

function capabilityName(value: string) {
  return (
    Object.fromEntries(CAPABILITIES)[value] ??
    (value === "structured_output" ? "结构化输出" : value)
  );
}
