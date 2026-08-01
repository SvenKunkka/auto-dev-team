import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { AutoRefresh } from "@/components/auto-refresh";
import { TaskDetailTabs } from "@/components/task-detail-tabs";
import { buttonVariants } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const terminalStatuses = new Set([
  "PASSED",
  "FAILED",
  "BLOCKED",
  "REQUIREMENTS_REVISION",
  "CANCELED",
  "PAUSED",
]);

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  return { title: `任务 ${id.slice(0, 8)}` };
}

export default async function TaskDetailPage({
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
      <AutoRefresh active={!terminalStatuses.has(task.status)} />
      <PageHeader
        eyebrow={`任务 ${task.task_id.slice(0, 8)}`}
        title={task.project_name}
        description={task.goal}
        action={
          <Link
            href={`/tasks/${task.task_id}/control`}
            className={cn(buttonVariants({ variant: "outline" }), "border-slate-300 bg-white")}
          >
            <SlidersHorizontal className="size-4" />
            控制任务
          </Link>
        }
      />
      <TaskDetailTabs task={task} />
    </>
  );
}
