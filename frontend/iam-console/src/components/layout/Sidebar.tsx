import { NavLink } from "react-router-dom";
import { visibleNavItems } from "../../lib/navigation";
import { currentPrincipalLabel } from "../../lib/auth";
import { initials } from "../../lib/format";
import { useAuth } from "../auth/AuthContext";
import { CloseIcon, ShieldIcon } from "../ui/icons";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: Props) {
  const { organizations, claims } = useAuth();
  const label = currentPrincipalLabel();
  const currentOrg = organizations.find((org) => org.id === claims?.org_id);
  const navItems = visibleNavItems(claims?.org_id);

  return (
    <>
      {open && <div className="sidebar-scrim" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="sidebar__header">
          <div className="sidebar__brand">
            <span className="sidebar__brand-mark">
              <ShieldIcon width={18} height={18} />
            </span>
            <span className="sidebar__brand-name">IAM Console</span>
          </div>
          <button type="button" className="sidebar__close" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <nav className="sidebar__nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              className={({ isActive }) => `sidebar__link ${isActive ? "sidebar__link--active" : ""}`}
              onClick={onClose}
            >
              <item.icon width={19} height={19} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <span className="sidebar__avatar">{initials(label)}</span>
          <div className="sidebar__footer-text">
            <span className="sidebar__footer-name">{label}</span>
            <span className="sidebar__footer-role">{currentOrg?.name || " "}</span>
          </div>
        </div>
      </aside>
    </>
  );
}
