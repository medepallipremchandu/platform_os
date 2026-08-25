import type { ComponentType, SVGProps } from "react";
import { SparkleIcon, TargetIcon } from "../components/ui/icons";
import { hasPermission, PERMISSIONS } from "./permissions";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
  section?: string;
  /** Only shown when the current session holds this permission - undefined means always shown. */
  requiresPermission?: string;
}

/** Single source of truth for the sidebar links and the topbar's section title -
 * add a route here once and both stay in sync automatically. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/agents", label: "Agents", icon: SparkleIcon, requiresPermission: PERMISSIONS.AGENTS_READ },
  { path: "/models", label: "Models", icon: TargetIcon, requiresPermission: PERMISSIONS.AGENTS_READ },
];

export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.requiresPermission || hasPermission(item.requiresPermission));
}

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS].reverse().find((item) => (item.end ? pathname === item.path : pathname.startsWith(item.path)));
  return match?.label ?? "Agent Builder";
}
