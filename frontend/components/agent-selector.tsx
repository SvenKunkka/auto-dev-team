"use client";

import {
  ArrowDown,
  ArrowUp,
  Bot,
  GripVertical,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import type {
  AgentCatalog,
  AgentModelId,
  AgentModelOption,
  AgentTemplate,
  WorkflowStep,
} from "@/types/task";

const DELIVERY_ROLES = [
  "developer",
  "verification_engineer",
  "reviewer",
];

export function AgentSelector({
  catalog,
  workflowSteps,
  loading,
  onWorkflowStepsChange,
}: {
  catalog: AgentCatalog | null;
  workflowSteps: WorkflowStep[];
  loading: boolean;
  onWorkflowStepsChange: (value: WorkflowStep[]) => void;
}) {
  if (loading || !catalog) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-600">
        <Loader2 className="size-4 animate-spin" />
        正在加载智能体模板…
      </div>
    );
  }

  const activeCatalog = catalog;
  const templateMap = Object.fromEntries(
    activeCatalog.templates.map((template) => [template.id, template]),
  );
  const modelMap = Object.fromEntries(
    activeCatalog.models.map((model) => [model.id, model]),
  );
  const specialists = activeCatalog.templates.filter(
    (template) => template.kind === "specialist",
  );
  const researchSteps = workflowSteps.filter(
    (step) => templateMap[step.role_id]?.kind === "specialist",
  );
  const requirement =
    workflowSteps.find((step) => step.role_id === "requirement_analyst") ??
    buildStep(templateMap.requirement_analyst);
  const supervisor =
    workflowSteps.find((step) => step.role_id === "supervisor") ??
    buildStep(templateMap.supervisor);
  const deliveryEnabled = DELIVERY_ROLES.every((roleId) =>
    workflowSteps.some((step) => step.role_id === roleId),
  );

  function commit(
    nextResearch: WorkflowStep[],
    withDelivery = deliveryEnabled,
    coreOverrides?: Record<string, WorkflowStep>,
  ) {
    const coreRequirement =
      coreOverrides?.requirement_analyst ?? requirement;
    const coreSupervisor = coreOverrides?.supervisor ?? supervisor;
    const delivery = withDelivery
      ? DELIVERY_ROLES.map(
          (roleId) =>
            workflowSteps.find((step) => step.role_id === roleId) ??
            buildStep(templateMap[roleId]),
        )
      : [];
    onWorkflowStepsChange(
      normalizeOrders([
        coreRequirement,
        ...nextResearch,
        coreSupervisor,
        ...delivery,
      ]),
    );
  }

  function selectPreset(agentIds: string[]) {
    const selected = new Set(agentIds);
    const presetResearch = activeCatalog.templates
      .filter(
        (template) =>
          template.kind === "specialist" && selected.has(template.id),
      )
      .map((template) => buildStep(template));
    const withDelivery = DELIVERY_ROLES.every((roleId) =>
      selected.has(roleId),
    );
    commit(presetResearch, withDelivery);
  }

  function updateResearch(index: number, next: WorkflowStep) {
    const updated = [...researchSteps];
    updated[index] = next;
    commit(updated);
  }

  function moveResearch(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= researchSteps.length) return;
    const updated = [...researchSteps];
    [updated[index], updated[target]] = [updated[target], updated[index]];
    commit(updated);
  }

  function updateCore(step: WorkflowStep) {
    commit(researchSteps, deliveryEnabled, { [step.role_id]: step });
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {activeCatalog.presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => selectPreset(preset.agent_ids)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-indigo-300 hover:bg-indigo-50/40"
          >
            <span className="text-xs font-semibold text-slate-900">
              {preset.name}
            </span>
            <span className="mt-1 block text-[11px] leading-5 text-slate-500">
              {preset.description}
            </span>
          </button>
        ))}
      </div>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              有序工作链
            </h3>
            <p className="mt-0.5 text-[11px] text-slate-500">
              专业角色可以重复添加、独立选模型并调整先后顺序。
            </p>
          </div>
          <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700">
            {workflowSteps.length} 个步骤
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          <LockedStep
            number={1}
            step={requirement}
            template={templateMap.requirement_analyst}
            models={modelMap}
            label="固定入口"
            onChange={updateCore}
          />

          {researchSteps.map((step, index) => {
            const template = templateMap[step.role_id];
            return (
              <div
                key={step.step_id}
                className="grid gap-3 px-4 py-3 lg:grid-cols-[42px_minmax(210px,1fr)_220px_104px]"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                  <GripVertical className="size-4" />
                  {index + 2}
                </div>
                <label>
                  <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-slate-400">
                    角色模板
                  </span>
                  <select
                    value={step.role_id}
                    onChange={(event) => {
                      const nextTemplate = templateMap[event.target.value];
                      updateResearch(
                        index,
                        buildStep(nextTemplate, step.step_id),
                      );
                    }}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800"
                  >
                    {specialists.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.department}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block truncate text-[11px] text-slate-500">
                    {template?.role}
                  </span>
                </label>
                <ModelSelect
                  template={template}
                  model={step.model_id}
                  models={modelMap}
                  onChange={(modelId) =>
                    updateResearch(index, {
                      ...step,
                      model_id: modelId,
                    })
                  }
                />
                <div className="flex items-center justify-end gap-1 pt-4">
                  <IconButton
                    label="上移"
                    disabled={index === 0}
                    onClick={() => moveResearch(index, -1)}
                  >
                    <ArrowUp className="size-4" />
                  </IconButton>
                  <IconButton
                    label="下移"
                    disabled={index === researchSteps.length - 1}
                    onClick={() => moveResearch(index, 1)}
                  >
                    <ArrowDown className="size-4" />
                  </IconButton>
                  <IconButton
                    label="删除"
                    onClick={() =>
                      commit(
                        researchSteps.filter(
                          (item) => item.step_id !== step.step_id,
                        ),
                      )
                    }
                  >
                    <Trash2 className="size-4" />
                  </IconButton>
                </div>
              </div>
            );
          })}

          <div className="px-4 py-3">
            <button
              type="button"
              disabled={specialists.length === 0}
              onClick={() =>
                commit([...researchSteps, buildStep(specialists[0])])
              }
              className="inline-flex h-9 items-center gap-2 rounded-md border border-dashed border-indigo-300 px-3 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              <Plus className="size-4" />
              添加一个专业角色
            </button>
          </div>

          <LockedStep
            number={researchSteps.length + 2}
            step={supervisor}
            template={templateMap.supervisor}
            models={modelMap}
            label="固定汇总"
            onChange={updateCore}
          />

          <div className="px-4 py-3">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={deliveryEnabled}
                onChange={(event) =>
                  commit(researchSteps, event.target.checked)
                }
                className="mt-0.5 size-4 rounded border-slate-300 text-indigo-600"
              />
              <span>
                <span className="block text-sm font-medium text-slate-900">
                  启用开发交付闭环
                </span>
                <span className="mt-0.5 block text-[11px] text-slate-500">
                  固定保持软件实现工程师 → 验证工程师 → 产品质量验收经理。
                </span>
              </span>
            </label>
          </div>

          {deliveryEnabled &&
            DELIVERY_ROLES.map((roleId, index) => {
              const step = workflowSteps.find(
                (item) => item.role_id === roleId,
              )!;
              return (
                <LockedStep
                  key={roleId}
                  number={researchSteps.length + 3 + index}
                  step={step}
                  template={templateMap[roleId]}
                  models={modelMap}
                  label="交付闭环"
                  onChange={(next) => {
                    const updated = workflowSteps.map((item) =>
                      item.step_id === next.step_id ? next : item,
                    );
                    onWorkflowStepsChange(normalizeOrders(updated));
                  }}
                />
              );
            })}
        </div>
      </section>

      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Bot className="size-4" />
        链条按编号严格串行执行；同一专业角色可使用不同模型重复出现。
      </div>
    </div>
  );
}

function LockedStep({
  number,
  step,
  template,
  models,
  label,
  onChange,
}: {
  number: number;
  step: WorkflowStep;
  template: AgentTemplate;
  models: Record<string, AgentModelOption>;
  label: string;
  onChange: (value: WorkflowStep) => void;
}) {
  return (
    <div className="grid gap-3 bg-slate-50/30 px-4 py-3 lg:grid-cols-[42px_minmax(210px,1fr)_220px_104px]">
      <div className="flex items-center text-xs font-semibold text-slate-400">
        {number}
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-900">
            {template.name}
          </span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-500">
            {label}
          </span>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">{template.role}</p>
      </div>
      <ModelSelect
        template={template}
        model={step.model_id}
        models={models}
        onChange={(modelId) => onChange({ ...step, model_id: modelId })}
      />
      <div />
    </div>
  );
}

function ModelSelect({
  template,
  model,
  models,
  onChange,
}: {
  template: AgentTemplate;
  model: AgentModelId;
  models: Record<string, AgentModelOption>;
  onChange: (value: AgentModelId) => void;
}) {
  const selectedModel = models[model];
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-slate-400">
        使用模型
      </span>
      <select
        value={model}
        onChange={(event) =>
          onChange(event.target.value as AgentModelId)
        }
        className="h-10 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700"
      >
        {template.supported_models.map((modelId) => (
          <option key={modelId} value={modelId}>
            {models[modelId]?.name ?? modelId}
            {models[modelId] && !models[modelId].configured
              ? " · 未配置"
              : ""}
          </option>
        ))}
      </select>
      {selectedModel && (
        <span className="mt-1.5 block">
          <span className="block text-[10px] leading-4 text-slate-500">
            {selectedModel.description}
          </span>
          <span className="mt-1 flex flex-wrap gap-1">
            {selectedModel.capabilities.slice(0, 4).map((capability) => (
              <span
                key={capability}
                className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-600"
              >
                {capabilityLabel(capability)}
              </span>
            ))}
          </span>
        </span>
      )}
    </label>
  );
}

function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-30"
    >
      {children}
    </button>
  );
}

function buildStep(
  template: AgentTemplate,
  stepId?: string,
): WorkflowStep {
  return {
    step_id:
      stepId ??
      `${template.id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role_id: template.id,
    model_id: template.default_model,
    order: 0,
  };
}

function normalizeOrders(steps: WorkflowStep[]): WorkflowStep[] {
  return steps.map((step, order) => ({ ...step, order }));
}

function capabilityLabel(capability: string) {
  return (
    {
      reasoning: "推理",
      multimodal: "多模态",
      vision: "视觉",
      long_context: "长上下文",
      coding: "代码",
      tool_use: "工具调用",
      design: "设计",
      fast: "快速",
      structured_output: "结构化输出",
      manual_handoff: "人工交接",
    }[capability] ?? capability
  );
}
