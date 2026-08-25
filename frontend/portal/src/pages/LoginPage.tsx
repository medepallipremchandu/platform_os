import { type FormEvent, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { login } from "../api/iam";
import Button from "../components/ui/Button";
import { EyeIcon, EyeOffIcon, ShieldIcon } from "../components/ui/icons";
import {
  buildHandoffUrl,
  getAccessToken,
  getClaims,
  getRefreshToken,
  hasValidSession,
  isAllowedReturnTarget,
  storeTokens,
} from "../lib/auth";
import type { OrgMembershipOption, TokenPair } from "../types";

/** The single login entry point for the whole TalentOS platform. Every other app
 * (iam-console, talentos-app, agent-builder-console) is a pure relying party: it has no login
 * form of its own, and redirects here with `?return_to=<its own URL>` whenever it has no valid
 * session. This page authenticates the user once and then either hands the resulting tokens
 * straight back to `return_to` (the redirect case) or sends them on to the launcher (a direct
 * visit to `portal`). */
export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [memberships, setMemberships] = useState<OrgMembershipOption[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const returnTo = searchParams.get("return_to");
  const validReturnTo = returnTo && isAllowedReturnTarget(returnTo) ? returnTo : null;

  function finishLogin(tokens: TokenPair) {
    if (validReturnTo) {
      window.location.href = buildHandoffUrl(validReturnTo, tokens, tokens.organization_id);
      return;
    }
    navigate("/", { replace: true });
  }

  // Someone can land on /login while already holding a valid session - e.g. a bookmark, or a
  // relying-party app redirecting here with `return_to` even though the user never signed out.
  // Either hand the existing session straight to `return_to`, or just go to the launcher.
  if (hasValidSession()) {
    if (validReturnTo) {
      const claims = getClaims()!;
      const tokens: TokenPair = {
        access_token: getAccessToken()!,
        refresh_token: getRefreshToken()!,
        token_type: "bearer",
        expires_in: 0,
        organization_id: claims.org_id,
      };
      window.location.href = buildHandoffUrl(validReturnTo, tokens, tokens.organization_id);
      return null;
    }
    return <Navigate to="/" replace />;
  }

  async function attemptLogin(organizationId?: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await login({ email, password, organization_id: organizationId });
      if (result.status === "multi_org") {
        setMemberships(result.memberships);
        return;
      }
      storeTokens(result.tokens);
      finishLogin(result.tokens);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleCredentialsSubmit(e: FormEvent) {
    e.preventDefault();
    attemptLogin();
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-card__brand">
          <span className="login-card__brand-mark">
            <ShieldIcon width={22} height={22} />
          </span>
          <div>
            <div className="login-card__title">TalentOS Portal</div>
            <div className="login-card__subtitle">Sign in to continue to the platform</div>
          </div>
        </div>

        {error && <p className="error-text">{error}</p>}

        {memberships ? (
          <div className="org-picker">
            <p className="hint-text">Your account belongs to more than one organization. Choose one to continue.</p>
            {memberships.map((membership) => (
              <button
                key={membership.id}
                type="button"
                className="org-picker__option"
                disabled={loading}
                onClick={() => attemptLogin(membership.id)}
              >
                {membership.name}
              </button>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setMemberships(null)} disabled={loading}>
              Back
            </Button>
          </div>
        ) : (
          <form className="form" onSubmit={handleCredentialsSubmit}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                autoComplete="username"
              />
            </label>
            <label>
              Password
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={12}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="password-field__toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOffIcon width={17} height={17} /> : <EyeIcon width={17} height={17} />}
                </button>
              </div>
            </label>
            <Button type="submit" loading={loading} className="btn--full">
              Sign in
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
