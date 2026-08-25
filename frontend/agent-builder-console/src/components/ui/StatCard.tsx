import type { ReactNode } from "react";
import { SkeletonLine } from "./Skeleton";

interface Props {
  icon: ReactNode;
  label: string;
  value: number | string | null;
  hint?: string;
  tone?: "brand" | "success" | "warning" | "info";
}

export default function StatCard({ icon, label, value, hint, tone = "brand" }: Props) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <div className="stat-card__icon">{icon}</div>
      <div className="stat-card__body">
        <span className="stat-card__label">{label}</span>
        {value === null ? <SkeletonLine width="50%" height={26} /> : <span className="stat-card__value">{value}</span>}
        {hint && <span className="stat-card__hint">{hint}</span>}
      </div>
    </div>
  );
}
