import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { KeyIcon, LogOutIcon, ShieldIcon } from "../components/ui/icons";
import {
  buildHandoffUrl,
  currentPrincipalLabel,
  getAccessToken,
  getClaims,
  getRefreshToken,
  hasPermissionPrefix,
  isSuperAdmin,
} from "../lib/auth";
import { APP_DESTINATIONS, type AppDestination } from "../lib/destinations";
import type { TokenPair } from "../types";

/** Post-login landing screen: a grid of tiles, one per platform app the signed-in user has
 * permission to open. Picking one builds the same tokens-in-the-fragment handoff URL that
 * iam-console's login page uses today and navigates there directly - `portal` never renders any
 * of those apps itself. */
export default function LauncherPage() {
  const claims = getClaims();
  const superAdmin = isSuperAdmin();
  const visibleDestinations = APP_DESTINATIONS.filter(
    (destination) => hasPermissionPrefix(destination.permissionPrefix) || (superAdmin && destination.showForSuperAdmin),
  );

  function openDestination(destination: AppDestination) {
    const accessToken = getAccessToken();
    const refreshToken = getRefreshToken();
    if (!accessToken || !refreshToken || !claims) return;
    const tokens: TokenPair = {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: "bearer",
      expires_in: 0,
      organization_id: claims.org_id,
    };
    window.location.href = buildHandoffUrl(destination.url, tokens, claims.org_id);
  }

  function handleSignOut() {
    // Routed through /logout rather than clearing inline, so every sign-out on the platform -
    // from here or from any relying-party app - runs the exact same code path.
    window.location.replace("/logout");
  }

  return (
    <div className="launcher-page">
      <header className="launcher-header">
        <div className="launcher-header__brand">
          <span className="launcher-header__brand-mark">
            <ShieldIcon width={20} height={20} />
          </span>
          <span className="launcher-header__brand-name">TalentOS Portal</span>
        </div>
        <div className="launcher-header__account">
          <span className="launcher-header__user">{currentPrincipalLabel()}</span>
          <Button variant="ghost" size="sm" icon={<LogOutIcon width={16} height={16} />} onClick={handleSignOut}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="launcher-main">
        <div className="launcher-intro">
          <h1 className="launcher-intro__title">Choose an application</h1>
          <p className="launcher-intro__subtitle">Pick where you&rsquo;d like to go - you&rsquo;ll stay signed in.</p>
        </div>

        {visibleDestinations.length === 0 ? (
          <Card>
            <EmptyState
              icon={<KeyIcon width={28} height={28} />}
              title="No applications available"
              description={
                superAdmin
                  ? "Your superadmin session has no organization, so the business apps have nothing to show. Open IAM Console to manage organizations."
                  : "You don't have access to any application yet - contact your organization admin."
              }
            />
          </Card>
        ) : (
          <div className="tile-grid">
            {visibleDestinations.map((destination) => {
              const Icon = destination.icon;
              return (
                <button
                  key={destination.id}
                  type="button"
                  className="tile"
                  onClick={() => openDestination(destination)}
                >
                  <span className="tile__icon">
                    <Icon width={22} height={22} />
                  </span>
                  <span className="tile__name">{destination.name}</span>
                  <span className="tile__description">{destination.description}</span>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
