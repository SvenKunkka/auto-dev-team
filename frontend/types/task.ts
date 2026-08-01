export type TaskStatus =
  | "CREATED"
  | "QUEUED"
  | "WAITING_DEPENDENCY"
  | "RUNNING"
  | "ANALYZING"
  | "RESEARCHING"
  | "PLANNING"
  | "REQUIREMENTS_REVISION"
  | "DEVELOPING"
  | "VERIFYING"
  | "REVIEWING"
  | "REWORKING"
  | "PAUSED"
  | "CANCELED"
  | "PASSED"
  | "FAILED"
  | "BLOCKED";

export type ExecutionMode = "dry_run" | "execute";
export type AgentModelId = string;

export interface WorkflowStep {
  step_id: string;
  role_id: string;
  model_id: AgentModelId;
  order: number;
}

export interface TaskRecord {
  id: number;
  task_id: string;
  project_name: string;
  workspace_path: string;
  goal: string;
  requirements: string[];
  priority: string;
  execution_mode: ExecutionMode;
  predecessor_task_id: string | null;
  sequence_no: number | null;
  resume_stage: TaskStatus;
  selected_agents: string[];
  agent_models: Record<string, string>;
  workflow_steps: WorkflowStep[];
  active_agent: string | null;
  status: TaskStatus;
  retry_count: number;
  max_retry: number;
  started_at: string | null;
  last_heartbeat: string | null;
  timeout_seconds: number;
  blocked_reason: string | null;
  required_action: string | null;
  requirements_output: string | null;
  supervisor_output: string | null;
  developer_output: string | null;
  verification_output: string | null;
  reviewer_output: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionLog {
  id: number;
  task_id: string;
  agent_name: string | null;
  event_type: string;
  level: string;
  message: string;
  created_at: string;
}

export interface EvidenceSummary {
  artifact_count: number;
  artifact_types: string[];
  changed_files_count: number;
  test_count: number;
  failed_test_count: number;
}

export interface TaskDocument {
  filename: string;
  content_type: string;
  size: number;
  sha256: string;
  storage_path: string;
}

export interface TaskDetail extends TaskRecord {
  current_agent: string | null;
  iteration: number;
  heartbeat: string | null;
  evidence_summary: EvidenceSummary;
  documents: TaskDocument[];
  specialist_outputs: SpecialistOutput[];
  logs: ExecutionLog[];
}

export interface SpecialistOutput {
  step_id: string;
  order: number;
  agent_id: string;
  agent_name: string;
  model: string;
  output: string;
  evidence: Record<string, unknown>;
}

export interface Health {
  status: "healthy" | "degraded";
  database: "healthy" | "unavailable";
  worker: "running" | "stopped";
  queue_size: number | null;
}

export interface CreateTaskPayload {
  project_name: string;
  workspace_path: string;
  goal: string;
  requirements: string[];
  priority: string;
  execution_mode: ExecutionMode;
  selected_agents: string[];
  agent_models: Record<string, string>;
  workflow_steps: WorkflowStep[];
}

export interface CreatedTask {
  task_id: string;
  status: TaskStatus;
}

export interface AgentModelOption {
  id: AgentModelId;
  name: string;
  description: string;
  provider: string;
  model_id: string;
  base_url: string;
  api_style: string;
  capabilities: string[];
  configured: boolean;
  enabled: boolean;
}

export interface ModelConfigCreate {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  base_url: string;
  api_style: "openai_compatible" | "anthropic_messages" | "manual";
  description: string;
  capabilities: string[];
  api_key: string;
}

export interface AgentTemplate {
  id: string;
  name: string;
  department: string;
  kind: "core" | "specialist" | "delivery";
  role: string;
  description: string;
  capabilities: string[];
  system_prompt: string;
  default_model: AgentModelOption["id"];
  supported_models: AgentModelOption["id"][];
  order: number;
  required: boolean;
  dependencies: string[];
  context_roles: string[];
  source_access: string;
}

export interface AgentPreset {
  id: string;
  name: string;
  description: string;
  agent_ids: string[];
}

export interface AgentCatalog {
  models: AgentModelOption[];
  templates: AgentTemplate[];
  presets: AgentPreset[];
}

export interface AgentExecutionStatistics {
  agent_name:
    | "requirement_analyst"
    | "supervisor"
    | "developer"
    | "verification_engineer"
    | "reviewer";
  role_name: string;
  goal_execution_count: number;
  cumulative_execution_count: number;
}

export interface DepartmentStatistics {
  department_name: string;
  selected_goal: {
    task_id: string;
    project_name: string;
    goal: string;
  } | null;
  roles: AgentExecutionStatistics[];
}
