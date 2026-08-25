import type { ReactNode } from "react";

interface Props {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function Card({ title, actions, children, className = "" }: Props) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || actions) && (
        <div className="card__header">
          {title && <h2 className="card__title">{title}</h2>}
          {actions && <div className="card__actions">{actions}</div>}
        </div>
      )}
      <div className="card__body">{children}</div>
    </section>
  );
}
