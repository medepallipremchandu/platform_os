import { useLocation } from "react-router-dom";
import { sectionTitleForPath } from "../../lib/navigation";
import { MenuIcon } from "../ui/icons";

interface Props {
  onMenuClick: () => void;
}

export default function Topbar({ onMenuClick }: Props) {
  const location = useLocation();
  const title = sectionTitleForPath(location.pathname);

  return (
    <header className="topbar">
      <button type="button" className="topbar__menu-btn" onClick={onMenuClick} aria-label="Open menu">
        <MenuIcon />
      </button>
      <h2 className="topbar__title">{title}</h2>
    </header>
  );
}
