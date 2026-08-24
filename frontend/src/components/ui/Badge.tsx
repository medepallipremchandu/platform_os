import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

interface Props {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

export default function Badge({ tone = "neutral", children, className = "" }: Props) {
  return <span className={`badge badge--${tone} ${className}`.trim()}>{children}</span>;
}
