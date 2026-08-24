interface Tab {
  key: string;
  label: string;
  badge?: number;
}

interface Props {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
}

export default function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div className="tabs">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`tabs__tab ${active === tab.key ? "tabs__tab--active" : ""}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
          {tab.badge !== undefined && tab.badge > 0 && <span className="tabs__badge">{tab.badge}</span>}
        </button>
      ))}
    </div>
  );
}
