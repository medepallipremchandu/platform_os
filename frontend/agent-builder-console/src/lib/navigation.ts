import { SparkleIcon, TargetIcon } from "../components/ui/icons";
import type { ComponentType, SVGProps } from "react";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
  section?: string;
}

/** Single source of truth for the sidebar links and the topbar's section title -
 * add a route here once and both stay in sync automatically. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/agents", label: "Agents", icon: SparkleIcon },
  { path: "/models", label: "Models", icon: TargetIcon },
];

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS].reverse().find((item) => item.end ? pathname === item.path : pathname.startsWith(item.path));
  return match?.label ?? "Agent Builder";
}
