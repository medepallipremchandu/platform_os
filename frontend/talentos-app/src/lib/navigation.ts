import {
  DashboardIcon,
  DocumentIcon,
  SubmissionIcon,
  UsersIcon,
} from "../components/ui/icons";
import type { ComponentType, SVGProps } from "react";
import { hasAnyPermission, hasPermission, PERMISSIONS } from "./permissions";

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
  { path: "/", label: "Dashboard", icon: DashboardIcon, end: true },
  { path: "/requirements", label: "Requirements", icon: DocumentIcon, requiresPermission: PERMISSIONS.REQUIREMENTS_READ },
  { path: "/applicants", label: "Applicants", icon: UsersIcon, requiresPermission: PERMISSIONS.APPLICANTS_READ },
  { path: "/submissions", label: "Submissions", icon: SubmissionIcon, requiresPermission: PERMISSIONS.SUBMISSIONS_READ },
];

/** Dashboard has no `requiresPermission` of its own - it's a cross-cutting summary page that
 * degrades gracefully with nothing to show if the session holds none of the read permissions
 * below, so it's always left visible rather than gated on any single one of them. */
export function visibleNavItems(): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.requiresPermission || hasPermission(item.requiresPermission));
}

export function hasAnyIntakeReadAccess(): boolean {
  return hasAnyPermission([PERMISSIONS.REQUIREMENTS_READ, PERMISSIONS.APPLICANTS_READ, PERMISSIONS.SUBMISSIONS_READ]);
}

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS].reverse().find((item) => item.end ? pathname === item.path : pathname.startsWith(item.path));
  return match?.label ?? "TalentOS";
}
