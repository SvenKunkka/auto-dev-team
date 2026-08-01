import type { TaskStatus } from "@/types/task";

export const taskStatusLabels: Record<TaskStatus, string> = {
  CREATED: "已创建",
  QUEUED: "排队中",
  WAITING_DEPENDENCY: "等待前置任务",
  RUNNING: "运行中",
  ANALYZING: "需求分析中",
  RESEARCHING: "专业研究中",
  PLANNING: "规划中",
  REQUIREMENTS_REVISION: "需求修订",
  DEVELOPING: "开发中",
  VERIFYING: "验证中",
  REVIEWING: "验收中",
  REWORKING: "返工中",
  PAUSED: "已暂停",
  CANCELED: "已取消",
  PASSED: "已通过",
  FAILED: "失败",
  BLOCKED: "已阻塞",
};

const agentLabels: Record<string, string> = {
  requirement_analyst: "需求分析师",
  supervisor: "产品交付规划师",
  developer: "软件实现工程师",
  verification_engineer: "验证工程师",
  reviewer: "产品质量验收经理",
  market_researcher: "市场研究员",
  user_insight_researcher: "用户洞察与评论研究员",
  competitive_analyst: "竞品分析师",
  product_strategist: "产品策略与PRD架构师",
  industrial_design_advisor: "工业设计顾问",
  ux_ui_designer: "UI/UX设计师",
  hardware_architect: "硬件系统架构师",
  bom_cost_engineer: "BOM与成本工程师",
  supply_chain_analyst: "供应链与采购分析师",
  compliance_specialist: "法规与认证专家",
  dfx_engineer: "DFX与制造工程师",
  test_validation_planner: "硬件测试与验证策划师",
  system: "系统",
};

const valueLabels: Record<string, string> = {
  healthy: "正常",
  degraded: "异常",
  running: "运行中",
  stopped: "已停止",
  unavailable: "不可用",
  unknown: "未知",
  low: "低",
  normal: "普通",
  high: "高",
  critical: "紧急",
};

const eventLabels: Record<string, string> = {
  TASK_CREATED: "任务已创建",
  TASK_STARTED: "任务已开始",
  REQUIREMENT_ANALYSIS_STARTED: "需求分析已开始",
  REQUIREMENT_ANALYSIS_FINISHED: "需求分析已完成",
  SPECIALIST_STARTED: "专业智能体已开始",
  SPECIALIST_FINISHED: "专业智能体已完成",
  REQUIREMENTS_REVISION_REQUIRED: "已退回需求阶段",
  SUPERVISOR_STARTED: "产品交付规划已开始",
  SUPERVISOR_FINISHED: "产品交付规划已完成",
  DEVELOPER_STARTED: "软件实现已开始",
  CODEX_STARTED: "Codex 已开始",
  CODE_CHANGE_STARTED: "代码修改已开始",
  CODE_CHANGE_FINISHED: "代码修改已完成",
  TEST_STARTED: "测试已开始",
  VERIFICATION_STARTED: "独立验证已开始",
  VERIFICATION_FINISHED: "独立验证已完成",
  REVIEW_STARTED: "验收已开始",
  REWORK_STARTED: "返工已开始",
  WORKSPACE_VALIDATED: "工作区验证通过",
  TASK_WORKSPACE_PREPARED: "任务隔离工作区已创建",
  TASK_WORKSPACE_PRESERVED: "未验收代码已隔离保留",
  TASK_COMMIT_INTEGRATED: "验收提交已集成交付分支",
  GIT_COMMIT_CREATED: "Git 提交已创建",
  TASK_FINISHED: "任务已完成",
  ERROR: "错误",
};

export function localizeAgent(value: string | null | undefined) {
  if (!value) return "系统";
  return agentLabels[value.toLowerCase()] ?? value;
}

export function taskStageLabel(
  status: TaskStatus,
  currentAgent: string | null | undefined,
) {
  if (currentAgent) return localizeAgent(currentAgent);
  const labels: Partial<Record<TaskStatus, string>> = {
    CREATED: "等待入队",
    QUEUED: "等待 Worker",
    WAITING_DEPENDENCY: "等待前置任务通过",
    RUNNING: "Worker 启动中",
    PAUSED: "已暂停",
    CANCELED: "已结束",
    PASSED: "已结束",
    FAILED: "已结束",
    BLOCKED: "等待人工处理",
    REQUIREMENTS_REVISION: "等待需求拆分或补充",
  };
  return labels[status] ?? "等待调度";
}

export function localizeValue(value: string | null | undefined) {
  if (!value) return "未知";
  return valueLabels[value.toLowerCase()] ?? value;
}

export function localizeEvent(value: string) {
  return eventLabels[value] ?? value;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
