import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { TaskTable } from "@/components/task-table";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { TaskRecord } from "@/types/task";

export const metadata: Metadata = { title: "任务" };
export const dynamic = "force-dynamic";

export default async function MissionsPage() {
  let tasks: TaskRecord[] = [];
  let error = "";
  try {
    tasks = await api.tasks();
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "任务列表不可用";
  }
  return (
    <>
      <PageHeader
        eyebrow="任务工作区"
        title="开发任务"
        description="查看所有排队中、执行中、已完成和已阻塞的开发任务。"
        action={
          <Link href="/tasks/new" className={buttonVariants()}>
            <Plus className="size-4" />
            新建任务
          </Link>
        }
      />
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          FastAPI 连接失败：{error}
        </div>
      ) : (
        <TaskTable tasks={tasks} />
      )}
    </>
  );
}
