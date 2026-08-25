import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { requestPasswordReset } from "../api/iam";
import Button from "../components/ui/Button";
import { ShieldIcon } from "../components/ui/icons";

/** Requests a reset link. The confirmation message is deliberately identical whether or not the
 * address exists - iam-service answers 202 either way and never reveals which - so this page must
 * not accidentally leak the distinction by rendering something different. */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset(email);
      setSubmitted(true);
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
            <div className="login-card__title">Reset your password</div>
            <div className="login-card__subtitle">We'll email you a link to choose a new one</div>
          </div>
        </div>

        {submitted ? (
          <>
            <p className="hint-text">
              If an account exists for {email}, a reset link is on its way. The link is single-use and expires
              shortly.
            </p>
            <Link to="/login">
              <Button variant="secondary" className="btn--full">
                Back to sign in
              </Button>
            </Link>
          </>
        ) : (
          <>
            {error && <p className="error-text">{error}</p>}
            <form className="form" onSubmit={handleSubmit}>
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoFocus
                  autoComplete="username"
                />
              </label>
              <Button type="submit" loading={loading} className="btn--full">
                Send reset link
              </Button>
              <Link to="/login" className="hint-text">
                Back to sign in
              </Link>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
