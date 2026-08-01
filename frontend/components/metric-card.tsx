import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  note,
  icon: Icon,
  accent = "text-slate-900",
}: {
  label: string;
  value: string | number;
  note: string;
  icon: LucideIcon;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-600">
          {label}
        </span>
        <Icon className="size-4 text-slate-400" />
      </div>
      <div className={`mt-5 text-3xl font-semibold tracking-tight ${accent}`}>
        {value}
      </div>
      <p className="mt-1 text-xs text-slate-500">{note}</p>
    </div>
  );
}
