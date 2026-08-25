import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import RequireOrganization from "./components/auth/RequireOrganization";
import AppLayout from "./components/layout/AppLayout";
import AuditLogPage from "./pages/AuditLogPage";
import DashboardPage from "./pages/DashboardPage";
import NotificationProvidersPage from "./pages/NotificationProvidersPage";
import OrganizationsPage from "./pages/OrganizationsPage";
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
          {/* Organizations is the one page a superadmin can use with no organization at all -
              it is the platform tier's own surface, so it sits outside RequireOrganization. */}
          <Route path="/organizations" element={<OrganizationsPage />} />
          {/* Everything else is organization-scoped and would otherwise fire org_id=null
              requests for a superadmin session. See RequireOrganization. */}
          <Route element={<RequireOrganization />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/notifications" element={<NotificationProvidersPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/users/:id" element={<UserDetailPage />} />
            <Route path="/roles" element={<RolesPage />} />
            <Route path="/role-assignments" element={<RoleAssignmentsPage />} />
            <Route path="/service-principals" element={<ServicePrincipalsPage />} />
            <Route path="/audit-log" element={<AuditLogPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
