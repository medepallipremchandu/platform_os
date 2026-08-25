import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import LauncherPage from "./pages/LauncherPage";
import LoginPage from "./pages/LoginPage";
import LogoutPage from "./pages/LogoutPage";
import SetPasswordPage from "./pages/SetPasswordPage";
import { hasValidSession } from "./lib/auth";
import "./App.css";

/** Auth guard for everything except /login. Deliberately a real component (not an inline
 * `hasValidSession() ? <X/> : <Y/>` ternary computed once inside `App()`) - a route's `element`
 * prop is a React element created when the parent renders, and React Router can re-render the
 * matched route without forcing that ancestor to re-render too. An inline ternary there gets
 * evaluated once at mount and never again, so a plain client-side `navigate()` after login would
 * still show the stale (pre-login) branch and bounce right back to /login. Calling
 * `hasValidSession()` inside this component's own body means it's re-evaluated every time this
 * route actually renders. */
function RequireSession() {
  return hasValidSession() ? <Outlet /> : <Navigate to="/login" replace />;
}

/** Routing + auth guard for the whole app: unauthenticated visitors land on /login (the root
 * path too, per the spec - a direct hit on "/" with no session just bounces to /login); an
 * authenticated session sees the launcher. */
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Outside RequireSession on purpose: an invited user has no session yet, and someone
          resetting a forgotten password cannot get one. Guarding these would bounce both flows
          to /login - the exact page they were emailed a link to get past. */}
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/set-password" element={<SetPasswordPage />} />
      {/* Outside RequireSession as well: sign-out has to work whether or not the session here is
          still valid, and guarding it would redirect to /login without ever clearing anything. */}
      <Route path="/logout" element={<LogoutPage />} />
      <Route element={<RequireSession />}>
        <Route path="/" element={<LauncherPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
