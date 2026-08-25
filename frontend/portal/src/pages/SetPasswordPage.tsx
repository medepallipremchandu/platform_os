import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { confirmPasswordReset } from "../api/iam";
import Button from "../components/ui/Button";
import { EyeIcon, EyeOffIcon, ShieldIcon } from "../components/ui/icons";

/** Where both an invite and a forgot-password link land.
 *
 * One page for both because iam-service uses one token type and one confirm endpoint for both:
 * an invited user choosing their first password and an existing user resetting a forgotten one
 * are the same operation (prove possession of an emailed single-use token, then set a password).
 * The copy stays neutral - "Set your password" reads correctly either way - because the token is
 * opaque and this page genuinely cannot tell the two cases apart.
 *
 * Mounted OUTSIDE the session guard in App.tsx: nobody arriving here has a session yet, and both
 * flows would otherwise be bounced to /login by the very redirect they exist to escape.
 */
const MIN_PASSWORD_LENGTH = 12;

export default function SetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    if (password !== confirmation) {
      setError("The two passwords do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-card__brand">
          <span className="login-card__brand-mark">
            <ShieldIcon width={22} height={22} />
          </span>
          <div>
            <div className="login-card__title">Set your password</div>
            <div className="login-card__subtitle">
              {done ? "You can now sign in with your new password" : "Choose a password for your TalentOS account"}
            </div>
          </div>
        </div>

        {!token && (
          <>
            <p className="error-text">
              This link is missing its token. Open the link from your invitation or reset email exactly as it was
              sent.
            </p>
            <Link to="/login">
              <Button variant="secondary" className="btn--full">
                Back to sign in
              </Button>
            </Link>
          </>
        )}

        {token && done && (
          <>
            <p className="hint-text">Your password has been set and your account is active.</p>
            <Button className="btn--full" onClick={() => navigate("/login", { replace: true })}>
              Continue to sign in
            </Button>
          </>
        )}

        {token && !done && (
          <>
            {error && <p className="error-text">{error}</p>}
            <form className="form" onSubmit={handleSubmit}>
              <label>
                New password
                <div className="password-field">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    autoFocus
                    minLength={MIN_PASSWORD_LENGTH}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="password-field__toggle"
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOffIcon width={17} height={17} /> : <EyeIcon width={17} height={17} />}
                  </button>
                </div>
              </label>
              <label>
                Confirm new password
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  required
                  minLength={MIN_PASSWORD_LENGTH}
                  autoComplete="new-password"
                />
              </label>
              <p className="hint-text">At least {MIN_PASSWORD_LENGTH} characters.</p>
              <Button type="submit" loading={loading} className="btn--full">
                Set password
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
