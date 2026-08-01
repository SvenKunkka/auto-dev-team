import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TaskDetailTabs } from "@/components/task-detail-tabs";
import type { TaskDetail } from "@/types/task";

const task: TaskDetail = {
  id: 1,
  task_id: "task-123",
  project_name: "Knowledge API",
  workspace_path: "/tmp/knowledge",
  goal: "Build a search API",
  requirements: ["Unified query"],
  priority: "high",
  execution_mode: "execute",
  status: "PASSED",
  retry_count: 0,
  max_retry: 3,
  started_at: "2026-07-27T10:00:00Z",
  last_heartbeat: "2026-07-27T10:05:00Z",
  timeout_seconds: 3600,
  blocked_reason: null,
  required_action: null,
  supervisor_output: "Plan",
  developer_output: JSON.stringify({
    evidence: {
      changed_files: ["src/search.py"],
      git_branch: "feature/search",
      git_status: "M src/search.py",
      git_diff: "+ search",
      test_results: [
        {
          command: ["pytest"],
          stdout: "1 passed",
          stderr: "",
          exit_code: 0,
        },
      ],
      commands: [["pytest"]],
      codex_output: "Implementation complete",
    },
  }),
  reviewer_output: "PASS\nAll acceptance criteria satisfied.",
  created_at: "2026-07-27T10:00:00Z",
  updated_at: "2026-07-27T10:05:00Z",
  current_agent: null,
  iteration: 1,
  heartbeat: "2026-07-27T10:05:00Z",
  evidence_summary: {
    artifact_count: 4,
    artifact_types: ["git_diff", "changed_files"],
    changed_files_count: 1,
    test_count: 1,
    failed_test_count: 0,
  },
  documents: [],
  logs: [],
};

describe("task detail tabs", () => {
  it("shows evidence details from existing developer output", () => {
    render(<TaskDetailTabs task={task} />);

    fireEvent.click(screen.getByRole("tab", { name: "开发证据" }));

    expect(screen.getByText("src/search.py")).toBeInTheDocument();
    expect(screen.getByText("feature/search")).toBeInTheDocument();
    expect(screen.getByText("Implementation complete")).toBeInTheDocument();
    expect(screen.getByText("1 passed")).toBeInTheDocument();
  });

  it("shows the normalized reviewer verdict", () => {
    render(<TaskDetailTabs task={task} />);

    fireEvent.click(screen.getByRole("tab", { name: "验收结果" }));

    expect(screen.getByText("通过")).toBeInTheDocument();
    expect(
      screen.getByText(/All acceptance criteria satisfied/),
    ).toBeInTheDocument();
  });
});
