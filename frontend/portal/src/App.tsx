import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import LauncherPage from "./pages/LauncherPage";
import LoginPage from "./pages/LoginPage";
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
      <Route element={<RequireSession />}>
        <Route path="/" element={<LauncherPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
