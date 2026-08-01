import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { TaskControlPanel } from "@/components/task-control-panel";
import { buttonVariants } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

export const metadata: Metadata = { title: "任务控制" };
export const dynamic = "force-dynamic";

export default async function TaskControlPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let task;
  try {
    task = await api.task(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  return (
    <>
      <PageHeader
        eyebrow="人工干预"
        title="任务控制"
        description={`在受控执行流程内管理「${task.project_name}」。`}
        action={
          <Link
            href={`/tasks/${id}`}
            className={buttonVariants({ variant: "ghost" })}
          >
            <ArrowLeft />
            返回任务
          </Link>
        }
      />
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <div>
            <p className="text-sm font-medium">{task.project_name}</p>
            <p className="mt-1 font-mono text-[10px] text-slate-600">
              {task.task_id}
            </p>
          </div>
          <StatusBadge status={task.status} />
        </div>
        <TaskControlPanel taskId={task.task_id} status={task.status} />
      </div>
    </>
  );
}
