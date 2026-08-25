import { useEffect } from "react";
import { logout } from "../api/iam";
import Spinner from "../components/ui/Spinner";
import { clearTokens } from "../lib/auth";

/** Platform-wide sign-out.
 *
 * Every other app redirects here to sign out rather than just clearing its own storage. Clearing
 * locally is not enough: each app keeps its session in its OWN sessionStorage, so a relying party
 * that only cleared itself would bounce to `portal`, find portal's session still valid, and be
 * handed the very same session straight back through the `return_to` handoff. To the user that
 * looks like the page merely reloading and never logging out.
 *
 * So sign-out has to end at the one place that holds the session everything else is handed from.
 * `POST /auth/logout` additionally revokes every refresh token for the user server-side, which
 * makes this a real single sign-out rather than a local tidy-up.
 */
export default function LogoutPage() {
  useEffect(() => {
    logout()
      .catch(() => {
        // Best-effort: the local session is cleared either way, and the server-side revoke has
        // usually already happened in whichever app sent the user here.
      })
      .finally(() => {
        clearTokens();
        // replace(), not href: sign-out must not leave an entry the back button can return to.
        window.location.replace("/login");
      });
  }, []);

  return (
    <div className="login-page">
      <div className="login-card">
        <Spinner size={20} />
        <p className="hint-text">Signing you out...</p>
      </div>
    </div>
  );
}
