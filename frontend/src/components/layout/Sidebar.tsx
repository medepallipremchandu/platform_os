import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../lib/navigation";
import { ACTOR_EMAIL } from "../../api/client";
import { initials } from "../../lib/format";
import { CloseIcon, SparkleIcon } from "../ui/icons";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: Props) {
  return (
    <>
      {open && <div className="sidebar-scrim" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="sidebar__header">
          <div className="sidebar__brand">
            <span className="sidebar__brand-mark">
              <SparkleIcon width={18} height={18} />
            </span>
            <span className="sidebar__brand-name">TalentOS</span>
          </div>
          <button type="button" className="sidebar__close" onClick={onClose} aria-label="Close menu">
            <CloseIcon />
          </button>
        </div>

        <nav className="sidebar__nav">
          {NAV_ITEMS.map((item) => (
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
          <span className="sidebar__avatar">{initials(ACTOR_EMAIL)}</span>
          <div className="sidebar__footer-text">
            <span className="sidebar__footer-name">{ACTOR_EMAIL}</span>
            <span className="sidebar__footer-role">Recruiter</span>
          </div>
        </div>
      </aside>
    </>
  );
}
