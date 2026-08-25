import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { redirectToLogin } from "../../lib/auth";
import { useAuth } from "./AuthContext";

/** Route guard: sends the browser to `portal` (the platform's one login page, carrying
 * `?return_to=` so it hands the session back here) whenever there's no valid session. Held off
 * until bootstrapping finishes so a page refresh with a still-valid stored session doesn't
 * bounce out to the portal first. This app has no login page of its own. */
export default function RequireAuth() {
  const { isAuthenticated, isBootstrapping } = useAuth();

  useEffect(() => {
    if (!isBootstrapping && !isAuthenticated) redirectToLogin();
  }, [isBootstrapping, isAuthenticated]);

  if (isBootstrapping || !isAuthenticated) return null;

  return <Outlet />;
}
