import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PageHeader } from "@/components/page-header";
import { TaskTable } from "@/components/task-table";

describe("dashboard surface", () => {
  it("renders the page shell content", () => {
    render(
      <PageHeader
        eyebrow="系统总览"
        title="AI 开发控制中心"
        description="监控 AI 团队。"
      />,
    );
    expect(
      screen.getByRole("heading", { name: "AI 开发控制中心" }),
    ).toBeInTheDocument();
  });

  it("renders an empty recent task list", () => {
    render(<TaskTable tasks={[]} />);
    expect(screen.getByText(/暂无任务/)).toBeInTheDocument();
  });
});
