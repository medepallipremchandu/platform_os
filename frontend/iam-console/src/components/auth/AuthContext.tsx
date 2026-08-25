import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ensureFreshSession, setSessionExpiredHandler } from "../../api/client";
import { listOrganizations, logout as apiLogout } from "../../api/iam";
import { clearTokens, getClaims, hasValidSession } from "../../lib/auth";
import type { AccessTokenClaims, Organization } from "../../types";

interface AuthContextValue {
  claims: AccessTokenClaims | null;
  organizations: Organization[];
  isAuthenticated: boolean;
  /** True only while the very first session check (and its follow-on org fetch) is in flight -
   * lets the route guard avoid a flash-redirect to /login before we know the answer. */
  isBootstrapping: boolean;
  refreshOrganizations: () => Promise<void>;
  /** Call after any flow that mints a new token pair (login, org switch) to re-read claims from
   * storage and refresh the org list. */
  onSessionChanged: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// How often to proactively check whether the access token needs refreshing, independent of
// whether any API call happens to be in flight - keeps a session alive through idle periods
// (e.g. someone reading the audit log for a while) without waiting for a request to fail.
const PROACTIVE_REFRESH_INTERVAL_MS = 60_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [claims, setClaims] = useState<AccessTokenClaims | null>(() => (hasValidSession() ? getClaims() : null));
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const refreshOrganizations = useCallback(async () => {
    if (!hasValidSession()) return;
    try {
      const orgs = await listOrganizations();
      setOrganizations(orgs);
    } catch {
      // Non-fatal: the dashboard/switcher just render with whatever they already had.
    }
  }, []);

  const onSessionChanged = useCallback(() => {
    setClaims(hasValidSession() ? getClaims() : null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Best-effort - clear local session state regardless of whether the server call succeeded.
    } finally {
      clearTokens();
      setClaims(null);
      setOrganizations([]);
    }
  }, []);

  // Wired to the axios layer so a failed silent-refresh (refresh token itself expired/revoked)
  // drops the app back to a logged-out state instead of leaving stale UI up.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setClaims(null);
      setOrganizations([]);
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  useEffect(() => {
    if (!claims) {
      setIsBootstrapping(false);
      return;
    }
    refreshOrganizations().finally(() => setIsBootstrapping(false));
    // Only re-run when the identity/org actually changes (login, switch-org, logout) - not on
    // every claims re-read after a routine silent refresh, which keeps the same sub/org_id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claims?.sub, claims?.org_id]);

  useEffect(() => {
    if (!claims) return;
    const interval = setInterval(() => {
      ensureFreshSession().then(onSessionChanged).catch(() => {
        // A hard failure here is also reported through setSessionExpiredHandler above.
      });
    }, PROACTIVE_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [claims, onSessionChanged]);

  const value = useMemo<AuthContextValue>(
    () => ({
      claims,
      organizations,
      isAuthenticated: !!claims,
      isBootstrapping,
      refreshOrganizations,
      onSessionChanged,
      logout,
    }),
    [claims, organizations, isBootstrapping, refreshOrganizations, onSessionChanged, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
