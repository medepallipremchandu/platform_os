import type { ComponentType, SVGProps } from "react";
import { BuildingIcon, ShieldIcon, SparkleIcon } from "../components/ui/icons";

// Every other app in the platform, sourced entirely from Vite env vars - never hardcoded.
// `portal` is the single login entry point: it never hosts business features itself, only
// auth + this launcher, so these three are the whole destination surface.
export const IAM_CONSOLE_URL = import.meta.env.VITE_IAM_CONSOLE_URL || "http://localhost:5174";
export const TALENTOS_APP_URL = import.meta.env.VITE_TALENTOS_APP_URL || "http://localhost:5173";
export const AGENT_BUILDER_CONSOLE_URL = import.meta.env.VITE_AGENT_BUILDER_CONSOLE_URL || "http://localhost:5176";

export interface AppDestination {
  id: string;
  name: string;
  description: string;
  url: string;
  /** A launcher tile is shown only when the signed-in user's access token carries at least one
   * permission whose code starts with this prefix. */
  permissionPrefix: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

/** The full set of relying-party apps `portal` can hand a session off to. Also doubles as the
 * source of truth for `isAllowedReturnTarget` in `lib/auth.ts` - a `?return_to=` is only ever
 * honored if its origin matches one of these, never an arbitrary URL a query param could name. */
export const APP_DESTINATIONS: AppDestination[] = [
  {
    id: "iam-console",
    name: "IAM Console",
    description: "Manage organizations, users, roles, and permissions.",
    url: IAM_CONSOLE_URL,
    permissionPrefix: "talentos.iam.",
    icon: ShieldIcon,
  },
  {
    id: "agent-builder-console",
    name: "Agent Builder",
    description: "Build and manage the AI models and agents that power the platform.",
    url: AGENT_BUILDER_CONSOLE_URL,
    permissionPrefix: "talentos.agentbuilder.",
    icon: SparkleIcon,
  },
  {
    id: "talentos-app",
    name: "TalentOS",
    description: "Requirements, applicants, submissions, and interviews.",
    url: TALENTOS_APP_URL,
    permissionPrefix: "talentos.intake.",
    icon: BuildingIcon,
  },
];
