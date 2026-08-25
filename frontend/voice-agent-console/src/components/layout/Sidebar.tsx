import { NavLink } from "react-router-dom";
import { currentPrincipalLabel, redirectToLogout } from "../../lib/auth";
import { initials } from "../../lib/format";
import { visibleNavItems } from "../../lib/navigation";
import { CloseIcon, LogoutIcon, PhoneOutgoingIcon } from "../ui/icons";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: Props) {
  const principal = currentPrincipalLabel();
  const items = visibleNavItems();

  function handleLogout() {
    // redirectToLogout, not clearTokens + redirectToLogin: clearing only this app's storage
    // leaves portal's session intact, and it hands the same one straight back through the
    // return_to handoff - which looks like a reload, not a sign-out.
    redirectToLogout();
  }

  return (
    <>
      {open && <div className="sidebar-scrim" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="sidebar__header">
          <div className="sidebar__brand">
            <span className="sidebar__brand-mark">
              <PhoneOutgoingIcon width={18} height={18} />
            </span>
            <span className="sidebar__brand-name">Voice Agent</span>
          </div>
          <button type="button" className="sidebar__close" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <nav className="sidebar__nav">
          {items.map((item) => (
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
          <span className="sidebar__avatar">{initials(principal)}</span>
          <div className="sidebar__footer-text">
            <span className="sidebar__footer-name">{principal}</span>
            <span className="sidebar__footer-role">Signed in</span>
          </div>
          <button type="button" className="sidebar__logout" onClick={handleLogout} aria-label="Sign out">
            <LogoutIcon width={17} height={17} />
          </button>
        </div>
      </aside>
    </>
  );
}
