import { LucideIcon } from "lucide-react";

type Accent = "blue" | "green" | "amber" | "purple" | "red" | "gray";

const accentStyles: Record<Accent, { chip: string; glow: string; ring: string }> = {
  blue: {
    chip: "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20",
    glow: "stat-glow-blue",
    ring: "group-hover:ring-blue-500/30",
  },
  green: {
    chip: "bg-green-500/10 text-green-400 ring-1 ring-green-500/20",
    glow: "stat-glow-green",
    ring: "group-hover:ring-green-500/30",
  },
  amber: {
    chip: "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20",
    glow: "stat-glow-amber",
    ring: "group-hover:ring-amber-500/30",
  },
  purple: {
    chip: "bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/20",
    glow: "stat-glow-purple",
    ring: "group-hover:ring-purple-500/30",
  },
  red: {
    chip: "bg-red-500/10 text-red-400 ring-1 ring-red-500/20",
    glow: "stat-glow-red",
    ring: "group-hover:ring-red-500/30",
  },
  gray: {
    chip: "bg-gray-500/10 text-gray-400 ring-1 ring-gray-500/20",
    glow: "",
    ring: "",
  },
};

export function StatCard({
  icon: Icon,
  label,
  value,
  sublabel,
  accent = "gray",
  valueClassName = "",
  delay = 0,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  sublabel?: React.ReactNode;
  accent?: Accent;
  valueClassName?: string;
  delay?: number;
}) {
  const style = accentStyles[accent];
  return (
    <div
      className={`group glass-card ${style.glow} p-4 animate-in fade-in slide-in-from-bottom-2`}
      style={{ animationDuration: "500ms", animationDelay: `${delay}ms`, animationFillMode: "backwards" }}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-gray-400 text-xs font-medium tracking-wide uppercase">{label}</p>
        <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${style.chip}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className={`text-2xl font-bold tabular-nums text-white ${valueClassName}`}>{value}</p>
      {sublabel && <p className="text-gray-500 text-xs mt-1">{sublabel}</p>}
    </div>
  );
}
