import { useLocation } from "react-router-dom";
import { redirectToLogin } from "../../lib/auth";
import { sectionTitleForPath } from "../../lib/navigation";
import { useAuth } from "../auth/AuthContext";
import { LogOutIcon, MenuIcon } from "../ui/icons";
import OrgSwitcher from "./OrgSwitcher";

interface Props {
  onMenuClick: () => void;
}

export default function Topbar({ onMenuClick }: Props) {
  const location = useLocation();
  const { logout } = useAuth();
  const title = sectionTitleForPath(location.pathname);

  async function handleLogout() {
    await logout();
    redirectToLogin();
  }

  return (
    <header className="topbar">
      <button type="button" className="topbar__menu-btn" onClick={onMenuClick} aria-label="Open menu">
        <MenuIcon />
      </button>
      <h2 className="topbar__title">{title}</h2>
      <div className="topbar__spacer" />
      <OrgSwitcher />
      <button type="button" className="topbar__logout" onClick={handleLogout}>
        <LogOutIcon width={17} height={17} />
        <span>Log out</span>
      </button>
    </header>
  );
}
