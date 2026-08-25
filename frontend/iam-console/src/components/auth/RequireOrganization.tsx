import { Navigate, Outlet } from "react-router-dom";
import EmptyState from "../ui/EmptyState";
import PageHeader from "../ui/PageHeader";
import { BuildingIcon } from "../ui/icons";
import { isSuperAdmin } from "../../lib/permissions";
import { useAuth } from "./AuthContext";

/** Guard for every organization-scoped page.
 *
 * Until the platform superadmin tier existed, `claims.org_id` was always a real UUID and each
 * page could assume it. A superadmin has no organization membership, so their token carries
 * `org_id: null` - and an unguarded page would fire `organization_id=null` at the API and render
 * a confusing empty shell rather than explaining itself.
 *
 * The two no-organization cases want opposite treatment, which is why this is a guard rather
 * than a per-page check: a superadmin has somewhere better to be, and an ordinary user has
 * nothing to do but ask someone.
 */
export default function RequireOrganization() {
  const { claims } = useAuth();
  if (claims?.org_id) return <Outlet />;

  // Organizations is the whole point of a superadmin session, and it sits outside this guard, so
  // send them straight there rather than explaining why the page they landed on is empty. No
  // loop risk: /organizations is not wrapped by this component.
  if (isSuperAdmin()) return <Navigate to="/organizations" replace />;

  return (
    <div className="page">
      <PageHeader eyebrow="Organization" title="No organization selected" />
      <EmptyState
        icon={<BuildingIcon width={26} height={26} />}
        title="You are not a member of an organization"
        description="Ask an administrator to add you to one. Until then there is nothing here to show."
      />
    </div>
  );
}
