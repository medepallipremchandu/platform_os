import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import AppLayout from "./components/layout/AppLayout";
import AuditLogPage from "./pages/AuditLogPage";
import DashboardPage from "./pages/DashboardPage";
import RoleAssignmentsPage from "./pages/RoleAssignmentsPage";
import RolesPage from "./pages/RolesPage";
import ServicePrincipalsPage from "./pages/ServicePrincipalsPage";
import UserDetailPage from "./pages/UserDetailPage";
import UsersPage from "./pages/UsersPage";
import "./App.css";

// This app has no login page of its own - `portal` is the platform's single login entry point.
// An unauthenticated visit gets bounced there by RequireAuth, and a successful login hands a
// session back here via a URL-fragment token handoff (consumed once in main.tsx before mount).
function App() {
  return (
    <Routes>
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:id" element={<UserDetailPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/role-assignments" element={<RoleAssignmentsPage />} />
          <Route path="/service-principals" element={<ServicePrincipalsPage />} />
          <Route path="/audit-log" element={<AuditLogPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
