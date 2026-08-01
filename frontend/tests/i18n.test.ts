import { describe, expect, it } from "vitest";
import { taskStageLabel } from "@/lib/i18n";

describe("task stage localization", () => {
  it("shows queued tasks as waiting for the worker", () => {
    expect(taskStageLabel("QUEUED", null)).toBe("等待 Worker");
  });

  it("shows the active agent when execution has started", () => {
    expect(taskStageLabel("PLANNING", "supervisor")).toBe("产品交付规划师");
  });
});
