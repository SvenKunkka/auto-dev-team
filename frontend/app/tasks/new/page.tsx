import type { Metadata } from "next";
import { CreateTaskForm } from "@/components/create-task-form";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "创建任务" };

export default function CreateTaskPage() {
  return (
    <>
      <PageHeader
        eyebrow="任务提交"
        title="创建产品任务"
        description="定义目标、资料和工作区，选择本次需要参与的专业智能体与AI模型。"
      />
      <div className="mx-auto max-w-4xl">
        <CreateTaskForm />
      </div>
    </>
  );
}
