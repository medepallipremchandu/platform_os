import type { ComponentType, SVGProps } from "react";
import {
  BuildingIcon,
  DashboardIcon,
  HistoryIcon,
  KeyIcon,
  LinkIcon,
  SparkleIcon,
  ShieldIcon,
  UsersIcon,
} from "../components/ui/icons";
import { PERMISSIONS, hasPermission, isSuperAdmin } from "./permissions";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
  /** Only shown when the current session holds this permission - undefined means always shown. */
  requiresPermission?: string;
  /** Only shown to a platform superadmin. A separate flag from `requiresPermission` because it
   * is a separate axis - see `isSuperAdmin()`. */
  requiresSuperAdmin?: boolean;
  /** Hidden for a session with no organization (a pure superadmin), because the page is
   * org-scoped and would have nothing to fetch. */
  requiresOrganization?: boolean;
}

/** Single source of truth for the sidebar links and the topbar's section title - add a route
 * here once and both stay in sync automatically. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Dashboard", icon: DashboardIcon, end: true, requiresOrganization: true },
  { path: "/organizations", label: "Organizations", icon: BuildingIcon, requiresSuperAdmin: true },
  { path: "/users", label: "Users", icon: UsersIcon, requiresOrganization: true },
  { path: "/roles", label: "Roles", icon: ShieldIcon, requiresOrganization: true },
  { path: "/role-assignments", label: "Role assignments", icon: LinkIcon, requiresOrganization: true },
  { path: "/service-principals", label: "Service principals", icon: KeyIcon, requiresOrganization: true },
  {
    path: "/notifications",
    label: "Notifications",
    icon: SparkleIcon,
    requiresOrganization: true,
    requiresPermission: PERMISSIONS.NOTIFICATION_PROVIDERS_READ,
  },
  { path: "/audit-log", label: "Audit log", icon: HistoryIcon, requiresPermission: PERMISSIONS.AUDIT_READ },
];

/** Hide-don't-disable, matching the rest of the app: a nav item the session cannot use simply
 * is not there. `currentOrgId` is passed in (rather than read from claims here) so the caller
 * decides what "current organization" means - a superadmin browsing has none. */
export function visibleNavItems(currentOrgId: string | null | undefined): NavItem[] {
  const superAdmin = isSuperAdmin();
  return NAV_ITEMS.filter((item) => {
    if (item.requiresSuperAdmin && !superAdmin) return false;
    if (item.requiresOrganization && !currentOrgId) return false;
    // A superadmin holds no org-scoped permissions at all, so a permission gate would hide
    // every org page from them even inside an organization they are legitimately administering.
    if (item.requiresPermission && !superAdmin && !hasPermission(item.requiresPermission)) return false;
    return true;
  });
}

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS]
    .reverse()
    .find((item) => (item.end ? pathname === item.path : pathname.startsWith(item.path)));
  return match?.label ?? "IAM Console";
}
