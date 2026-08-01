import type {
  CreateTaskPayload,
  CreatedTask,
  DepartmentStatistics,
  Health,
  TaskDetail,
  TaskRecord,
  AgentCatalog,
  AgentModelOption,
  ModelConfigCreate,
} from "@/types/task";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function baseUrl() {
  if (typeof window !== "undefined") return "/api/backend";
  return (
    process.env.AUTO_DEV_API_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      ...(!isFormData && { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep the status-based fallback when the backend returns no JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  tasks: () => request<TaskRecord[]>("/tasks"),
  agentCatalog: () => request<AgentCatalog>("/agents/catalog"),
  models: () => request<AgentModelOption[]>("/models"),
  createModel: (payload: ModelConfigCreate) =>
    request<AgentModelOption>("/models", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateModelCredential: (modelId: string, apiKey: string) =>
    request<AgentModelOption>(
      `/models/${encodeURIComponent(modelId)}/credential`,
      {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      },
    ),
  deleteModel: (modelId: string) =>
    request<void>(`/models/${encodeURIComponent(modelId)}`, {
      method: "DELETE",
    }),
  task: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}`),
  departmentStatistics: (taskId?: string) =>
    request<DepartmentStatistics>(
      `/departments/statistics${taskId ? `?task_id=${encodeURIComponent(taskId)}` : ""}`,
    ),
  createTask: (payload: CreateTaskPayload) =>
    request<CreatedTask>("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createTaskWithDocuments: (
    payload: CreateTaskPayload,
    documents: File[],
  ) => {
    const form = new FormData();
    form.append("project_name", payload.project_name);
    form.append("workspace_path", payload.workspace_path);
    form.append("goal", payload.goal);
    form.append("requirements", JSON.stringify(payload.requirements));
    form.append("priority", payload.priority);
    form.append("execution_mode", payload.execution_mode);
    form.append("selected_agents", JSON.stringify(payload.selected_agents));
    form.append("agent_models", JSON.stringify(payload.agent_models));
    form.append("workflow_steps", JSON.stringify(payload.workflow_steps));
    documents.forEach((document) =>
      form.append("documents", document, document.name),
    );
    return request<CreatedTask>("/tasks/with-documents", {
      method: "POST",
      body: form,
    });
  },
  controlTask: (
    taskId: string,
    action: "pause" | "cancel" | "retry",
  ) =>
    request<TaskRecord>(`/tasks/${taskId}/${action}`, {
      method: "POST",
    }),
};
