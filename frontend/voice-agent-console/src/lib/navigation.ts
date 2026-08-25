import type { ComponentType, SVGProps } from "react";
import { PhoneIcon, SlidersIcon, TargetIcon } from "../components/ui/icons";
import { hasPermission, PERMISSIONS } from "./permissions";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
  /** Only shown when the current session holds this permission - undefined means always shown. */
  requiresPermission?: string;
}

/** Single source of truth for the sidebar links and the topbar's section title - add a route
 * here once and both stay in sync automatically. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/providers", label: "Providers", icon: TargetIcon, requiresPermission: PERMISSIONS.PROVIDERS_READ },
  { path: "/call-agents", label: "Call Agents", icon: SlidersIcon, requiresPermission: PERMISSIONS.CALLAGENTS_READ },
  { path: "/calls", label: "Calls", icon: PhoneIcon, requiresPermission: PERMISSIONS.CALLS_READ },
];

export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.requiresPermission || hasPermission(item.requiresPermission));
}

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS].reverse().find((item) => (item.end ? pathname === item.path : pathname.startsWith(item.path)));
  return match?.label ?? "Voice Agent Console";
}
