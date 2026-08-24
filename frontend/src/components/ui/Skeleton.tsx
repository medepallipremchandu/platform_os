interface LineProps {
  width?: string;
  height?: number;
}

export function SkeletonLine({ width = "100%", height = 14 }: LineProps) {
  return <span className="skeleton-line" style={{ width, height }} />;
}

export function SkeletonBlock({ height = 80 }: { height?: number }) {
  return <div className="skeleton-block" style={{ height }} />;
}

/** A generic "list of rows" skeleton for tables/cards while data is loading. */
export function SkeletonRows({ rows = 4, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="skeleton-rows" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div className="skeleton-rows__row" key={r}>
          {Array.from({ length: columns }).map((_, c) => (
            <SkeletonLine key={c} width={c === 0 ? "60%" : "85%"} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-busy="true" aria-label="Loading">
      <SkeletonLine width="40%" height={18} />
      <SkeletonLine width="90%" />
      <SkeletonLine width="75%" />
    </div>
  );
}
