"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pause, RefreshCcw, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { TaskStatus } from "@/types/task";

const retryable = new Set([
  "FAILED",
  "BLOCKED",
  "REQUIREMENTS_REVISION",
  "CANCELED",
  "PAUSED",
]);
const terminal = new Set([
  "PASSED",
  "FAILED",
  "BLOCKED",
  "REQUIREMENTS_REVISION",
  "CANCELED",
]);
const cancelDisabled = new Set(["PASSED", "CANCELED"]);

export function TaskControlPanel({
  taskId,
  status,
}: {
  taskId: string;
  status: TaskStatus;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function control(action: "pause" | "cancel" | "retry") {
    setPending(action);
    setError("");
    try {
      await api.controlTask(taskId, action);
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "控制操作失败");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h2 className="text-sm font-semibold">人工控制</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          控制命令会以协作方式执行，并在当前运行过程安全退出前保留工作区锁。
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        <Button
          variant="outline"
          disabled={status === "PAUSED" || terminal.has(status) || !!pending}
          onClick={() => control("pause")}
          className="border-slate-300 bg-white hover:bg-amber-50 hover:text-amber-700"
        >
          {pending === "pause" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Pause />
          )}
          暂停
        </Button>
        <Button
          variant="outline"
          disabled={cancelDisabled.has(status) || !!pending}
          onClick={() => control("cancel")}
          className="border-slate-300 bg-white hover:bg-red-50 hover:text-red-700"
        >
          {pending === "cancel" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Square />
          )}
          取消
        </Button>
        <Button
          variant="outline"
          disabled={!retryable.has(status) || !!pending}
          onClick={() => control("retry")}
          className="border-slate-300 bg-white hover:bg-emerald-50 hover:text-emerald-700"
        >
          {pending === "retry" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <RefreshCcw />
          )}
          重试
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
