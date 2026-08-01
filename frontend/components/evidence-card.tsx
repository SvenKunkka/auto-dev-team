import { FileDiff, FlaskConical, PackageCheck } from "lucide-react";
import type { EvidenceSummary } from "@/types/task";

export function EvidenceCard({ evidence }: { evidence: EvidenceSummary }) {
  const items = [
    {
      label: "产物",
      value: evidence.artifact_count,
      icon: PackageCheck,
    },
    {
      label: "变更文件",
      value: evidence.changed_files_count,
      icon: FileDiff,
    },
    {
      label: "测试",
      value: `${evidence.test_count - evidence.failed_test_count}/${evidence.test_count}`,
      icon: FlaskConical,
    },
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h2 className="text-sm font-semibold">开发证据</h2>
        <p className="mt-1 text-xs text-slate-500">
          最近开发周期中保存的可验证证据
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {items.map(({ label, value, icon: Icon }) => (
          <div
            key={label}
            className="rounded-lg border border-slate-200 bg-slate-50 p-3"
          >
            <Icon className="size-4 text-slate-600" />
            <p className="mt-4 text-xl font-semibold text-slate-900">{value}</p>
            <p className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-600">
              {label}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {evidence.artifact_types.map((type) => (
          <span
            key={type}
            className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[9px] uppercase text-slate-500"
          >
            {type}
          </span>
        ))}
      </div>
    </section>
  );
}
