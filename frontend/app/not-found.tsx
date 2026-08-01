import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-white px-6 py-16 text-center shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
        404
      </p>
      <h1 className="mt-3 text-xl font-semibold text-slate-950">
        未找到此页面
      </h1>
      <p className="mt-2 text-sm text-slate-500">
        页面可能已被移动，或者任务编号不存在。
      </p>
      <Link href="/" className={`${buttonVariants()} mt-6`}>
        返回总览
      </Link>
    </div>
  );
}
