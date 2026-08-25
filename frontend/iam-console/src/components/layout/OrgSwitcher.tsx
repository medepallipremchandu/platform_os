import { useEffect, useRef, useState } from "react";
import { switchOrganization } from "../../api/iam";
import { extractErrorMessage } from "../../api/client";
import { storeTokens } from "../../lib/auth";
import { useAuth } from "../auth/AuthContext";
import { BuildingIcon, ChevronDownIcon, CheckCircleIcon } from "../ui/icons";

/** Mints a new, differently-scoped token via POST /auth/token/switch-org without a full
 * re-login.
 *
 * `organizations` is whatever GET /organizations returned for this session - the caller's
 * memberships normally, but EVERY organization for a platform superadmin, who may scope into any
 * active one without holding a membership. So this renders for a superadmin too, and the list it
 * offers is exactly the list the server will accept. */
export default function OrgSwitcher() {
  const { claims, organizations, onSessionChanged } = useAuth();
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClickAway = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, [open]);

  // Hidden only when there is genuinely nothing to choose. "Fewer than two" alone is not the
  // test: a superadmin session carries no org_id, so even a single organization is a real choice
  // for them - it is how they scope into it at all.
  if (organizations.length === 0 || (organizations.length < 2 && claims?.org_id)) return null;

  const currentOrg = organizations.find((org) => org.id === claims?.org_id);

  async function handleSwitch(organizationId: string) {
    if (organizationId === claims?.org_id) {
      setOpen(false);
      return;
    }
    setSwitching(true);
    setError(null);
    try {
      const tokens = await switchOrganization(organizationId);
      storeTokens(tokens);
      onSessionChanged();
      setOpen(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="org-switcher" ref={containerRef}>
      <button type="button" className="org-switcher__trigger" onClick={() => setOpen((v) => !v)} disabled={switching}>
        <BuildingIcon width={16} height={16} />
        <span className="org-switcher__name">{currentOrg?.name || "Select organization"}</span>
        <ChevronDownIcon width={16} height={16} />
      </button>
      {open && (
        <div className="org-switcher__menu" role="listbox">
          {organizations.map((org) => (
            <button
              key={org.id}
              type="button"
              className="org-switcher__option"
              role="option"
              aria-selected={org.id === claims?.org_id}
              onClick={() => handleSwitch(org.id)}
            >
              <span>{org.name}</span>
              {org.id === claims?.org_id && <CheckCircleIcon width={15} height={15} />}
            </button>
          ))}
          {error && <p className="org-switcher__error">{error}</p>}
        </div>
      )}
    </div>
  );
}
