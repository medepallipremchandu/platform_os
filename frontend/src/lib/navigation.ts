import {
  DashboardIcon,
  DocumentIcon,
  SubmissionIcon,
  UsersIcon,
} from "../components/ui/icons";
import type { ComponentType, SVGProps } from "react";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  end?: boolean;
}

/** Single source of truth for the sidebar links and the topbar's section title -
 * add a route here once and both stay in sync automatically. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Dashboard", icon: DashboardIcon, end: true },
  { path: "/requirements", label: "Requirements", icon: DocumentIcon },
  { path: "/applicants", label: "Applicants", icon: UsersIcon },
  { path: "/submissions", label: "Submissions", icon: SubmissionIcon },
];

export function sectionTitleForPath(pathname: string): string {
  const match = [...NAV_ITEMS].reverse().find((item) => item.end ? pathname === item.path : pathname.startsWith(item.path));
  return match?.label ?? "TalentOS";
}
