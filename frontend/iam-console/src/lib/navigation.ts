import type { ComponentType, SVGProps } from "react";
import {
  DashboardIcon,
  HistoryIcon,
  KeyIcon,
  LinkIcon,
  ShieldIcon,
  UsersIcon,
} from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "./permissions";

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
  { path: "/", label: "Dashboard", icon: DashboardIcon, end: true },
  { path: "/users", label: "Users", icon: UsersIcon },
  { path: "/roles", label: "Roles", icon: ShieldIcon },
  { path: "/role-assignments", label: "Role assignments", icon: LinkIcon },
  { path: "/service-principals", label: "Service principals", icon: KeyIcon },
  { path: "/audit-log", label: "Audit log", icon: HistoryIcon, requiresPermission: PERMISSIONS.AUDIT_READ },
];

export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.requiresPermission || hasPermission(item.requiresPermission));
}

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS]
    .reverse()
    .find((item) => (item.end ? pathname === item.path : pathname.startsWith(item.path)));
  return match?.label ?? "IAM Console";
}
