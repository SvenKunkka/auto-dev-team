import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("FastAPI client", () => {
  it("loads health and task list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          status: "healthy",
          database: "healthy",
          worker: "running",
          queue_size: 2,
        }),
      )
      .mockResolvedValueOnce(response([]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.health()).resolves.toMatchObject({ status: "healthy" });
    await expect(api.tasks()).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("submits the create task payload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(response({ task_id: "task-123", status: "CREATED" }));
    vi.stubGlobal("fetch", fetchMock);
    const payload = {
      project_name: "Knowledge",
      workspace_path: "/tmp/knowledge",
      goal: "Build API",
      requirements: ["Search"],
      priority: "high",
      execution_mode: "dry_run" as const,
    };

    await expect(api.createTask(payload)).resolves.toEqual({
      task_id: "task-123",
      status: "CREATED",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/tasks"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("uploads documents with the task as multipart data", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(response({ task_id: "task-456", status: "CREATED" }));
    vi.stubGlobal("fetch", fetchMock);
    const payload = {
      project_name: "Knowledge",
      workspace_path: "/tmp/knowledge",
      goal: "Build API",
      requirements: ["Search"],
      priority: "high",
      execution_mode: "dry_run" as const,
    };
    const document = new File(["# Specification"], "spec.md", {
      type: "text/markdown",
    });

    await api.createTaskWithDocuments(payload, [document]);

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toContain("/tasks/with-documents");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).not.toHaveProperty("Content-Type");
    expect((init.body as FormData).get("documents")).toBeInstanceOf(File);
  });

  it("loads task detail including evidence and logs", async () => {
    const detail = {
      task_id: "task-123",
      status: "REVIEWING",
      iteration: 2,
      current_agent: "reviewer",
      heartbeat: "2026-07-27T12:00:00Z",
      evidence_summary: {
        artifact_count: 4,
        artifact_types: ["git_diff"],
        changed_files_count: 2,
        test_count: 3,
        failed_test_count: 0,
      },
      logs: [{ id: 1, event_type: "TASK_STARTED" }],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(detail)));

    await expect(api.task("task-123")).resolves.toMatchObject({
      current_agent: "reviewer",
      iteration: 2,
      evidence_summary: { changed_files_count: 2 },
    });
  });

  it("loads department statistics for one goal", async () => {
    const statistics = {
      department_name: "任务统计部",
      selected_goal: {
        task_id: "task-123",
        project_name: "Knowledge",
        goal: "Build API",
      },
      roles: [
        {
          agent_name: "developer",
          role_name: "开发者",
          goal_execution_count: 2,
          cumulative_execution_count: 9,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(response(statistics));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.departmentStatistics("task-123")).resolves.toEqual(
      statistics,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/departments/statistics?task_id=task-123",
      ),
      expect.any(Object),
    );
  });
});
