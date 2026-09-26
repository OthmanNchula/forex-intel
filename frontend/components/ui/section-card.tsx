import { LucideIcon } from "lucide-react";

export function SectionCard({
  icon: Icon,
  iconClassName = "text-blue-400",
  title,
  action,
  children,
  delay = 0,
  className = "",
}: {
  icon?: LucideIcon;
  iconClassName?: string;
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <div
      className={`glass-card p-4 animate-in fade-in slide-in-from-bottom-2 ${className}`}
      style={{ animationDuration: "500ms", animationDelay: `${delay}ms`, animationFillMode: "backwards" }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold flex items-center gap-2">
          {Icon && <Icon className={`h-4 w-4 ${iconClassName}`} />}
          {title}
        </h2>
        {action}
      </div>
      {children}
    </div>
  );
}
