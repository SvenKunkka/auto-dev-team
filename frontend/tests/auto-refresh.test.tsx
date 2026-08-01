import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AutoRefresh } from "@/components/auto-refresh";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

describe("task auto refresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    refresh.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("refreshes while a task is nonterminal", () => {
    render(<AutoRefresh active intervalMs={1000} />);

    act(() => vi.advanceTimersByTime(3000));

    expect(refresh).toHaveBeenCalledTimes(3);
  });

  it("does not refresh terminal tasks", () => {
    render(<AutoRefresh active={false} intervalMs={1000} />);

    act(() => vi.advanceTimersByTime(3000));

    expect(refresh).not.toHaveBeenCalled();
  });
});
