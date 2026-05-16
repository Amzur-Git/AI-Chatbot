type EventBadgeProps = {
  label: string;
  tone?: "info" | "success" | "warn" | "muted";
};

const toneClass: Record<NonNullable<EventBadgeProps["tone"]>, string> = {
  info: "bg-sky-100 text-sky-800 border-sky-200",
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  warn: "bg-amber-100 text-amber-800 border-amber-200",
  muted: "bg-slate-100 text-slate-700 border-slate-200",
};

export default function EventBadge({ label, tone = "muted" }: EventBadgeProps) {
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${toneClass[tone]}`}>{label}</span>;
}
